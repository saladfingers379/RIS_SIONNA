"""RT-side RIS synthesis runner."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import logging
import math
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from app.config import load_config
from app.io import save_json, save_yaml
from app.radio_map_grid import align_center_to_anchor
from app.ris.rt_synthesis_artifacts import (
    write_cdf_plot,
    write_eval_artifacts,
    write_objective_trace,
    write_offset_sweep,
    write_phase_artifacts,
    write_summary,
    write_target_region_artifacts,
)
from app.ris.rt_synthesis_binarize import (
    greedy_flip_refine,
    project_1bit_offset_sweep,
    project_nbit_offset_sweep,
)
from app.ris.rt_synthesis_config import (
    load_ris_synthesis_config,
    resolve_and_snapshot_ris_synthesis_config,
    resolve_and_snapshot_ris_synthesis_quantization_config,
)
from app.ris.rt_synthesis_objective import (
    compute_roi_metrics,
    masked_mean_log_path_gain,
)
from app.ris.rt_synthesis_phase_manifold import (
    PANEL_BASIS_NAMES,
    ensure_finite_array,
    panel_coordinates_from_cell_positions,
    phase_field_diagnostics,
    quadratic_panel_basis,
    unwrap_panel_phase,
)
from app.ris.rt_synthesis_roi import (
    build_target_mask_from_cell_centers,
    boxes_to_overlay_polygons,
    coverage_plane_metadata_from_seed_cfg,
)
from app.scene import build_scene
from app.simulate import _rt_backend_from_variant
from app.utils.system import (
    collect_environment_info,
    configure_tensorflow_for_mitsuba_variant,
    configure_tensorflow_memory_growth,
    select_mitsuba_variant,
)
from app.utils.sionna_patches import reset_svd_cpu_fallback_flag, svd_cpu_fallback_used
from app.viewer import generate_viewer

logger = logging.getLogger(__name__)


def _to_numpy(value: Any) -> np.ndarray:
    try:
        return value.numpy()
    except AttributeError:
        return np.asarray(value)


def _assign_profile_values(profile: Any, values: Any) -> None:
    try:
        assign = getattr(profile.values, "assign", None)
        if callable(assign):
            assign(values)
            return
    except Exception:
        pass
    profile.values = values


def _load_seed_rt_config(config: dict) -> dict:
    seed_cfg = load_config(config["seed"]["config_path"]).data
    return copy.deepcopy(seed_cfg)


def _resolve_map_anchor(scene: Any, cfg_local: Dict[str, Any], ris_obj: Any) -> Optional[list[float]]:
    anchor_mode = str(cfg_local.get("cell_anchor", "auto")).strip().lower()
    if anchor_mode in {"none", "off", "disabled", "false"}:
        return None
    anchor_xyz = cfg_local.get("cell_anchor_point")
    if isinstance(anchor_xyz, (list, tuple)) and len(anchor_xyz) >= 3:
        return [float(anchor_xyz[0]), float(anchor_xyz[1]), float(anchor_xyz[2])]
    if anchor_mode in {"auto", "ris"} and ris_obj is not None:
        pos = _to_numpy(ris_obj.position).reshape(-1)
        return [float(pos[0]), float(pos[1]), float(pos[2])]
    try:
        tx = next(iter(scene.transmitters.values()))
        tx_pos = _to_numpy(tx.position).reshape(-1)
    except Exception:
        tx_pos = None
    if anchor_mode in {"auto", "tx"} and tx_pos is not None:
        return [float(tx_pos[0]), float(tx_pos[1]), float(tx_pos[2])]
    try:
        rx = next(iter(scene.receivers.values()))
        rx_pos = _to_numpy(rx.position).reshape(-1)
    except Exception:
        rx_pos = None
    if anchor_mode in {"auto", "rx"} and rx_pos is not None:
        return [float(rx_pos[0]), float(rx_pos[1]), float(rx_pos[2])]
    return None


def _resolve_seed_run_dir(config: Optional[dict]) -> Optional[Path]:
    if not isinstance(config, dict):
        return None
    seed_cfg = config.get("seed")
    if not isinstance(seed_cfg, dict):
        return None
    source_run_id = str(seed_cfg.get("source_run_id") or "").strip()
    if not source_run_id:
        return None
    config_path = str(seed_cfg.get("config_path") or "").strip()
    candidates: list[Path] = []
    if config_path:
        candidates.append(Path(config_path).expanduser().resolve().parent)
    candidates.append((Path("outputs") / source_run_id).resolve())
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _grid_step_from_cell_centers(cell_centers: np.ndarray, axis: int) -> Optional[float]:
    centers = _require_finite("seed run cell centers", cell_centers)
    if centers.ndim != 3 or centers.shape[-1] < 3:
        return None
    if axis == 1:
        if centers.shape[1] < 2:
            return None
        diffs = centers[:, 1:, :3] - centers[:, :-1, :3]
    else:
        if centers.shape[0] < 2:
            return None
        diffs = centers[1:, :, :3] - centers[:-1, :, :3]
    norms = np.linalg.norm(diffs, axis=-1)
    valid = norms[np.isfinite(norms) & (norms > 1.0e-9)]
    if valid.size == 0:
        return None
    return float(np.median(valid))


def _infer_fixed_plane_from_cell_centers(seed_cfg: dict, cell_centers: Any) -> dict:
    plane = coverage_plane_metadata_from_seed_cfg(seed_cfg)
    centers = _require_finite("seed run coverage-map cell centers", cell_centers)
    if centers.ndim != 3 or centers.shape[-1] < 3:
        raise ValueError("seed run coverage-map cell centers must be shaped [ny, nx, 3]")
    center = np.mean(centers.reshape(-1, centers.shape[-1]), axis=0)
    cell_x = _grid_step_from_cell_centers(centers, axis=1)
    cell_y = _grid_step_from_cell_centers(centers, axis=0)
    fallback_x = float(plane["cell_size"][0])
    fallback_y = float(plane["cell_size"][1])
    cell_x = cell_x if cell_x is not None else fallback_x
    cell_y = cell_y if cell_y is not None else fallback_y
    plane["center"] = [float(center[0]), float(center[1]), float(center[2])]
    plane["cell_size"] = [float(cell_x), float(cell_y)]
    plane["size"] = [
        float(centers.shape[1]) * float(cell_x),
        float(centers.shape[0]) * float(cell_y),
    ]
    return plane


def _load_seed_run_cell_centers(seed_run_dir: Path) -> Optional[np.ndarray]:
    npz_path = seed_run_dir / "data" / "radio_map.npz"
    if npz_path.exists():
        with np.load(npz_path) as payload:
            centers = payload.get("cell_centers")
        if centers is not None:
            return np.asarray(centers, dtype=float)
    viewer_json = seed_run_dir / "viewer" / "heatmap.json"
    if viewer_json.exists():
        try:
            payload = json.loads(viewer_json.read_text(encoding="utf-8"))
            centers = payload.get("cell_centers")
            if centers is not None:
                return np.asarray(centers, dtype=float)
        except Exception:
            return None
    return None


def _load_realized_fixed_plane(seed_cfg: dict, config: Optional[dict]) -> Optional[dict]:
    seed_run_dir = _resolve_seed_run_dir(config)
    if seed_run_dir is None:
        return None
    cell_centers = _load_seed_run_cell_centers(seed_run_dir)
    if cell_centers is None:
        return None
    plane = _infer_fixed_plane_from_cell_centers(seed_cfg, cell_centers)
    plane["source_run_dir"] = str(seed_run_dir)
    plane["derived_from"] = "seed_run_radio_map"
    return plane


def _apply_radio_map_autosize(seed_cfg: dict, plane: dict, scene: Any) -> dict:
    radio_cfg = seed_cfg.get("radio_map", {})
    if not isinstance(radio_cfg, dict) or not radio_cfg.get("auto_size", False):
        return plane
    try:
        bbox = scene.mi_scene.bbox()
        padding = float(radio_cfg.get("auto_padding", 0.0))
        size_x = float(bbox.max.x - bbox.min.x) + padding * 2.0
        size_y = float(bbox.max.y - bbox.min.y) + padding * 2.0
        cell_x = float(plane["cell_size"][0]) if plane["cell_size"][0] else 0.0
        cell_y = float(plane["cell_size"][1]) if plane["cell_size"][1] else 0.0
        if cell_x > 0.0:
            size_x = math.ceil(size_x / cell_x) * cell_x
        if cell_y > 0.0:
            size_y = math.ceil(size_y / cell_y) * cell_y
        center_z = float(plane["center"][2])
        plane = dict(plane)
        plane["size"] = [float(size_x), float(size_y)]
        plane["center"] = [
            float(bbox.min.x + bbox.max.x) * 0.5,
            float(bbox.min.y + bbox.max.y) * 0.5,
            center_z,
        ]
        plane["derived_from"] = "seed_config_auto_size"
    except Exception:
        return plane
    return plane


def _resolve_fixed_plane(seed_cfg: dict, scene: Any, ris_obj: Any, config: Optional[dict] = None) -> dict:
    realized_plane = _load_realized_fixed_plane(seed_cfg, config)
    if realized_plane is not None:
        anchor = _resolve_map_anchor(scene, realized_plane, ris_obj)
        return {
            "center": list(realized_plane["center"]),
            "size": list(realized_plane["size"]),
            "cell_size": list(realized_plane["cell_size"]),
            "orientation": list(realized_plane["orientation"]),
            "anchor": anchor,
            "alignment": {
                "applied": False,
                "source": realized_plane.get("derived_from", "seed_run_radio_map"),
            },
        }
    plane = coverage_plane_metadata_from_seed_cfg(seed_cfg)
    plane = _apply_radio_map_autosize(seed_cfg, plane, scene)
    center = list(plane["center"])
    anchor = _resolve_map_anchor(scene, plane, ris_obj)
    alignment = None
    if plane.get("align_grid_to_anchor", True) and anchor is not None:
        aligned_center, alignment = align_center_to_anchor(
            center,
            plane["size"],
            plane["cell_size"],
            anchor,
            inside_only=True,
        )
        if aligned_center is not None:
            center = aligned_center
    return {
        "center": center,
        "size": plane["size"],
        "cell_size": plane["cell_size"],
        "orientation": plane["orientation"],
        "anchor": anchor,
        "alignment": alignment,
    }


def _coverage_kwargs(seed_cfg: dict, plane: dict, *, ris_enabled: bool) -> dict:
    radio_cfg = seed_cfg.get("radio_map", {})
    if not isinstance(radio_cfg, dict) or not radio_cfg.get("enabled", False):
        raise ValueError("Seed RT config must enable radio_map for RIS synthesis")
    return {
        "cm_center": plane["center"],
        "cm_orientation": plane["orientation"],
        "cm_size": plane["size"],
        "cm_cell_size": plane["cell_size"],
        "num_samples": int(radio_cfg.get("samples_per_tx", 200000)),
        "max_depth": int(radio_cfg.get("max_depth", seed_cfg.get("simulation", {}).get("max_depth", 3))),
        "los": bool(radio_cfg.get("los", True)),
        "reflection": bool(radio_cfg.get("specular_reflection", True)),
        "diffraction": bool(radio_cfg.get("diffraction", False)),
        "scattering": bool(radio_cfg.get("diffuse_reflection", False)),
        "ris": bool(ris_enabled),
    }


def _result_to_arrays(result: Any, tx_power_dbm: float) -> dict:
    path_gain = _to_numpy(result.path_gain)
    cell_centers = _to_numpy(result.cell_centers)
    path_gain_linear = path_gain[0] if path_gain.ndim == 3 else path_gain
    path_gain_db = 10.0 * np.log10(path_gain_linear + 1.0e-12)
    rx_power_dbm = float(tx_power_dbm) + path_gain_db
    return {
        "path_gain_linear": path_gain_linear,
        "path_gain_db": path_gain_db,
        "rx_power_dbm": rx_power_dbm,
        "path_loss_db": -path_gain_db,
        "cell_centers": cell_centers,
    }


def _write_default_radio_map_artifacts(
    output_dir: Path,
    evaluation: dict,
    *,
    diff_vs_off: Optional[np.ndarray] = None,
) -> None:
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    path_gain_linear = _require_finite("viewer radio_map path gain", evaluation["path_gain_linear"])
    path_gain_db = _require_finite("viewer radio_map path gain dB", evaluation["path_gain_db"])
    rx_power_dbm = _require_finite("viewer radio_map rx power", evaluation["rx_power_dbm"])
    path_loss_db = _require_finite("viewer radio_map path loss", evaluation["path_loss_db"])
    cell_centers = _require_finite("viewer radio_map cell centers", evaluation["cell_centers"])

    np.savez_compressed(
        data_dir / "radio_map.npz",
        path_gain_linear=path_gain_linear,
        path_gain_db=path_gain_db,
        rx_power_dbm=rx_power_dbm,
        path_loss_db=path_loss_db,
        cell_centers=cell_centers,
    )

    flat_gain = path_gain_db.reshape(-1)
    flat_centers = cell_centers.reshape(-1, 3)
    csv_data = np.column_stack([flat_centers, flat_gain])
    np.savetxt(
        data_dir / "radio_map.csv",
        csv_data,
        delimiter=",",
        header="x,y,z,path_gain_db",
        comments="",
    )

    if diff_vs_off is not None:
        diff_arr = _require_finite("viewer radio_map diff", diff_vs_off)
        np.savez_compressed(
            data_dir / "radio_map_diff.npz",
            path_gain_db=diff_arr,
            cell_centers=cell_centers,
        )


def _build_viewer_seed_config(seed_cfg: dict, fixed_plane: dict) -> dict:
    viewer_cfg = copy.deepcopy(seed_cfg)
    radio_cfg = viewer_cfg.get("radio_map")
    if not isinstance(radio_cfg, dict):
        radio_cfg = {}
    viewer_cfg["radio_map"] = radio_cfg
    radio_cfg["enabled"] = True
    radio_cfg["center"] = list(fixed_plane["center"])
    radio_cfg["size"] = list(fixed_plane["size"])
    radio_cfg["cell_size"] = list(fixed_plane["cell_size"])
    radio_cfg["orientation"] = list(fixed_plane["orientation"])
    viewer_section = viewer_cfg.get("viewer")
    if not isinstance(viewer_section, dict):
        viewer_section = {}
    viewer_section["enabled"] = True
    viewer_cfg["viewer"] = viewer_section
    return viewer_cfg


def _try_generate_result_viewer(
    output_dir: Path,
    *,
    seed_cfg: dict,
    fixed_plane: dict,
    scene: Any,
    evaluation: dict,
    diff_vs_off: Optional[np.ndarray] = None,
) -> None:
    _write_default_radio_map_artifacts(output_dir, evaluation, diff_vs_off=diff_vs_off)
    viewer_cfg = _build_viewer_seed_config(seed_cfg, fixed_plane)
    try:
        generate_viewer(output_dir, viewer_cfg, scene=scene)
    except Exception as exc:  # pragma: no cover
        logger.warning("Target region illumination viewer generation failed: %s", exc)


def _coverage_map_bounds_from_cell_centers(cell_centers: Any) -> dict:
    centers = _require_finite("coverage-map cell centers", cell_centers)
    if centers.ndim != 3 or centers.shape[-1] < 2:
        raise ValueError("coverage-map cell centers must be shaped [ny, nx, 3]")
    uu = centers[..., 0]
    vv = centers[..., 1]
    return {
        "u_min_m": float(np.min(uu)),
        "u_max_m": float(np.max(uu)),
        "v_min_m": float(np.min(vv)),
        "v_max_m": float(np.max(vv)),
    }


def _evaluate_variant(
    scene: Any,
    kwargs: dict,
    tx_power_dbm: float,
    *,
    title: str,
) -> dict:
    result = scene.coverage_map(**kwargs)
    arrays = _result_to_arrays(result, tx_power_dbm)
    _require_finite(f"{title} path gain", arrays["path_gain_linear"])
    arrays["title"] = title
    return arrays


def _masked_mean_log_path_gain_tf(path_gain_linear: Any, mask: Any, eps: float) -> Any:
    import tensorflow as tf

    masked = tf.boolean_mask(path_gain_linear, mask)
    return tf.reduce_mean(tf.math.log(masked + tf.cast(eps, masked.dtype)))


def _wrap_phase_variable(phase_values: Any) -> Any:
    import tensorflow as tf

    tensor = tf.convert_to_tensor(phase_values)
    if not isinstance(phase_values, tf.Variable):
        phase_values = tf.Variable(tensor, trainable=True, name="ris_synthesis_phase")
    two_pi = tf.cast(2.0 * np.pi, phase_values.dtype)
    phase_values.assign(tf.math.floormod(phase_values, two_pi))
    return phase_values


def _require_finite(name: str, value: Any) -> np.ndarray:
    return ensure_finite_array(_to_numpy(value), name=name)


def _normalize_vector(value: Any, *, name: str) -> np.ndarray:
    vector = _require_finite(name, value).reshape(-1)
    if vector.size != 3:
        raise ValueError(f"{name} must be a 3-element vector")
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        raise ValueError(f"{name} must be non-zero")
    return vector / norm


def _direction_from_az_el_deg(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    azimuth_rad = np.deg2rad(float(azimuth_deg))
    elevation_rad = np.deg2rad(float(elevation_deg))
    return np.array(
        [
            np.cos(elevation_rad) * np.cos(azimuth_rad),
            np.cos(elevation_rad) * np.sin(azimuth_rad),
            np.sin(elevation_rad),
        ],
        dtype=float,
    )


def _direction_to_az_el_deg(direction: Any) -> tuple[float, float]:
    unit = _normalize_vector(direction, name="direction")
    azimuth_deg = float(np.degrees(np.arctan2(unit[1], unit[0])))
    elevation_deg = float(np.degrees(np.arctan2(unit[2], np.linalg.norm(unit[:2]))))
    return azimuth_deg, elevation_deg


def _search_axis(center_deg: float, span_deg: float, count: int) -> np.ndarray:
    samples = max(1, int(count))
    if samples == 1 or float(span_deg) <= 0.0:
        return np.array([float(center_deg)], dtype=float)
    half_span = 0.5 * float(span_deg)
    return np.linspace(float(center_deg) - half_span, float(center_deg) + half_span, samples, dtype=float)


def _scaled_coverage_kwargs(
    kwargs: dict,
    *,
    cell_scale: float,
    sample_scale: float,
) -> dict:
    scaled = dict(kwargs)
    cell_size = kwargs.get("cm_cell_size") or [1.0, 1.0]
    scaled["cm_cell_size"] = [
        max(float(cell_size[0]) * float(cell_scale), 1.0e-6),
        max(float(cell_size[1]) * float(cell_scale), 1.0e-6),
    ]
    scaled["num_samples"] = max(1, int(round(float(kwargs.get("num_samples", 1)) * float(sample_scale))))
    return scaled


def _estimate_search_evaluations(config: dict) -> int:
    search_cfg = config["search"]
    coarse = int(search_cfg["coarse_num_azimuth"]) * int(search_cfg["coarse_num_elevation"])
    refine = (
        int(search_cfg["refine_top_k"])
        * int(search_cfg["refine_num_azimuth"])
        * int(search_cfg["refine_num_elevation"])
    )
    final = int(search_cfg["refine_top_k"])
    return 1 + coarse + refine + final


def _estimate_optimization_evaluations(config: dict) -> int:
    if str(config["parameterization"]["kind"]) == "steering_search":
        return _estimate_search_evaluations(config)
    return int(config["optimizer"]["iterations"])


def _unwrap_phase_profile(phase_values: Any) -> np.ndarray:
    wrapped = _require_finite("phase profile", phase_values)
    if wrapped.ndim != 3:
        raise ValueError("Phase profile must be shaped [num_modes, num_rows, num_cols]")
    return np.stack([unwrap_panel_phase(mode) for mode in wrapped], axis=0)


def _best_mask_for_candidate_map(
    cell_centers: np.ndarray,
    boxes: list[dict],
    roi_centroid: np.ndarray,
) -> np.ndarray:
    mask = build_target_mask_from_cell_centers(cell_centers, boxes)
    if np.any(mask):
        return mask
    centers = _require_finite("candidate steering cell centers", cell_centers)
    centroid = _require_finite("ROI centroid", roi_centroid).reshape(1, 1, 3)
    distances = np.sum((centers - centroid) ** 2, axis=-1)
    fallback_mask = np.zeros(distances.shape, dtype=bool)
    fallback_mask.reshape(-1)[int(np.argmin(distances))] = True
    return fallback_mask


def _select_top_candidates(records: list[dict], limit: int) -> list[dict]:
    unique: list[dict] = []
    seen: set[tuple[float, float]] = set()
    for record in sorted(records, key=lambda item: float(item["objective"]), reverse=True):
        key = (round(float(record["azimuth_deg"]), 6), round(float(record["elevation_deg"]), 6))
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
        if len(unique) >= max(1, int(limit)):
            break
    return unique


def _evaluate_steering_candidate(
    scene: Any,
    ris_obj: Any,
    kwargs: dict,
    boxes: list[dict],
    objective_cfg: dict,
    source_position: np.ndarray,
    ris_position: np.ndarray,
    roi_centroid: np.ndarray,
    target_radius_m: float,
    *,
    azimuth_deg: float,
    elevation_deg: float,
    stage: str,
) -> dict:
    direction = _direction_from_az_el_deg(azimuth_deg, elevation_deg)
    target_point = ris_position + float(target_radius_m) * direction
    ris_obj.phase_gradient_reflector([source_position], [target_point])
    phase_wrapped = _require_finite("steering-search phase profile", ris_obj.phase_profile.values)
    eval_arrays = _evaluate_variant(scene, kwargs, 0.0, title=f"steering_{stage}")
    mask = _best_mask_for_candidate_map(eval_arrays["cell_centers"], boxes, roi_centroid)
    objective_value = masked_mean_log_path_gain(
        eval_arrays["path_gain_linear"],
        mask,
        float(objective_cfg["eps"]),
    )
    return {
        "stage": stage,
        "objective": float(objective_value),
        "azimuth_deg": float(azimuth_deg),
        "elevation_deg": float(elevation_deg),
        "target_point_xyz": [float(target_point[0]), float(target_point[1]), float(target_point[2])],
        "phase_wrapped": phase_wrapped,
    }


def _search_steering_phase(
    scene: Any,
    ris_obj: Any,
    kwargs: dict,
    mask: np.ndarray,
    cell_centers: np.ndarray,
    config: dict,
    progress_cb,
) -> dict:
    boxes = config["target_region"]["boxes"]
    objective_cfg = config["objective"]
    search_cfg = config["search"]
    ris_position = _require_finite("RIS position", ris_obj.position).reshape(-1)
    source_position = _require_finite(
        "transmitter position",
        next(iter(scene.transmitters.values())).position,
    ).reshape(-1)
    roi_points = _require_finite("ROI cell centers", cell_centers)[np.asarray(mask, dtype=bool)]
    if roi_points.size == 0:
        raise ValueError("Target ROI mask is empty on the full-resolution coverage map")
    roi_centroid = np.mean(roi_points, axis=0)
    base_direction = _normalize_vector(roi_centroid - ris_position, name="ROI steering direction")
    base_azimuth_deg, base_elevation_deg = _direction_to_az_el_deg(base_direction)
    target_radius_m = max(float(np.linalg.norm(roi_centroid - ris_position)), 1.0)
    total_evaluations = _estimate_search_evaluations(config)
    trace: list[dict] = []
    completed = 0

    seed_phase = _require_finite("seed steering phase", ris_obj.phase_profile.values)
    seed_unwrapped = _unwrap_phase_profile(seed_phase)
    seed_score = masked_mean_log_path_gain(
        _evaluate_variant(scene, kwargs, 0.0, title="seed_steering_baseline")["path_gain_linear"],
        mask,
        float(objective_cfg["eps"]),
    )
    seed_record = {
        "stage": "seed",
        "objective": float(seed_score),
        "azimuth_deg": base_azimuth_deg,
        "elevation_deg": base_elevation_deg,
        "target_point_xyz": [float(roi_centroid[0]), float(roi_centroid[1]), float(roi_centroid[2])],
    }
    trace.append({"iteration": completed, **seed_record})
    progress_cb(completed, total_evaluations, float(seed_score))
    completed += 1

    coarse_kwargs = _scaled_coverage_kwargs(
        kwargs,
        cell_scale=float(search_cfg["coarse_cell_scale"]),
        sample_scale=float(search_cfg["coarse_sample_scale"]),
    )
    refine_kwargs = _scaled_coverage_kwargs(
        kwargs,
        cell_scale=float(search_cfg["refine_cell_scale"]),
        sample_scale=float(search_cfg["refine_sample_scale"]),
    )

    def _run_stage(stage: str, kwargs_stage: dict, candidates: list[tuple[float, float]]) -> list[dict]:
        nonlocal completed
        records: list[dict] = []
        if not candidates:
            return records
        try:
            normal = _normalize_vector(getattr(ris_obj, "world_normal"), name="RIS world normal")
        except Exception:
            normal = None

        filtered: list[tuple[float, float]] = []
        for azimuth_deg, elevation_deg in candidates:
            direction = _direction_from_az_el_deg(azimuth_deg, elevation_deg)
            if normal is None or float(np.dot(direction, normal)) > 1.0e-6:
                filtered.append((float(azimuth_deg), float(elevation_deg)))
        if filtered:
            candidates = filtered

        for azimuth_deg, elevation_deg in candidates:
            record = _evaluate_steering_candidate(
                scene,
                ris_obj,
                kwargs_stage,
                boxes,
                objective_cfg,
                source_position,
                ris_position,
                roi_centroid,
                target_radius_m,
                azimuth_deg=azimuth_deg,
                elevation_deg=elevation_deg,
                stage=stage,
            )
            trace.append({"iteration": completed, **{k: v for k, v in record.items() if k != "phase_wrapped"}})
            progress_cb(completed, total_evaluations, float(record["objective"]))
            completed += 1
            records.append(record)
        return records

    coarse_azimuths = _search_axis(
        base_azimuth_deg,
        float(search_cfg["azimuth_span_deg"]),
        int(search_cfg["coarse_num_azimuth"]),
    )
    coarse_elevations = _search_axis(
        base_elevation_deg,
        float(search_cfg["elevation_span_deg"]),
        int(search_cfg["coarse_num_elevation"]),
    )
    coarse_candidates = [(float(azimuth), float(elevation)) for elevation in coarse_elevations for azimuth in coarse_azimuths]
    coarse_records = _run_stage("coarse", coarse_kwargs, coarse_candidates)
    if not coarse_records:
        raise ValueError("Steering search produced no valid coarse candidates")

    coarse_azimuth_step = (
        abs(float(coarse_azimuths[1] - coarse_azimuths[0])) if coarse_azimuths.size > 1 else max(float(search_cfg["azimuth_span_deg"]), 1.0)
    )
    coarse_elevation_step = (
        abs(float(coarse_elevations[1] - coarse_elevations[0])) if coarse_elevations.size > 1 else max(float(search_cfg["elevation_span_deg"]), 1.0)
    )
    shortlist = _select_top_candidates(coarse_records, int(search_cfg["refine_top_k"]))

    refine_candidates: list[tuple[float, float]] = []
    seen_candidates: set[tuple[float, float]] = set()
    for record in shortlist:
        azimuths = _search_axis(
            float(record["azimuth_deg"]),
            2.0 * coarse_azimuth_step,
            int(search_cfg["refine_num_azimuth"]),
        )
        elevations = _search_axis(
            float(record["elevation_deg"]),
            2.0 * coarse_elevation_step,
            int(search_cfg["refine_num_elevation"]),
        )
        for elevation in elevations:
            for azimuth in azimuths:
                key = (round(float(azimuth), 6), round(float(elevation), 6))
                if key in seen_candidates:
                    continue
                seen_candidates.add(key)
                refine_candidates.append((float(azimuth), float(elevation)))
    refine_records = _run_stage("refine", refine_kwargs, refine_candidates)
    final_shortlist = _select_top_candidates(
        refine_records or coarse_records,
        int(search_cfg["refine_top_k"]),
    )
    final_records = _run_stage(
        "final",
        kwargs,
        [(float(record["azimuth_deg"]), float(record["elevation_deg"])) for record in final_shortlist],
    )
    best_record = max(final_records + [seed_record], key=lambda item: float(item["objective"]))

    if best_record["stage"] == "seed":
        _assign_profile_values(ris_obj.phase_profile, seed_phase)
        phase_wrapped = seed_phase
        phase_unwrapped = seed_unwrapped
    else:
        best_direction = _direction_from_az_el_deg(
            float(best_record["azimuth_deg"]),
            float(best_record["elevation_deg"]),
        )
        best_target = ris_position + target_radius_m * best_direction
        ris_obj.phase_gradient_reflector([source_position], [best_target])
        phase_wrapped = _require_finite("best steering phase export", ris_obj.phase_profile.values)
        phase_unwrapped = _unwrap_phase_profile(phase_wrapped)

    diagnostics = phase_field_diagnostics(
        phase_wrapped,
        phase_unwrapped=phase_unwrapped,
    )
    return {
        "trace": trace,
        "phase_wrapped": phase_wrapped,
        "phase_unwrapped": phase_unwrapped,
        "diagnostics": diagnostics,
        "parameterization": {
            "kind": "steering_search",
            "search": copy.deepcopy(search_cfg),
            "base_direction": {
                "azimuth_deg": float(base_azimuth_deg),
                "elevation_deg": float(base_elevation_deg),
                "target_radius_m": float(target_radius_m),
            },
            "best_candidate": {
                "stage": str(best_record["stage"]),
                "azimuth_deg": float(best_record["azimuth_deg"]),
                "elevation_deg": float(best_record["elevation_deg"]),
                "objective": float(best_record["objective"]),
                "target_point_xyz": [float(v) for v in best_record["target_point_xyz"]],
            },
        },
        "optimizer": {
            "mode": "steering_search",
            "gradient_fallback_used": False,
            "fallback_reason": None,
            "num_evaluations": int(completed),
        },
    }


def _build_phase_parameterization(ris_obj: Any, config: dict) -> dict:
    import tensorflow as tf

    parameterization_cfg = config["parameterization"]
    kind = str(parameterization_cfg["kind"])
    phase_dtype = ris_obj.phase_profile.values.dtype
    if kind == "raw_phase":
        phase_values = _wrap_phase_variable(ris_obj.phase_profile.values)
        _require_finite("raw RIS phase variable", phase_values)
        _assign_profile_values(ris_obj.phase_profile, phase_values)
        return {
            "kind": kind,
            "variable": phase_values,
            "metadata": {"kind": kind},
        }

    if kind != "smooth_residual":
        raise ValueError(f"Unsupported RIS synthesis parameterization kind: {kind}")

    seed_phase = _require_finite("seed RIS phase profile", ris_obj.phase_profile.values)
    if seed_phase.ndim != 3:
        raise ValueError("RIS phase profile must be shaped [num_modes, num_rows, num_cols]")
    seed_unwrapped = np.stack([unwrap_panel_phase(mode) for mode in seed_phase], axis=0)
    coords = panel_coordinates_from_cell_positions(
        _to_numpy(ris_obj.cell_positions),
        num_rows=int(ris_obj.num_rows),
        num_cols=int(ris_obj.num_cols),
    )
    basis_stack = quadratic_panel_basis(coords["x"], coords["y"])
    coefficients = tf.Variable(
        tf.zeros((int(ris_obj.num_modes), basis_stack.shape[0]), dtype=phase_dtype),
        trainable=True,
        name="ris_synthesis_quadratic_coefficients",
    )
    return {
        "kind": kind,
        "variable": coefficients,
        "seed_unwrapped_tf": tf.convert_to_tensor(seed_unwrapped, dtype=phase_dtype),
        "basis_tf": tf.convert_to_tensor(basis_stack, dtype=phase_dtype),
        "two_pi": tf.cast(2.0 * np.pi, phase_dtype),
        "metadata": {
            "kind": kind,
            "basis": str(parameterization_cfg["basis"]),
            "basis_names": list(PANEL_BASIS_NAMES),
            "x_scale_m": float(coords["x_scale"]),
            "y_scale_m": float(coords["y_scale"]),
        },
    }


def _apply_phase_parameterization(ris_obj: Any, parameterization: dict) -> tuple[Any, Any]:
    import tensorflow as tf

    kind = parameterization["kind"]
    if kind == "raw_phase":
        phase_wrapped = tf.math.floormod(
            parameterization["variable"],
            tf.cast(2.0 * np.pi, parameterization["variable"].dtype),
        )
        _assign_profile_values(ris_obj.phase_profile, phase_wrapped)
        return phase_wrapped, phase_wrapped

    phase_unwrapped = parameterization["seed_unwrapped_tf"] + tf.einsum(
        "mb,bij->mij",
        parameterization["variable"],
        parameterization["basis_tf"],
    )
    phase_wrapped = tf.math.floormod(phase_unwrapped, parameterization["two_pi"])
    _assign_profile_values(ris_obj.phase_profile, phase_wrapped)
    return phase_wrapped, phase_unwrapped


def _evaluate_parameterized_objective(
    scene: Any,
    ris_obj: Any,
    kwargs: dict,
    mask_tf: Any,
    objective_cfg: dict,
    parameterization: dict,
) -> tuple[float, np.ndarray, np.ndarray]:
    phase_wrapped, phase_unwrapped = _apply_phase_parameterization(ris_obj, parameterization)
    phase_wrapped_np = _require_finite("continuous phase manifold", phase_wrapped)
    result = scene.coverage_map(**kwargs)
    path_gain = result.path_gain[0] if len(result.path_gain.shape) == 3 else result.path_gain
    objective = _masked_mean_log_path_gain_tf(
        path_gain,
        mask_tf,
        float(objective_cfg["eps"]),
    )
    objective_value = float(_require_finite("continuous optimization objective", objective).reshape(-1)[0])
    phase_unwrapped_np = _require_finite("continuous unwrapped phase manifold", phase_unwrapped)
    return objective_value, phase_wrapped_np, phase_unwrapped_np


def _optimize_continuous_phase_coordinate_search(
    scene: Any,
    ris_obj: Any,
    kwargs: dict,
    objective_cfg: dict,
    parameterization: dict,
    mask_tf: Any,
    *,
    iterations: int,
    log_every: int,
    learning_rate: float,
    progress_cb,
    trace_prefix: list[dict],
    start_iteration: int,
    current_objective: float,
    fallback_reason: str,
) -> dict:
    import tensorflow as tf

    logger.warning(
        "RIS synthesis switching to derivative-free coordinate search. Reason: %s",
        fallback_reason,
    )

    coeff_limit = float(2.0 * np.pi)
    min_step = max(float(learning_rate) * 0.05, 1.0e-3)
    coefficients = np.asarray(_to_numpy(parameterization["variable"]), dtype=float)
    step_sizes = np.full(coefficients.size, max(float(learning_rate), min_step), dtype=float)
    trace = list(trace_prefix)
    if not trace or int(trace[-1]["iteration"]) != int(start_iteration):
        trace.append({"iteration": int(start_iteration), "objective": float(current_objective)})
        if start_iteration == 0 or (start_iteration + 1) % log_every == 0 or (start_iteration + 1) == iterations:
            progress_cb(start_iteration, iterations, float(current_objective))

    current_wrapped = None
    current_unwrapped = None

    for iteration in range(start_iteration + 1, iterations):
        flat_index = iteration % coefficients.size
        step = float(step_sizes[flat_index])
        best_objective = float(current_objective)
        best_coefficients = np.array(coefficients, copy=True)
        best_wrapped = current_wrapped
        best_unwrapped = current_unwrapped

        for direction in (1.0, -1.0):
            candidate = np.array(coefficients, copy=True).reshape(-1)
            candidate[flat_index] = float(np.clip(candidate[flat_index] + direction * step, -coeff_limit, coeff_limit))
            candidate = candidate.reshape(coefficients.shape)
            parameterization["variable"].assign(tf.cast(candidate, parameterization["variable"].dtype))
            try:
                score, phase_wrapped_np, phase_unwrapped_np = _evaluate_parameterized_objective(
                    scene,
                    ris_obj,
                    kwargs,
                    mask_tf,
                    objective_cfg,
                    parameterization,
                )
            except ValueError:
                continue
            if score > best_objective:
                best_objective = float(score)
                best_coefficients = np.array(candidate, copy=True)
                best_wrapped = phase_wrapped_np
                best_unwrapped = phase_unwrapped_np

        improved = best_objective > float(current_objective)
        if improved:
            coefficients = best_coefficients
            current_objective = best_objective
            current_wrapped = best_wrapped
            current_unwrapped = best_unwrapped
            step_sizes[flat_index] = min(step * 1.25, coeff_limit)
        else:
            step_sizes[flat_index] = max(step * 0.5, min_step)

        parameterization["variable"].assign(tf.cast(coefficients, parameterization["variable"].dtype))
        if current_wrapped is None or current_unwrapped is None:
            current_objective, current_wrapped, current_unwrapped = _evaluate_parameterized_objective(
                scene,
                ris_obj,
                kwargs,
                mask_tf,
                objective_cfg,
                parameterization,
            )

        trace.append({"iteration": int(iteration), "objective": float(current_objective)})
        if iteration == 0 or (iteration + 1) % log_every == 0 or (iteration + 1) == iterations:
            progress_cb(iteration, iterations, float(current_objective))

    if current_wrapped is None or current_unwrapped is None:
        current_objective, current_wrapped, current_unwrapped = _evaluate_parameterized_objective(
            scene,
            ris_obj,
            kwargs,
            mask_tf,
            objective_cfg,
            parameterization,
        )

    return {
        "trace": trace,
        "phase_wrapped": current_wrapped,
        "phase_unwrapped": current_unwrapped,
        "optimizer": {
            "mode": "coordinate_search",
            "gradient_fallback_used": True,
            "fallback_reason": fallback_reason,
        },
    }


def _optimize_continuous_phase(
    scene: Any,
    ris_obj: Any,
    kwargs: dict,
    mask: np.ndarray,
    cell_centers: np.ndarray,
    config: dict,
    progress_cb,
) -> dict:
    import tensorflow as tf

    if str(config["parameterization"]["kind"]) == "steering_search":
        return _search_steering_phase(
            scene,
            ris_obj,
            kwargs,
            mask,
            cell_centers,
            config,
            progress_cb,
        )

    parameterization = _build_phase_parameterization(ris_obj, config)
    optimizer_cfg = config["optimizer"]
    objective_cfg = config["objective"]
    optimizer = tf.keras.optimizers.Adam(learning_rate=float(optimizer_cfg["learning_rate"]))
    mask_tf = tf.convert_to_tensor(np.asarray(mask, dtype=bool))
    trace = []
    iterations = int(optimizer_cfg["iterations"])
    log_every = int(optimizer_cfg["log_every"])

    for iteration in range(iterations):
        with tf.GradientTape() as tape:
            phase_wrapped, phase_unwrapped = _apply_phase_parameterization(ris_obj, parameterization)
            _require_finite("continuous phase manifold", phase_wrapped)
            result = scene.coverage_map(**kwargs)
            path_gain = result.path_gain[0] if len(result.path_gain.shape) == 3 else result.path_gain
            objective = _masked_mean_log_path_gain_tf(
                path_gain,
                mask_tf,
                float(objective_cfg["eps"]),
            )
            objective_value = float(_require_finite("continuous optimization objective", objective).reshape(-1)[0])
            loss = -objective
        gradient = tape.gradient(loss, parameterization["variable"])
        if gradient is None:
            raise RuntimeError("RIS synthesis optimizer produced no gradient for the active phase parameterization")
        try:
            _require_finite("continuous optimization gradient", gradient)
        except ValueError as exc:
            fallback = _optimize_continuous_phase_coordinate_search(
                scene,
                ris_obj,
                kwargs,
                objective_cfg,
                parameterization,
                mask_tf,
                iterations=iterations,
                log_every=log_every,
                learning_rate=float(optimizer_cfg["learning_rate"]),
                progress_cb=progress_cb,
                trace_prefix=trace,
                start_iteration=iteration,
                current_objective=objective_value,
                fallback_reason=str(exc),
            )
            phase_wrapped_np = _require_finite("optimized continuous phase export", fallback["phase_wrapped"])
            phase_unwrapped_np = _require_finite(
                "optimized continuous unwrapped phase export",
                fallback["phase_unwrapped"],
            )
            diagnostics = phase_field_diagnostics(
                phase_wrapped_np,
                phase_unwrapped=phase_unwrapped_np,
            )
            metadata = dict(parameterization["metadata"])
            if parameterization["kind"] == "smooth_residual":
                metadata["coefficients"] = np.asarray(_to_numpy(parameterization["variable"]), dtype=float).tolist()
            return {
                "trace": fallback["trace"],
                "phase_wrapped": phase_wrapped_np,
                "phase_unwrapped": phase_unwrapped_np,
                "diagnostics": diagnostics,
                "parameterization": metadata,
                "optimizer": fallback["optimizer"],
            }
        optimizer.apply_gradients([(gradient, parameterization["variable"])])
        if parameterization["kind"] == "raw_phase":
            parameterization["variable"].assign(
                tf.math.floormod(
                    parameterization["variable"],
                    tf.cast(2.0 * np.pi, parameterization["variable"].dtype),
                )
            )
        phase_wrapped, phase_unwrapped = _apply_phase_parameterization(ris_obj, parameterization)
        _require_finite("optimized continuous phase manifold", phase_wrapped)
        trace.append({"iteration": int(iteration), "objective": objective_value})
        if iteration == 0 or (iteration + 1) % log_every == 0 or (iteration + 1) == iterations:
            progress_cb(iteration, iterations, objective_value)
    phase_wrapped_np = _require_finite("optimized continuous phase export", phase_wrapped)
    phase_unwrapped_np = _require_finite("optimized continuous unwrapped phase export", phase_unwrapped)
    diagnostics = phase_field_diagnostics(
        phase_wrapped_np,
        phase_unwrapped=phase_unwrapped_np,
    )
    metadata = dict(parameterization["metadata"])
    if parameterization["kind"] == "smooth_residual":
        metadata["coefficients"] = np.asarray(_to_numpy(parameterization["variable"]), dtype=float).tolist()
    return {
        "trace": trace,
        "phase_wrapped": phase_wrapped_np,
        "phase_unwrapped": phase_unwrapped_np,
        "diagnostics": diagnostics,
        "parameterization": metadata,
        "optimizer": {
            "mode": "adam",
            "gradient_fallback_used": False,
            "fallback_reason": None,
        },
    }


def _project_to_1bit(
    scene: Any,
    ris_obj: Any,
    kwargs: dict,
    mask: np.ndarray,
    config: dict,
) -> dict:
    objective_cfg = config["objective"]
    current_phase = _require_finite("continuous phase before 1-bit projection", ris_obj.phase_profile.values)

    def _score_phase(candidate_phase: np.ndarray) -> float:
        import tensorflow as tf

        _require_finite("1-bit candidate phase", candidate_phase)
        _assign_profile_values(
            ris_obj.phase_profile,
            tf.cast(candidate_phase, ris_obj.phase_profile.values.dtype),
        )
        eval_arrays = _evaluate_variant(scene, kwargs, 0.0, title="candidate")
        return masked_mean_log_path_gain(
            eval_arrays["path_gain_linear"],
            mask,
            float(objective_cfg["eps"]),
        )

    result = project_1bit_offset_sweep(
        current_phase,
        _score_phase,
        int(config["binarization"]["num_offset_samples"]),
    )
    best_phase = np.asarray(result["best_phase"], dtype=float)
    if config["refinement"]["enabled"]:
        initial_bits = np.asarray(result["best_bits"], dtype=np.int8)

        def _score_bits(bits: np.ndarray) -> float:
            return _score_phase(np.asarray(bits, dtype=float) * np.pi)

        refined = greedy_flip_refine(
            initial_bits,
            _score_bits,
            int(config["refinement"]["candidate_budget"]),
            int(config["refinement"]["max_passes"]),
        )
        if float(refined["best_score"]) >= float(result["best_score"]):
            result["best_bits"] = np.asarray(refined["best_bits"], dtype=np.int8)
            result["best_phase"] = np.asarray(refined["best_phase"], dtype=float)
            result["best_score"] = float(refined["best_score"])
            result["refinement"] = refined["history"]
            best_phase = np.asarray(refined["best_phase"], dtype=float)
    import tensorflow as tf

    _assign_profile_values(
        ris_obj.phase_profile,
        tf.cast(best_phase, ris_obj.phase_profile.values.dtype),
    )
    return result


def _build_metrics(
    off_eval: dict,
    seed_eval: dict,
    continuous_eval: dict,
    one_bit_eval: Optional[dict],
    mask: np.ndarray,
    config: dict,
    projected: Optional[dict],
    trace: list[dict],
    optimizer_info: dict,
    parameterization: dict,
    phase_diagnostics: dict,
    refined_eval: Optional[dict] = None,
) -> dict:
    threshold_dbm = float(config["objective"]["threshold_dbm"])
    metrics = {
        "objective": {
            "kind": config["objective"]["kind"],
            "trace": trace,
            "continuous_final": float(trace[-1]["objective"]) if trace else None,
            "one_bit_best": float(projected["best_score"]) if projected is not None else None,
            "best_offset_rad": float(projected["best_offset_rad"]) if projected is not None else None,
        },
        "optimizer": optimizer_info,
        "parameterization": parameterization,
        "phase_diagnostics": phase_diagnostics,
        "target_region": {
            "num_masked_cells": int(np.count_nonzero(mask)),
            "boxes": config["target_region"]["boxes"],
        },
        "variants": {},
    }
    for key, evaluation in (
        ("ris_off", off_eval),
        ("seed", seed_eval),
        ("continuous", continuous_eval),
    ):
        variant_metrics = compute_roi_metrics(
            evaluation["path_gain_db"],
            evaluation["rx_power_dbm"],
            mask,
            threshold_dbm,
        )
        variant_metrics["roi_objective"] = masked_mean_log_path_gain(
            evaluation["path_gain_linear"],
            mask,
            float(config["objective"]["eps"]),
        )
        metrics["variants"][key] = variant_metrics
    if one_bit_eval is not None:
        variant_metrics = compute_roi_metrics(
            one_bit_eval["path_gain_db"],
            one_bit_eval["rx_power_dbm"],
            mask,
            threshold_dbm,
        )
        variant_metrics["roi_objective"] = masked_mean_log_path_gain(
            one_bit_eval["path_gain_linear"],
            mask,
            float(config["objective"]["eps"]),
        )
        metrics["variants"]["1bit"] = variant_metrics
    metrics["variants"]["seed"]["delta_mean_rx_power_dbm_vs_off"] = (
        metrics["variants"]["seed"]["mean_rx_power_dbm"]
        - metrics["variants"]["ris_off"]["mean_rx_power_dbm"]
    )
    metrics["variants"]["continuous"]["delta_mean_rx_power_dbm_vs_off"] = (
        metrics["variants"]["continuous"]["mean_rx_power_dbm"]
        - metrics["variants"]["ris_off"]["mean_rx_power_dbm"]
    )
    metrics["variants"]["continuous"]["delta_mean_rx_power_dbm_vs_seed"] = (
        metrics["variants"]["continuous"]["mean_rx_power_dbm"]
        - metrics["variants"]["seed"]["mean_rx_power_dbm"]
    )
    if one_bit_eval is not None:
        metrics["variants"]["1bit"]["delta_mean_rx_power_dbm_vs_off"] = (
            metrics["variants"]["1bit"]["mean_rx_power_dbm"]
            - metrics["variants"]["ris_off"]["mean_rx_power_dbm"]
        )
        metrics["variants"]["1bit"]["delta_mean_rx_power_dbm_vs_seed"] = (
            metrics["variants"]["1bit"]["mean_rx_power_dbm"]
            - metrics["variants"]["seed"]["mean_rx_power_dbm"]
        )
        metrics["variants"]["1bit"]["delta_mean_rx_power_dbm_vs_continuous"] = (
            metrics["variants"]["1bit"]["mean_rx_power_dbm"]
            - metrics["variants"]["continuous"]["mean_rx_power_dbm"]
        )
    if refined_eval is not None:
        metrics["variants"]["1bit_refined"] = compute_roi_metrics(
            refined_eval["path_gain_db"],
            refined_eval["rx_power_dbm"],
            mask,
            threshold_dbm,
        )
    return metrics


def _manual_profile_payload(phase_path: Path, amp_path: Path) -> dict:
    return {
        "kind": "manual",
        "manual_phase_values": str(phase_path),
        "manual_amp_values": str(amp_path),
    }


def _write_promoted_sionna_configs(
    output_dir: Path,
    seed_cfg: dict,
    ris_name: str,
    *,
    continuous_phase_path: Path,
    continuous_amp_path: Path,
    one_bit_phase_path: Optional[Path] = None,
    one_bit_amp_path: Optional[Path] = None,
    quantized_phase_path: Optional[Path] = None,
    quantized_amp_path: Optional[Path] = None,
) -> dict:
    ris_cfg = seed_cfg.get("ris", {})
    objects = ris_cfg.get("objects") if isinstance(ris_cfg, dict) else None
    if not isinstance(objects, list):
        return {}

    def _write_variant(tag: str, phase_path: Path, amp_path: Path) -> tuple[Path, Path] | None:
        promoted = copy.deepcopy(seed_cfg)
        promoted.pop("job", None)
        output_cfg = promoted.get("output")
        if isinstance(output_cfg, dict):
            output_cfg.pop("run_id", None)
        ris_objects = (((promoted.get("ris") or {}).get("objects")) if isinstance(promoted.get("ris"), dict) else None)
        if not isinstance(ris_objects, list):
            return None
        target_obj = next((item for item in ris_objects if isinstance(item, dict) and item.get("name") == ris_name), None)
        if target_obj is None:
            return None
        target_obj["profile"] = _manual_profile_payload(phase_path, amp_path)
        snippet_path = output_dir / f"ris_profile_{tag}.yaml"
        seed_config_path = output_dir / f"seed_config_{tag}.yaml"
        save_yaml(snippet_path, {"name": ris_name, "profile": copy.deepcopy(target_obj["profile"])})
        save_yaml(seed_config_path, promoted)
        return snippet_path, seed_config_path

    artifacts: dict[str, Any] = {}
    continuous_written = _write_variant("continuous", continuous_phase_path, continuous_amp_path)
    if continuous_written is not None:
        artifacts["continuous_profile_snippet_path"] = str(continuous_written[0].relative_to(output_dir))
        artifacts["continuous_seed_config_path"] = str(continuous_written[1].relative_to(output_dir))
    if one_bit_phase_path is not None and one_bit_amp_path is not None:
        one_bit_written = _write_variant("1bit", one_bit_phase_path, one_bit_amp_path)
        if one_bit_written is not None:
            artifacts["one_bit_profile_snippet_path"] = str(one_bit_written[0].relative_to(output_dir))
            artifacts["one_bit_seed_config_path"] = str(one_bit_written[1].relative_to(output_dir))
    if quantized_phase_path is not None and quantized_amp_path is not None:
        quantized_written = _write_variant("quantized", quantized_phase_path, quantized_amp_path)
        if quantized_written is not None:
            artifacts["quantized_profile_snippet_path"] = str(quantized_written[0].relative_to(output_dir))
            artifacts["quantized_seed_config_path"] = str(quantized_written[1].relative_to(output_dir))
    return artifacts


def _resolve_ris_synthesis_source_run_dir(config: dict) -> Path:
    source_cfg = config.get("source", {})
    run_dir = str(source_cfg.get("run_dir") or "").strip()
    if run_dir:
        path = Path(run_dir)
    else:
        run_id = str(source_cfg.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("RIS synthesis quantization requires source.run_id or source.run_dir")
        base_dir = str(config.get("output", {}).get("base_dir") or "outputs")
        path = Path(base_dir) / run_id
    if not path.exists():
        raise FileNotFoundError(f"RIS synthesis source run not found: {path}")
    return path


def _load_source_ris_synthesis_config(source_run_dir: Path) -> dict:
    config_path = source_run_dir / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"RIS synthesis source config not found: {config_path}")
    return load_ris_synthesis_config(config_path)


def _build_quantization_metrics(
    *,
    off_eval: dict,
    seed_eval: dict,
    continuous_eval: dict,
    quantized_eval: dict,
    mask: np.ndarray,
    source_config: dict,
    quantization_cfg: dict,
    projected: dict,
) -> dict:
    threshold_dbm = float(source_config["objective"]["threshold_dbm"])
    metrics = {
        "objective": {
            "kind": source_config["objective"]["kind"],
            "continuous_source": masked_mean_log_path_gain(
                continuous_eval["path_gain_linear"],
                mask,
                float(source_config["objective"]["eps"]),
            ),
            "quantized_best": float(projected["best_score"]),
            "best_offset_rad": float(projected["best_offset_rad"]),
        },
        "quantization": {
            "bits": int(quantization_cfg["bits"]),
            "levels": int(projected["levels"]),
            "method": str(quantization_cfg["method"]),
            "num_offset_samples": int(quantization_cfg["num_offset_samples"]),
        },
        "target_region": {
            "num_masked_cells": int(np.count_nonzero(mask)),
            "boxes": source_config["target_region"]["boxes"],
        },
        "variants": {},
    }
    for key, evaluation in (
        ("ris_off", off_eval),
        ("seed", seed_eval),
        ("continuous", continuous_eval),
        ("quantized", quantized_eval),
    ):
        variant_metrics = compute_roi_metrics(
            evaluation["path_gain_db"],
            evaluation["rx_power_dbm"],
            mask,
            threshold_dbm,
        )
        variant_metrics["roi_objective"] = masked_mean_log_path_gain(
            evaluation["path_gain_linear"],
            mask,
            float(source_config["objective"]["eps"]),
        )
        metrics["variants"][key] = variant_metrics
    metrics["variants"]["quantized"]["delta_mean_rx_power_dbm_vs_off"] = (
        metrics["variants"]["quantized"]["mean_rx_power_dbm"]
        - metrics["variants"]["ris_off"]["mean_rx_power_dbm"]
    )
    metrics["variants"]["quantized"]["delta_mean_rx_power_dbm_vs_seed"] = (
        metrics["variants"]["quantized"]["mean_rx_power_dbm"]
        - metrics["variants"]["seed"]["mean_rx_power_dbm"]
    )
    metrics["variants"]["quantized"]["delta_mean_rx_power_dbm_vs_continuous"] = (
        metrics["variants"]["quantized"]["mean_rx_power_dbm"]
        - metrics["variants"]["continuous"]["mean_rx_power_dbm"]
    )
    return metrics


def run_ris_synthesis_quantization(config_path: str) -> Path:
    config, output_dir, summary_seed = resolve_and_snapshot_ris_synthesis_quantization_config(config_path)
    progress_path = output_dir / "progress.json"
    log_path = output_dir / "run.log"
    log_stream = log_path.open("a", encoding="utf-8")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    source_run_dir = _resolve_ris_synthesis_source_run_dir(config)
    steps = ["Load source run", "Build scene", "Project to n-bit", "Evaluate", "Write outputs"]
    step_index = 0
    last_progress_payload: dict[str, Any] = {}

    def write_progress(step_index: int, status: str, **extra: Any) -> None:
        normalized_step = max(0, min(int(step_index), len(steps) - 1)) if steps else 0
        progress_value = min(normalized_step / max(len(steps), 1), 1.0)
        if status == "completed":
            progress_value = 1.0
        payload = {
            "status": status,
            "step_index": normalized_step,
            "step_name": steps[normalized_step] if steps else "Complete",
            "total_steps": len(steps),
            "progress": progress_value,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        payload.update(extra)
        last_progress_payload.clear()
        last_progress_payload.update(payload)
        save_json(progress_path, payload)

    run_start = time.time()
    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            write_progress(step_index, "running")
            source_synth_cfg = _load_source_ris_synthesis_config(source_run_dir)
            source_hash = hashlib.sha256(
                json.dumps(source_synth_cfg, sort_keys=True).encode("utf-8")
            ).hexdigest()
            continuous_phase = _require_finite(
                "source continuous phase",
                np.load(source_run_dir / "data" / "manual_profile_phase_continuous.npy"),
            )
            continuous_amp_path = source_run_dir / "data" / "manual_profile_amp_continuous.npy"
            continuous_amp = (
                _require_finite("source continuous amplitude", np.load(continuous_amp_path))
                if continuous_amp_path.exists()
                else None
            )

            step_index = 1
            write_progress(step_index, "running")
            seed_cfg = _load_seed_rt_config(source_synth_cfg)
            seed_hash = hashlib.sha256(json.dumps(seed_cfg, sort_keys=True).encode("utf-8")).hexdigest()
            runtime_cfg = seed_cfg.get("runtime", {})
            prefer_gpu = bool(runtime_cfg.get("prefer_gpu", True)) and not runtime_cfg.get("force_cpu")
            reset_svd_cpu_fallback_flag()
            variant = select_mitsuba_variant(
                prefer_gpu=prefer_gpu,
                forced_variant=str(runtime_cfg.get("mitsuba_variant", "auto")),
                require_cuda=bool(runtime_cfg.get("require_cuda", False)),
            )
            tf_device_info = configure_tensorflow_for_mitsuba_variant(variant)
            tf_info = configure_tensorflow_memory_growth(
                mode=str(runtime_cfg.get("tensorflow_import", "auto"))
            )
            if tf_device_info:
                tf_info.setdefault("device_policy", tf_device_info)
            scene = build_scene(seed_cfg, mitsuba_variant=variant)
            try:
                ris_obj = scene.ris[source_synth_cfg["seed"]["ris_name"]]
            except Exception as exc:
                raise ValueError(f"Seed scene does not contain RIS '{source_synth_cfg['seed']['ris_name']}'") from exc
            tx_device = next(iter(scene.transmitters.values()))
            tx_power_dbm = float(_to_numpy(tx_device.power_dbm).item())
            fixed_plane = _resolve_fixed_plane(seed_cfg, scene, ris_obj, source_synth_cfg)
            kwargs_on = _coverage_kwargs(seed_cfg, fixed_plane, ris_enabled=True)
            kwargs_off = _coverage_kwargs(seed_cfg, fixed_plane, ris_enabled=False)
            off_eval = _evaluate_variant(scene, kwargs_off, tx_power_dbm, title="RIS Off")
            mask = build_target_mask_from_cell_centers(
                off_eval["cell_centers"],
                source_synth_cfg["target_region"]["boxes"],
            )
            if not np.any(mask):
                bounds = _coverage_map_bounds_from_cell_centers(off_eval["cell_centers"])
                raise ValueError(
                    "Target ROI mask is empty on the frozen coverage-map grid. "
                    f"ROI boxes={source_synth_cfg['target_region']['boxes']} "
                    f"grid_bounds={bounds}"
                )
            seed_eval = _evaluate_variant(scene, kwargs_on, tx_power_dbm, title="Seed Continuous Sionna RIS")
            import tensorflow as tf

            _assign_profile_values(ris_obj.phase_profile, tf.cast(continuous_phase, ris_obj.phase_profile.values.dtype))
            if continuous_amp is not None:
                _assign_profile_values(ris_obj.amplitude_profile, tf.cast(continuous_amp, ris_obj.amplitude_profile.values.dtype))

            step_index = 2
            total_offsets = int(config["quantization"]["num_offset_samples"])
            write_progress(step_index, "running", current_iteration=0, total_iterations=total_offsets)
            evaluated_offsets = 0

            def _score_phase(candidate_phase: np.ndarray) -> float:
                nonlocal evaluated_offsets
                _require_finite("n-bit candidate phase", candidate_phase)
                _assign_profile_values(
                    ris_obj.phase_profile,
                    tf.cast(candidate_phase, ris_obj.phase_profile.values.dtype),
                )
                if continuous_amp is not None:
                    _assign_profile_values(
                        ris_obj.amplitude_profile,
                        tf.cast(continuous_amp, ris_obj.amplitude_profile.values.dtype),
                    )
                eval_arrays = _evaluate_variant(scene, kwargs_on, tx_power_dbm, title="quantized_candidate")
                evaluated_offsets += 1
                write_progress(
                    step_index,
                    "running",
                    current_iteration=evaluated_offsets,
                    total_iterations=total_offsets,
                    progress=min((step_index + evaluated_offsets / max(total_offsets, 1)) / len(steps), 0.95),
                )
                return masked_mean_log_path_gain(
                    eval_arrays["path_gain_linear"],
                    mask,
                    float(source_synth_cfg["objective"]["eps"]),
                )

            quant_bits = int(config["quantization"]["bits"])
            projected = project_nbit_offset_sweep(
                continuous_phase,
                _score_phase,
                total_offsets,
                quant_bits,
            )
            quantized_phase = _require_finite("quantized phase", projected["best_phase"])
            quantized_amp = continuous_amp if continuous_amp is not None else _require_finite(
                "quantized amplitude profile",
                ris_obj.amplitude_profile.values,
            )

            step_index = 3
            write_progress(step_index, "running")
            _assign_profile_values(ris_obj.phase_profile, tf.cast(continuous_phase, ris_obj.phase_profile.values.dtype))
            if continuous_amp is not None:
                _assign_profile_values(ris_obj.amplitude_profile, tf.cast(continuous_amp, ris_obj.amplitude_profile.values.dtype))
            continuous_eval = _evaluate_variant(scene, kwargs_on, tx_power_dbm, title="Source Continuous Sionna RIS")
            _assign_profile_values(ris_obj.phase_profile, tf.cast(quantized_phase, ris_obj.phase_profile.values.dtype))
            if continuous_amp is not None:
                _assign_profile_values(ris_obj.amplitude_profile, tf.cast(continuous_amp, ris_obj.amplitude_profile.values.dtype))
            quantized_eval = _evaluate_variant(scene, kwargs_on, tx_power_dbm, title=f"{quant_bits}-Bit Quantized RIS")

            step_index = 4
            write_progress(step_index, "running")
            continuous_unwrapped = _unwrap_phase_profile(continuous_phase)
            write_target_region_artifacts(
                output_dir,
                source_synth_cfg["target_region"]["boxes"],
                mask,
                off_eval["cell_centers"],
            )
            write_phase_artifacts(
                output_dir,
                continuous_phase,
                amp_continuous=continuous_amp,
                phase_continuous_unwrapped=continuous_unwrapped,
                phase_quantized=quantized_phase,
                amp_quantized=quantized_amp,
                quantized_bits=quant_bits,
            )
            write_offset_sweep(output_dir, projected["offset_sweep"])
            write_eval_artifacts(
                output_dir,
                key="ris_off",
                evaluation=off_eval,
                boxes=source_synth_cfg["target_region"]["boxes"],
            )
            write_eval_artifacts(
                output_dir,
                key="seed",
                evaluation=seed_eval,
                boxes=source_synth_cfg["target_region"]["boxes"],
                diff_vs_off=seed_eval["path_gain_db"] - off_eval["path_gain_db"],
            )
            write_eval_artifacts(
                output_dir,
                key="continuous",
                evaluation=continuous_eval,
                boxes=source_synth_cfg["target_region"]["boxes"],
                diff_vs_off=continuous_eval["path_gain_db"] - off_eval["path_gain_db"],
            )
            write_eval_artifacts(
                output_dir,
                key="quantized",
                evaluation=quantized_eval,
                boxes=source_synth_cfg["target_region"]["boxes"],
                diff_vs_off=quantized_eval["path_gain_db"] - off_eval["path_gain_db"],
                diff_vs_continuous=quantized_eval["path_gain_db"] - continuous_eval["path_gain_db"],
            )
            write_cdf_plot(
                output_dir,
                {
                    "RIS Off": off_eval["rx_power_dbm"][mask],
                    "Seed": seed_eval["rx_power_dbm"][mask],
                    "Continuous": continuous_eval["rx_power_dbm"][mask],
                    f"{quant_bits}-Bit": quantized_eval["rx_power_dbm"][mask],
                },
            )
            _try_generate_result_viewer(
                output_dir,
                seed_cfg=seed_cfg,
                fixed_plane=fixed_plane,
                scene=scene,
                evaluation=quantized_eval,
                diff_vs_off=quantized_eval["path_gain_db"] - off_eval["path_gain_db"],
            )
            promoted_artifacts = _write_promoted_sionna_configs(
                output_dir,
                seed_cfg,
                source_synth_cfg["seed"]["ris_name"],
                continuous_phase_path=output_dir / "data" / "manual_profile_phase_continuous.npy",
                continuous_amp_path=output_dir / "data" / "manual_profile_amp_continuous.npy",
                quantized_phase_path=output_dir / "data" / "manual_profile_phase_quantized.npy",
                quantized_amp_path=output_dir / "data" / "manual_profile_amp_quantized.npy",
            )
            metrics = _build_quantization_metrics(
                off_eval=off_eval,
                seed_eval=seed_eval,
                continuous_eval=continuous_eval,
                quantized_eval=quantized_eval,
                mask=mask,
                source_config=source_synth_cfg,
                quantization_cfg=config["quantization"],
                projected=projected,
            )
            plot_files = sorted(path.name for path in (output_dir / "plots").glob("*.png"))
            summary = {
                "schema_version": config.get("schema_version", 1),
                "run_id": output_dir.name,
                "action": "quantize",
                "source": {
                    "run_id": source_run_dir.name,
                    "run_dir": str(source_run_dir),
                    "config_hash_sha256": source_hash,
                },
                "seed": {
                    "config_path": source_synth_cfg["seed"]["config_path"],
                    "config_hash_sha256": seed_hash,
                    "ris_name": source_synth_cfg["seed"]["ris_name"],
                    "source_run_id": source_synth_cfg["seed"].get("source_run_id"),
                },
                "quantization": {
                    "bits": quant_bits,
                    "levels": int(projected["levels"]),
                    "method": str(config["quantization"]["method"]),
                    "best_offset_rad": float(projected["best_offset_rad"]),
                    "num_offset_samples": total_offsets,
                },
                "runtime": {
                    "mitsuba_variant": variant,
                    "rt_backend": _rt_backend_from_variant(variant),
                    "tensorflow": tf_info,
                    "ris_curvature_svd_cpu_fallback_used": svd_cpu_fallback_used(),
                    "timings_s": {
                        "total_s": time.time() - run_start,
                    },
                },
                "environment": collect_environment_info(),
                "target_region": {
                    "boxes": source_synth_cfg["target_region"]["boxes"],
                    "mask_shape": list(mask.shape),
                    "num_masked_cells": int(np.count_nonzero(mask)),
                    "plane": fixed_plane,
                    "overlay_polygons": boxes_to_overlay_polygons(source_synth_cfg["target_region"]["boxes"]),
                },
                "metrics": metrics,
                "config": {
                    "hash_sha256": summary_seed["config"]["hash_sha256"],
                    "path": str(output_dir / "config.yaml"),
                },
                "artifacts": {
                    "plot_files": plot_files,
                    "viewer_heatmap_array_path": "data/radio_map.npz",
                    "viewer_heatmap_diff_array_path": "data/radio_map_diff.npz",
                    "continuous_phase_array_path": "data/manual_profile_phase_continuous.npy",
                    "continuous_unwrapped_phase_array_path": "data/phase_continuous_unwrapped.npy",
                    "continuous_amp_array_path": "data/manual_profile_amp_continuous.npy",
                    "quantized_phase_array_path": "data/manual_profile_phase_quantized.npy",
                    "quantized_amp_array_path": "data/manual_profile_amp_quantized.npy",
                    "quantized_levels_array_path": "data/levels_quantized.npy",
                    **promoted_artifacts,
                },
            }
            write_summary(output_dir, summary, metrics)
            write_progress(len(steps) - 1, "completed")
            logger.info("RIS synthesis quantization complete: %s", output_dir)
            return output_dir
    except Exception as exc:
        logger.exception("RIS synthesis quantization failed")
        failure_payload = dict(last_progress_payload) if last_progress_payload else {}
        failure_payload.update(
            {
                "status": "failed",
                "step_index": max(0, min(int(step_index), len(steps) - 1)) if steps else 0,
                "step_name": steps[max(0, min(int(step_index), len(steps) - 1))] if steps else "Failed",
                "total_steps": len(steps),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "error": str(exc),
            }
        )
        if "progress" not in failure_payload:
            failure_payload["progress"] = min(
                max(0, min(int(step_index), len(steps) - 1)) / max(len(steps), 1),
                0.99,
            )
        save_json(progress_path, failure_payload)
        raise
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()
        log_stream.close()


def run_ris_synthesis(config_path: str) -> Path:
    config, output_dir, summary_seed = resolve_and_snapshot_ris_synthesis_config(config_path)
    progress_path = output_dir / "progress.json"
    log_path = output_dir / "run.log"
    log_stream = log_path.open("a", encoding="utf-8")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    binarization_enabled = bool(config.get("binarization", {}).get("enabled", True))
    steps = ["Load seed config", "Build scene", "Freeze ROI", "Optimize continuous"]
    if binarization_enabled:
        steps.append("Project to 1-bit")
    steps.extend(["Evaluate", "Write outputs"])
    step_index = 0
    last_progress_payload: dict[str, Any] = {}

    def write_progress(step_index: int, status: str, **extra: Any) -> None:
        normalized_step = max(0, min(int(step_index), len(steps) - 1)) if steps else 0
        progress_value = min(normalized_step / max(len(steps), 1), 1.0)
        if status == "completed":
            progress_value = 1.0
        payload = {
            "status": status,
            "step_index": normalized_step,
            "step_name": steps[normalized_step] if steps else "Complete",
            "total_steps": len(steps),
            "progress": progress_value,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        payload.update(extra)
        last_progress_payload.clear()
        last_progress_payload.update(payload)
        save_json(progress_path, payload)

    run_start = time.time()
    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            step_index = 0
            write_progress(step_index, "running")
            seed_cfg = _load_seed_rt_config(config)
            seed_hash = hashlib.sha256(json.dumps(seed_cfg, sort_keys=True).encode("utf-8")).hexdigest()

            step_index = 1
            write_progress(step_index, "running")
            runtime_cfg = seed_cfg.get("runtime", {})
            prefer_gpu = bool(runtime_cfg.get("prefer_gpu", True)) and not runtime_cfg.get("force_cpu")
            reset_svd_cpu_fallback_flag()
            variant = select_mitsuba_variant(
                prefer_gpu=prefer_gpu,
                forced_variant=str(runtime_cfg.get("mitsuba_variant", "auto")),
                require_cuda=bool(runtime_cfg.get("require_cuda", False)),
            )
            tf_device_info = configure_tensorflow_for_mitsuba_variant(variant)
            tf_info = configure_tensorflow_memory_growth(
                mode=str(runtime_cfg.get("tensorflow_import", "auto"))
            )
            if tf_device_info:
                tf_info.setdefault("device_policy", tf_device_info)
            scene = build_scene(seed_cfg, mitsuba_variant=variant)
            try:
                ris_obj = scene.ris[config["seed"]["ris_name"]]
            except Exception as exc:
                raise ValueError(f"Seed scene does not contain RIS '{config['seed']['ris_name']}'") from exc
            tx_device = next(iter(scene.transmitters.values()))
            tx_power_dbm = float(_to_numpy(tx_device.power_dbm).item())

            fixed_plane = _resolve_fixed_plane(seed_cfg, scene, ris_obj, config)
            kwargs_on = _coverage_kwargs(seed_cfg, fixed_plane, ris_enabled=True)
            kwargs_off = _coverage_kwargs(seed_cfg, fixed_plane, ris_enabled=False)

            step_index = 2
            write_progress(step_index, "running")
            off_eval = _evaluate_variant(scene, kwargs_off, tx_power_dbm, title="RIS Off")
            mask = build_target_mask_from_cell_centers(
                off_eval["cell_centers"],
                config["target_region"]["boxes"],
            )
            if not np.any(mask):
                bounds = _coverage_map_bounds_from_cell_centers(off_eval["cell_centers"])
                raise ValueError(
                    "Target ROI mask is empty on the frozen coverage-map grid. "
                    f"ROI boxes={config['target_region']['boxes']} "
                    f"grid_bounds={bounds}"
                )
            seed_eval = _evaluate_variant(scene, kwargs_on, tx_power_dbm, title="Seed Continuous Sionna RIS")

            optimization_total = _estimate_optimization_evaluations(config)
            step_index = 3
            write_progress(step_index, "running", current_iteration=0, total_iterations=optimization_total)

            def _progress_iteration(iteration: int, total: int, objective_value: float) -> None:
                write_progress(
                    step_index,
                    "running",
                    current_iteration=int(iteration + 1),
                    total_iterations=int(total),
                    objective=float(objective_value),
                    progress=min((step_index + (iteration + 1) / max(total, 1)) / len(steps), 0.95),
                )

            optimization = _optimize_continuous_phase(
                scene,
                ris_obj,
                kwargs_on,
                mask,
                off_eval["cell_centers"],
                config,
                _progress_iteration,
            )
            trace = optimization["trace"]
            continuous_phase = _require_finite("optimized continuous phase", optimization["phase_wrapped"])
            continuous_phase_unwrapped = _require_finite(
                "optimized continuous unwrapped phase",
                optimization["phase_unwrapped"],
            )
            continuous_amp = _require_finite(
                "continuous amplitude profile",
                ris_obj.amplitude_profile.values,
            )

            projected = None
            one_bit_phase = None
            one_bit_amp = None
            if binarization_enabled:
                step_index += 1
                write_progress(step_index, "running")
                projected = _project_to_1bit(scene, ris_obj, kwargs_on, mask, config)
                one_bit_phase = _require_finite("projected 1-bit phase", projected["best_phase"])
                one_bit_amp = _require_finite("1-bit amplitude profile", ris_obj.amplitude_profile.values)

            step_index += 1
            write_progress(step_index, "running")
            import tensorflow as tf

            _assign_profile_values(ris_obj.phase_profile, tf.cast(continuous_phase, ris_obj.phase_profile.values.dtype))
            continuous_eval = _evaluate_variant(
                scene,
                kwargs_on,
                tx_power_dbm,
                title="Optimized Continuous Sionna RIS",
            )
            one_bit_eval = None
            if one_bit_phase is not None:
                _assign_profile_values(ris_obj.phase_profile, tf.cast(one_bit_phase, ris_obj.phase_profile.values.dtype))
                one_bit_eval = _evaluate_variant(scene, kwargs_on, tx_power_dbm, title="1-Bit")

            refined_eval = None
            if projected is not None and config["refinement"]["enabled"] and projected.get("refinement"):
                refined_eval = one_bit_eval

            step_index += 1
            write_progress(step_index, "running")
            write_target_region_artifacts(
                output_dir,
                config["target_region"]["boxes"],
                mask,
                off_eval["cell_centers"],
            )
            write_phase_artifacts(
                output_dir,
                continuous_phase,
                one_bit_phase,
                amp_continuous=continuous_amp,
                amp_1bit=one_bit_amp,
                phase_continuous_unwrapped=continuous_phase_unwrapped,
            )
            write_objective_trace(output_dir, trace)
            if projected is not None:
                write_offset_sweep(output_dir, projected["offset_sweep"])
            diff_seed_vs_off = seed_eval["path_gain_db"] - off_eval["path_gain_db"]
            diff_cont_vs_off = continuous_eval["path_gain_db"] - off_eval["path_gain_db"]
            write_eval_artifacts(
                output_dir,
                key="ris_off",
                evaluation=off_eval,
                boxes=config["target_region"]["boxes"],
            )
            write_eval_artifacts(
                output_dir,
                key="seed",
                evaluation=seed_eval,
                boxes=config["target_region"]["boxes"],
                diff_vs_off=diff_seed_vs_off,
            )
            write_eval_artifacts(
                output_dir,
                key="continuous",
                evaluation=continuous_eval,
                boxes=config["target_region"]["boxes"],
                diff_vs_off=diff_cont_vs_off,
            )
            if one_bit_eval is not None:
                diff_1bit_vs_off = one_bit_eval["path_gain_db"] - off_eval["path_gain_db"]
                diff_1bit_vs_cont = one_bit_eval["path_gain_db"] - continuous_eval["path_gain_db"]
                write_eval_artifacts(
                    output_dir,
                    key="1bit",
                    evaluation=one_bit_eval,
                    boxes=config["target_region"]["boxes"],
                    diff_vs_off=diff_1bit_vs_off,
                    diff_vs_continuous=diff_1bit_vs_cont,
                )
            write_cdf_plot(
                output_dir,
                ({
                    "RIS Off": off_eval["rx_power_dbm"][mask],
                    "Seed": seed_eval["rx_power_dbm"][mask],
                    "Continuous": continuous_eval["rx_power_dbm"][mask],
                } | ({"1-Bit": one_bit_eval["rx_power_dbm"][mask]} if one_bit_eval is not None else {})),
            )
            _try_generate_result_viewer(
                output_dir,
                seed_cfg=seed_cfg,
                fixed_plane=fixed_plane,
                scene=scene,
                evaluation=continuous_eval,
                diff_vs_off=diff_cont_vs_off,
            )
            promoted_artifacts = _write_promoted_sionna_configs(
                output_dir,
                seed_cfg,
                config["seed"]["ris_name"],
                continuous_phase_path=output_dir / "data" / "manual_profile_phase_continuous.npy",
                continuous_amp_path=output_dir / "data" / "manual_profile_amp_continuous.npy",
                one_bit_phase_path=(output_dir / "data" / "manual_profile_phase_1bit.npy") if one_bit_phase is not None else None,
                one_bit_amp_path=(output_dir / "data" / "manual_profile_amp_1bit.npy") if one_bit_phase is not None else None,
            )
            metrics = _build_metrics(
                off_eval,
                seed_eval,
                continuous_eval,
                one_bit_eval,
                mask,
                config,
                projected,
                trace,
                optimization["optimizer"],
                optimization["parameterization"],
                optimization["diagnostics"],
                refined_eval=refined_eval,
            )
            plot_files = sorted(path.name for path in (output_dir / "plots").glob("*.png"))
            summary = {
                "schema_version": config.get("schema_version", 1),
                "run_id": output_dir.name,
                "seed": {
                    "config_path": config["seed"]["config_path"],
                    "config_hash_sha256": seed_hash,
                    "ris_name": config["seed"]["ris_name"],
                    "source_run_id": config["seed"].get("source_run_id"),
                },
                "runtime": {
                    "mitsuba_variant": variant,
                    "rt_backend": _rt_backend_from_variant(variant),
                    "tensorflow": tf_info,
                    "ris_curvature_svd_cpu_fallback_used": svd_cpu_fallback_used(),
                    "timings_s": {
                        "total_s": time.time() - run_start,
                    },
                },
                "environment": collect_environment_info(),
                "target_region": {
                    "boxes": config["target_region"]["boxes"],
                    "mask_shape": list(mask.shape),
                    "num_masked_cells": int(np.count_nonzero(mask)),
                    "plane": fixed_plane,
                    "overlay_polygons": boxes_to_overlay_polygons(config["target_region"]["boxes"]),
                },
                "metrics": metrics,
                "config": {
                    "hash_sha256": summary_seed["config"]["hash_sha256"],
                    "path": str(output_dir / "config.yaml"),
                },
                "artifacts": {
                    "plot_files": plot_files,
                    "viewer_heatmap_array_path": "data/radio_map.npz",
                    "viewer_heatmap_diff_array_path": "data/radio_map_diff.npz",
                    "continuous_phase_array_path": "data/manual_profile_phase_continuous.npy",
                    "continuous_unwrapped_phase_array_path": "data/phase_continuous_unwrapped.npy",
                    "continuous_amp_array_path": "data/manual_profile_amp_continuous.npy",
                    **(
                        {
                            "one_bit_phase_array_path": "data/manual_profile_phase_1bit.npy",
                            "one_bit_amp_array_path": "data/manual_profile_amp_1bit.npy",
                        }
                        if one_bit_phase is not None
                        else {}
                    ),
                    **promoted_artifacts,
                },
            }
            write_summary(output_dir, summary, metrics)
            write_progress(len(steps) - 1, "completed")
            logger.info("RIS synthesis complete: %s", output_dir)
            return output_dir
    except Exception as exc:
        logger.exception("RIS synthesis failed")
        failure_payload = dict(last_progress_payload) if last_progress_payload else {}
        failure_payload.update(
            {
                "status": "failed",
                "step_index": max(0, min(int(step_index), len(steps) - 1)) if steps else 0,
                "step_name": steps[max(0, min(int(step_index), len(steps) - 1))] if steps else "Failed",
                "total_steps": len(steps),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "error": str(exc),
            }
        )
        if "progress" not in failure_payload:
            failure_payload["progress"] = min(
                max(0, min(int(step_index), len(steps) - 1)) / max(len(steps), 1),
                0.99,
            )
        save_json(
            progress_path,
            failure_payload,
        )
        raise
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()
        log_stream.close()
