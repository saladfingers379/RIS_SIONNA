from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _to_vec3(value: Any) -> Optional[List[float]]:
    if isinstance(value, np.ndarray):
        if value.size < 3:
            return None
        flat = value.reshape(-1)
        try:
            return [float(flat[0]), float(flat[1]), float(flat[2])]
        except Exception:
            return None
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except Exception:
        return None


def _to_vec2(value: Any) -> Optional[Tuple[float, float]]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return float(value[0]), float(value[1])
        except Exception:
            return None
    return None


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def radio_map_z_slice_offsets(radio_map_cfg: Optional[Dict[str, Any]]) -> List[float]:
    radio_cfg = radio_map_cfg if isinstance(radio_map_cfg, dict) else {}
    stack_cfg = radio_cfg.get("z_stack")
    if not isinstance(stack_cfg, dict) or not bool(stack_cfg.get("enabled", False)):
        return []

    explicit_offsets = stack_cfg.get("offsets_m")
    offsets: List[float] = []
    if isinstance(explicit_offsets, (list, tuple)):
        for value in explicit_offsets:
            try:
                offset = float(value)
            except Exception:
                continue
            if abs(offset) > 1e-12:
                offsets.append(offset)
    else:
        spacing_m = abs(_to_float(stack_cfg.get("spacing_m"), 0.05))
        if spacing_m <= 0.0:
            return []
        num_below = max(0, int(_to_float(stack_cfg.get("num_below"), 0.0)))
        num_above = max(0, int(_to_float(stack_cfg.get("num_above"), 0.0)))
        offsets.extend([-float(idx) * spacing_m for idx in range(num_below, 0, -1)])
        offsets.extend([float(idx) * spacing_m for idx in range(1, num_above + 1)])

    unique_offsets = sorted({round(float(offset), 10) for offset in offsets if abs(float(offset)) > 1e-12})
    return [float(offset) for offset in unique_offsets]


def _aligned_axis(
    center: float,
    size: float,
    cell: float,
    anchor: float,
    *,
    inside_only: bool = True,
) -> Tuple[float, float, int]:
    if cell <= 0.0 or size <= 0.0:
        return center, 0.0, 0

    # Only align when the anchor is on/near the map plane in this axis.
    if inside_only:
        half = 0.5 * size
        if anchor < (center - half - 0.5 * cell) or anchor > (center + half + 0.5 * cell):
            return center, 0.0, 0

    num_cells = max(1, int(round(size / cell)))
    phase = ((num_cells - 1) * 0.5 * cell) % cell
    target_mod = (anchor + phase) % cell
    current_mod = center % cell

    raw_delta = target_mod - current_mod
    shift = ((raw_delta + 0.5 * cell) % cell) - 0.5 * cell
    if abs(shift) < 1e-12:
        return center, 0.0, num_cells
    return center + shift, shift, num_cells


def align_center_to_anchor(
    center: Any,
    size: Any,
    cell_size: Any,
    anchor: Any,
    *,
    inside_only: bool = True,
) -> Tuple[Optional[List[float]], Optional[Dict[str, Any]]]:
    center_v = _to_vec3(center)
    anchor_v = _to_vec3(anchor)
    size_v = _to_vec2(size)
    cell_v = _to_vec2(cell_size)
    if center_v is None or anchor_v is None or size_v is None or cell_v is None:
        return center_v, None

    x_new, x_shift, nx = _aligned_axis(
        center_v[0], size_v[0], cell_v[0], anchor_v[0], inside_only=inside_only
    )
    y_new, y_shift, ny = _aligned_axis(
        center_v[1], size_v[1], cell_v[1], anchor_v[1], inside_only=inside_only
    )

    out = [x_new, y_new, center_v[2]]
    info = {
        "anchor": anchor_v,
        "shift_xy_m": [float(x_shift), float(y_shift)],
        "num_cells_xy": [int(nx), int(ny)],
        "applied": bool(abs(x_shift) > 0.0 or abs(y_shift) > 0.0),
    }
    return out, info


def _rotation_matrix(angles: Any) -> Optional[np.ndarray]:
    vec = _to_vec3(angles)
    if vec is None:
        return None
    a, b, c = vec
    cos_a = math.cos(a)
    cos_b = math.cos(b)
    cos_c = math.cos(c)
    sin_a = math.sin(a)
    sin_b = math.sin(b)
    sin_c = math.sin(c)
    return np.array(
        [
            [cos_a * cos_b, cos_a * sin_b * sin_c - sin_a * cos_c, cos_a * sin_b * cos_c + sin_a * sin_c],
            [sin_a * cos_b, sin_a * sin_b * sin_c + cos_a * cos_c, sin_a * sin_b * cos_c - cos_a * sin_c],
            [-sin_b, cos_b * sin_c, cos_b * cos_c],
        ],
        dtype=float,
    )


def coverage_plane_normal(orientation: Any) -> Optional[List[float]]:
    rot = _rotation_matrix(orientation)
    if rot is None:
        return None
    normal = rot @ np.array([0.0, 0.0, 1.0], dtype=float)
    norm = float(np.linalg.norm(normal))
    if norm <= 0.0:
        return None
    normal = normal / norm
    return [float(normal[0]), float(normal[1]), float(normal[2])]


