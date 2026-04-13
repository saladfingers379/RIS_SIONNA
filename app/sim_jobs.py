from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .config import apply_quality_preset
from .io import create_output_dir, generate_run_id, save_json, save_yaml
from .radio_map_grid import radio_map_z_slice_offsets
from .utils.system import get_gpu_memory_mb


def _now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_run_config(output_root: Path, run_id: str) -> Dict[str, Any]:
    run_dir = output_root / str(run_id)
    if not run_dir.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")
    for name in ("job_config.yaml", "config.yaml"):
        candidate = run_dir / name
        if candidate.exists():
            cfg = _load_yaml(candidate)
            if isinstance(cfg, dict):
                return cfg
    raise FileNotFoundError(f"No config found for run: {run_id}")


def _reconcile_loaded_jobs(jobs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    reconciled: Dict[str, Dict[str, Any]] = {}
    for job_id, job in (jobs or {}).items():
        if not isinstance(job, dict):
            continue
        updated = dict(job)
        if updated.get("status") == "running":
            output_dir = Path(str(updated.get("output_dir", "") or ""))
            progress_path = output_dir / "progress.json"
            progress_payload: Dict[str, Any] | None = None
            if progress_path.exists():
                try:
                    payload = json.loads(progress_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        progress_payload = payload
                except Exception:
                    progress_payload = None

            if isinstance(progress_payload, dict):
                progress_status = str(progress_payload.get("status") or "").strip().lower()
                if progress_status == "completed":
                    updated["status"] = "completed"
                    updated.setdefault("ended_at", _now_ts())
                    updated.setdefault("return_code", 0)
                elif progress_status == "failed":
                    updated["status"] = "failed"
                    updated.setdefault("ended_at", _now_ts())
                    updated.setdefault("return_code", 1)
                    if progress_payload.get("error"):
                        updated["error"] = progress_payload["error"]
                else:
                    updated["status"] = "failed"
                    updated.setdefault("ended_at", _now_ts())
                    updated.setdefault("return_code", 1)
                    updated.setdefault("error", "Job was interrupted before completion.")
            else:
                updated["status"] = "failed"
                updated.setdefault("ended_at", _now_ts())
                updated.setdefault("return_code", 1)
                updated.setdefault("error", "Job was interrupted before completion.")
        reconciled[str(job_id)] = updated
    return reconciled


def _job_output_exists(job: Dict[str, Any]) -> bool:
    output_dir = str(job.get("output_dir") or "").strip()
    if not output_dir:
        return False
    return Path(output_dir).exists()


def _estimate_job_cost(cfg: Dict[str, Any]) -> Dict[str, Any]:
    sim = cfg.get("simulation", {})
    radio = cfg.get("radio_map", {})
    max_depth = int(sim.get("max_depth", 1))
    rays = int(sim.get("samples_per_src", 1))
    grid = 1
    if radio.get("enabled"):
        size = radio.get("size", [1.0, 1.0])
        cell = radio.get("cell_size", [1.0, 1.0])
        grid = max(1, int(size[0] / cell[0])) * max(1, int(size[1] / cell[1]))
    if radio.get("enabled"):
        slice_count = 1 + len(radio_map_z_slice_offsets(radio))
        if radio.get("ris_off_map"):
            slice_count *= 2
    else:
        slice_count = 1
    score = grid * rays * max_depth * slice_count
    return {
        "score": score,
        "grid_cells": grid,
        "rays": rays,
        "max_depth": max_depth,
        "radio_map_slices": slice_count,
    }


def _apply_vram_guard(cfg: Dict[str, Any]) -> Dict[str, Any]:
    guard_cfg = cfg.get("runtime", {}).get("vram_guard", {})
    threshold = int(guard_cfg.get("threshold_mb", 9000))
    vram_mb = get_gpu_memory_mb()
    if vram_mb is None or vram_mb >= threshold:
        return {"vram_mb": vram_mb, "applied": False}

    sim = cfg.setdefault("simulation", {})
    radio = cfg.setdefault("radio_map", {})
    adjustments = {}

    def _scale(key: str, factor: float, section: Dict[str, Any]):
        if key in section:
            original = int(section[key])
            section[key] = max(1000, int(original * factor))
            adjustments[key] = {"from": original, "to": section[key]}

    factor = float(guard_cfg.get("scale", 0.5))
    _scale("samples_per_src", factor, sim)
    _scale("max_num_paths_per_src", factor, sim)
    _scale("samples_per_tx", factor, radio)
    if "max_depth" in sim:
        original = int(sim["max_depth"])
        sim["max_depth"] = max(1, original - 1)
        adjustments["max_depth"] = {"from": original, "to": sim["max_depth"]}
    if "max_depth" in radio:
        original = int(radio["max_depth"])
        radio["max_depth"] = max(1, original - 1)
        adjustments["radio_max_depth"] = {"from": original, "to": radio["max_depth"]}

    return {"vram_mb": vram_mb, "applied": True, "adjustments": adjustments, "threshold_mb": threshold}


def _job_overrides(kind: str) -> Dict[str, Any]:
    if kind != "run":
        return {}
    return {}


def _deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


_SIM_RUN_SCOPES = {"sim", "indoor"}


def normalize_run_scope(scope: Any, profile: Optional[str] = None) -> str:
    scope_value = str(scope or "").strip().lower()
    if scope_value in _SIM_RUN_SCOPES:
        return scope_value
    return "indoor" if str(profile or "").strip() == "indoor_box_high" else "sim"


def infer_run_scope_from_job(job: Optional[Dict[str, Any]]) -> str:
    if not isinstance(job, dict):
        return "sim"
    kind = str(job.get("kind") or "run")
    if kind != "run":
        return kind
    return normalize_run_scope(job.get("scope"), profile=job.get("profile"))


def infer_run_scope_from_config(cfg: Optional[Dict[str, Any]]) -> str:
    if not isinstance(cfg, dict):
        return "sim"
    job_cfg = cfg.get("job")
    if isinstance(job_cfg, dict):
        kind = str(job_cfg.get("kind") or "run")
        if kind != "run":
            return kind
        return normalize_run_scope(job_cfg.get("scope"), profile=job_cfg.get("profile"))
    output_cfg = cfg.get("output")
    if isinstance(output_cfg, dict):
        return normalize_run_scope(output_cfg.get("scope"))
    return "sim"


@dataclass
class JobHandle:
    job_id: str
    run_id: str
    process: subprocess.Popen


class JobManager:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root
        self.jobs_path = output_root / "_sim_jobs.json"
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.processes: Dict[str, JobHandle] = {}
        self._lock = threading.Lock()
        self._load_jobs()
        self._start_monitor()

    def _load_jobs(self) -> None:
        if not self.jobs_path.exists():
            return
        try:
            loaded = json.loads(self.jobs_path.read_text())
            self.jobs = _reconcile_loaded_jobs(loaded if isinstance(loaded, dict) else {})
        except Exception:
            self.jobs = {}

    def _save_jobs(self) -> None:
        self.jobs_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs_path.write_text(json.dumps(self.jobs, indent=2), encoding="utf-8")

    def _reconcile_orphaned_running_jobs_locked(self) -> None:
        orphaned = {
            job_id: job
            for job_id, job in self.jobs.items()
            if isinstance(job, dict) and job.get("status") == "running" and job_id not in self.processes
        }
        if not orphaned:
            return
        reconciled = _reconcile_loaded_jobs(orphaned)
        self.jobs.update(reconciled)
        self._save_jobs()

    def _start_monitor(self) -> None:
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()

    def _monitor_loop(self) -> None:
        while True:
            with self._lock:
                for job_id, handle in list(self.processes.items()):
                    ret = handle.process.poll()
                    if ret is None:
                        continue
                    job = self.jobs.get(job_id, {})
                    job["status"] = "completed" if ret == 0 else "failed"
                    job["ended_at"] = _now_ts()
                    job["return_code"] = ret
                    if ret != 0:
                        progress_path = Path(job.get("output_dir", "")) / "progress.json"
                        if progress_path.exists():
                            try:
                                payload = json.loads(progress_path.read_text())
                                if isinstance(payload, dict) and payload.get("error"):
                                    job["error"] = payload["error"]
                            except Exception:
                                pass
                    self.jobs[job_id] = job
                    self.processes.pop(job_id, None)
            self._save_jobs()
            time.sleep(1.0)

    def list_jobs(self, kind: Optional[str] = None, scope: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            self._reconcile_orphaned_running_jobs_locked()
            jobs = [job for job in self.jobs.values() if isinstance(job, dict) and _job_output_exists(job)]
            if kind:
                jobs = [job for job in jobs if job.get("kind") == kind]
            if scope:
                jobs = [job for job in jobs if infer_run_scope_from_job(job) == scope]
            return {"jobs": jobs}

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.jobs.get(job_id)

    def create_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        kind = payload.get("kind", "run")
        if kind == "campaign":
            return self._create_campaign_job(payload)
        if kind == "ris_lab":
            return self._create_ris_lab_job(payload)
        if kind == "link_level":
            return self._create_link_level_job(payload)
        if kind == "ris_synthesis":
            return self._create_ris_synthesis_job(payload)
        if kind != "run":
            kind = "run"
        preset = payload.get("preset")
        profile = payload.get("profile")
        scope = normalize_run_scope(payload.get("scope"), profile=profile)
        base_config = payload.get("base_config", "configs/default.yaml")
        config_path = Path(base_config)
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")

        cfg = _load_yaml(config_path)
        if preset:
            cfg.setdefault("quality", {})["preset"] = preset
        cfg = apply_quality_preset(cfg)
        _deep_update(cfg, _job_overrides(kind))

        scene_overrides = payload.get("scene", {})
        if scene_overrides:
            cfg.setdefault("scene", {})
            _deep_update(cfg["scene"], scene_overrides)

        runtime_overrides = payload.get("runtime", {})
        if runtime_overrides:
            cfg.setdefault("runtime", {})
            _deep_update(cfg["runtime"], runtime_overrides)

        sim_overrides = payload.get("simulation", {})
        if sim_overrides:
            cfg.setdefault("simulation", {})
            _deep_update(cfg["simulation"], sim_overrides)

        radio_overrides = payload.get("radio_map", {})
        if radio_overrides:
            cfg.setdefault("radio_map", {})
            _deep_update(cfg["radio_map"], radio_overrides)

        ris_overrides = payload.get("ris", {})
        if ris_overrides:
            cfg.setdefault("ris", {})
            _deep_update(cfg["ris"], ris_overrides)

        cfg.setdefault("radio_map", {})["enabled"] = True
        cfg.setdefault("render", {})["enabled"] = True

        run_id = generate_run_id()
        output_dir = create_output_dir(cfg.get("output", {}).get("base_dir", "outputs"), run_id=run_id)
        cfg.setdefault("output", {})["run_id"] = run_id
        cfg["output"]["scope"] = scope

        guard_info = _apply_vram_guard(cfg)
        estimate = _estimate_job_cost(cfg)

        job_id = f"job-{run_id}"
        cfg.setdefault("job", {})
        cfg["job"].update(
            {
                "id": job_id,
                "kind": kind,
                "scope": scope,
                "profile": profile,
                "preset": preset,
                "estimate": estimate,
            }
        )

        job_config_path = output_dir / "job_config.yaml"
        save_yaml(job_config_path, cfg)
        job_log_path = output_dir / "job.log"

        job = {
            "job_id": job_id,
            "run_id": run_id,
            "kind": kind,
            "scope": scope,
            "profile": profile,
            "preset": preset,
            "status": "running",
            "created_at": _now_ts(),
            "started_at": _now_ts(),
            "config_path": str(job_config_path),
            "output_dir": str(output_dir),
            "estimate": estimate,
            "vram_guard": guard_info,
        }

        process = subprocess.Popen(
            [sys.executable, "-m", "app", "run", "--config", str(job_config_path)],
            stdout=job_log_path.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )

        with self._lock:
            self.jobs[job_id] = job
            self.processes[job_id] = JobHandle(job_id=job_id, run_id=run_id, process=process)
            self._save_jobs()

        save_json(output_dir / "job.json", job)
        return job

    def _create_link_level_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        seed_type = str(payload.get("seed_type") or "run").strip().lower()
        seed_cfg: Dict[str, Any] | None = None
        seed_run_id = None
        seed_config_path = None

        if isinstance(payload.get("seed_config"), dict):
            seed_cfg = payload["seed_config"]
            seed_type = "inline"
        elif seed_type == "run":
            seed_run_id = str(payload.get("seed_run_id") or payload.get("run_id") or "").strip()
            if not seed_run_id:
                raise ValueError("Link-level job requires seed_run_id when seed_type=run")
            seed_cfg = _load_run_config(self.output_root, seed_run_id)
        else:
            seed_config_path = str(payload.get("seed_config_path") or payload.get("config_path") or "").strip()
            if not seed_config_path:
                raise ValueError("Link-level job requires seed_config_path when seed_type=config")
            config_path = Path(seed_config_path)
            if not config_path.exists():
                raise FileNotFoundError(f"Link seed config not found: {config_path}")
            seed_cfg = _load_yaml(config_path)
            if not isinstance(seed_cfg, dict):
                raise ValueError("Link seed config must be a YAML mapping")

        runtime = dict((seed_cfg.get("runtime") or {}))
        runtime_overrides = payload.get("runtime")
        if isinstance(runtime_overrides, dict):
            _deep_update(runtime, runtime_overrides)

        evaluation = payload.get("evaluation") if isinstance(payload.get("evaluation"), dict) else {}
        ris_variants = payload.get("ris_variants")
        if isinstance(ris_variants, list):
            evaluation["ris_variants"] = ris_variants

        estimators = payload.get("estimators")
        if isinstance(estimators, list):
            evaluation["estimators"] = estimators

        run_id = generate_run_id()
        base_dir = str(payload.get("base_dir") or "outputs")
        output_dir = create_output_dir(base_dir, run_id=run_id)
        job_id = f"job-{run_id}"

        job_cfg = {
            "schema_version": 1,
            "job": {
                "id": job_id,
                "kind": "link_level",
            },
            "seed": {
                "type": seed_type,
                "run_id": seed_run_id,
                "config_path": seed_config_path,
                "config": seed_cfg,
                "prepare_seed_run": bool(seed_type == "config" and payload.get("prepare_seed_run", True)),
            },
            "runtime": runtime,
            "evaluation": evaluation,
            "output": {
                "base_dir": base_dir,
                "run_id": run_id,
            },
        }

        job_config_path = output_dir / "job_config.yaml"
        save_yaml(job_config_path, job_cfg)
        job_log_path = output_dir / "job.log"

        job = {
            "job_id": job_id,
            "run_id": run_id,
            "kind": "link_level",
            "status": "running",
            "created_at": _now_ts(),
            "started_at": _now_ts(),
            "config_path": str(job_config_path),
            "output_dir": str(output_dir),
            "seed_type": seed_type,
            "seed_run_id": seed_run_id,
            "seed_config_path": seed_config_path,
        }

        process = subprocess.Popen(
            [sys.executable, "-m", "app", "link", "eval", "--config", str(job_config_path)],
            stdout=job_log_path.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )

        with self._lock:
            self.jobs[job_id] = job
            self.processes[job_id] = JobHandle(job_id=job_id, run_id=run_id, process=process)
            self._save_jobs()

        save_json(output_dir / "job.json", job)
        return job

    def _create_campaign_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        base_config = payload.get("base_config", "configs/indoor_box_high.yaml")
        config_path = Path(base_config)
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")

        cfg = _load_yaml(config_path)
        if not isinstance(cfg, dict):
            raise ValueError("Campaign config must be a YAML mapping")

        scene_overrides = payload.get("scene", {})
        if scene_overrides:
            cfg.setdefault("scene", {})
            _deep_update(cfg["scene"], scene_overrides)

        runtime_overrides = payload.get("runtime", {})
        if runtime_overrides:
            cfg.setdefault("runtime", {})
            _deep_update(cfg["runtime"], runtime_overrides)

        sim_overrides = payload.get("simulation", {})
        if sim_overrides:
            cfg.setdefault("simulation", {})
            _deep_update(cfg["simulation"], sim_overrides)

        radio_overrides = payload.get("radio_map", {})
        if radio_overrides:
            cfg.setdefault("radio_map", {})
            _deep_update(cfg["radio_map"], radio_overrides)

        ris_overrides = payload.get("ris", {})
        if ris_overrides:
            cfg.setdefault("ris", {})
            _deep_update(cfg["ris"], ris_overrides)

        campaign_overrides = payload.get("campaign", {})
        if not isinstance(campaign_overrides, dict):
            raise ValueError("Campaign payload requires a campaign mapping")
        cfg.setdefault("campaign", {})
        _deep_update(cfg["campaign"], campaign_overrides)

        output_cfg = cfg.setdefault("output", {})
        resume_run_id = campaign_overrides.get("resume_run_id")
        run_id = str(resume_run_id).strip() if resume_run_id else generate_run_id()
        output_cfg["run_id"] = run_id
        base_dir = output_cfg.get("base_dir", "outputs")
        output_dir = create_output_dir(base_dir, run_id=run_id)

        job_id = f"job-{run_id}-{int(time.time() * 1000)}"
        cfg.setdefault("job", {})
        cfg["job"].update({"id": job_id, "kind": "campaign", "scope": "indoor"})

        job_config_path = output_dir / "job_config.yaml"
        save_yaml(job_config_path, cfg)
        job_log_path = output_dir / "job.log"

        job = {
            "job_id": job_id,
            "run_id": run_id,
            "kind": "campaign",
            "status": "running",
            "created_at": _now_ts(),
            "started_at": _now_ts(),
            "config_path": str(job_config_path),
            "output_dir": str(output_dir),
            "resume_run_id": str(resume_run_id) if resume_run_id else None,
            "campaign": cfg.get("campaign", {}),
        }

        process = subprocess.Popen(
            [sys.executable, "-m", "app", "campaign", "run", "--config", str(job_config_path)],
            stdout=job_log_path.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )

        with self._lock:
            self.jobs[job_id] = job
            self.processes[job_id] = JobHandle(job_id=job_id, run_id=run_id, process=process)
            self._save_jobs()

        save_json(output_dir / "job.json", job)
        return job

    def _create_ris_lab_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "run")
        if action not in {"run", "validate", "compare"}:
            raise ValueError("RIS Lab action must be 'run', 'validate', or 'compare'")

        cfg = None
        config_data = payload.get("config_data")
        if isinstance(config_data, dict):
            cfg = config_data
        elif isinstance(payload.get("config"), dict):
            cfg = payload.get("config")
        else:
            config_value = payload.get("config_path") or payload.get("config") or payload.get("base_config")
            if not config_value:
                raise ValueError("RIS Lab job requires config_path or config_data")
            config_path = Path(config_value)
            if not config_path.exists():
                raise FileNotFoundError(f"RIS Lab config not found: {config_path}")

            cfg = _load_yaml(config_path)
            if not isinstance(cfg, dict):
                raise ValueError("RIS Lab config must be a YAML mapping")
        compare_overrides = payload.get("compare_overrides")
        if action == "compare" and isinstance(compare_overrides, dict):
            cfg.setdefault("compare", {})
            _deep_update(cfg["compare"], compare_overrides)

        output_cfg = cfg.setdefault("output", {})
        run_id = generate_run_id()
        output_cfg["run_id"] = run_id
        base_dir = output_cfg.get("base_dir", "outputs")
        output_dir = create_output_dir(base_dir, run_id=run_id)

        job_id = f"job-{run_id}"
        cfg.setdefault("job", {})
        cfg["job"].update({"id": job_id, "kind": "ris_lab", "action": action})

        job_config_path = output_dir / "job_config.yaml"
        save_yaml(job_config_path, cfg)
        job_log_path = output_dir / "job.log"

        command = [sys.executable, "-m", "app", "ris"]
        job_mode = None
        ref_path = None
        if action == "run":
            job_mode = payload.get("mode", "pattern")
            if job_mode not in {"pattern", "link"}:
                raise ValueError("RIS Lab run mode must be 'pattern' or 'link'")
            command += ["run", "--config", str(job_config_path), "--mode", job_mode]
        elif action == "compare":
            command += ["compare", "--config", str(job_config_path)]
        else:
            ref_path = payload.get("ref") or payload.get("ref_path") or payload.get("reference")
            if not ref_path:
                raise ValueError("RIS Lab validate requires ref path")
            command += ["validate", "--config", str(job_config_path), "--ref", str(ref_path)]

        job = {
            "job_id": job_id,
            "run_id": run_id,
            "kind": "ris_lab",
            "status": "running",
            "created_at": _now_ts(),
            "started_at": _now_ts(),
            "action": action,
            "mode": job_mode,
            "reference_path": str(ref_path) if ref_path else None,
            "config_path": str(job_config_path),
            "output_dir": str(output_dir),
        }

        process = subprocess.Popen(
            command,
            stdout=job_log_path.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )

        with self._lock:
            self.jobs[job_id] = job
            self.processes[job_id] = JobHandle(job_id=job_id, run_id=run_id, process=process)
            self._save_jobs()

        save_json(output_dir / "job.json", job)
        return job

    def _create_ris_synthesis_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action") or "run").strip().lower()
        if action == "quantize":
            return self._create_ris_synthesis_quantization_job(payload)
        cfg = None
        config_data = payload.get("config_data")
        if isinstance(config_data, dict):
            cfg = config_data
        elif isinstance(payload.get("config"), dict):
            cfg = payload.get("config")
        else:
            config_value = payload.get("config_path") or payload.get("config") or payload.get("base_config")
            if not config_value:
                raise ValueError("RIS synthesis job requires config_path or config_data")
            config_path = Path(config_value)
            if not config_path.exists():
                raise FileNotFoundError(f"RIS synthesis config not found: {config_path}")
            cfg = _load_yaml(config_path)
            if not isinstance(cfg, dict):
                raise ValueError("RIS synthesis config must be a YAML mapping")

        output_cfg = cfg.setdefault("output", {})
        run_id = generate_run_id()
        output_cfg["run_id"] = run_id
        base_dir = output_cfg.get("base_dir", "outputs")
        output_dir = create_output_dir(base_dir, run_id=run_id)

        job_id = f"job-{run_id}"
        cfg.setdefault("job", {})
        cfg["job"].update({"id": job_id, "kind": "ris_synthesis", "action": "run"})

        job_config_path = output_dir / "job_config.yaml"
        save_yaml(job_config_path, cfg)
        job_log_path = output_dir / "job.log"

        job = {
            "job_id": job_id,
            "run_id": run_id,
            "kind": "ris_synthesis",
            "status": "running",
            "created_at": _now_ts(),
            "started_at": _now_ts(),
            "action": "run",
            "config_path": str(job_config_path),
            "output_dir": str(output_dir),
        }

        process = subprocess.Popen(
            [sys.executable, "-m", "app", "ris-synth", "run", "--config", str(job_config_path)],
            stdout=job_log_path.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )

        with self._lock:
            self.jobs[job_id] = job
            self.processes[job_id] = JobHandle(job_id=job_id, run_id=run_id, process=process)
            self._save_jobs()

        save_json(output_dir / "job.json", job)
        return job

    def _create_ris_synthesis_quantization_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        source_run_id = str(payload.get("source_run_id") or "").strip()
        source_run_dir = str(payload.get("source_run_dir") or "").strip()
        if not source_run_id and not source_run_dir:
            raise ValueError("RIS synthesis quantization requires source_run_id or source_run_dir")

        bits = max(1, int(payload.get("bits", 2)))
        num_offset_samples = max(1, int(payload.get("num_offset_samples", 181)))
        run_id = generate_run_id()
        output_dir = create_output_dir("outputs", run_id=run_id)
        job_id = f"job-{run_id}"

        cfg = {
            "schema_version": 1,
            "source": {
                "run_id": source_run_id or None,
                "run_dir": source_run_dir or None,
            },
            "quantization": {
                "bits": bits,
                "method": "global_offset_sweep",
                "num_offset_samples": num_offset_samples,
            },
            "output": {
                "base_dir": "outputs",
                "run_id": run_id,
            },
            "job": {
                "id": job_id,
                "kind": "ris_synthesis",
                "action": "quantize",
            },
        }

        job_config_path = output_dir / "job_config.yaml"
        save_yaml(job_config_path, cfg)
        job_log_path = output_dir / "job.log"
        job = {
            "job_id": job_id,
            "run_id": run_id,
            "kind": "ris_synthesis",
            "status": "running",
            "created_at": _now_ts(),
            "started_at": _now_ts(),
            "action": "quantize",
            "source_run_id": source_run_id or None,
            "bits": bits,
            "num_offset_samples": num_offset_samples,
            "config_path": str(job_config_path),
            "output_dir": str(output_dir),
        }

        process = subprocess.Popen(
            [sys.executable, "-m", "app", "ris-synth", "quantize", "--config", str(job_config_path)],
            stdout=job_log_path.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )

        with self._lock:
            self.jobs[job_id] = job
            self.processes[job_id] = JobHandle(job_id=job_id, run_id=run_id, process=process)
            self._save_jobs()

        save_json(output_dir / "job.json", job)
        return job
