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
from .utils.system import get_gpu_memory_mb


def _now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    score = grid * rays * max_depth
    return {"score": score, "grid_cells": grid, "rays": rays, "max_depth": max_depth}


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
    if kind == "quick_trace":
        return {
            "radio_map": {"enabled": False},
            "simulation": {"max_depth": 2, "samples_per_src": 20000, "max_num_paths_per_src": 20000},
            "visualization": {"ray_paths": {"max_paths": 120}},
        }
    if kind == "link_trace":
        return {
            "radio_map": {"enabled": False},
            "simulation": {"max_depth": 3, "samples_per_src": 120000, "max_num_paths_per_src": 200000},
            "visualization": {"ray_paths": {"max_paths": 400}},
        }
    if kind == "coverage_map":
        return {
            "radio_map": {"enabled": True},
            "visualization": {"ray_paths": {"max_paths": 200}},
        }
    return {}


def _deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


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
            self.jobs = json.loads(self.jobs_path.read_text())
        except Exception:
            self.jobs = {}

    def _save_jobs(self) -> None:
        self.jobs_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs_path.write_text(json.dumps(self.jobs, indent=2), encoding="utf-8")

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
                    self.jobs[job_id] = job
                    self.processes.pop(job_id, None)
            self._save_jobs()
            time.sleep(1.0)

    def list_jobs(self) -> Dict[str, Any]:
        with self._lock:
            return {"jobs": list(self.jobs.values())}

    def create_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        kind = payload.get("kind", "quick_trace")
        preset = payload.get("preset")
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

        radio_overrides = payload.get("radio_map", {})
        if radio_overrides:
            cfg.setdefault("radio_map", {})
            _deep_update(cfg["radio_map"], radio_overrides)

        if kind in {"quick_trace", "link_trace"}:
            cfg.setdefault("radio_map", {})["enabled"] = False

        run_id = generate_run_id()
        output_dir = create_output_dir(cfg.get("output", {}).get("base_dir", "outputs"), run_id=run_id)
        cfg.setdefault("output", {})["run_id"] = run_id

        guard_info = _apply_vram_guard(cfg)
        estimate = _estimate_job_cost(cfg)

        job_id = f"job-{run_id}"
        cfg.setdefault("job", {})
        cfg["job"].update({"id": job_id, "kind": kind, "preset": preset, "estimate": estimate})

        job_config_path = output_dir / "job_config.yaml"
        save_yaml(job_config_path, cfg)
        job_log_path = output_dir / "job.log"

        job = {
            "job_id": job_id,
            "run_id": run_id,
            "kind": kind,
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
