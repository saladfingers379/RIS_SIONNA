"""ROI utilities for RT-side RIS synthesis."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

import numpy as np


def coverage_plane_metadata_from_seed_cfg(seed_cfg: dict) -> dict:
    radio_cfg = seed_cfg.get("radio_map") if isinstance(seed_cfg, dict) else {}
    if not isinstance(radio_cfg, dict):
        raise ValueError("Seed config missing radio_map mapping")
    center = list(radio_cfg.get("center") or [0.0, 0.0, 0.0])
    if len(center) < 3:
        center = list(center) + [0.0] * (3 - len(center))
    if radio_cfg.get("center_z_only") is not None:
        center[2] = float(radio_cfg.get("center_z_only"))
    return {
        "center": [float(center[0]), float(center[1]), float(center[2])],
        "size": [float(radio_cfg.get("size", [1.0, 1.0])[0]), float(radio_cfg.get("size", [1.0, 1.0])[1])],
        "cell_size": [
            float(radio_cfg.get("cell_size", [1.0, 1.0])[0]),
            float(radio_cfg.get("cell_size", [1.0, 1.0])[1]),
        ],
        "orientation": list(radio_cfg.get("orientation") or [0.0, 0.0, 0.0]),
        "align_grid_to_anchor": bool(radio_cfg.get("align_grid_to_anchor", True)),
        "cell_anchor": str(radio_cfg.get("cell_anchor", "auto")),
        "cell_anchor_point": radio_cfg.get("cell_anchor_point"),
    }


def _axis_centers(center: float, size: float, cell_size: float) -> np.ndarray:
    num_cells = max(1, int(round(float(size) / float(cell_size))))
    return float(center) + (np.arange(num_cells, dtype=float) - (num_cells - 1) / 2.0) * float(cell_size)


def _normalize_boxes(boxes: Iterable[dict]) -> List[dict]:
    normalized = []
    for idx, box in enumerate(boxes):
        if not isinstance(box, dict):
            raise ValueError(f"ROI box {idx} must be a mapping")
        normalized.append(
            {
                "name": str(box.get("name") or f"roi_{idx + 1}"),
                "u_min_m": float(box["u_min_m"]),
                "u_max_m": float(box["u_max_m"]),
                "v_min_m": float(box["v_min_m"]),
                "v_max_m": float(box["v_max_m"]),
            }
        )
    return normalized


def build_target_mask_from_boxes(center, size, cell_size, boxes) -> np.ndarray:
    boxes_norm = _normalize_boxes(boxes)
    u_axis = _axis_centers(float(center[0]), float(size[0]), float(cell_size[0]))
    v_axis = _axis_centers(float(center[1]), float(size[1]), float(cell_size[1]))
    uu, vv = np.meshgrid(u_axis, v_axis)
    mask = np.zeros_like(uu, dtype=bool)
    for box in boxes_norm:
        box_mask = (
            (uu >= box["u_min_m"])
            & (uu <= box["u_max_m"])
            & (vv >= box["v_min_m"])
            & (vv <= box["v_max_m"])
        )
        mask |= box_mask
    return mask


def build_target_mask_from_cell_centers(cell_centers: np.ndarray, boxes) -> np.ndarray:
    centers = np.asarray(cell_centers, dtype=float)
    if centers.ndim != 3 or centers.shape[-1] < 2:
        raise ValueError("cell_centers must be an array shaped [ny, nx, 3]")
    boxes_norm = _normalize_boxes(boxes)
    uu = centers[..., 0]
    vv = centers[..., 1]
    mask = np.zeros(uu.shape, dtype=bool)
    for box in boxes_norm:
        mask |= (
            (uu >= box["u_min_m"])
            & (uu <= box["u_max_m"])
            & (vv >= box["v_min_m"])
            & (vv <= box["v_max_m"])
        )
    return mask


def boxes_to_overlay_polygons(boxes) -> list[dict]:
    polygons = []
    for box in _normalize_boxes(boxes):
        polygons.append(
            {
                "name": box["name"],
                "points_uv_m": [
                    [box["u_min_m"], box["v_min_m"]],
                    [box["u_max_m"], box["v_min_m"]],
                    [box["u_max_m"], box["v_max_m"]],
                    [box["u_min_m"], box["v_max_m"]],
                ],
            }
        )
    return polygons
