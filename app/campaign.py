from __future__ import annotations

import copy
import csv
import json
import logging
import math
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .io import create_output_dir, save_json, save_yaml
from .simulate import run_simulation

logger = logging.getLogger(__name__)


def _load_yaml(path: Path) -> Dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("Campaign config must be a YAML mapping")
    return data


def _normalize_angle_list(values: Any) -> List[float]:
    normalized: List[float] = []
    if not isinstance(values, list):
        return normalized
    for value in values:
        try:
            normalized.append(float(value))
        except Exception:
            continue
    return normalized


def _validate_resume_state(state: Dict[str, Any], *, all_angles: List[float], run_id: str) -> None:
    stored_angles = _normalize_angle_list(state.get("all_angles_deg"))
    current_angle_set = {float(angle) for angle in all_angles}

    invalid_measurement_angles: List[float] = []
    measurements = state.get("measurements", [])
    if isinstance(measurements, list):
        for row in measurements:
            if not isinstance(row, dict):
                continue
            try:
                measurement_angle = float(row["measurement_angle_deg"])
            except Exception:
                continue
            if measurement_angle not in current_angle_set:
                invalid_measurement_angles.append(measurement_angle)

    mismatch_reasons: List[str] = []
    if stored_angles and stored_angles != all_angles:
        mismatch_reasons.append(
            f"stored angle sweep has {len(stored_angles)} angles but current config has {len(all_angles)}"
        )
    if invalid_measurement_angles:
        preview = ", ".join(f"{angle:g}" for angle in invalid_measurement_angles[:6])
        if len(invalid_measurement_angles) > 6:
            preview += ", ..."
        mismatch_reasons.append(
            "stored measurements include angles outside the current sweep "
            f"({preview})"
        )

    if mismatch_reasons:
        reason_text = "; ".join(mismatch_reasons)
        raise ValueError(
            "Existing campaign state is incompatible with the current config for "
            f"run_id='{run_id}': {reason_text}. Start a new campaign run or resume "
            "with a matching sweep configuration."
        )


def _save_progress(
    progress_path: Path,
    *,
    status: str,
    completed: int,
    total: int,
    current_angle_deg: float | None = None,
    error: str | None = None,
) -> None:
    payload: Dict[str, Any] = {
        "status": status,
        "step_index": completed,
        "step_name": "Campaign sweep",
        "total_steps": total,
        "progress": (completed / total) if total else 1.0,
        "completed_angles": completed,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if current_angle_deg is not None:
        payload["current_angle_deg"] = float(current_angle_deg)
    if error:
        payload["error"] = error
    save_json(progress_path, payload)


def _angle_series(start_deg: float, stop_deg: float, step_deg: float) -> List[float]:
    if step_deg <= 0.0:
        raise ValueError("campaign.step_deg must be > 0")
    direction = 1.0 if stop_deg >= start_deg else -1.0
    signed_step = abs(step_deg) * direction
    count = int(math.floor(((stop_deg - start_deg) / signed_step) + 0.5)) + 1
    if count <= 0:
        raise ValueError("campaign angle sweep is empty")
    angles = [start_deg + idx * signed_step for idx in range(count)]
    while angles and (
        (direction > 0 and angles[-1] > stop_deg + 1e-6)
        or (direction < 0 and angles[-1] < stop_deg - 1e-6)
    ):
        angles.pop()
    return [float(round(angle, 6)) for angle in angles]


def _angle_run_id(index: int, angle_deg: float) -> str:
    angle_int = int(round(angle_deg))
    prefix = "p" if angle_int >= 0 else "m"
    return f"angle_{index:03d}_{prefix}{abs(angle_int):03d}"


def _position_on_arc(
    pivot: Iterable[float],
    radius_m: float,
    angle_deg: float,
    reference_yaw_deg: float = 0.0,
    arc_z_m: float | None = None,
) -> List[float]:
    pivot_vals = [float(v) for v in pivot]
    theta = math.radians(float(angle_deg) + float(reference_yaw_deg))
    return [
        float(pivot_vals[0] + radius_m * math.cos(theta)),
        float(pivot_vals[1] + radius_m * math.sin(theta)),
        float(pivot_vals[2] if arc_z_m is None else arc_z_m),
    ]


def _campaign_arc_z_m(pivot: Iterable[float], campaign_cfg: Dict[str, Any]) -> float:
    pivot_vals = [float(v) for v in pivot]
    if campaign_cfg.get("arc_height_m") is not None:
        return float(campaign_cfg["arc_height_m"])
    return float(pivot_vals[2] + float(campaign_cfg.get("arc_height_offset_m", 0.0)))


def _campaign_reference_yaw_deg(config: Dict[str, Any], campaign_cfg: Dict[str, Any]) -> float:
    explicit = campaign_cfg.get("reference_yaw_deg")
    if explicit is not None:
        return float(explicit)

    ris_cfg = config.get("ris", {})
    ris_objects = ris_cfg.get("objects", []) if isinstance(ris_cfg, dict) else []
    if not isinstance(ris_objects, list):
        return 0.0
    for item in ris_objects:
        if not isinstance(item, dict) or item.get("enabled", True) is False:
            continue
        orientation = item.get("orientation")
        if isinstance(orientation, (list, tuple)) and len(orientation) >= 1:
            try:
                return math.degrees(float(orientation[0]))
            except (TypeError, ValueError):
                pass
        look_at = item.get("look_at")
        position = item.get("position")
        if (
            isinstance(look_at, (list, tuple))
            and len(look_at) >= 2
            and isinstance(position, (list, tuple))
            and len(position) >= 2
        ):
            dx = float(look_at[0]) - float(position[0])
            dy = float(look_at[1]) - float(position[1])
            if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                return math.degrees(math.atan2(dy, dx))
    return 0.0


def _normalize_angle_deg(angle_deg: float) -> float:
    angle = float(angle_deg)
    while angle <= -180.0:
        angle += 360.0
    while angle > 180.0:
        angle -= 360.0
    return float(angle)


def _campaign_mode(campaign_cfg: Dict[str, Any]) -> str:
    return str(campaign_cfg.get("mode", "arc_sweep")).strip().lower() or "arc_sweep"


def _safe_slug(value: Any) -> str:
    text = str(value).strip().lower()
    return (
        text.replace(" ", "_")
        .replace("-", "m")
        .replace("+", "p")
        .replace(".", "p")
        .replace("/", "_")
    )


def _format_angle_token(angle_deg: float) -> str:
    rounded = float(angle_deg)
    prefix = "p" if rounded >= 0.0 else "m"
    magnitude = abs(rounded)
    if abs(magnitude - round(magnitude)) < 1e-6:
        return f"{prefix}{int(round(magnitude)):03d}"
    return f"{prefix}{magnitude:05.1f}".replace(".", "p")


def _format_frequency_token(freq_ghz: float) -> str:
    return f"{float(freq_ghz):0.1f}ghz".replace(".", "p")


def _active_ris_object(config: Dict[str, Any]) -> Dict[str, Any]:
    ris_cfg = config.get("ris", {})
    ris_objects = ris_cfg.get("objects", []) if isinstance(ris_cfg, dict) else []
    if not isinstance(ris_objects, list):
        raise ValueError("RIS config must define ris.objects")
    for item in ris_objects:
        if isinstance(item, dict) and item.get("enabled", True) is not False:
            return item
    raise ValueError("Campaign requires at least one enabled RIS object")


def _scene_position(scene_cfg: Dict[str, Any], key: str) -> List[float]:
    device_cfg = scene_cfg.get(key, {}) if isinstance(scene_cfg.get(key), dict) else {}
    position = device_cfg.get("position")
    if not isinstance(position, (list, tuple)) or len(position) < 3:
        raise ValueError(f"scene.{key}.position must be [x, y, z]")
    return [float(position[0]), float(position[1]), float(position[2])]


def _series_values(
    start_value: float | None,
    stop_value: float | None,
    step_value: float | None,
    *,
    fallback_values: Any = None,
) -> List[float]:
    if start_value is not None and stop_value is not None and step_value is not None:
        return _angle_series(float(start_value), float(stop_value), float(step_value))
    return _normalize_angle_list(fallback_values)


def _qub_target_angles_deg(campaign_cfg: Dict[str, Any]) -> List[float]:
    values = _series_values(
        campaign_cfg.get("target_angle_start_deg"),
        campaign_cfg.get("target_angle_stop_deg"),
        campaign_cfg.get("target_angle_step_deg"),
        fallback_values=campaign_cfg.get("target_angles_deg", [0.0, 15.0, 45.0, 60.0]),
    )
    if not values:
        raise ValueError("campaign target angles are empty")
    return [float(v) for v in values]


def _qub_frequency_series_ghz(config: Dict[str, Any], campaign_cfg: Dict[str, Any]) -> List[float]:
    start_value = campaign_cfg.get("frequency_start_ghz")
    stop_value = campaign_cfg.get("frequency_stop_ghz")
    step_value = campaign_cfg.get("frequency_step_ghz")
    if start_value is not None and stop_value is not None:
        start_ghz = float(start_value)
        stop_ghz = float(stop_value)
        if abs(start_ghz - stop_ghz) < 1e-9:
            return [start_ghz]
        if step_value is None or float(step_value) <= 0.0:
            raise ValueError("campaign.frequency_step_ghz must be > 0 when sweeping multiple frequencies")
        return _angle_series(start_ghz, stop_ghz, float(step_value))

    values = _normalize_angle_list(campaign_cfg.get("frequencies_ghz"))
    if values:
        return [float(v) for v in values]
    sim_cfg = config.get("simulation", {}) if isinstance(config.get("simulation"), dict) else {}
    freq_hz = sim_cfg.get("frequency_hz")
    if freq_hz is None:
        raise ValueError("campaign frequencies are required for qub_near_field mode")
    return [float(freq_hz) / 1.0e9]


def _qub_polarizations(config: Dict[str, Any], campaign_cfg: Dict[str, Any]) -> List[str]:
    values = campaign_cfg.get("polarizations")
    normalized: List[str] = []
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",")]
    if isinstance(values, list):
        for item in values:
            value = str(item).strip().upper()
            if value in {"V", "H"} and value not in normalized:
                normalized.append(value)
    if normalized:
        return normalized
    scene_cfg = config.get("scene", {}) if isinstance(config.get("scene"), dict) else {}
    arrays_cfg = scene_cfg.get("arrays", {}) if isinstance(scene_cfg.get("arrays"), dict) else {}
    tx_cfg = arrays_cfg.get("tx", {}) if isinstance(arrays_cfg.get("tx"), dict) else {}
    fallback = str(tx_cfg.get("polarization", "V")).strip().upper()
    return [fallback if fallback in {"V", "H"} else "V"]


def _set_array_polarization(scene_cfg: Dict[str, Any], polarization: str) -> None:
    arrays_cfg = scene_cfg.setdefault("arrays", {})
    for key in ("tx", "rx"):
        arrays_cfg.setdefault(key, {})
        arrays_cfg[key]["polarization"] = str(polarization).strip().upper()


def _set_ris_yaw_deg(ris_obj_cfg: Dict[str, Any], yaw_deg: float) -> None:
    orientation = ris_obj_cfg.get("orientation")
    orientation_vals = list(orientation) if isinstance(orientation, (list, tuple)) and len(orientation) >= 3 else [0.0, 0.0, 0.0]
    orientation_vals[0] = math.radians(float(yaw_deg))
    ris_obj_cfg["orientation"] = orientation_vals
    if "look_at" in ris_obj_cfg:
        del ris_obj_cfg["look_at"]


def _qub_case_id(target_angle_deg: float, freq_ghz: float, polarization: str) -> str:
    return "__".join(
        [
            f"target_{_format_angle_token(target_angle_deg)}deg",
            _format_frequency_token(freq_ghz),
            f"{_safe_slug(polarization)}pol",
        ]
    )


def _strongest_peak(values: np.ndarray) -> tuple[float | None, int | None]:
    if values.size == 0 or not np.isfinite(values).any():
        return None, None
    idx = int(np.nanargmax(values))
    return float(values[idx]), idx


def _estimate_sidelobe_metrics(
    measurement_angles_deg: np.ndarray,
    values_db: np.ndarray,
    *,
    guard_deg: float,
) -> Dict[str, float | None]:
    peak_value, peak_idx = _strongest_peak(values_db)
    if peak_value is None or peak_idx is None:
        return {
            "main_lobe_peak_db": None,
            "main_lobe_angle_deg": None,
            "strongest_sidelobe_db": None,
            "strongest_sidelobe_angle_deg": None,
            "strongest_sidelobe_relative_db": None,
        }
    peak_angle = float(measurement_angles_deg[peak_idx])
    mask = np.isfinite(values_db) & (np.abs(measurement_angles_deg - peak_angle) > float(guard_deg))
    if not np.any(mask):
        return {
            "main_lobe_peak_db": peak_value,
            "main_lobe_angle_deg": peak_angle,
            "strongest_sidelobe_db": None,
            "strongest_sidelobe_angle_deg": None,
            "strongest_sidelobe_relative_db": None,
        }
    sidelobe_values = values_db.copy()
    sidelobe_values[~mask] = np.nan
    sidelobe_peak, sidelobe_idx = _strongest_peak(sidelobe_values)
    sidelobe_angle = float(measurement_angles_deg[sidelobe_idx]) if sidelobe_idx is not None else None
    return {
        "main_lobe_peak_db": peak_value,
        "main_lobe_angle_deg": peak_angle,
        "strongest_sidelobe_db": sidelobe_peak,
        "strongest_sidelobe_angle_deg": sidelobe_angle,
        "strongest_sidelobe_relative_db": (float(sidelobe_peak - peak_value) if sidelobe_peak is not None else None),
    }


def _prune_angle_outputs(angle_dir: Path) -> None:
    for dirname in ("data", "plots", "viewer"):
        target = angle_dir / dirname
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    for filename in ("job.log", "job.json", "manifest.json"):
        target = angle_dir / filename
        if target.exists():
            try:
                target.unlink()
            except OSError:
                pass


def _prune_case_cache(case_dir: Path) -> None:
    cache_dir = case_dir / "_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)


def _is_ris_off_radio_map_entry(entry: Dict[str, Any]) -> bool:
    label = str(entry.get("label") or "").strip()
    suffix = str(entry.get("suffix") or "").strip()
    return label == "ris_off" or suffix == "ris_off" or label.startswith("ris_off_") or suffix.startswith("ris_off_")


def _is_tx_ris_radio_map_entry(entry: Dict[str, Any]) -> bool:
    label = str(entry.get("label") or "").strip()
    suffix = str(entry.get("suffix") or "").strip()
    return "tx_ris_incidence" in label or "tx_ris_incidence" in suffix


