"""RIS synthesis configuration schema and snapshot helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from app.io import create_output_dir, save_json, save_yaml

RIS_SYNTHESIS_SCHEMA_VERSION = 1
RIS_SYNTHESIS_QUANTIZATION_SCHEMA_VERSION = 1

DEFAULT_RIS_SYNTHESIS_CONFIG: Dict[str, Any] = {
    "schema_version": RIS_SYNTHESIS_SCHEMA_VERSION,
    "seed": {
        "type": "config",
        "config_path": None,
        "ris_name": "ris",
    },
    "target_region": {
        "plane": "coverage_map",
        "boxes": [],
        "freeze_mask": True,
    },
    "objective": {
        "kind": "mean_log_path_gain",
        "eps": 1.0e-12,
        "threshold_dbm": -90.0,
        "temperature_db": 2.0,
    },
    "parameterization": {
        "kind": "steering_search",
        "basis": "quadratic",
    },
    "search": {
        "azimuth_span_deg": 30.0,
        "elevation_span_deg": 16.0,
        "coarse_num_azimuth": 9,
        "coarse_num_elevation": 5,
        "coarse_cell_scale": 4.0,
        "coarse_sample_scale": 0.15,
        "refine_top_k": 5,
        "refine_num_azimuth": 7,
        "refine_num_elevation": 5,
        "refine_cell_scale": 2.0,
        "refine_sample_scale": 0.4,
    },
    "optimizer": {
        "iterations": 150,
        "learning_rate": 0.03,
        "algorithm": "adam",
        "log_every": 5,
    },
    "binarization": {
        "enabled": True,
        "method": "global_offset_sweep",
        "num_offset_samples": 181,
    },
    "refinement": {
        "enabled": False,
        "method": "greedy_flip",
        "candidate_budget": 64,
        "max_passes": 1,
    },
    "evaluation": {
        "dense_map": {
            "enabled": True,
        }
    },
    "output": {
        "base_dir": "outputs",
        "run_id": None,
    },
}

DEFAULT_RIS_SYNTHESIS_QUANTIZATION_CONFIG: Dict[str, Any] = {
    "schema_version": RIS_SYNTHESIS_QUANTIZATION_SCHEMA_VERSION,
    "source": {
        "run_id": None,
        "run_dir": None,
    },
    "quantization": {
        "bits": 2,
        "method": "global_offset_sweep",
        "num_offset_samples": 181,
    },
    "output": {
        "base_dir": "outputs",
        "run_id": None,
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _canonicalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    ordered_keys = [
        "schema_version",
        "seed",
        "target_region",
        "objective",
        "parameterization",
        "search",
        "optimizer",
        "binarization",
        "refinement",
        "evaluation",
        "output",
    ]
    ordered: Dict[str, Any] = {}
    for key in ordered_keys:
        if key in config:
            ordered[key] = config[key]
    extras = {k: v for k, v in config.items() if k not in ordered_keys}
    for key in sorted(extras):
        ordered[key] = extras[key]
    return ordered


def _resolve_seed_config_path(path_value: str) -> str:
    config_path = Path(str(path_value or "").strip())
    if not str(config_path):
        return ""
    if config_path.exists():
        return str(config_path)
    sibling_candidates = []
    if config_path.name == "job_config.yaml":
        sibling_candidates.append(config_path.with_name("config.yaml"))
    elif config_path.name == "config.yaml":
        sibling_candidates.append(config_path.with_name("job_config.yaml"))
    for candidate in sibling_candidates:
        if candidate.exists():
            return str(candidate)
    return str(config_path)


def resolve_ris_synthesis_config(raw_config: dict) -> dict:
    if not isinstance(raw_config, dict):
        raise ValueError("RIS synthesis config must be a YAML mapping")

    resolved = _deep_merge(copy.deepcopy(DEFAULT_RIS_SYNTHESIS_CONFIG), raw_config)
    seed_cfg = resolved.get("seed")
    if not isinstance(seed_cfg, dict):
        raise ValueError("RIS synthesis config seed must be a mapping")
    if str(seed_cfg.get("type") or "config").strip().lower() != "config":
        raise ValueError("RIS synthesis config seed.type must be 'config'")
    config_path = str(seed_cfg.get("config_path") or "").strip()
    if not config_path:
        raise ValueError("RIS synthesis config missing required field: seed.config_path")
    seed_cfg["type"] = "config"
    seed_cfg["config_path"] = _resolve_seed_config_path(config_path)
    seed_cfg["ris_name"] = str(seed_cfg.get("ris_name") or "ris").strip() or "ris"
    resolved["seed"] = seed_cfg

    target_cfg = resolved.get("target_region")
    if not isinstance(target_cfg, dict):
        raise ValueError("RIS synthesis config target_region must be a mapping")
    if str(target_cfg.get("plane") or "coverage_map").strip().lower() != "coverage_map":
        raise ValueError("RIS synthesis target_region.plane must be 'coverage_map'")
    boxes = target_cfg.get("boxes")
    if not isinstance(boxes, list) or not boxes:
        raise ValueError("RIS synthesis target_region.boxes must contain at least one box")
    normalized_boxes = []
    for idx, box in enumerate(boxes):
        if not isinstance(box, dict):
            raise ValueError(f"RIS synthesis target box {idx} must be a mapping")
        required = ("u_min_m", "u_max_m", "v_min_m", "v_max_m")
        missing = [name for name in required if box.get(name) is None]
        if missing:
            raise ValueError(
                f"RIS synthesis target box {idx} missing required fields: {', '.join(missing)}"
            )
        u_min = float(box["u_min_m"])
        u_max = float(box["u_max_m"])
        v_min = float(box["v_min_m"])
        v_max = float(box["v_max_m"])
        if u_min > u_max or v_min > v_max:
            raise ValueError(f"RIS synthesis target box {idx} has inverted bounds")
        normalized_boxes.append(
            {
                "name": str(box.get("name") or f"roi_{idx + 1}"),
                "u_min_m": u_min,
                "u_max_m": u_max,
                "v_min_m": v_min,
                "v_max_m": v_max,
            }
        )
    target_cfg["plane"] = "coverage_map"
    target_cfg["boxes"] = normalized_boxes
    target_cfg["freeze_mask"] = bool(target_cfg.get("freeze_mask", True))
    resolved["target_region"] = target_cfg

    objective_cfg = resolved.get("objective")
    if not isinstance(objective_cfg, dict):
        raise ValueError("RIS synthesis objective must be a mapping")
    if str(objective_cfg.get("kind") or "mean_log_path_gain").strip() != "mean_log_path_gain":
        raise ValueError("RIS synthesis objective.kind must be 'mean_log_path_gain'")
    objective_cfg["eps"] = float(objective_cfg.get("eps", 1.0e-12))
    objective_cfg["threshold_dbm"] = float(objective_cfg.get("threshold_dbm", -90.0))
    objective_cfg["temperature_db"] = float(objective_cfg.get("temperature_db", 2.0))
    resolved["objective"] = objective_cfg

    parameterization_cfg = resolved.get("parameterization")
    if not isinstance(parameterization_cfg, dict):
        raise ValueError("RIS synthesis parameterization must be a mapping")
    kind = str(parameterization_cfg.get("kind") or "steering_search").strip().lower()
    if kind not in {"steering_search", "smooth_residual", "raw_phase"}:
        raise ValueError(
            "RIS synthesis parameterization.kind must be "
            "'steering_search', 'smooth_residual', or 'raw_phase'"
        )
    basis = str(parameterization_cfg.get("basis") or "quadratic").strip().lower()
    if kind == "smooth_residual" and basis != "quadratic":
        raise ValueError("RIS synthesis parameterization.basis must be 'quadratic'")
    parameterization_cfg["kind"] = kind
    parameterization_cfg["basis"] = basis
    resolved["parameterization"] = parameterization_cfg

    search_cfg = resolved.get("search")
    if not isinstance(search_cfg, dict):
        raise ValueError("RIS synthesis search must be a mapping")
    search_cfg["azimuth_span_deg"] = max(0.0, float(search_cfg.get("azimuth_span_deg", 30.0)))
    search_cfg["elevation_span_deg"] = max(0.0, float(search_cfg.get("elevation_span_deg", 16.0)))
    search_cfg["coarse_num_azimuth"] = max(1, int(search_cfg.get("coarse_num_azimuth", 9)))
    search_cfg["coarse_num_elevation"] = max(1, int(search_cfg.get("coarse_num_elevation", 5)))
    search_cfg["coarse_cell_scale"] = max(1.0, float(search_cfg.get("coarse_cell_scale", 4.0)))
    search_cfg["coarse_sample_scale"] = min(
        1.0,
        max(1.0e-3, float(search_cfg.get("coarse_sample_scale", 0.15))),
    )
    search_cfg["refine_top_k"] = max(1, int(search_cfg.get("refine_top_k", 5)))
    search_cfg["refine_num_azimuth"] = max(1, int(search_cfg.get("refine_num_azimuth", 7)))
    search_cfg["refine_num_elevation"] = max(1, int(search_cfg.get("refine_num_elevation", 5)))
    search_cfg["refine_cell_scale"] = max(1.0, float(search_cfg.get("refine_cell_scale", 2.0)))
    search_cfg["refine_sample_scale"] = min(
        1.0,
        max(1.0e-3, float(search_cfg.get("refine_sample_scale", 0.4))),
    )
    resolved["search"] = search_cfg

    optimizer_cfg = resolved.get("optimizer")
    if not isinstance(optimizer_cfg, dict):
        raise ValueError("RIS synthesis optimizer must be a mapping")
    if str(optimizer_cfg.get("algorithm") or "adam").strip().lower() != "adam":
        raise ValueError("RIS synthesis optimizer.algorithm must be 'adam'")
    optimizer_cfg["algorithm"] = "adam"
    optimizer_cfg["iterations"] = max(1, int(optimizer_cfg.get("iterations", 150)))
    optimizer_cfg["learning_rate"] = float(optimizer_cfg.get("learning_rate", 0.03))
    optimizer_cfg["log_every"] = max(1, int(optimizer_cfg.get("log_every", 5)))
    resolved["optimizer"] = optimizer_cfg

    binarization_cfg = resolved.get("binarization")
    if not isinstance(binarization_cfg, dict):
        raise ValueError("RIS synthesis binarization must be a mapping")
    binarization_cfg["enabled"] = bool(binarization_cfg.get("enabled", True))
    if str(binarization_cfg.get("method") or "global_offset_sweep").strip() != "global_offset_sweep":
        raise ValueError("RIS synthesis binarization.method must be 'global_offset_sweep'")
    binarization_cfg["method"] = "global_offset_sweep"
    binarization_cfg["num_offset_samples"] = max(
        1, int(binarization_cfg.get("num_offset_samples", 181))
    )
    resolved["binarization"] = binarization_cfg

    refinement_cfg = resolved.get("refinement")
    if not isinstance(refinement_cfg, dict):
        raise ValueError("RIS synthesis refinement must be a mapping")
    if str(refinement_cfg.get("method") or "greedy_flip").strip() != "greedy_flip":
        raise ValueError("RIS synthesis refinement.method must be 'greedy_flip'")
    refinement_cfg["method"] = "greedy_flip"
    refinement_cfg["enabled"] = bool(refinement_cfg.get("enabled", False))
    refinement_cfg["candidate_budget"] = max(
        1, int(refinement_cfg.get("candidate_budget", 64))
    )
    refinement_cfg["max_passes"] = max(1, int(refinement_cfg.get("max_passes", 1)))
    resolved["refinement"] = refinement_cfg

    evaluation_cfg = resolved.get("evaluation")
    if not isinstance(evaluation_cfg, dict):
        raise ValueError("RIS synthesis evaluation must be a mapping")
    dense_map_cfg = evaluation_cfg.get("dense_map")
    if not isinstance(dense_map_cfg, dict):
        dense_map_cfg = {"enabled": True}
    dense_map_cfg["enabled"] = bool(dense_map_cfg.get("enabled", True))
    evaluation_cfg["dense_map"] = dense_map_cfg
    resolved["evaluation"] = evaluation_cfg

    output_cfg = resolved.get("output")
    if not isinstance(output_cfg, dict):
        raise ValueError("RIS synthesis output must be a mapping")
    output_cfg["base_dir"] = str(output_cfg.get("base_dir") or "outputs")
    run_id = output_cfg.get("run_id")
    output_cfg["run_id"] = str(run_id).strip() if run_id is not None else None
    resolved["output"] = output_cfg

    return _canonicalize_config(resolved)


def load_ris_synthesis_config(path: str | Path) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"RIS synthesis config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return resolve_ris_synthesis_config(data)


def resolve_ris_synthesis_quantization_config(raw_config: dict) -> dict:
    if not isinstance(raw_config, dict):
        raise ValueError("RIS synthesis quantization config must be a YAML mapping")

    resolved = _deep_merge(copy.deepcopy(DEFAULT_RIS_SYNTHESIS_QUANTIZATION_CONFIG), raw_config)
    source_cfg = resolved.get("source")
    if not isinstance(source_cfg, dict):
        raise ValueError("RIS synthesis quantization source must be a mapping")
    run_id = str(source_cfg.get("run_id") or "").strip() or None
    run_dir = str(source_cfg.get("run_dir") or "").strip() or None
    if not run_id and not run_dir:
        raise ValueError("RIS synthesis quantization requires source.run_id or source.run_dir")
    source_cfg["run_id"] = run_id
    source_cfg["run_dir"] = run_dir
    resolved["source"] = source_cfg

    quant_cfg = resolved.get("quantization")
    if not isinstance(quant_cfg, dict):
        raise ValueError("RIS synthesis quantization.quantization must be a mapping")
    quant_cfg["bits"] = max(1, int(quant_cfg.get("bits", 2)))
    if str(quant_cfg.get("method") or "global_offset_sweep").strip() != "global_offset_sweep":
        raise ValueError("RIS synthesis quantization.method must be 'global_offset_sweep'")
    quant_cfg["method"] = "global_offset_sweep"
    quant_cfg["num_offset_samples"] = max(1, int(quant_cfg.get("num_offset_samples", 181)))
    resolved["quantization"] = quant_cfg

    output_cfg = resolved.get("output")
    if not isinstance(output_cfg, dict):
        raise ValueError("RIS synthesis quantization output must be a mapping")
    output_cfg["base_dir"] = str(output_cfg.get("base_dir") or "outputs")
    run_id_out = output_cfg.get("run_id")
    output_cfg["run_id"] = str(run_id_out).strip() if run_id_out is not None else None
    resolved["output"] = output_cfg

    return {
        "schema_version": RIS_SYNTHESIS_QUANTIZATION_SCHEMA_VERSION,
        "source": resolved["source"],
        "quantization": resolved["quantization"],
        "output": resolved["output"],
    }


def load_ris_synthesis_quantization_config(path: str | Path) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"RIS synthesis quantization config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return resolve_ris_synthesis_quantization_config(data)


def compute_ris_synthesis_config_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ensure_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "plots").mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    return output_dir


def snapshot_ris_synthesis_config(output_dir: Path, config: dict) -> dict:
    output_dir = _ensure_output_dir(output_dir)
    yaml_path = output_dir / "config.yaml"
    save_yaml(yaml_path, config)
    config_hash = compute_ris_synthesis_config_hash(config)
    summary = {
        "schema_version": config.get("schema_version", RIS_SYNTHESIS_SCHEMA_VERSION),
        "config": {
            "hash_sha256": config_hash,
            "path_yaml": str(yaml_path),
        },
    }
    save_json(output_dir / "summary.json", summary)
    return summary


def resolve_and_snapshot_ris_synthesis_config(
    config_path, output_dir=None
) -> tuple[dict, Path, dict]:
    config = load_ris_synthesis_config(config_path)
    if output_dir is None:
        output_cfg = config.get("output", {})
        base_dir = output_cfg.get("base_dir", "outputs")
        run_id = output_cfg.get("run_id")
        output_path = create_output_dir(base_dir, run_id=run_id)
    else:
        output_path = _ensure_output_dir(Path(output_dir))
    summary = snapshot_ris_synthesis_config(output_path, config)
    return config, output_path, summary


def resolve_and_snapshot_ris_synthesis_quantization_config(
    config_path, output_dir=None
) -> tuple[dict, Path, dict]:
    config = load_ris_synthesis_quantization_config(config_path)
    if output_dir is None:
        output_cfg = config.get("output", {})
        base_dir = output_cfg.get("base_dir", "outputs")
        run_id = output_cfg.get("run_id")
        output_path = create_output_dir(base_dir, run_id=run_id)
    else:
        output_path = _ensure_output_dir(Path(output_dir))
    summary = snapshot_ris_synthesis_config(output_path, config)
    return config, output_path, summary