def assess_ris_plane_visibility(
    ris_position: Any,
    rx_position: Any,
    plane_orientation: Any,
    *,
    parallel_threshold_deg: float = 5.0,
) -> Optional[Dict[str, Any]]:
    ris_v = _to_vec3(ris_position)
    rx_v = _to_vec3(rx_position)
    normal_v = coverage_plane_normal(plane_orientation)
    if ris_v is None or rx_v is None or normal_v is None:
        return None

    beam = np.asarray(rx_v, dtype=float) - np.asarray(ris_v, dtype=float)
    beam_norm = float(np.linalg.norm(beam))
    if beam_norm <= 0.0:
        return None
    beam_unit = beam / beam_norm
    normal = np.asarray(normal_v, dtype=float)
    alignment = float(abs(np.clip(np.dot(beam_unit, normal), -1.0, 1.0)))
    angle_from_plane = float(np.degrees(np.arcsin(alignment)))
    return {
        "plane_normal": normal_v,
        "ris_to_rx_unit": [float(beam_unit[0]), float(beam_unit[1]), float(beam_unit[2])],
        "ris_to_rx_angle_from_plane_deg": angle_from_plane,
        "beam_parallel_to_plane": bool(angle_from_plane <= float(parallel_threshold_deg)),
        "parallel_threshold_deg": float(parallel_threshold_deg),
    }


def diagnose_ris_map_sampling_issue(
    radio_map_stats: Optional[Dict[str, Any]],
    visibility_info: Optional[Dict[str, Any]],
    ris_link_probe: Optional[Dict[str, Any]] = None,
    *,
    floor_db: float = -119.0,
    strong_delta_db: float = 3.0,
) -> Optional[Dict[str, Any]]:
    if not isinstance(radio_map_stats, dict):
        return None

    try:
        path_gain_db_max = float(radio_map_stats["path_gain_db_max"])
    except Exception:
        return None

    link_delta_db = None
    if isinstance(ris_link_probe, dict):
        try:
            link_delta_db = float(ris_link_probe["delta_total_path_gain_db"])
        except Exception:
            link_delta_db = None

    flat_floor_map = path_gain_db_max <= float(floor_db)
    beam_parallel = bool(
        isinstance(visibility_info, dict) and visibility_info.get("beam_parallel_to_plane")
    )
    strong_link_delta = link_delta_db is not None and link_delta_db >= float(strong_delta_db)

    if beam_parallel and flat_floor_map:
        issue: Dict[str, Any] = {
            "kind": "beam_parallel_to_plane",
            "path_gain_db_max": path_gain_db_max,
            "floor_db": float(floor_db),
            "message": (
                "Radio-map slice is nearly parallel to the RIS beam, so the 2D coverage "
                "plane can miss the reradiated energy."
            ),
            "recommended_action": (
                "Use a vertical slice or rotate the radio-map plane so it cuts across the RIS->Rx beam."
            ),
        }
        if isinstance(visibility_info, dict):
            try:
                issue["ris_to_rx_angle_from_plane_deg"] = float(
                    visibility_info["ris_to_rx_angle_from_plane_deg"]
                )
            except Exception:
                pass
        if link_delta_db is not None:
            issue["ris_link_probe_delta_db"] = link_delta_db
        return issue

    if strong_link_delta and flat_floor_map:
        return {
            "kind": "slice_missed_ris_energy",
            "path_gain_db_max": path_gain_db_max,
            "floor_db": float(floor_db),
            "ris_link_probe_delta_db": link_delta_db,
            "message": (
                "Radio map is at the noise floor even though the RIS improves the Tx/Rx link."
            ),
            "recommended_action": (
                "Move or rotate the coverage-map slice so it intersects the RIS reradiation lobe."
            ),
        }

    return None


def derive_tx_ris_incidence_slice(
    tx_position: Any,
    ris_position: Any,
    radio_map_cfg: Optional[Dict[str, Any]] = None,
    slice_cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    tx_v = _to_vec3(tx_position)
    ris_v = _to_vec3(ris_position)
    if tx_v is None or ris_v is None:
        return None

    tx = np.asarray(tx_v, dtype=float)
    ris = np.asarray(ris_v, dtype=float)
    delta = ris - tx
    distance = float(np.linalg.norm(delta))
    if distance <= 0.0:
        return None

    radio_cfg = radio_map_cfg if isinstance(radio_map_cfg, dict) else {}
    slice_local = slice_cfg if isinstance(slice_cfg, dict) else {}
    base_size = _to_vec2(radio_cfg.get("size"))
    base_cell = _to_vec2(radio_cfg.get("cell_size"))

    length_padding = max(0.0, _to_float(slice_local.get("length_padding_m"), 0.2))
    vertical_padding = max(0.0, _to_float(slice_local.get("vertical_padding_m"), 0.6))
    min_height = max(0.0, _to_float(slice_local.get("min_height_m"), 1.0))

    delta_xy = delta[:2]
    delta_xy_norm = float(np.linalg.norm(delta_xy))
    normal_azimuth = math.atan2(delta_xy[1], delta_xy[0]) + (0.5 * math.pi) if delta_xy_norm > 0.0 else 0.0
    orientation = [float(normal_azimuth), float(0.5 * math.pi), 0.0]

    center = ((tx + ris) * 0.5).tolist()
    length_m = distance + 2.0 * length_padding
    if base_cell is not None:
        length_m = max(length_m, float(base_cell[0]))
    height_base = abs(float(delta[2])) + 2.0 * vertical_padding
    if base_size is not None:
        height_base = max(height_base, float(base_size[1]))
    if base_cell is not None:
        height_base = max(height_base, float(base_cell[1]))
    height_m = max(height_base, min_height)

    result: Dict[str, Any] = {
        "center": [float(center[0]), float(center[1]), float(center[2])],
        "orientation": orientation,
        "size": [float(length_m), float(height_m)],
        "auto_size": False,
        "align_grid_to_anchor": False,
        "plot_axis_labels": ["Tx->RIS distance [m]", "z [m]"],
        "tx_ris_distance_m": float(distance),
    }
    if base_cell is not None:
        result["cell_size"] = [float(base_cell[0]), float(base_cell[1])]
    return result