def _radio_map_suffix_token(entry: Dict[str, Any] | None) -> str | None:
    if not isinstance(entry, dict):
        return None
    suffix = entry.get("suffix")
    if suffix is None:
        return None
    suffix_text = str(suffix).strip()
    if not suffix_text or suffix_text == "ris_off":
        return None
    if suffix_text.startswith("ris_off_"):
        suffix_text = suffix_text[len("ris_off_") :]
    return suffix_text or None


def _radio_map_plane_z(entry: Dict[str, Any] | None) -> float | None:
    if not isinstance(entry, dict):
        return None
    try:
        return float(entry["plane_center_z_m"])
    except Exception:
        return None


def _radio_map_peak_value(entry: Dict[str, Any]) -> float | None:
    stats = entry.get("stats", {}) if isinstance(entry.get("stats"), dict) else {}
    try:
        value = float(stats["path_gain_db_max"])
    except Exception:
        return None
    return value if np.isfinite(value) else None


def _radio_map_entry_matches(entry: Dict[str, Any], reference: Dict[str, Any] | None) -> bool:
    if not isinstance(reference, dict):
        return False
    entry_token = _radio_map_suffix_token(entry)
    reference_token = _radio_map_suffix_token(reference)
    if entry_token == reference_token:
        return True
    entry_z = _radio_map_plane_z(entry)
    reference_z = _radio_map_plane_z(reference)
    return entry_z is not None and reference_z is not None and abs(entry_z - reference_z) < 1e-6


