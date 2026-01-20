"""RIS Lab configuration schema and snapshot helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from app.io import create_output_dir, save_json, save_yaml

RIS_LAB_SCHEMA_VERSION = 1

DEFAULT_RIS_LAB_CONFIG: Dict[str, Any] = {
    "schema_version": RIS_LAB_SCHEMA_VERSION,
    "geometry": {
        "nx": None,
        "ny": None,
        "dx": None,
        "dy": None,
        "origin": [0.0, 0.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "x_axis_hint": [1.0, 0.0, 0.0],
    },
    "control": {
        "mode": "uniform",
        "params": {"phase_rad": 0.0},
    },
    "quantization": {
        "bits": 0,
    },
    "pattern_mode": {
        "normalization": "peak_0db",
        "rx_sweep_deg": {"start": -90.0, "stop": 90.0, "step": 2.0},
    },
    "link_mode": {
        "weighting": "inverse_distance",
        "enabled": False,
    },
    "validation": {
        "normalization": "peak_0db",
        "rmse_db_max": 2.0,
        "peak_angle_err_deg_max": 2.0,
        "peak_db_err_max": 1.5,
    },
    "experiment": {
        "frequency_hz": 28_000_000_000,
        "tx_incident_angle_deg": -30.0,
    },
    "output": {
        "base_dir": "outputs",
        "run_id": None,
    },
}

_ALIAS_FIELDS = {
    ("geometry", "nx"): [("geometry", "n")],
    ("geometry", "ny"): [("geometry", "m")],
    ("geometry", "dx"): [("geometry", "dx_m")],
    ("geometry", "dy"): [("geometry", "dy_m")],
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _apply_aliases(config: Dict[str, Any]) -> Dict[str, Any]:
    updated = copy.deepcopy(config)
    for (section, key), aliases in _ALIAS_FIELDS.items():
        section_data = updated.get(section)
        if not isinstance(section_data, dict):
            continue
        if key in section_data:
            continue
        for alias_section, alias_key in aliases:
            alias_data = updated.get(alias_section)
            if isinstance(alias_data, dict) and alias_key in alias_data:
                section_data[key] = alias_data[alias_key]
                break
        updated[section] = section_data
    return updated


def _missing_required_fields(geometry: Dict[str, Any]) -> list[str]:
    required = ("nx", "ny", "dx", "dy")
    missing = []
    for key in required:
        value = geometry.get(key)
        if value is None:
            missing.append(f"geometry.{key}")
    return missing


def _canonicalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    ordered_keys = [
        "schema_version",
        "geometry",
        "control",
        "quantization",
        "pattern_mode",
        "link_mode",
        "validation",
        "experiment",
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


def resolve_ris_lab_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_config, dict):
        raise ValueError("RIS Lab config must be a YAML mapping")

    normalized = _apply_aliases(raw_config)
    resolved = _deep_merge(copy.deepcopy(DEFAULT_RIS_LAB_CONFIG), normalized)

    geometry = resolved.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError("RIS Lab config geometry must be a mapping")

    missing = _missing_required_fields(geometry)
    if missing:
        raise ValueError(
            "RIS Lab config missing required fields: " + ", ".join(missing)
        )

    return _canonicalize_config(resolved)


def load_ris_lab_config(path: str | Path) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"RIS Lab config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return resolve_ris_lab_config(data)


def compute_ris_lab_config_hash(config: Dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ensure_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "plots").mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    return output_dir


def snapshot_ris_lab_config(output_dir: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = _ensure_output_dir(output_dir)
    yaml_path = output_dir / "config.yaml"
    json_path = output_dir / "config.json"
    save_yaml(yaml_path, config)
    save_json(json_path, config)

    config_hash = compute_ris_lab_config_hash(config)
    summary = {
        "schema_version": config.get("schema_version", RIS_LAB_SCHEMA_VERSION),
        "config": {
            "hash_sha256": config_hash,
            "path_yaml": str(yaml_path),
            "path_json": str(json_path),
        },
    }
    save_json(output_dir / "summary.json", summary)
    return summary


def resolve_and_snapshot_ris_lab_config(
    config_path: str | Path,
    output_dir: Optional[str | Path] = None,
) -> tuple[Dict[str, Any], Path, Dict[str, Any]]:
    config = load_ris_lab_config(config_path)
    if output_dir is None:
        output_cfg = config.get("output", {})
        base_dir = output_cfg.get("base_dir", "outputs")
        run_id = output_cfg.get("run_id")
        output_path = create_output_dir(base_dir, run_id=run_id)
    else:
        output_path = _ensure_output_dir(Path(output_dir))

    summary = snapshot_ris_lab_config(output_path, config)
    return config, output_path, summary