def _select_radio_map_entry(
    entries: List[Any],
    *,
    ris_off: bool,
    match: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    candidates: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if _is_tx_ris_radio_map_entry(entry):
            continue
        if _is_ris_off_radio_map_entry(entry) != ris_off:
            continue
        candidates.append(entry)
    if not candidates:
        return None

    if match is not None:
        matched = [entry for entry in candidates if _radio_map_entry_matches(entry, match)]
        if matched:
            candidates = matched

    best = None
    best_value = -float("inf")
    for entry in candidates:
        value = _radio_map_peak_value(entry)
        if value is None:
            continue
        if best is None or value > best_value:
            best = entry
            best_value = value
    return best or candidates[0]


def _radio_map_entry_metadata(entry: Dict[str, Any], *, prefix: str) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    label = entry.get("label")
    suffix = entry.get("suffix")
    if label is not None:
        metadata[f"{prefix}_label"] = label
    if suffix is not None:
        metadata[f"{prefix}_suffix"] = suffix
    plane_z = _radio_map_plane_z(entry)
    if plane_z is not None:
        metadata[f"{prefix}_plane_z_m"] = plane_z
    return metadata


def _radio_map_entry_data_path(output_dir: Path, entry: Dict[str, Any]) -> Path:
    suffix = entry.get("suffix")
    suffix_text = str(suffix).strip() if suffix is not None else ""
    if not suffix_text:
        return output_dir / "data" / "radio_map.npz"
    return output_dir / "data" / f"radio_map_{suffix_text}.npz"


def _radio_map_entry_sample_at_position(
    output_dir: Path,
    entry: Dict[str, Any] | None,
    position: List[float],
) -> Dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    path = _radio_map_entry_data_path(output_dir, entry)
    if not path.exists():
        return None
    try:
        with np.load(path) as data:
            cell_centers = np.asarray(data["cell_centers"], dtype=float)
            path_gain_db = np.asarray(data["path_gain_db"], dtype=float)
            rx_power_dbm = np.asarray(data["rx_power_dbm"], dtype=float) if "rx_power_dbm" in data.files else None
    except Exception:
        return None
    if cell_centers.ndim < 3 or cell_centers.shape[-1] < 3 or path_gain_db.shape != cell_centers.shape[:2]:
        return None
    target = np.asarray(position[:3], dtype=float)
    if target.size < 3 or not np.isfinite(target[:3]).all():
        return None
    deltas = cell_centers[..., :3] - target[None, None, :3]
    distances = np.sum(deltas * deltas, axis=-1)
    if distances.size == 0 or not np.isfinite(distances).any():
        return None
    flat_index = int(np.nanargmin(distances))
    row_idx, col_idx = np.unravel_index(flat_index, distances.shape)
    center = cell_centers[row_idx, col_idx, :3]
    measurement: Dict[str, Any] = {
        "path_gain_db": float(path_gain_db[row_idx, col_idx]),
        "cell_center": [float(center[0]), float(center[1]), float(center[2])],
        "cell_distance_m": float(np.sqrt(distances[row_idx, col_idx])),
    }
    if rx_power_dbm is not None and rx_power_dbm.shape == path_gain_db.shape:
        measurement["rx_power_dbm"] = float(rx_power_dbm[row_idx, col_idx])
    return measurement


def _select_radio_map_entry_for_position(
    entries: List[Any],
    position: List[float],
    *,
    ris_off: bool,
    match: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    candidates: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if _is_tx_ris_radio_map_entry(entry):
            continue
        if _is_ris_off_radio_map_entry(entry) != ris_off:
            continue
        candidates.append(entry)
    if not candidates:
        return None
    if match is not None:
        matched = [entry for entry in candidates if _radio_map_entry_matches(entry, match)]
        if matched:
            candidates = matched

    try:
        target_z = float(position[2])
    except Exception:
        target_z = None
    if target_z is None or not np.isfinite(target_z):
        return candidates[0]

    def sort_key(entry: Dict[str, Any]) -> tuple[float, float]:
        plane_z = _radio_map_plane_z(entry)
        z_error = abs(float(plane_z) - target_z) if plane_z is not None else float("inf")
        peak = _radio_map_peak_value(entry)
        return (z_error, -float(peak) if peak is not None else float("inf"))

    return sorted(candidates, key=sort_key)[0]


def _enrich_measurement_with_radio_map_point(output_dir: Path, row: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
    metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}
    radio_map_entries = metrics.get("radio_map", []) if isinstance(metrics.get("radio_map"), list) else []
    try:
        position = [float(row["position_x_m"]), float(row["position_y_m"]), float(row["position_z_m"])]
    except Exception:
        return row

    radio_map_entry = _select_radio_map_entry_for_position(radio_map_entries, position, ris_off=False)
    ris_off_radio_map_entry = _select_radio_map_entry_for_position(
        radio_map_entries,
        position,
        ris_off=True,
        match=radio_map_entry,
    )
    measurement = _radio_map_entry_sample_at_position(output_dir, radio_map_entry, position)
    ris_off_measurement = _radio_map_entry_sample_at_position(output_dir, ris_off_radio_map_entry, position)
    if measurement is None and ris_off_measurement is None:
        return row

    enriched = dict(row)
    if measurement is not None:
        enriched["radio_map_measurement_path_gain_db"] = measurement.get("path_gain_db")
        enriched["radio_map_measurement_rx_power_dbm"] = measurement.get("rx_power_dbm")
        enriched["radio_map_measurement_cell_distance_m"] = measurement.get("cell_distance_m")
        cell_center = measurement.get("cell_center")
        if isinstance(cell_center, list) and len(cell_center) >= 3:
            enriched["radio_map_measurement_cell_x_m"] = cell_center[0]
            enriched["radio_map_measurement_cell_y_m"] = cell_center[1]
            enriched["radio_map_measurement_cell_z_m"] = cell_center[2]
        if isinstance(radio_map_entry, dict):
            enriched.update(_radio_map_entry_metadata(radio_map_entry, prefix="radio_map_measurement"))
    if ris_off_measurement is not None:
        enriched["ris_off_radio_map_measurement_path_gain_db"] = ris_off_measurement.get("path_gain_db")
        enriched["ris_off_radio_map_measurement_rx_power_dbm"] = ris_off_measurement.get("rx_power_dbm")
        enriched["ris_off_radio_map_measurement_cell_distance_m"] = ris_off_measurement.get("cell_distance_m")
        if isinstance(ris_off_radio_map_entry, dict):
            enriched.update(_radio_map_entry_metadata(ris_off_radio_map_entry, prefix="ris_off_radio_map_measurement"))
    try:
        if (
            enriched.get("radio_map_measurement_path_gain_db") is not None
            and enriched.get("ris_off_radio_map_measurement_path_gain_db") is not None
        ):
            enriched["radio_map_measurement_delta_path_gain_db"] = float(
                enriched["radio_map_measurement_path_gain_db"]
            ) - float(enriched["ris_off_radio_map_measurement_path_gain_db"])
        if (
            enriched.get("radio_map_measurement_rx_power_dbm") is not None
            and enriched.get("ris_off_radio_map_measurement_rx_power_dbm") is not None
        ):
            enriched["radio_map_measurement_delta_rx_power_dbm"] = float(
                enriched["radio_map_measurement_rx_power_dbm"]
            ) - float(enriched["ris_off_radio_map_measurement_rx_power_dbm"])
    except Exception:
        pass
    return enriched


def _extract_measurement(
    summary: Dict[str, Any],
    *,
    angle_deg: float,
    run_id: str,
    position: List[float],
    extras: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}
    radio_map_entries = metrics.get("radio_map", []) if isinstance(metrics.get("radio_map"), list) else []
    radio_map_stats = {}
    ris_off_radio_map_stats = {}
    ris_link_probe = metrics.get("ris_link_probe", {}) if isinstance(metrics.get("ris_link_probe"), dict) else {}
    radio_map_entry = _select_radio_map_entry(radio_map_entries, ris_off=False)
    ris_off_radio_map_entry = _select_radio_map_entry(
        radio_map_entries,
        ris_off=True,
        match=radio_map_entry,
    )
    if isinstance(radio_map_entry, dict):
        radio_map_stats = radio_map_entry.get("stats", {}) or {}
    if isinstance(ris_off_radio_map_entry, dict):
        ris_off_radio_map_stats = ris_off_radio_map_entry.get("stats", {}) or {}

    radio_map_peak_gain = radio_map_stats.get("path_gain_db_max")
    radio_map_peak_rx = radio_map_stats.get("rx_power_dbm_max")
    ris_off_radio_map_peak_gain = ris_off_radio_map_stats.get("path_gain_db_max")
    ris_off_radio_map_peak_rx = ris_off_radio_map_stats.get("rx_power_dbm_max")
    radio_map_delta_gain = None
    radio_map_delta_rx = None
    try:
        if radio_map_peak_gain is not None and ris_off_radio_map_peak_gain is not None:
            radio_map_delta_gain = float(radio_map_peak_gain) - float(ris_off_radio_map_peak_gain)
        if radio_map_peak_rx is not None and ris_off_radio_map_peak_rx is not None:
            radio_map_delta_rx = float(radio_map_peak_rx) - float(ris_off_radio_map_peak_rx)
    except Exception:
        radio_map_delta_gain = None
        radio_map_delta_rx = None

    row = {
        "measurement_angle_deg": float(angle_deg),
        "run_id": str(run_id),
        "status": "completed",
        "position_x_m": float(position[0]),
        "position_y_m": float(position[1]),
        "position_z_m": float(position[2]),
        "total_path_gain_db": metrics.get("total_path_gain_db"),
        "rx_power_dbm_estimate": metrics.get("rx_power_dbm_estimate"),
        "ris_path_gain_db": metrics.get("ris_path_gain_db"),
        "non_ris_path_gain_db": metrics.get("non_ris_path_gain_db"),
        "ris_off_total_path_gain_db": ris_link_probe.get("off_total_path_gain_db"),
        "ris_off_rx_power_dbm_estimate": ris_link_probe.get("off_rx_power_dbm_estimate"),
        "ris_delta_total_path_gain_db": ris_link_probe.get("delta_total_path_gain_db"),
        "ris_delta_rx_power_dbm_estimate": ris_link_probe.get("delta_rx_power_dbm_estimate"),
        "num_valid_paths": metrics.get("num_valid_paths"),
        "num_ris_paths": metrics.get("num_ris_paths"),
        "radio_map_path_gain_db_mean": radio_map_stats.get("path_gain_db_mean"),
        "radio_map_rx_power_dbm_mean": radio_map_stats.get("rx_power_dbm_mean"),
        "radio_map_path_loss_db_mean": radio_map_stats.get("path_loss_db_mean"),
        "radio_map_path_gain_db_max": radio_map_peak_gain,
        "radio_map_rx_power_dbm_max": radio_map_peak_rx,
        "ris_off_radio_map_path_gain_db_max": ris_off_radio_map_peak_gain,
        "ris_off_radio_map_rx_power_dbm_max": ris_off_radio_map_peak_rx,
        "radio_map_delta_path_gain_db_max": radio_map_delta_gain,
        "radio_map_delta_rx_power_dbm_max": radio_map_delta_rx,
    }
    if isinstance(radio_map_entry, dict):
        row.update(_radio_map_entry_metadata(radio_map_entry, prefix="radio_map"))
    if isinstance(ris_off_radio_map_entry, dict):
        row.update(_radio_map_entry_metadata(ris_off_radio_map_entry, prefix="ris_off_radio_map"))
    if isinstance(extras, dict):
        row.update(extras)
    return row


def _enrich_qub_sample_from_summary(output_dir: Path, sample: Dict[str, Any]) -> Dict[str, Any]:
    if sample.get("radio_map_measurement_path_gain_db") is not None:
        return sample
    case_id = str(sample.get("case_id") or "").strip()
    run_id = str(sample.get("run_id") or "").strip()
    if not case_id or not run_id:
        return sample
    sample_output_dir = output_dir / "cases" / case_id / run_id
    summary_path = sample_output_dir / "summary.json"
    if not summary_path.exists():
        return sample
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        position = [
            float(sample.get("position_x_m", 0.0)),
            float(sample.get("position_y_m", 0.0)),
            float(sample.get("position_z_m", 0.0)),
        ]
        enriched = _extract_measurement(
            summary,
            angle_deg=float(sample.get("measurement_angle_deg", 0.0)),
            run_id=run_id,
            position=position,
            extras={
                "case_id": case_id,
                "target_angle_deg": sample.get("target_angle_deg"),
                "frequency_ghz": sample.get("frequency_ghz"),
                "polarization": sample.get("polarization"),
                "turntable_angle_deg": sample.get("turntable_angle_deg"),
            },
        )
        enriched = _enrich_measurement_with_radio_map_point(sample_output_dir, enriched, summary)
    except Exception:
        return sample
    return {**sample, **enriched}


def _enrich_qub_case_samples_from_summaries(output_dir: Path, case: Dict[str, Any]) -> Dict[str, Any]:
    samples = case.get("samples")
    if not isinstance(samples, list) or not samples:
        return case
    enriched_case = dict(case)
    enriched_case["samples"] = [
        _enrich_qub_sample_from_summary(output_dir, sample) if isinstance(sample, dict) else sample
        for sample in samples
    ]
    return enriched_case


def _write_measurements_csv(path: Path, measurements: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "measurement_angle_deg",
        "run_id",
        "status",
        "position_x_m",
        "position_y_m",
        "position_z_m",
        "total_path_gain_db",
        "rx_power_dbm_estimate",
        "ris_path_gain_db",
        "non_ris_path_gain_db",
        "ris_off_total_path_gain_db",
        "ris_off_rx_power_dbm_estimate",
        "ris_delta_total_path_gain_db",
        "ris_delta_rx_power_dbm_estimate",
        "num_valid_paths",
        "num_ris_paths",
        "radio_map_path_gain_db_mean",
        "radio_map_rx_power_dbm_mean",
        "radio_map_path_loss_db_mean",
        "radio_map_path_gain_db_max",
        "radio_map_rx_power_dbm_max",
        "ris_off_radio_map_path_gain_db_max",
        "ris_off_radio_map_rx_power_dbm_max",
        "radio_map_delta_path_gain_db_max",
        "radio_map_delta_rx_power_dbm_max",
        "radio_map_measurement_path_gain_db",
        "radio_map_measurement_rx_power_dbm",
        "radio_map_measurement_cell_distance_m",
        "radio_map_measurement_cell_x_m",
        "radio_map_measurement_cell_y_m",
        "radio_map_measurement_cell_z_m",
        "ris_off_radio_map_measurement_path_gain_db",
        "ris_off_radio_map_measurement_rx_power_dbm",
        "ris_off_radio_map_measurement_cell_distance_m",
        "radio_map_measurement_delta_path_gain_db",
        "radio_map_measurement_delta_rx_power_dbm",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in measurements:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _plot_series(path: Path, angles: np.ndarray, values: np.ndarray, *, title: str, ylabel: str, color: str) -> None:
    if angles.size == 0 or values.size == 0:
        return
    finite = np.isfinite(values)
    if not np.any(finite):
        return
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    ax.plot(angles[finite], values[finite], color=color, linewidth=2.0, marker="o", markersize=3.2)
    ax.set_title(title)
    ax.set_xlabel("Measurement angle [deg]")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_comparison_series(
    path: Path,
    angles: np.ndarray,
    primary: np.ndarray,
    secondary: np.ndarray,
    *,
    title: str,
    ylabel: str,
    primary_label: str,
    secondary_label: str,
    primary_color: str,
    secondary_color: str,
) -> None:
    if angles.size == 0 or primary.size == 0 or secondary.size == 0:
        return
    primary_finite = np.isfinite(primary)
    secondary_finite = np.isfinite(secondary)
    if not np.any(primary_finite) and not np.any(secondary_finite):
        return
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    if np.any(primary_finite):
        ax.plot(
            angles[primary_finite],
            primary[primary_finite],
            color=primary_color,
            linewidth=2.0,
            marker="o",
            markersize=3.2,
            label=primary_label,
        )
    if np.any(secondary_finite):
        ax.plot(
            angles[secondary_finite],
            secondary[secondary_finite],
            color=secondary_color,
            linewidth=2.0,
            marker="s",
            markersize=3.0,
            linestyle="--",
            label=secondary_label,
        )
    ax.set_title(title)
    ax.set_xlabel("Measurement angle [deg]")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _summarize_series(values: np.ndarray) -> Dict[str, float] | None:
    if values.size == 0 or not np.isfinite(values).any():
        return None
    return {
        "min": float(np.nanmin(values)),
        "mean": float(np.nanmean(values)),
        "max": float(np.nanmax(values)),
    }


def _measurement_series(measurements: List[Dict[str, Any]], key: str) -> tuple[np.ndarray, np.ndarray]:
    ordered = sorted(
        [item for item in measurements if item.get("status") == "completed"],
        key=lambda item: float(item.get("measurement_angle_deg", 0.0)),
    )
    angles = np.array(
        [float(item.get("measurement_angle_deg", index)) for index, item in enumerate(ordered)],
        dtype=float,
    )
    values = np.array(
        [float(item[key]) if item.get(key) is not None else np.nan for item in ordered],
        dtype=float,
    )
    return angles, values


def _select_reference_measurement(measurements: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    completed = [item for item in measurements if item.get("status") == "completed" and item.get("run_id")]
    if not completed:
        return None
    zeroish = sorted(
        completed,
        key=lambda item: (
            abs(float(item.get("measurement_angle_deg", 0.0))),
            float(item.get("measurement_angle_deg", 0.0)),
        ),
    )
    return zeroish[0]


def _copy_reference_radio_map_plots(
    campaign_dir: Path,
    plots_dir: Path,
    reference_measurement: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    if not isinstance(reference_measurement, dict):
        return []
    run_id = str(reference_measurement.get("run_id") or "").strip()
    if not run_id:
        return []
    angle_deg = float(reference_measurement.get("measurement_angle_deg", 0.0))
    source_plots_dir = campaign_dir / "angles" / run_id / "plots"
    if not source_plots_dir.exists():
        return []
    source_cfg_path = campaign_dir / "angles" / run_id / "config.yaml"
    if not source_cfg_path.exists():
        fallback_cfg_path = campaign_dir / "angles" / run_id / "job_config.yaml"
        if fallback_cfg_path.exists():
            source_cfg_path = fallback_cfg_path
    preferred_plane_z = _preferred_radio_map_plane_z(source_cfg_path, reference_measurement)

    plot_specs = [
        (
            "radio_map_path_gain_db.png",
            "campaign_reference_radio_map_path_gain_db.png",
            f"Representative path gain map ({angle_deg:g} deg)",
        ),
        (
            "radio_map_rx_power_dbm.png",
            "campaign_reference_radio_map_rx_power_dbm.png",
            f"Representative Rx power map ({angle_deg:g} deg)",
        ),
        (
            "radio_map_tx_ris_incidence_path_gain_db.png",
            "campaign_reference_tx_ris_incidence_path_gain_db.png",
            f"Tx->RIS incidence path gain ({angle_deg:g} deg)",
        ),
        (
            "radio_map_tx_ris_incidence_rx_power_dbm.png",
            "campaign_reference_tx_ris_incidence_rx_power_dbm.png",
            f"Tx->RIS incidence Rx power ({angle_deg:g} deg)",
        ),
    ]

    copied: List[Dict[str, Any]] = []
    for source_name, target_name, label in plot_specs:
        src = _resolve_radio_map_plot_source(source_plots_dir, source_name, preferred_plane_z)
        if not src.exists():
            continue
        dst = plots_dir / target_name
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
        copied.append({"file": target_name, "label": label})
    return copied


def _preferred_radio_map_plane_z(source_cfg_path: Path, measurement: Dict[str, Any] | None) -> float | None:
    preferred_plane_z = None
    if isinstance(measurement, dict):
        try:
            selected_plane_z = measurement.get("radio_map_measurement_plane_z_m")
            if selected_plane_z is not None:
                return float(selected_plane_z)
        except Exception:
            pass
        try:
            selected_plane_z = measurement.get("radio_map_plane_z_m")
            if selected_plane_z is not None:
                return float(selected_plane_z)
        except Exception:
            pass
    if source_cfg_path.exists():
        try:
            source_cfg = _load_yaml(source_cfg_path)
            radio_cfg = source_cfg.get("radio_map", {}) if isinstance(source_cfg, dict) else {}
            if radio_cfg.get("center_z_only") is not None:
                preferred_plane_z = float(radio_cfg.get("center_z_only"))
            else:
                center = radio_cfg.get("center")
                if isinstance(center, (list, tuple)) and len(center) >= 3:
                    preferred_plane_z = float(center[2])
        except Exception:
            preferred_plane_z = None
    if preferred_plane_z is None and isinstance(measurement, dict):
        try:
            preferred_plane_z = float(measurement.get("position_z_m"))
        except Exception:
            preferred_plane_z = None
    return preferred_plane_z


def _resolve_radio_map_plot_source(source_plots_dir: Path, source_name: str, preferred_plane_z: float | None) -> Path:
    src = source_plots_dir / source_name
    if not src.exists() and preferred_plane_z is not None and source_name.startswith("radio_map_") and "tx_ris_incidence" not in source_name:
        stem = Path(source_name).stem
        z_token = f"zm{abs(preferred_plane_z):.2f}".replace(".", "p") if preferred_plane_z < 0.0 else f"z{preferred_plane_z:.2f}".replace(".", "p")
        candidates = [
            source_plots_dir / f"{stem}_{z_token}.png",
            source_plots_dir / f"{stem}_{z_token}m.png",
        ]
        src = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    return src


def _copy_angle_radio_map_plot(
    campaign_dir: Path,
    plots_dir: Path,
    measurement: Dict[str, Any] | None,
) -> Dict[str, Any] | None:
    if not isinstance(measurement, dict):
        return None
    run_id = str(measurement.get("run_id") or "").strip()
    if not run_id:
        return None
    source_plots_dir = campaign_dir / "angles" / run_id / "plots"
    if not source_plots_dir.exists():
        return None
    source_cfg_path = campaign_dir / "angles" / run_id / "config.yaml"
    if not source_cfg_path.exists():
        fallback_cfg_path = campaign_dir / "angles" / run_id / "job_config.yaml"
        if fallback_cfg_path.exists():
            source_cfg_path = fallback_cfg_path
    preferred_plane_z = _preferred_radio_map_plane_z(source_cfg_path, measurement)
    src = _resolve_radio_map_plot_source(source_plots_dir, "radio_map_path_gain_db.png", preferred_plane_z)
    if not src.exists():
        return None

    angle_deg = float(measurement.get("measurement_angle_deg", 0.0))
    target_dir = plots_dir / "angle_radio_maps"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = f"angle_{_format_angle_token(angle_deg)}deg_radio_map_path_gain_db.png"
    dst = target_dir / target_name
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)
    return {
        "file": f"angle_radio_maps/{target_name}",
        "label": f"Angle {angle_deg:g} deg radio-map path gain",
    }


def _collect_angle_radio_map_plots(plots_dir: Path) -> List[Dict[str, Any]]:
    angle_dir = plots_dir / "angle_radio_maps"
    if not angle_dir.exists():
        return []
    manifest: List[Dict[str, Any]] = []
    for path in sorted(angle_dir.glob("*.png")):
        label = path.name
        prefix = "angle_"
        suffix = "_radio_map_path_gain_db.png"
        if path.name.startswith(prefix) and path.name.endswith(suffix):
            angle_token = path.name[len(prefix) : -len(suffix)]
            label = f"{angle_token} radio-map path gain"
        manifest.append({"file": f"angle_radio_maps/{path.name}", "label": label})
    return manifest


def _copy_qub_sample_radio_map_plot(
    sample_output_dir: Path,
    plots_dir: Path,
    sample_row: Dict[str, Any] | None,
) -> Dict[str, Any] | None:
    if not isinstance(sample_row, dict):
        return None
    source_plots_dir = sample_output_dir / "plots"
    if not source_plots_dir.exists():
        return None
    source_cfg_path = sample_output_dir / "config.yaml"
    if not source_cfg_path.exists():
        fallback_cfg_path = sample_output_dir / "job_config.yaml"
        if fallback_cfg_path.exists():
            source_cfg_path = fallback_cfg_path
    preferred_plane_z = _preferred_radio_map_plane_z(source_cfg_path, sample_row)
    case_id = str(sample_row.get("case_id") or "case").strip()
    measurement_angle_deg = float(sample_row.get("measurement_angle_deg", 0.0))
    run_id = str(sample_row.get("run_id") or "").strip() or f"sample_{_format_angle_token(measurement_angle_deg)}deg"
    target_dir = plots_dir / "qub_angle_radio_maps" / case_id
    target_dir.mkdir(parents=True, exist_ok=True)
    copied_default = None
    copied_sources: set[Path] = set()
    for source_name, target_suffix in (
        ("radio_map_path_gain_db.png", "radio_map_path_gain_db.png"),
        ("radio_map_ris_off_path_gain_db.png", "radio_map_ris_off_path_gain_db.png"),
    ):
        src = _resolve_radio_map_plot_source(source_plots_dir, source_name, preferred_plane_z)
        if not src.exists():
            continue
        copied_sources.add(src.resolve())
        target_name = f"{run_id}_{target_suffix}"
        dst = target_dir / target_name
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
        if source_name == "radio_map_path_gain_db.png":
            copied_default = target_name
    for src in sorted(
        [
            *source_plots_dir.glob("radio_map_path_gain_db_z*m.png"),
            *source_plots_dir.glob("radio_map_ris_off_path_gain_db_z*m.png"),
        ]
    ):
        if src.resolve() in copied_sources:
            continue
        target_name = f"{run_id}_{src.name}"
        dst = target_dir / target_name
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
    if copied_default is None:
        return None
    return {
        "file": f"qub_angle_radio_maps/{case_id}/{copied_default}",
        "label": f"{case_id} · {measurement_angle_deg:g} deg radio-map path gain",
        "case_id": case_id,
        "measurement_angle_deg": measurement_angle_deg,
    }


def _collect_qub_angle_radio_map_plots(plots_dir: Path) -> List[Dict[str, Any]]:
    root = plots_dir / "qub_angle_radio_maps"
    if not root.exists():
        return []
    manifest: List[Dict[str, Any]] = []
    for path in sorted(root.glob("*/*.png")):
        rel = path.relative_to(plots_dir).as_posix()
        case_id = path.parent.name
        manifest.append(
            {
                "file": rel,
                "label": f"{case_id} · {path.name}",
                "case_id": case_id,
            }
        )
    return manifest


def _measurement_series_from_samples(samples: List[Dict[str, Any]], key: str) -> tuple[np.ndarray, np.ndarray]:
    ordered = sorted(
        [item for item in samples if item.get("status", "completed") == "completed"],
        key=lambda item: float(item.get("measurement_angle_deg", 0.0)),
    )
    angles = np.array(
        [float(item.get("measurement_angle_deg", index)) for index, item in enumerate(ordered)],
        dtype=float,
    )
    values = np.array(
        [float(item[key]) if item.get(key) is not None else np.nan for item in ordered],
        dtype=float,
    )
    return angles, values


def _sample_series_has_finite_values(samples: List[Dict[str, Any]], key: str) -> bool:
    if not key:
        return False
    _, values = _measurement_series_from_samples(samples, key)
    return bool(values.size and np.isfinite(values).any())


def _sample_pair_has_finite_values(samples: List[Dict[str, Any]], on_key: str, off_key: str) -> bool:
    if not on_key or not off_key:
        return False
    _, on_values = _measurement_series_from_samples(samples, on_key)
    _, off_values = _measurement_series_from_samples(samples, off_key)
    if on_values.size == 0 or off_values.size == 0:
        return False
    pair_mask = np.isfinite(on_values) & np.isfinite(off_values)
    return bool(np.any(pair_mask))


def _sample_pair_has_contrast(
    samples: List[Dict[str, Any]],
    on_key: str,
    off_key: str,
    *,
    tolerance_db: float = 1e-6,
) -> bool:
    if not _sample_pair_has_finite_values(samples, on_key, off_key):
        return False
    _, on_values = _measurement_series_from_samples(samples, on_key)
    _, off_values = _measurement_series_from_samples(samples, off_key)
    pair_mask = np.isfinite(on_values) & np.isfinite(off_values)
    if not np.any(pair_mask):
        return False
    return bool(np.any(np.abs(on_values[pair_mask] - off_values[pair_mask]) > float(tolerance_db)))


def _normalize_series_to_peak(values: np.ndarray) -> np.ndarray:
    if values.size == 0 or not np.isfinite(values).any():
        return np.full(values.shape, np.nan, dtype=float)
    peak = float(np.nanmax(values))
    return values - peak


def _qub_specular_measurement_angle_deg(campaign_cfg: Dict[str, Any]) -> float:
    tx_incidence_angle_deg = float(campaign_cfg.get("tx_incidence_angle_deg", -30.0))
    return _normalize_angle_deg(-tx_incidence_angle_deg)


def _qub_specular_turntable_angle_deg(target_angle_deg: float, campaign_cfg: Dict[str, Any]) -> float:
    tx_incidence_angle_deg = float(campaign_cfg.get("tx_incidence_angle_deg", -30.0))
    return _normalize_angle_deg(float(target_angle_deg) + tx_incidence_angle_deg)


def _add_qub_angle_guide(
    ax: Any,
    measurement_angles_deg: np.ndarray,
    angle_deg: float | None,
    *,
    label: str,
    color: str,
    linestyle: Any,
    linewidth: float = 1.6,
) -> bool:
    if angle_deg is None or not np.isfinite(angle_deg):
        return False
    finite_angles = measurement_angles_deg[np.isfinite(measurement_angles_deg)]
    if finite_angles.size == 0:
        return False
    angle_min = float(np.nanmin(finite_angles))
    angle_max = float(np.nanmax(finite_angles))
    guide_angle = float(angle_deg)
    if guide_angle < angle_min - 1e-6 or guide_angle > angle_max + 1e-6:
        return False
    ax.axvline(
        guide_angle,
        color=color,
        linewidth=linewidth,
        linestyle=linestyle,
        alpha=0.85,
        label=label,
    )
    return True


def _add_qub_specular_path_guide(
    ax: Any,
    measurement_angles_deg: np.ndarray,
    specular_angle_deg: float | None,
) -> bool:
    return _add_qub_angle_guide(
        ax,
        measurement_angles_deg,
        specular_angle_deg,
        label="Specular path",
        color="#374151",
        linestyle=(0, (4, 3)),
    )


def _plot_qub_cut(
    path: Path,
    measurement_angles_deg: np.ndarray,
    values_on_db: np.ndarray,
    values_off_db: np.ndarray,
    *,
    title: str,
    ylabel: str,
    on_label: str = "RIS on",
    off_label: str = "RIS off",
    specular_angle_deg: float | None = None,
    ris_target_angle_deg: float | None = None,
) -> None:
    if measurement_angles_deg.size == 0:
        return
    on_finite = np.isfinite(values_on_db)
    off_finite = np.isfinite(values_off_db)
    if not np.any(on_finite) and not np.any(off_finite):
        return
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    if np.any(on_finite):
        ax.plot(
            measurement_angles_deg[on_finite],
            values_on_db[on_finite],
            color="#005f73",
            linewidth=2.0,
            label=on_label,
        )
    if np.any(off_finite):
        ax.plot(
            measurement_angles_deg[off_finite],
            values_off_db[off_finite],
            color="#ca6702",
            linewidth=1.8,
            linestyle="--",
            label=off_label,
        )
    _add_qub_specular_path_guide(ax, measurement_angles_deg, specular_angle_deg)
    _add_qub_angle_guide(
        ax,
        measurement_angles_deg,
        ris_target_angle_deg,
        label="RIS target",
        color="#9b2226",
        linestyle=(0, (1, 2)),
        linewidth=1.8,
    )
    ax.set_title(title)
    ax.set_xlabel("Measurement angle [deg]")
    ax.set_ylabel(ylabel)
    finite_stack = []
    if np.any(on_finite):
        finite_stack.append(values_on_db[on_finite])
    if np.any(off_finite):
        finite_stack.append(values_off_db[off_finite])
    values = np.concatenate(finite_stack)
    lower_limit = float(np.floor(np.nanmin(values) / 5.0) * 5.0)
    upper_limit = float(np.ceil(np.nanmax(values) / 5.0) * 5.0)
    if upper_limit - lower_limit < 5.0:
        upper_limit = lower_limit + 5.0
    ax.set_ylim(lower_limit, upper_limit)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_qub_delta(
    path: Path,
    measurement_angles_deg: np.ndarray,
    delta_db: np.ndarray,
    *,
    title: str,
    ylabel: str = "RIS boost [dB]",
    specular_angle_deg: float | None = None,
) -> None:
    if measurement_angles_deg.size == 0:
        return
    finite = np.isfinite(delta_db)
    if not np.any(finite):
        return
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    ax.plot(
        measurement_angles_deg[finite],
        delta_db[finite],
        color="#0a9396",
        linewidth=2.0,
        marker="o",
        markersize=3.2,
        label="RIS boost",
    )
    _add_qub_specular_path_guide(ax, measurement_angles_deg, specular_angle_deg)
    delta_min = float(np.nanmin(delta_db[finite]))
    delta_max = float(np.nanmax(delta_db[finite]))
    lower_limit = min(0.0, float(np.floor(delta_min / 5.0) * 5.0))
    upper_limit = max(5.0, float(np.ceil(delta_max / 5.0) * 5.0))
    if upper_limit - lower_limit < 5.0:
        upper_limit = lower_limit + 5.0
    ax.set_title(title)
    ax.set_xlabel("Measurement angle [deg]")
    ax.set_ylabel(ylabel)
    ax.set_ylim(lower_limit, upper_limit)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _select_preferred_series_candidate(
    samples: List[Dict[str, Any]],
    candidates: List[tuple[str, str, str, str, str]],
) -> tuple[str, str, str, str, str] | None:
    available: List[tuple[str, str, str, str, str]] = []
    for candidate in candidates:
        on_key, off_key, _, _, _ = candidate
        if off_key:
            if not _sample_pair_has_finite_values(samples, on_key, off_key):
                continue
            available.append(candidate)
            if _sample_pair_has_contrast(samples, on_key, off_key):
                return candidate
        elif _sample_series_has_finite_values(samples, on_key):
            available.append(candidate)
            return candidate
    return available[0] if available else None


def _find_series_candidate(
    candidates: List[tuple[str, str, str, str, str]],
    on_key: str,
) -> tuple[str, str, str, str, str] | None:
    for candidate in candidates:
        if candidate[0] == on_key:
            return candidate
    return None


def _qub_cut_series_keys(samples: List[Dict[str, Any]]) -> tuple[str, str, str, str, str]:
    candidates: List[tuple[str, str, str, str, str]] = []
    for item in samples:
        try:
            value = float(item.get("radio_map_measurement_path_gain_db"))
            reference = float(item.get("ris_off_radio_map_measurement_path_gain_db"))
        except Exception:
            continue
        if np.isfinite(value) and np.isfinite(reference):
            candidates.append(
                (
                    "radio_map_measurement_path_gain_db",
                    "ris_off_radio_map_measurement_path_gain_db",
                    "Radio-map measurement path gain [dB]",
                    "RIS on radio-map measurement",
                    "RIS off radio-map measurement",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("radio_map_path_gain_db_max"))
            reference = float(item.get("ris_off_radio_map_path_gain_db_max"))
        except Exception:
            continue
        if np.isfinite(value) and np.isfinite(reference):
            candidates.append(
                (
                    "radio_map_path_gain_db_max",
                    "ris_off_radio_map_path_gain_db_max",
                    "Radio-map peak path gain [dB]",
                    "RIS on radio-map peak",
                    "RIS off radio-map peak",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("ris_off_total_path_gain_db"))
        except Exception:
            continue
        if np.isfinite(value):
            candidates.append(
                (
                    "total_path_gain_db",
                    "ris_off_total_path_gain_db",
                    "Path gain [dB]",
                    "RIS on",
                    "RIS off",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("ris_path_gain_db"))
        except Exception:
            continue
        if np.isfinite(value) and value > -119.0:
            candidates.append(
                (
                    "ris_path_gain_db",
                    "non_ris_path_gain_db",
                    "RIS-only path gain [dB]",
                    "RIS only",
                    "Non-RIS background",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("ris_delta_total_path_gain_db"))
        except Exception:
            continue
        if np.isfinite(value):
            candidates.append(
                (
                    "ris_delta_total_path_gain_db",
                    "",
                    "RIS boost [dB]",
                    "RIS boost",
                    "",
                )
            )
            break
    measurement_candidate = _find_series_candidate(candidates, "radio_map_measurement_path_gain_db")
    total_candidate = _find_series_candidate(candidates, "total_path_gain_db")
    if (
        measurement_candidate is not None
        and not _sample_pair_has_contrast(samples, measurement_candidate[0], measurement_candidate[1])
        and total_candidate is not None
        and _sample_pair_has_contrast(samples, total_candidate[0], total_candidate[1])
    ):
        return total_candidate
    selected = _select_preferred_series_candidate(samples, candidates)
    if selected is not None:
        return selected
    fallback = (
        "total_path_gain_db",
        "ris_off_total_path_gain_db",
        "Path gain [dB]",
        "RIS on",
        "RIS off",
    )
    return fallback


def _qub_rx_power_series_key(samples: List[Dict[str, Any]]) -> str:
    on_key, _, _, _, _ = _qub_rx_power_series_keys(samples)
    return on_key


def _qub_rx_power_series_keys(samples: List[Dict[str, Any]]) -> tuple[str, str, str, str, str]:
    candidates: List[tuple[str, str, str, str, str]] = []
    for item in samples:
        try:
            value = float(item.get("radio_map_measurement_rx_power_dbm"))
            reference = float(item.get("ris_off_radio_map_measurement_rx_power_dbm"))
        except Exception:
            continue
        if np.isfinite(value) and np.isfinite(reference):
            candidates.append(
                (
                    "radio_map_measurement_rx_power_dbm",
                    "ris_off_radio_map_measurement_rx_power_dbm",
                    "Radio-map measurement Rx power [dBm]",
                    "RIS on radio-map measurement",
                    "RIS off radio-map measurement",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("radio_map_rx_power_dbm_max"))
            reference = float(item.get("ris_off_radio_map_rx_power_dbm_max"))
        except Exception:
            continue
        if np.isfinite(value) and np.isfinite(reference):
            candidates.append(
                (
                    "radio_map_rx_power_dbm_max",
                    "ris_off_radio_map_rx_power_dbm_max",
                    "Radio-map peak Rx power [dBm]",
                    "RIS on radio-map peak",
                    "RIS off radio-map peak",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("rx_power_dbm_estimate"))
            reference = float(item.get("ris_off_rx_power_dbm_estimate"))
        except Exception:
            continue
        if np.isfinite(value) and np.isfinite(reference):
            candidates.append(
                (
                    "rx_power_dbm_estimate",
                    "ris_off_rx_power_dbm_estimate",
                    "Rx power estimate [dBm]",
                    "RIS on",
                    "RIS off",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("radio_map_measurement_rx_power_dbm"))
        except Exception:
            continue
        if np.isfinite(value):
            candidates.append(
                (
                    "radio_map_measurement_rx_power_dbm",
                    "",
                    "Radio-map measurement Rx power [dBm]",
                    "RIS on radio-map measurement",
                    "",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("radio_map_rx_power_dbm_max"))
        except Exception:
            continue
        if np.isfinite(value):
            candidates.append(
                (
                    "radio_map_rx_power_dbm_max",
                    "",
                    "Radio-map peak Rx power [dBm]",
                    "RIS on radio-map peak",
                    "",
                )
            )
            break
    for item in samples:
        try:
            value = float(item.get("rx_power_dbm_estimate"))
        except Exception:
            continue
        if np.isfinite(value):
            candidates.append(
                (
                    "rx_power_dbm_estimate",
                    "",
                    "Rx power estimate [dBm]",
                    "RIS on",
                    "",
                )
            )
            break
    selected = _select_preferred_series_candidate(samples, candidates)
    measurement_candidate = _find_series_candidate(candidates, "radio_map_measurement_rx_power_dbm")
    rx_power_candidate = _find_series_candidate(candidates, "rx_power_dbm_estimate")
    if (
        measurement_candidate is not None
        and measurement_candidate[1]
        and not _sample_pair_has_contrast(samples, measurement_candidate[0], measurement_candidate[1])
        and rx_power_candidate is not None
        and rx_power_candidate[1]
        and _sample_pair_has_contrast(samples, rx_power_candidate[0], rx_power_candidate[1])
    ):
        return rx_power_candidate
    if selected is not None:
        return selected
    return ("rx_power_dbm_estimate", "ris_off_rx_power_dbm_estimate", "Rx power estimate [dBm]", "RIS on", "RIS off")


def _plot_qub_peak_vs_frequency(
    path: Path,
    frequencies_ghz: np.ndarray,
    series: List[Dict[str, Any]],
    *,
    title: str,
) -> None:
    if frequencies_ghz.size == 0 or not series:
        return
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    plotted = False
    palette = plt.get_cmap("tab10")
    for idx, row in enumerate(series):
        values = np.array(row.get("peak_values_db", []), dtype=float)
        if values.size != frequencies_ghz.size or not np.isfinite(values).any():
            continue
        normalized = _normalize_series_to_peak(values)
        finite = np.isfinite(normalized)
        if not np.any(finite):
            continue
        ax.plot(
            frequencies_ghz[finite],
            normalized[finite],
            linewidth=2.0,
            marker="o",
            markersize=3.2,
            color=palette(idx / max(len(series) - 1, 1)),
            label=row.get("label", f"Series {idx + 1}"),
        )
        plotted = True
    if not plotted:
        plt.close(fig)
        return
    ax.set_title(title)
    ax.set_xlabel("Frequency [GHz]")
    ax.set_ylabel("Normalized peak [dB]")
    ax.set_ylim(-12.0, 2.0)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_qub_peak_power_vs_target_angle(
    path: Path,
    target_angles_deg: np.ndarray,
    peak_power_dbm: np.ndarray,
    *,
    title: str,
    off_peak_power_dbm: np.ndarray | None = None,
    on_label: str = "RIS on peak Rx power",
    off_label: str = "RIS off peak Rx power",
) -> None:
    if target_angles_deg.size == 0 or peak_power_dbm.size != target_angles_deg.size:
        return
    finite = np.isfinite(peak_power_dbm)
    off_finite = (
        np.isfinite(off_peak_power_dbm)
        if off_peak_power_dbm is not None and off_peak_power_dbm.size == target_angles_deg.size
        else np.full(target_angles_deg.shape, False, dtype=bool)
    )
    if not np.any(finite) and not np.any(off_finite):
        return
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    finite_series = []
    if np.any(finite):
        ax.plot(
            target_angles_deg[finite],
            peak_power_dbm[finite],
            color="#005f73",
            linewidth=2.0,
            marker="o",
            markersize=3.2,
            label=on_label,
        )
        finite_series.append(peak_power_dbm[finite])
    if off_peak_power_dbm is not None and np.any(off_finite):
        ax.plot(
            target_angles_deg[off_finite],
            off_peak_power_dbm[off_finite],
            color="#ca6702",
            linewidth=1.8,
            marker="s",
            markersize=3.0,
            linestyle="--",
            label=off_label,
        )
        finite_series.append(off_peak_power_dbm[off_finite])
    finite_values = np.concatenate(finite_series)
    power_min = float(np.nanmin(finite_values))
    power_max = float(np.nanmax(finite_values))
    lower_limit = float(np.floor(power_min / 5.0) * 5.0)
    upper_limit = float(np.ceil(power_max / 5.0) * 5.0)
    if upper_limit - lower_limit < 5.0:
        upper_limit = lower_limit + 5.0
    ax.set_title(title)
    ax.set_xlabel("Target angle [deg]")
    ax.set_ylabel("Peak Rx power [dBm]")
    ax.set_ylim(lower_limit, upper_limit)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _case_peak_value(case: Dict[str, Any], case_key: str, sample_key: str) -> float | None:
    try:
        case_value = float(case.get(case_key))
        if np.isfinite(case_value):
            return case_value
    except (TypeError, ValueError):
        pass
    samples = case.get("samples", [])
    if not isinstance(samples, list) or not samples:
        return None
    _, values = _measurement_series_from_samples(samples, sample_key)
    peak_value, _ = _strongest_peak(values)
    return peak_value


def _qub_case_metric_summary(case: Dict[str, Any], campaign_cfg: Dict[str, Any]) -> Dict[str, Any]:
    samples = case.get("samples", [])
    if not isinstance(samples, list) or not samples:
        return {}
    on_key, off_key, _, _, _ = _qub_cut_series_keys(samples)
    measurement_angles, on_values = _measurement_series_from_samples(samples, on_key)
    _, off_values = _measurement_series_from_samples(samples, off_key)
    rx_power_key, rx_power_off_key, _, _, _ = _qub_rx_power_series_keys(samples)
    _, rx_power_values = _measurement_series_from_samples(samples, rx_power_key)
    _, rx_power_off_values = _measurement_series_from_samples(samples, rx_power_off_key)
    sidelobe_guard_deg = float(campaign_cfg.get("sidelobe_guard_deg", 6.0))
    on_metrics = _estimate_sidelobe_metrics(measurement_angles, on_values, guard_deg=sidelobe_guard_deg)
    off_metrics = _estimate_sidelobe_metrics(measurement_angles, off_values, guard_deg=sidelobe_guard_deg)
    rx_power_metrics = _estimate_sidelobe_metrics(
        measurement_angles,
        rx_power_values,
        guard_deg=sidelobe_guard_deg,
    )
    rx_power_off_metrics = _estimate_sidelobe_metrics(
        measurement_angles,
        rx_power_off_values,
        guard_deg=sidelobe_guard_deg,
    )
    return {
        "response_metric_key": on_key,
        "reference_metric_key": off_key,
        "main_lobe_peak_db": on_metrics.get("main_lobe_peak_db"),
        "main_lobe_angle_deg": on_metrics.get("main_lobe_angle_deg"),
        "main_lobe_rx_power_dbm": rx_power_metrics.get("main_lobe_peak_db"),
        "main_lobe_rx_power_angle_deg": rx_power_metrics.get("main_lobe_angle_deg"),
        "main_lobe_rx_power_metric_key": rx_power_key,
        "ris_off_main_lobe_rx_power_dbm": rx_power_off_metrics.get("main_lobe_peak_db"),
        "ris_off_main_lobe_rx_power_angle_deg": rx_power_off_metrics.get("main_lobe_angle_deg"),
        "ris_off_main_lobe_rx_power_metric_key": rx_power_off_key,
        "strongest_sidelobe_db": on_metrics.get("strongest_sidelobe_db"),
        "strongest_sidelobe_angle_deg": on_metrics.get("strongest_sidelobe_angle_deg"),
        "strongest_sidelobe_relative_db": on_metrics.get("strongest_sidelobe_relative_db"),
        "ris_off_main_lobe_peak_db": off_metrics.get("main_lobe_peak_db"),
        "ris_off_main_lobe_angle_deg": off_metrics.get("main_lobe_angle_deg"),
        "ris_off_strongest_sidelobe_db": off_metrics.get("strongest_sidelobe_db"),
        "ris_off_strongest_sidelobe_angle_deg": off_metrics.get("strongest_sidelobe_angle_deg"),
        "ris_off_strongest_sidelobe_relative_db": off_metrics.get("strongest_sidelobe_relative_db"),
    }


def _qub_target_position(
    ris_position: List[float],
    *,
    target_radius_m: float,
    target_angle_deg: float,
    reference_yaw_deg: float,
    target_z_m: float,
) -> List[float]:
    return _position_on_arc(
        ris_position,
        float(target_radius_m),
        float(target_angle_deg),
        float(reference_yaw_deg),
        arc_z_m=float(target_z_m),
    )


def _qub_measurement_angle_deg(rx_position: List[float], ris_position: List[float], reference_yaw_deg: float) -> float:
    global_angle = math.degrees(
        math.atan2(float(rx_position[1]) - float(ris_position[1]), float(rx_position[0]) - float(ris_position[0]))
    )
    return _normalize_angle_deg(global_angle - float(reference_yaw_deg))


def _build_qub_turntable_config(
    config: Dict[str, Any],
    campaign_cfg: Dict[str, Any],
    *,
    case_id: str,
    target_angle_deg: float,
    frequency_ghz: float,
    polarization: str,
    turntable_angle_deg: float,
    sample_index: int,
    sample_base_dir: Path,
) -> tuple[Dict[str, Any], Path, Dict[str, Any]]:
    cfg = copy.deepcopy(config)
    cfg.pop("campaign", None)
    cfg["job"] = {"kind": "run", "scope": "indoor"}

    scene_cfg = cfg.setdefault("scene", {})
    sim_cfg = cfg.setdefault("simulation", {})
    sim_cfg["frequency_hz"] = float(frequency_ghz) * 1.0e9
    radio_map_cfg = cfg.setdefault("radio_map", {})
    if campaign_cfg.get("ris_off_amplitude") is not None:
        ris_off_amplitude = float(campaign_cfg["ris_off_amplitude"])
        sim_cfg["ris_off_amplitude"] = ris_off_amplitude
        radio_map_cfg["ris_off_amplitude"] = ris_off_amplitude
    else:
        sim_cfg.setdefault("ris_off_amplitude", 0.9)
        radio_map_cfg.setdefault("ris_off_amplitude", float(sim_cfg.get("ris_off_amplitude", 0.9)))
    _set_array_polarization(scene_cfg, polarization)

    ris_obj_cfg = _active_ris_object(cfg)
    ris_position = [float(v) for v in ris_obj_cfg.get("position", [0.0, 0.0, 0.0])[:3]]
    base_reference_yaw_deg = _campaign_reference_yaw_deg(config, campaign_cfg)
    current_reference_yaw_deg = float(base_reference_yaw_deg + turntable_angle_deg)
    _set_ris_yaw_deg(ris_obj_cfg, current_reference_yaw_deg)

    tx_position_base = _scene_position(scene_cfg, "tx")
    rx_position = _scene_position(scene_cfg, "rx")
    tx_z_offset_m = float(campaign_cfg.get("tx_height_offset_m", tx_position_base[2] - ris_position[2]))
    target_z_offset_m = float(campaign_cfg.get("target_height_offset_m", rx_position[2] - ris_position[2]))
    tx_ris_distance_m = float(campaign_cfg.get("tx_ris_distance_m", 0.4))
    target_radius_m = float(
        campaign_cfg.get(
            "target_distance_m",
            campaign_cfg.get("rx_ris_distance_m", math.dist(rx_position, ris_position)),
        )
    )
    if tx_ris_distance_m <= 0.0:
        raise ValueError("campaign.tx_ris_distance_m must be > 0 for qub_near_field mode")
    if target_radius_m <= 0.0:
        raise ValueError("campaign.target_distance_m must be > 0 for qub_near_field mode")
    tx_incidence_angle_deg = float(campaign_cfg.get("tx_incidence_angle_deg", -30.0))
    tx_position = _position_on_arc(
        ris_position,
        tx_ris_distance_m,
        tx_incidence_angle_deg,
        current_reference_yaw_deg,
        arc_z_m=float(ris_position[2] + tx_z_offset_m),
    )
    scene_cfg.setdefault("tx", {})["position"] = tx_position
    if bool(campaign_cfg.get("tx_look_at_ris", True)):
        scene_cfg["tx"]["look_at"] = [float(v) for v in ris_position]
        if "orientation" in scene_cfg["tx"]:
            del scene_cfg["tx"]["orientation"]
    if bool(campaign_cfg.get("rx_look_at_ris", True)):
        scene_cfg.setdefault("rx", {})["look_at"] = [float(v) for v in ris_position]
        if "orientation" in scene_cfg["rx"]:
            del scene_cfg["rx"]["orientation"]

    target_position = _qub_target_position(
        ris_position,
        target_radius_m=target_radius_m,
        target_angle_deg=target_angle_deg,
        reference_yaw_deg=current_reference_yaw_deg,
        target_z_m=float(ris_position[2] + target_z_offset_m),
    )
    if bool(campaign_cfg.get("show_specular_path", True)):
        specular_target_position = _qub_target_position(
            ris_position,
            target_radius_m=target_radius_m,
            target_angle_deg=_qub_specular_measurement_angle_deg(campaign_cfg),
            reference_yaw_deg=current_reference_yaw_deg,
            target_z_m=float(ris_position[2] + target_z_offset_m),
        )
        guide_path = {
            "enabled": True,
            "label": "Specular path",
            "points": [tx_position, ris_position, specular_target_position],
            "color": "#f59e0b",
            "linestyle": "--",
            "linewidth": 2.2,
            "alpha": 0.95,
        }
        existing_guides = radio_map_cfg.get("specular_paths")
        if not isinstance(existing_guides, list):
            existing_guides = []
        radio_map_cfg["specular_paths"] = [*existing_guides, guide_path]
    profile_cfg = ris_obj_cfg.get("profile")
    if isinstance(profile_cfg, dict):
        requested_profile_kind = str(campaign_cfg.get("ris_profile_kind") or "").strip().lower()
        if requested_profile_kind:
            profile_cfg["kind"] = requested_profile_kind
        profile_cfg["sources"] = [float(v) for v in tx_position]
        profile_cfg["targets"] = [float(v) for v in target_position]
        profile_cfg["auto_aim"] = True

    compact_output = bool(campaign_cfg.get("compact_output", True))
    disable_render = bool(campaign_cfg.get("disable_render", compact_output))
    disable_ray_paths = bool(campaign_cfg.get("disable_ray_path_export", compact_output))
    disable_mesh_export = bool(campaign_cfg.get("disable_mesh_export", compact_output))
    coarse_cell_size = campaign_cfg.get("coarse_cell_size_m")
    if disable_render:
        cfg.setdefault("render", {})["enabled"] = False
    cfg.setdefault("viewer", {})["enabled"] = False
    if disable_ray_paths:
        cfg.setdefault("visualization", {}).setdefault("ray_paths", {})["enabled"] = False
    if disable_mesh_export:
        cfg.setdefault("scene", {})["export_mesh"] = False
    if coarse_cell_size is not None:
        coarse_value = float(coarse_cell_size)
        if coarse_value <= 0.0:
            raise ValueError("campaign.coarse_cell_size_m must be > 0")
        cfg.setdefault("radio_map", {})["cell_size"] = [coarse_value, coarse_value]
    if compact_output:
        _disable_nonessential_campaign_radio_maps(cfg, preserve_z_stack=True)

    sample_run_id = f"{case_id}__sample_{sample_index:03d}_{_format_angle_token(turntable_angle_deg)}deg"
    cfg.setdefault("output", {})
    cfg["output"]["base_dir"] = str(sample_base_dir)
    cfg["output"]["run_id"] = sample_run_id
    sample_run_dir = create_output_dir(str(sample_base_dir), run_id=sample_run_id)
    sample_config_path = sample_run_dir / "job_config.yaml"
    save_yaml(sample_config_path, cfg)
    metadata = {
        "ris_position": ris_position,
        "tx_position": tx_position,
        "rx_position": rx_position,
        "target_position": target_position,
        "current_reference_yaw_deg": current_reference_yaw_deg,
        "measurement_angle_deg": _qub_measurement_angle_deg(rx_position, ris_position, current_reference_yaw_deg),
        "turntable_angle_deg": float(turntable_angle_deg),
        "target_angle_deg": float(target_angle_deg),
        "frequency_ghz": float(frequency_ghz),
        "polarization": str(polarization).strip().upper(),
    }
    return cfg, sample_config_path, metadata


def _write_qub_measurements_csv(path: Path, cases: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "case_id",
        "target_angle_deg",
        "frequency_ghz",
        "polarization",
        "measurement_angle_deg",
        "turntable_angle_deg",
        "run_id",
        "status",
        "position_x_m",
        "position_y_m",
        "position_z_m",
        "total_path_gain_db",
        "rx_power_dbm_estimate",
        "ris_path_gain_db",
        "non_ris_path_gain_db",
        "ris_off_total_path_gain_db",
        "ris_off_rx_power_dbm_estimate",
        "ris_delta_total_path_gain_db",
        "ris_delta_rx_power_dbm_estimate",
        "num_valid_paths",
        "num_ris_paths",
        "radio_map_path_gain_db_max",
        "radio_map_rx_power_dbm_max",
        "ris_off_radio_map_path_gain_db_max",
        "ris_off_radio_map_rx_power_dbm_max",
        "radio_map_delta_path_gain_db_max",
        "radio_map_delta_rx_power_dbm_max",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for case in cases:
            samples = case.get("samples", [])
            if not isinstance(samples, list):
                continue
            for row in samples:
                writer.writerow({key: row.get(key) for key in fieldnames})


def _write_qub_outputs(
    output_dir: Path,
    config: Dict[str, Any],
    completed_cases: List[Dict[str, Any]],
    requested_case_ids: List[str],
    *,
    chunk_processed: int,
) -> None:
    plots_dir = output_dir / "plots"
    data_dir = output_dir / "data"
    plots_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    campaign_cfg = config.get("campaign", {})
    if not isinstance(campaign_cfg, dict):
        campaign_cfg = {}
    show_specular_path = bool(campaign_cfg.get("show_specular_path", True))
    specular_measurement_angle_deg = (
        _qub_specular_measurement_angle_deg(campaign_cfg) if show_specular_path else None
    )

    ordered_cases = sorted(
        completed_cases,
        key=lambda item: (
            str(item.get("polarization", "")),
            float(item.get("target_angle_deg", 0.0)),
            float(item.get("frequency_ghz", 0.0)),
        ),
    )
    ordered_cases = [_enrich_qub_case_samples_from_summaries(output_dir, case) for case in ordered_cases]
    ordered_cases = [
        {
            **case,
            **_qub_case_metric_summary(case, campaign_cfg),
        }
        for case in ordered_cases
    ]
    save_json(data_dir / "campaign_measurements.json", {"cases": ordered_cases})
    _write_qub_measurements_csv(data_dir / "campaign_measurements.csv", ordered_cases)

    plot_manifest: List[Dict[str, Any]] = []
    peak_series_by_pol: Dict[str, List[Dict[str, Any]]] = {}

    for case in ordered_cases:
        samples = case.get("samples", [])
        if not isinstance(samples, list) or not samples:
            continue
        on_key, off_key, ylabel, on_label, off_label = _qub_cut_series_keys(samples)
        measurement_angles, on_values = _measurement_series_from_samples(samples, on_key)
        _, off_values = _measurement_series_from_samples(samples, off_key)
        if measurement_angles.size == 0:
            continue
        target_angle_deg = float(case.get("target_angle_deg", 0.0))
        frequency_ghz = float(case.get("frequency_ghz", 0.0))
        polarization = str(case.get("polarization", "V")).upper()
        specular_turntable_angle_deg = (
            _qub_specular_turntable_angle_deg(target_angle_deg, campaign_cfg) if show_specular_path else None
        )
        delta_values = on_values.copy() if on_key == "ris_delta_total_path_gain_db" else on_values - off_values
        delta_file = "__".join(
            [
                "qub_boost",
                f"target_{_format_angle_token(target_angle_deg)}deg",
                _format_frequency_token(frequency_ghz),
                f"{_safe_slug(polarization)}pol",
            ]
        ) + ".png"
        _plot_qub_delta(
            plots_dir / delta_file,
            measurement_angles,
            delta_values,
            title=f"QUB RIS boost · {frequency_ghz:g} GHz · {polarization} · target {target_angle_deg:g} deg",
            specular_angle_deg=specular_measurement_angle_deg,
        )
        plot_manifest.append(
            {
                "file": delta_file,
                "label": f"{frequency_ghz:g} GHz · {polarization} · target {target_angle_deg:g} deg · boost",
                "metric": (
                    "ris_delta_total_path_gain_db"
                    if on_key == "ris_delta_total_path_gain_db"
                    else f"{on_key}_minus_{off_key}"
                ),
                "show_specular_path": show_specular_path,
                "specular_measurement_angle_deg": specular_measurement_angle_deg,
                "specular_turntable_angle_deg": specular_turntable_angle_deg,
            }
        )
        plot_file = "__".join(
            [
                "qub_cut",
                f"target_{_format_angle_token(target_angle_deg)}deg",
                _format_frequency_token(frequency_ghz),
                f"{_safe_slug(polarization)}pol",
            ]
        ) + ".png"
        _plot_qub_cut(
            plots_dir / plot_file,
            measurement_angles,
            on_values,
            off_values,
            title=f"QUB angular cut · {frequency_ghz:g} GHz · {polarization} · target {target_angle_deg:g} deg",
            ylabel=ylabel,
            on_label=on_label,
            off_label=off_label,
            specular_angle_deg=specular_measurement_angle_deg,
            ris_target_angle_deg=target_angle_deg,
        )
        plot_manifest.append(
            {
                "file": plot_file,
                "label": f"{frequency_ghz:g} GHz · {polarization} · target {target_angle_deg:g} deg",
                "metric": on_key,
                "show_specular_path": show_specular_path,
                "specular_measurement_angle_deg": specular_measurement_angle_deg,
                "specular_turntable_angle_deg": specular_turntable_angle_deg,
                "ris_target_measurement_angle_deg": target_angle_deg,
            }
        )
        peak_series_by_pol.setdefault(polarization, [])

    for polarization in sorted({str(item.get("polarization", "V")).upper() for item in ordered_cases}):
        target_angles = sorted({float(item.get("target_angle_deg", 0.0)) for item in ordered_cases if str(item.get("polarization", "V")).upper() == polarization})
        freq_values = sorted({float(item.get("frequency_ghz", 0.0)) for item in ordered_cases if str(item.get("polarization", "V")).upper() == polarization})
        if not target_angles or not freq_values:
            continue
        aggregated_series: List[Dict[str, Any]] = []
        for target_angle_deg in target_angles:
            peaks: List[float] = []
            for frequency_ghz in freq_values:
                case = next(
                    (
                        item
                        for item in ordered_cases
                        if str(item.get("polarization", "V")).upper() == polarization
                        and abs(float(item.get("target_angle_deg", 0.0)) - target_angle_deg) < 1e-6
                        and abs(float(item.get("frequency_ghz", 0.0)) - frequency_ghz) < 1e-6
                    ),
                    None,
                )
                peaks.append(float(case.get("main_lobe_peak_db")) if isinstance(case, dict) and case.get("main_lobe_peak_db") is not None else np.nan)
            aggregated_series.append(
                {
                    "label": f"{target_angle_deg:g} deg",
                    "peak_values_db": peaks,
                }
            )
        plot_file = f"qub_peak_vs_frequency_{_safe_slug(polarization)}pol.png"
        _plot_qub_peak_vs_frequency(
            plots_dir / plot_file,
            np.array(freq_values, dtype=float),
            aggregated_series,
            title=f"QUB main-lobe peaks vs frequency · {polarization}",
        )
        plot_manifest.append(
            {
                "file": plot_file,
                "label": f"Peak vs frequency · {polarization}",
            }
        )

    for polarization in sorted({str(item.get("polarization", "V")).upper() for item in ordered_cases}):
        target_angles = sorted({float(item.get("target_angle_deg", 0.0)) for item in ordered_cases if str(item.get("polarization", "V")).upper() == polarization})
        freq_values = sorted({float(item.get("frequency_ghz", 0.0)) for item in ordered_cases if str(item.get("polarization", "V")).upper() == polarization})
        if not target_angles or not freq_values:
            continue
        for frequency_ghz in freq_values:
            peaks: List[float] = []
            off_peaks: List[float] = []
            for target_angle_deg in target_angles:
                case = next(
                    (
                        item
                        for item in ordered_cases
                        if str(item.get("polarization", "V")).upper() == polarization
                        and abs(float(item.get("target_angle_deg", 0.0)) - target_angle_deg) < 1e-6
                        and abs(float(item.get("frequency_ghz", 0.0)) - frequency_ghz) < 1e-6
                    ),
                    None,
                )
                peak = _case_peak_value(case, "main_lobe_rx_power_dbm", "rx_power_dbm_estimate") if isinstance(case, dict) else None
                off_peak = (
                    _case_peak_value(case, "ris_off_main_lobe_rx_power_dbm", "ris_off_rx_power_dbm_estimate")
                    if isinstance(case, dict)
                    else None
                )
                peaks.append(float(peak) if peak is not None else np.nan)
                off_peaks.append(float(off_peak) if off_peak is not None else np.nan)
            plot_file = "__".join(
                [
                    "qub_peak_rx_power_vs_target_angle",
                    _format_frequency_token(frequency_ghz),
                    f"{_safe_slug(polarization)}pol",
                ]
            ) + ".png"
            _plot_qub_peak_power_vs_target_angle(
                plots_dir / plot_file,
                np.array(target_angles, dtype=float),
                np.array(peaks, dtype=float),
                title=f"QUB peak Rx power vs target angle · {frequency_ghz:g} GHz · {polarization}",
                off_peak_power_dbm=np.array(off_peaks, dtype=float),
            )
            if (plots_dir / plot_file).exists():
                plot_manifest.append(
                    {
                        "file": plot_file,
                        "label": f"Peak Rx power vs target angle · {frequency_ghz:g} GHz · {polarization}",
                        "metric": "main_lobe_rx_power_dbm",
                        "reference_metric": "ris_off_main_lobe_rx_power_dbm",
                    }
                )

    save_json(data_dir / "campaign_plots.json", {"plots": plot_manifest})
    angle_radio_maps = _collect_qub_angle_radio_map_plots(plots_dir)
    save_json(data_dir / "campaign_angle_radio_maps.json", {"plots": angle_radio_maps})
    requested_count = len(requested_case_ids)
    completed_count = len(ordered_cases)
    remaining_count = max(0, requested_count - completed_count)
    metrics: Dict[str, Any] = {
        "requested_cases": requested_count,
        "completed_cases": completed_count,
        "remaining_cases": remaining_count,
        "chunk_processed_cases": int(chunk_processed),
        "mode": "qub_near_field",
        "angle_radio_map_plots": len(angle_radio_maps),
    }
    summary = {
        "schema_version": 1,
        "kind": "campaign",
        "campaign_complete": remaining_count == 0,
        "metrics": metrics,
        "campaign": config.get("campaign", {}),
    }
    save_json(output_dir / "summary.json", summary)


def _format_conductivity_tag(conductivity: float) -> str:
    return f"{conductivity:g}".replace("-", "m").replace(".", "p")


def _disable_ris_for_baseline(cfg: Dict[str, Any]) -> None:
    ris_cfg = cfg.setdefault("ris", {})
    ris_objects = ris_cfg.get("objects") if isinstance(ris_cfg.get("objects"), list) else []
    has_ris_objects = any(isinstance(obj_cfg, dict) for obj_cfg in ris_objects)
    cfg.setdefault("simulation", {})["ris"] = has_ris_objects
    radio_map_cfg = cfg.setdefault("radio_map", {})
    radio_map_cfg["ris"] = has_ris_objects
    radio_map_cfg["diff_ris"] = False
    ris_cfg["enabled"] = has_ris_objects
    if has_ris_objects:
        for obj_cfg in ris_objects:
            if not isinstance(obj_cfg, dict):
                continue
            obj_cfg["enabled"] = True
            profile_cfg = obj_cfg.setdefault("profile", {})
            if not isinstance(profile_cfg, dict):
                profile_cfg = {}
                obj_cfg["profile"] = profile_cfg
            profile_cfg["kind"] = "flat"
            profile_cfg["amplitude"] = 1.0
            profile_cfg["auto_aim"] = False


def _plot_absorber_sweep_angles(
    path: Path,
    series: List[Dict[str, Any]],
    *,
    key: str,
    title: str,
    ylabel: str,
) -> None:
    if not series:
        return
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    cmap = plt.get_cmap("viridis")
    plotted = False
    for idx, item in enumerate(series):
        angles, values = _measurement_series(item.get("measurements", []), key)
        finite = np.isfinite(values)
        if angles.size == 0 or not np.any(finite):
            continue
        color = cmap(idx / max(len(series) - 1, 1))
        conductivity = item.get("conductivity_s_per_m")
        ax.plot(
            angles[finite],
            values[finite],
            linewidth=1.8,
            marker="o",
            markersize=2.8,
            color=color,
            label=f"{conductivity:g} S/m",
        )
        plotted = True
    if not plotted:
        plt.close(fig)
        return
    ax.set_title(title)
    ax.set_xlabel("Measurement angle [deg]")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend(title="Absorber sigma")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_absorber_sweep_summary(
    path: Path,
    conductivities: np.ndarray,
    values: np.ndarray,
    *,
    title: str,
    ylabel: str,
    color: str,
) -> None:
    if conductivities.size == 0 or values.size == 0:
        return
    finite = np.isfinite(values)
    if not np.any(finite):
        return
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(conductivities[finite], values[finite], color=color, linewidth=2.0, marker="o", markersize=4.0)
    ax.set_title(title)
    ax.set_xlabel("Absorber conductivity [S/m]")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_outputs(
    output_dir: Path,
    config: Dict[str, Any],
    all_angles: List[float],
    measurements: List[Dict[str, Any]],
    *,
    chunk_processed: int,
) -> None:
    plots_dir = output_dir / "plots"
    data_dir = output_dir / "data"
    plots_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    ordered = sorted(measurements, key=lambda item: float(item.get("measurement_angle_deg", 0.0)))
    save_json(data_dir / "campaign_measurements.json", {"measurements": ordered})
    _write_measurements_csv(data_dir / "campaign_measurements.csv", ordered)

    completed = [item for item in ordered if item.get("status") == "completed"]
    completed_angles = np.array([float(item["measurement_angle_deg"]) for item in completed], dtype=float)
    rx_power = np.array(
        [float(item["rx_power_dbm_estimate"]) if item.get("rx_power_dbm_estimate") is not None else np.nan for item in completed],
        dtype=float,
    )
    path_gain = np.array(
        [float(item["total_path_gain_db"]) if item.get("total_path_gain_db") is not None else np.nan for item in completed],
        dtype=float,
    )
    ris_off_rx_power = np.array(
        [float(item["ris_off_rx_power_dbm_estimate"]) if item.get("ris_off_rx_power_dbm_estimate") is not None else np.nan for item in completed],
        dtype=float,
    )
    ris_off_path_gain = np.array(
        [float(item["ris_off_total_path_gain_db"]) if item.get("ris_off_total_path_gain_db") is not None else np.nan for item in completed],
        dtype=float,
    )
    ris_delta_rx_power = np.array(
        [float(item["ris_delta_rx_power_dbm_estimate"]) if item.get("ris_delta_rx_power_dbm_estimate") is not None else np.nan for item in completed],
        dtype=float,
    )
    ris_delta_path_gain = np.array(
        [float(item["ris_delta_total_path_gain_db"]) if item.get("ris_delta_total_path_gain_db") is not None else np.nan for item in completed],
        dtype=float,
    )

    _plot_series(
        plots_dir / "campaign_rx_power_dbm.png",
        completed_angles,
        rx_power,
        title="Campaign Rx Power",
        ylabel="Rx power estimate [dBm]",
        color="#005f73",
    )
    _plot_series(
        plots_dir / "campaign_path_gain_db.png",
        completed_angles,
        path_gain,
        title="Campaign Path Gain",
        ylabel="Path gain [dB]",
        color="#9b2226",
    )
    _plot_comparison_series(
        plots_dir / "campaign_rx_power_compare_dbm.png",
        completed_angles,
        rx_power,
        ris_off_rx_power,
        title="Campaign Rx Power (RIS on vs off)",
        ylabel="Rx power estimate [dBm]",
        primary_label="RIS on",
        secondary_label="RIS off",
        primary_color="#005f73",
        secondary_color="#ca6702",
    )
    _plot_comparison_series(
        plots_dir / "campaign_path_gain_compare_db.png",
        completed_angles,
        path_gain,
        ris_off_path_gain,
        title="Campaign Path Gain (RIS on vs off)",
        ylabel="Path gain [dB]",
        primary_label="RIS on",
        secondary_label="RIS off",
        primary_color="#9b2226",
        secondary_color="#ca6702",
    )
    _plot_series(
        plots_dir / "campaign_rx_power_delta_db.png",
        completed_angles,
        ris_delta_rx_power,
        title="Campaign Rx Power Delta (RIS on - off)",
        ylabel="Rx power delta [dB]",
        color="#0a9396",
    )
    _plot_series(
        plots_dir / "campaign_path_gain_delta_db.png",
        completed_angles,
        ris_delta_path_gain,
        title="Campaign Path Gain Delta (RIS on - off)",
        ylabel="Path gain delta [dB]",
        color="#bb3e03",
    )

    plot_manifest: List[Dict[str, Any]] = [
        {"file": "campaign_rx_power_dbm.png", "label": "Campaign Rx power"},
        {"file": "campaign_path_gain_db.png", "label": "Campaign path gain"},
        {"file": "campaign_rx_power_compare_dbm.png", "label": "Campaign Rx power (RIS on vs off)"},
        {"file": "campaign_path_gain_compare_db.png", "label": "Campaign path gain (RIS on vs off)"},
        {"file": "campaign_rx_power_delta_db.png", "label": "Campaign Rx power delta (RIS on - off)"},
        {"file": "campaign_path_gain_delta_db.png", "label": "Campaign path gain delta (RIS on - off)"},
    ]
    angle_radio_maps = _collect_angle_radio_map_plots(plots_dir)
    reference_measurement = _select_reference_measurement(ordered)
    plot_manifest.extend(_copy_reference_radio_map_plots(output_dir, plots_dir, reference_measurement))
    save_json(data_dir / "campaign_plots.json", {"plots": plot_manifest})
    save_json(data_dir / "campaign_angle_radio_maps.json", {"plots": angle_radio_maps})

    completed_count = len(completed)
    requested_count = len(all_angles)
    remaining_count = max(0, requested_count - completed_count)
    metrics: Dict[str, Any] = {
        "requested_angles": requested_count,
        "completed_angles": completed_count,
        "remaining_angles": remaining_count,
        "chunk_processed_angles": int(chunk_processed),
        "sweep_device": config.get("campaign", {}).get("sweep_device", "rx"),
        "radius_m": config.get("campaign", {}).get("radius_m"),
        "compact_output": bool(config.get("campaign", {}).get("compact_output", True)),
    }
    comparison_mask = (
        np.isfinite(ris_off_rx_power)
        | np.isfinite(ris_off_path_gain)
        | np.isfinite(ris_delta_rx_power)
        | np.isfinite(ris_delta_path_gain)
    )
    metrics["ris_off_probe_angles"] = int(np.count_nonzero(comparison_mask))
    metrics["angle_radio_map_plots"] = len(angle_radio_maps)

    rx_summary = _summarize_series(rx_power)
    if rx_summary is not None:
        metrics["rx_power_dbm_estimate"] = rx_summary
    path_gain_summary = _summarize_series(path_gain)
    if path_gain_summary is not None:
        metrics["total_path_gain_db"] = path_gain_summary
    ris_off_rx_summary = _summarize_series(ris_off_rx_power)
    if ris_off_rx_summary is not None:
        metrics["ris_off_rx_power_dbm_estimate"] = ris_off_rx_summary
    ris_off_gain_summary = _summarize_series(ris_off_path_gain)
    if ris_off_gain_summary is not None:
        metrics["ris_off_total_path_gain_db"] = ris_off_gain_summary
    ris_delta_rx_summary = _summarize_series(ris_delta_rx_power)
    if ris_delta_rx_summary is not None:
        metrics["ris_delta_rx_power_dbm_estimate"] = ris_delta_rx_summary
    ris_delta_gain_summary = _summarize_series(ris_delta_path_gain)
    if ris_delta_gain_summary is not None:
        metrics["ris_delta_total_path_gain_db"] = ris_delta_gain_summary

    summary = {
        "schema_version": 1,
        "kind": "campaign",
        "campaign_complete": remaining_count == 0,
        "metrics": metrics,
        "campaign": config.get("campaign", {}),
    }
    save_json(output_dir / "summary.json", summary)


def _disable_nonessential_campaign_radio_maps(cfg: Dict[str, Any], *, preserve_z_stack: bool = False) -> None:
    radio_map_cfg = cfg.setdefault("radio_map", {})
    if not isinstance(radio_map_cfg, dict):
        return
    z_stack_cfg = radio_map_cfg.get("z_stack")
    if preserve_z_stack:
        if not isinstance(z_stack_cfg, dict):
            radio_map_cfg["z_stack"] = {"enabled": False}
    elif isinstance(z_stack_cfg, dict):
        z_stack_cfg["enabled"] = False
    else:
        radio_map_cfg["z_stack"] = {"enabled": False}
    tx_ris_cfg = radio_map_cfg.get("tx_ris_incidence")
    if isinstance(tx_ris_cfg, dict):
        tx_ris_cfg["enabled"] = False
    else:
        radio_map_cfg["tx_ris_incidence"] = {"enabled": False}
    radio_map_cfg["diff_ris"] = False


def _build_angle_config(config: Dict[str, Any], campaign_cfg: Dict[str, Any], *, angle_deg: float, angle_index: int, angle_base_dir: Path) -> tuple[Dict[str, Any], Path, List[float]]:
    cfg = copy.deepcopy(config)
    cfg.pop("campaign", None)
    cfg["job"] = {"kind": "run", "scope": "indoor"}

    sweep_device = str(campaign_cfg.get("sweep_device", "rx")).strip().lower()
    if sweep_device not in {"tx", "rx"}:
        raise ValueError("campaign.sweep_device must be 'tx' or 'rx'")

    pivot = campaign_cfg.get("pivot", [0.0, 0.0, 1.5])
    if not isinstance(pivot, (list, tuple)) or len(pivot) < 3:
        raise ValueError("campaign.pivot must be [x, y, z]")
    radius_m = float(campaign_cfg.get("radius_m", 1.0))
    if radius_m <= 0.0:
        raise ValueError("campaign.radius_m must be > 0")
    reference_yaw_deg = _campaign_reference_yaw_deg(config, campaign_cfg)
    arc_z_m = _campaign_arc_z_m(pivot, campaign_cfg)
    position = _position_on_arc(pivot, radius_m, angle_deg, reference_yaw_deg, arc_z_m=arc_z_m)

    scene_cfg = cfg.setdefault("scene", {})
    device_cfg = scene_cfg.setdefault(sweep_device, {})
    device_cfg["position"] = position
    if sweep_device == "tx" and bool(campaign_cfg.get("tx_look_at_pivot", True)):
        device_cfg["look_at"] = [float(v) for v in pivot[:3]]
    if sweep_device == "rx" and bool(campaign_cfg.get("rx_look_at_pivot", True)):
        device_cfg["look_at"] = [float(v) for v in pivot[:3]]

    tx_cfg = scene_cfg.get("tx", {}) if isinstance(scene_cfg.get("tx"), dict) else {}
    rx_cfg = scene_cfg.get("rx", {}) if isinstance(scene_cfg.get("rx"), dict) else {}
    tx_position = tx_cfg.get("position") if isinstance(tx_cfg.get("position"), (list, tuple)) and len(tx_cfg.get("position", [])) >= 3 else None
    rx_position = rx_cfg.get("position") if isinstance(rx_cfg.get("position"), (list, tuple)) and len(rx_cfg.get("position", [])) >= 3 else None
    ris_cfg = cfg.get("ris", {}) if isinstance(cfg.get("ris"), dict) else {}
    ris_objects = ris_cfg.get("objects") if isinstance(ris_cfg.get("objects"), list) else []
    for obj_cfg in ris_objects:
        if not isinstance(obj_cfg, dict):
            continue
        profile_cfg = obj_cfg.get("profile")
        if not isinstance(profile_cfg, dict) or not profile_cfg.get("auto_aim"):
            continue
        if tx_position is not None:
            profile_cfg["sources"] = [float(v) for v in tx_position[:3]]
        if rx_position is not None:
            profile_cfg["targets"] = [float(v) for v in rx_position[:3]]

    compact_output = bool(campaign_cfg.get("compact_output", True))
    coarse_cell_size = campaign_cfg.get("coarse_cell_size_m")
    disable_render = bool(campaign_cfg.get("disable_render", compact_output))
    disable_ray_paths = bool(campaign_cfg.get("disable_ray_path_export", compact_output))
    disable_mesh_export = bool(campaign_cfg.get("disable_mesh_export", compact_output))

    if disable_render:
        cfg.setdefault("render", {})["enabled"] = False
    if disable_ray_paths:
        cfg.setdefault("visualization", {}).setdefault("ray_paths", {})["enabled"] = False
    if disable_mesh_export:
        cfg.setdefault("scene", {})["export_mesh"] = False

    if coarse_cell_size is not None:
        coarse_value = float(coarse_cell_size)
        if coarse_value <= 0.0:
            raise ValueError("campaign.coarse_cell_size_m must be > 0")
        cfg.setdefault("radio_map", {})["cell_size"] = [coarse_value, coarse_value]
    if compact_output:
        _disable_nonessential_campaign_radio_maps(cfg)

    angle_run_id = _angle_run_id(angle_index, angle_deg)
    cfg.setdefault("output", {})
    cfg["output"]["base_dir"] = str(angle_base_dir)
    cfg["output"]["run_id"] = angle_run_id

    angle_run_dir = create_output_dir(str(angle_base_dir), run_id=angle_run_id)
    angle_config_path = angle_run_dir / "job_config.yaml"
    save_yaml(angle_config_path, cfg)
    return cfg, angle_config_path, position


def _validate_qub_resume_state(state: Dict[str, Any], *, requested_case_ids: List[str], run_id: str) -> None:
    stored_case_ids = state.get("requested_case_ids", [])
    if isinstance(stored_case_ids, list) and stored_case_ids and [str(v) for v in stored_case_ids] != [str(v) for v in requested_case_ids]:
        raise ValueError(
            "Existing campaign state is incompatible with the current QUB campaign "
            f"configuration for run_id='{run_id}'. Start a new run or resume with a matching case set."
        )
    current_case_set = {str(case_id) for case_id in requested_case_ids}
    invalid_case_ids: List[str] = []
    cases = state.get("cases", [])
    if isinstance(cases, list):
        for row in cases:
            if not isinstance(row, dict):
                continue
            case_id = str(row.get("case_id") or "").strip()
            if case_id and case_id not in current_case_set:
                invalid_case_ids.append(case_id)
    if invalid_case_ids:
        preview = ", ".join(invalid_case_ids[:4])
        if len(invalid_case_ids) > 4:
            preview += ", ..."
        raise ValueError(
            "Existing campaign state contains QUB cases outside the current configuration "
            f"for run_id='{run_id}': {preview}"
        )


def _run_qub_near_field_campaign(config_path: str) -> Path:
    config = _load_yaml(Path(config_path))
    campaign_cfg = config.get("campaign", {})
    if not isinstance(campaign_cfg, dict):
        raise ValueError("campaign config section is required")

    turntable_angles = _angle_series(
        float(campaign_cfg.get("start_angle_deg", -90.0)),
        float(campaign_cfg.get("stop_angle_deg", 90.0)),
        float(campaign_cfg.get("step_deg", 2.0)),
    )
    target_angles = _qub_target_angles_deg(campaign_cfg)
    frequencies_ghz = _qub_frequency_series_ghz(config, campaign_cfg)
    polarizations = _qub_polarizations(config, campaign_cfg)
    requested_cases = [
        {
            "case_id": _qub_case_id(target_angle_deg, frequency_ghz, polarization),
            "target_angle_deg": float(target_angle_deg),
            "frequency_ghz": float(frequency_ghz),
            "polarization": str(polarization).upper(),
        }
        for polarization in polarizations
        for target_angle_deg in target_angles
        for frequency_ghz in frequencies_ghz
    ]
    requested_case_ids = [str(item["case_id"]) for item in requested_cases]

    output_cfg = config.setdefault("output", {})
    output_dir = create_output_dir(output_cfg.get("base_dir", "outputs"), run_id=output_cfg.get("run_id"))
    progress_path = output_dir / "progress.json"
    state_path = output_dir / "campaign_state.json"
    save_yaml(output_dir / "config.yaml", config)

    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        _validate_qub_resume_state(state, requested_case_ids=requested_case_ids, run_id=output_dir.name)
    else:
        state = {}

    completed_cases_map: Dict[str, Dict[str, Any]] = {}
    for row in state.get("cases", []) if isinstance(state.get("cases"), list) else []:
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or "").strip()
        if case_id:
            completed_cases_map[case_id] = row

    remaining_cases = [item for item in requested_cases if item["case_id"] not in completed_cases_map]
    max_cases_per_job = int(campaign_cfg.get("max_cases_per_job", campaign_cfg.get("max_angles_per_job", len(requested_cases))))
    if max_cases_per_job <= 0:
        raise ValueError("campaign.max_cases_per_job must be >= 1")
    chunk_cases = remaining_cases[:max_cases_per_job]

    if not chunk_cases:
        ordered_cases = sorted(completed_cases_map.values(), key=lambda item: str(item.get("case_id", "")))
        _write_qub_outputs(output_dir, config, ordered_cases, requested_case_ids, chunk_processed=0)
        _save_progress(progress_path, status="completed", completed=len(ordered_cases), total=len(requested_cases))
        return output_dir

    sample_base_dir = output_dir / "cases"
    sample_base_dir.mkdir(parents=True, exist_ok=True)
    _save_progress(progress_path, status="running", completed=len(completed_cases_map), total=len(requested_cases))

    try:
        for case in chunk_cases:
            case_id = str(case["case_id"])
            target_angle_deg = float(case["target_angle_deg"])
            frequency_ghz = float(case["frequency_ghz"])
            polarization = str(case["polarization"]).upper()
            case_sample_dir = sample_base_dir / case_id
            case_sample_dir.mkdir(parents=True, exist_ok=True)
            samples: List[Dict[str, Any]] = []

            _save_progress(
                progress_path,
                status="running",
                completed=len(completed_cases_map),
                total=len(requested_cases),
                current_angle_deg=target_angle_deg,
            )
            for sample_index, turntable_angle_deg in enumerate(turntable_angles):
                _, sample_config_path, metadata = _build_qub_turntable_config(
                    config,
                    campaign_cfg,
                    case_id=case_id,
                    target_angle_deg=target_angle_deg,
                    frequency_ghz=frequency_ghz,
                    polarization=polarization,
                    turntable_angle_deg=turntable_angle_deg,
                    sample_index=sample_index,
                    sample_base_dir=case_sample_dir,
                )
                sample_output_dir = run_simulation(str(sample_config_path))
                sample_summary = json.loads((sample_output_dir / "summary.json").read_text(encoding="utf-8"))
                sample_row = _extract_measurement(
                    sample_summary,
                    angle_deg=metadata["measurement_angle_deg"],
                    run_id=sample_output_dir.name,
                    position=metadata["rx_position"],
                    extras={
                        "case_id": case_id,
                        "target_angle_deg": target_angle_deg,
                        "frequency_ghz": frequency_ghz,
                        "polarization": polarization,
                        "turntable_angle_deg": turntable_angle_deg,
                    },
                )
                sample_row = _enrich_measurement_with_radio_map_point(sample_output_dir, sample_row, sample_summary)
                samples.append(sample_row)
                _copy_qub_sample_radio_map_plot(sample_output_dir, output_dir / "plots", sample_row)
                if bool(campaign_cfg.get("prune_angle_outputs", campaign_cfg.get("compact_output", True))):
                    _prune_angle_outputs(sample_output_dir)

            _prune_case_cache(case_sample_dir)

            case_record = {
                "case_id": case_id,
                "target_angle_deg": target_angle_deg,
                "frequency_ghz": frequency_ghz,
                "polarization": polarization,
                "show_specular_path": bool(campaign_cfg.get("show_specular_path", True)),
                "specular_measurement_angle_deg": _qub_specular_measurement_angle_deg(campaign_cfg),
                "specular_turntable_angle_deg": _qub_specular_turntable_angle_deg(target_angle_deg, campaign_cfg),
                "samples": samples,
            }
            case_record.update(_qub_case_metric_summary(case_record, campaign_cfg))
            completed_cases_map[case_id] = case_record
            ordered_cases = [completed_cases_map[key] for key in sorted(completed_cases_map)]
            save_json(
                state_path,
                {
                    "cases": ordered_cases,
                    "requested_case_ids": requested_case_ids,
                },
            )
            _write_qub_outputs(output_dir, config, ordered_cases, requested_case_ids, chunk_processed=len(chunk_cases))

        ordered_cases = [completed_cases_map[key] for key in sorted(completed_cases_map)]
        save_json(
            state_path,
            {
                "cases": ordered_cases,
                "requested_case_ids": requested_case_ids,
            },
        )
        _write_qub_outputs(output_dir, config, ordered_cases, requested_case_ids, chunk_processed=len(chunk_cases))
        _save_progress(
            progress_path,
            status="completed",
            completed=len(ordered_cases),
            total=len(requested_cases),
        )
        logger.info(
            "QUB campaign run_id=%s processed=%s/%s",
            output_dir.name,
            len(ordered_cases),
            len(requested_cases),
        )
        return output_dir
    except Exception as exc:
        _save_progress(
            progress_path,
            status="failed",
            completed=len(completed_cases_map),
            total=len(requested_cases),
            error=str(exc),
        )
        raise


def run_campaign(config_path: str) -> Path:
    config = _load_yaml(Path(config_path))
    campaign_cfg = config.get("campaign", {})
    if not isinstance(campaign_cfg, dict):
        raise ValueError("campaign config section is required")
    if _campaign_mode(campaign_cfg) == "qub_near_field":
        return _run_qub_near_field_campaign(config_path)

    all_angles = _angle_series(
        float(campaign_cfg.get("start_angle_deg", -90.0)),
        float(campaign_cfg.get("stop_angle_deg", 90.0)),
        float(campaign_cfg.get("step_deg", 2.0)),
    )

    output_cfg = config.setdefault("output", {})
    output_dir = create_output_dir(output_cfg.get("base_dir", "outputs"), run_id=output_cfg.get("run_id"))
    progress_path = output_dir / "progress.json"
    state_path = output_dir / "campaign_state.json"
    save_yaml(output_dir / "config.yaml", config)

    state: Dict[str, Any]
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        _validate_resume_state(state, all_angles=all_angles, run_id=output_dir.name)
    else:
        state = {}
    measurements_map: Dict[float, Dict[str, Any]] = {}
    for row in state.get("measurements", []) if isinstance(state.get("measurements"), list) else []:
        try:
            measurements_map[float(row["measurement_angle_deg"])] = row
        except Exception:
            continue
    remaining_angles = [angle for angle in all_angles if angle not in measurements_map]
    max_angles_per_job = int(campaign_cfg.get("max_angles_per_job", len(all_angles)))
    if max_angles_per_job <= 0:
        raise ValueError("campaign.max_angles_per_job must be >= 1")
    chunk_angles = remaining_angles[:max_angles_per_job]

    if not chunk_angles:
        ordered = sorted(measurements_map.values(), key=lambda item: float(item.get("measurement_angle_deg", 0.0)))
        _write_outputs(output_dir, config, all_angles, ordered, chunk_processed=0)
        _save_progress(progress_path, status="completed", completed=len(ordered), total=len(all_angles))
        return output_dir

    angle_base_dir = output_dir / "angles"
    angle_base_dir.mkdir(parents=True, exist_ok=True)
    completed_before = len(measurements_map)
    _save_progress(progress_path, status="running", completed=completed_before, total=len(all_angles))

    try:
        for angle_deg in chunk_angles:
            angle_index = all_angles.index(angle_deg)
            _, angle_config_path, position = _build_angle_config(
                config,
                campaign_cfg,
                angle_deg=angle_deg,
                angle_index=angle_index,
                angle_base_dir=angle_base_dir,
            )
            _save_progress(
                progress_path,
                status="running",
                completed=len(measurements_map),
                total=len(all_angles),
                current_angle_deg=angle_deg,
            )
            angle_output_dir = run_simulation(str(angle_config_path))
            angle_summary = json.loads((angle_output_dir / "summary.json").read_text(encoding="utf-8"))
            measurement = _extract_measurement(
                angle_summary,
                angle_deg=angle_deg,
                run_id=angle_output_dir.name,
                position=position,
            )
            measurements_map[float(angle_deg)] = measurement
            _copy_angle_radio_map_plot(output_dir, output_dir / "plots", measurement)
            if bool(campaign_cfg.get("prune_angle_outputs", campaign_cfg.get("compact_output", True))):
                _prune_angle_outputs(angle_output_dir)

            ordered = sorted(measurements_map.values(), key=lambda item: float(item.get("measurement_angle_deg", 0.0)))
            state = {
                "measurements": ordered,
                "all_angles_deg": all_angles,
            }
            save_json(state_path, state)
            _write_outputs(output_dir, config, all_angles, ordered, chunk_processed=len(chunk_angles))

        ordered = sorted(measurements_map.values(), key=lambda item: float(item.get("measurement_angle_deg", 0.0)))
        save_json(state_path, {"measurements": ordered, "all_angles_deg": all_angles})
        _write_outputs(output_dir, config, all_angles, ordered, chunk_processed=len(chunk_angles))
        _save_progress(
            progress_path,
            status="completed",
            completed=len(ordered),
            total=len(all_angles),
        )
        logger.info(
            "Campaign run_id=%s processed=%s/%s",
            output_dir.name,
            len(ordered),
            len(all_angles),
        )
        return output_dir
    except Exception as exc:
        ordered = sorted(measurements_map.values(), key=lambda item: float(item.get("measurement_angle_deg", 0.0)))
        save_json(state_path, {"measurements": ordered, "all_angles_deg": all_angles})
        _write_outputs(output_dir, config, all_angles, ordered, chunk_processed=len(chunk_angles))
        _save_progress(
            progress_path,
            status="failed",
            completed=len(ordered),
            total=len(all_angles),
            error=str(exc),
        )
        logger.exception("Campaign execution failed")
        raise


def run_absorber_sweep(config_path: str, conductivities: List[float]) -> Path:
    if not conductivities:
        raise ValueError("Provide at least one absorber conductivity value")

    base_config = _load_yaml(Path(config_path))
    if not isinstance(base_config.get("campaign"), dict):
        raise ValueError("campaign config section is required")

    normalized_conductivities = [float(value) for value in conductivities]
    output_cfg = base_config.setdefault("output", {})
    base_dir = output_cfg.get("base_dir", "outputs")
    requested_run_id = output_cfg.get("run_id")
    sweep_run_id = f"{requested_run_id}_absorber_sweep" if requested_run_id else None
    output_dir = create_output_dir(base_dir, run_id=sweep_run_id)
    save_yaml(output_dir / "config.yaml", base_config)

    variants_dir = output_dir / "variants"
    configs_dir = output_dir / "variant_configs"
    data_dir = output_dir / "data"
    plots_dir = output_dir / "plots"
    variants_dir.mkdir(parents=True, exist_ok=True)
    configs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    aggregate_rows: List[Dict[str, Any]] = []
    plot_series: List[Dict[str, Any]] = []
    all_errors: List[str] = []

    for conductivity in normalized_conductivities:
        variant_cfg = copy.deepcopy(base_config)
        variant_cfg.setdefault("scene", {}).setdefault("custom_radio_materials", {})
        variant_cfg["scene"]["custom_radio_materials"].setdefault("itu_absorber", {})
        variant_cfg["scene"]["custom_radio_materials"]["itu_absorber"]["conductivity"] = conductivity
        _disable_ris_for_baseline(variant_cfg)

        variant_tag = _format_conductivity_tag(conductivity)
        variant_run_id = f"sigma_{variant_tag}"
        variant_cfg.setdefault("output", {})
        variant_cfg["output"]["base_dir"] = str(variants_dir)
        variant_cfg["output"]["run_id"] = variant_run_id

        variant_config_path = configs_dir / f"{variant_run_id}.yaml"
        save_yaml(variant_config_path, variant_cfg)

        variant_output_dir = run_campaign(str(variant_config_path))
        summary = json.loads((variant_output_dir / "summary.json").read_text(encoding="utf-8"))
        measurements_payload = json.loads(
            (variant_output_dir / "data" / "campaign_measurements.json").read_text(encoding="utf-8")
        )
        measurements = measurements_payload.get("measurements", []) if isinstance(measurements_payload, dict) else []
        completed_measurements = [
            item for item in measurements if isinstance(item, dict) and item.get("status") == "completed"
        ]
        errors = [str(item.get("error")) for item in measurements if isinstance(item, dict) and item.get("error")]
        all_errors.extend(errors)

        _, path_gain = _measurement_series(completed_measurements, "total_path_gain_db")
        _, rx_power = _measurement_series(completed_measurements, "rx_power_dbm_estimate")
        path_gain_summary = _summarize_series(path_gain)
        rx_power_summary = _summarize_series(rx_power)

        row = {
            "conductivity_s_per_m": conductivity,
            "run_id": variant_output_dir.name,
            "completed_angles": len(completed_measurements),
            "requested_angles": summary.get("metrics", {}).get("requested_angles"),
            "mean_path_gain_db": path_gain_summary["mean"] if path_gain_summary is not None else None,
            "mean_rx_power_dbm": rx_power_summary["mean"] if rx_power_summary is not None else None,
            "min_path_gain_db": path_gain_summary["min"] if path_gain_summary is not None else None,
            "max_path_gain_db": path_gain_summary["max"] if path_gain_summary is not None else None,
            "campaign_complete": bool(summary.get("campaign_complete", False)),
            "error_count": len(errors),
        }
        aggregate_rows.append(row)
        plot_series.append(
            {
                "conductivity_s_per_m": conductivity,
                "run_id": variant_output_dir.name,
                "measurements": completed_measurements,
            }
        )

    aggregate_rows.sort(key=lambda item: float(item["conductivity_s_per_m"]))
    plot_series.sort(key=lambda item: float(item["conductivity_s_per_m"]))

    summary_fieldnames = [
        "conductivity_s_per_m",
        "run_id",
        "completed_angles",
        "requested_angles",
        "mean_path_gain_db",
        "mean_rx_power_dbm",
        "min_path_gain_db",
        "max_path_gain_db",
        "campaign_complete",
        "error_count",
    ]
    with (data_dir / "absorber_sweep_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fieldnames)
        writer.writeheader()
        for row in aggregate_rows:
            writer.writerow(row)

    conductivities_arr = np.array([float(item["conductivity_s_per_m"]) for item in aggregate_rows], dtype=float)
    mean_path_gain_arr = np.array(
        [float(item["mean_path_gain_db"]) if item.get("mean_path_gain_db") is not None else np.nan for item in aggregate_rows],
        dtype=float,
    )
    mean_rx_power_arr = np.array(
        [float(item["mean_rx_power_dbm"]) if item.get("mean_rx_power_dbm") is not None else np.nan for item in aggregate_rows],
        dtype=float,
    )

    _plot_absorber_sweep_angles(
        plots_dir / "absorber_sweep_path_gain_by_angle.png",
        plot_series,
        key="total_path_gain_db",
        title="RIS-off chamber baseline by absorber conductivity",
        ylabel="Path gain [dB]",
    )
    _plot_absorber_sweep_angles(
        plots_dir / "absorber_sweep_rx_power_by_angle.png",
        plot_series,
        key="rx_power_dbm_estimate",
        title="RIS-off chamber Rx power by absorber conductivity",
        ylabel="Rx power estimate [dBm]",
    )
    _plot_absorber_sweep_summary(
        plots_dir / "absorber_sweep_mean_path_gain_vs_conductivity.png",
        conductivities_arr,
        mean_path_gain_arr,
        title="Mean RIS-off path gain vs absorber conductivity",
        ylabel="Mean path gain [dB]",
        color="#9b2226",
    )
    _plot_absorber_sweep_summary(
        plots_dir / "absorber_sweep_mean_rx_power_vs_conductivity.png",
        conductivities_arr,
        mean_rx_power_arr,
        title="Mean RIS-off Rx power vs absorber conductivity",
        ylabel="Mean Rx power [dBm]",
        color="#005f73",
    )

    recommended = None
    finite_idx = np.where(np.isfinite(mean_path_gain_arr))[0]
    if finite_idx.size:
        best_idx = int(finite_idx[np.argmin(mean_path_gain_arr[finite_idx])])
        recommended = aggregate_rows[best_idx]

    summary_payload: Dict[str, Any] = {
        "schema_version": 1,
        "kind": "campaign_absorber_sweep",
        "base_config": str(Path(config_path)),
        "ris_baseline_mode": "metal_plate",
        "variants": aggregate_rows,
        "recommended_conductivity_s_per_m": recommended.get("conductivity_s_per_m") if recommended else None,
        "recommended_run_id": recommended.get("run_id") if recommended else None,
        "selection_rule": "lowest mean RIS-off total path gain across completed campaign angles",
        "error_count": len(all_errors),
    }
    save_json(data_dir / "absorber_sweep_summary.json", summary_payload)
    save_json(output_dir / "summary.json", summary_payload)
    logger.info(
        "Absorber sweep complete: run_id=%s variants=%d recommended_sigma=%s",
        output_dir.name,
        len(aggregate_rows),
        summary_payload.get("recommended_conductivity_s_per_m"),
    )
    return output_dir
