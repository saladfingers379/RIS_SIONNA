from __future__ import annotations

import math
from typing import Any, Dict, Optional


def _as_float(value: Any, name: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if out <= 0.0:
        raise ValueError(f"{name} must be positive")
    return out


def _as_int(value: Any, name: str) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if out <= 0:
        raise ValueError(f"{name} must be >= 1")
    return out


def _resolve_mode(raw: Any) -> str:
    if raw is None:
        return "legacy"
    mode = str(raw).strip().lower()
    aliases = {
        "size": "size_driven",
        "size-driven": "size_driven",
        "spacing": "spacing_driven",
        "spacing-driven": "spacing_driven",
    }
    return aliases.get(mode, mode)


def build_ris_geometry(ris_cfg: Dict[str, Any], obj_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    obj_cfg = obj_cfg or {}
    mode = _resolve_mode(ris_cfg.get("geometry_mode", "legacy"))
    if mode not in {"legacy", "size_driven", "spacing_driven"}:
        raise ValueError("ris.geometry_mode must be legacy, size_driven, or spacing_driven")

    nx_default = int(obj_cfg.get("num_rows", 8))
    ny_default = int(obj_cfg.get("num_cols", 8))
    result: Dict[str, Any] = {
        "mode": mode,
        "nx": nx_default,
        "ny": ny_default,
        "dx_m": None,
        "dy_m": None,
        "width_m": None,
        "height_m": None,
        "requested": {},
        "effective": {},
        "rounding": {},
    }

    if mode == "legacy":
        workbench = ris_cfg.get("workbench", {}) if isinstance(ris_cfg, dict) else {}
        geom = workbench.get("geometry_override", {}) if isinstance(workbench, dict) else {}
        dx = geom.get("dx")
        dy = geom.get("dy")
        if dx is not None and dy is not None:
            dx = _as_float(dx, "ris.workbench.geometry_override.dx")
            dy = _as_float(dy, "ris.workbench.geometry_override.dy")
            width = (nx_default - 1) * dx if nx_default > 1 else dx
            height = (ny_default - 1) * dy if ny_default > 1 else dy
            result.update({"dx_m": dx, "dy_m": dy, "width_m": width, "height_m": height})
            result["effective"].update({"dx_m": dx, "dy_m": dy, "width_m": width, "height_m": height})
        return result

    if mode == "size_driven":
        size_cfg = ris_cfg.get("size", {})
        width = _as_float(size_cfg.get("width_m"), "ris.size.width_m")
        height = _as_float(size_cfg.get("height_m"), "ris.size.height_m")
        target_dx = size_cfg.get("target_dx_m")
        target_dy = size_cfg.get("target_dy_m")
        density = size_cfg.get("target_density_per_m2")

        if target_dx is None or target_dy is None:
            if density is None:
                raise ValueError("ris.size requires target_dx_m/target_dy_m or target_density_per_m2")
            density = _as_float(density, "ris.size.target_density_per_m2")
            target_dx = math.sqrt(1.0 / density)
            target_dy = math.sqrt(1.0 / density)
        target_dx = _as_float(target_dx, "ris.size.target_dx_m")
        target_dy = _as_float(target_dy, "ris.size.target_dy_m")

        nx = max(1, int(round(width / target_dx)) + 1)
        ny = max(1, int(round(height / target_dy)) + 1)
        dx_eff = width / (nx - 1) if nx > 1 else width
        dy_eff = height / (ny - 1) if ny > 1 else height
        width_eff = (nx - 1) * dx_eff if nx > 1 else width
        height_eff = (ny - 1) * dy_eff if ny > 1 else height

        result.update({"nx": nx, "ny": ny, "dx_m": dx_eff, "dy_m": dy_eff, "width_m": width_eff, "height_m": height_eff})
        result["requested"].update({"width_m": width, "height_m": height, "target_dx_m": target_dx, "target_dy_m": target_dy, "target_density_per_m2": density})
        result["effective"].update({"width_m": width_eff, "height_m": height_eff, "dx_m": dx_eff, "dy_m": dy_eff})
        result["rounding"].update({
            "width_m_delta": width_eff - width,
            "height_m_delta": height_eff - height,
            "dx_m_delta": dx_eff - target_dx,
            "dy_m_delta": dy_eff - target_dy,
        })
        return result

    spacing_cfg = ris_cfg.get("spacing", {})
    dx = _as_float(spacing_cfg.get("dx_m"), "ris.spacing.dx_m")
    dy = _as_float(spacing_cfg.get("dy_m"), "ris.spacing.dy_m")

    nx = spacing_cfg.get("num_cells_x")
    ny = spacing_cfg.get("num_cells_y")
    width = spacing_cfg.get("width_m")
    height = spacing_cfg.get("height_m")

    if nx is not None or ny is not None:
        nx = _as_int(nx, "ris.spacing.num_cells_x")
        ny = _as_int(ny, "ris.spacing.num_cells_y")
        width_eff = (nx - 1) * dx if nx > 1 else dx
        height_eff = (ny - 1) * dy if ny > 1 else dy
        result.update({"nx": nx, "ny": ny, "dx_m": dx, "dy_m": dy, "width_m": width_eff, "height_m": height_eff})
        result["requested"].update({"dx_m": dx, "dy_m": dy, "num_cells_x": nx, "num_cells_y": ny})
        result["effective"].update({"width_m": width_eff, "height_m": height_eff, "dx_m": dx, "dy_m": dy})
        return result

    if width is None or height is None:
        raise ValueError("ris.spacing requires num_cells_x/num_cells_y or width_m/height_m")
    width = _as_float(width, "ris.spacing.width_m")
    height = _as_float(height, "ris.spacing.height_m")
    nx = max(1, int(round(width / dx)) + 1)
    ny = max(1, int(round(height / dy)) + 1)
    width_eff = (nx - 1) * dx if nx > 1 else width
    height_eff = (ny - 1) * dy if ny > 1 else height

    result.update({"nx": nx, "ny": ny, "dx_m": dx, "dy_m": dy, "width_m": width_eff, "height_m": height_eff})
    result["requested"].update({"dx_m": dx, "dy_m": dy, "width_m": width, "height_m": height})
    result["effective"].update({"width_m": width_eff, "height_m": height_eff, "dx_m": dx, "dy_m": dy})
    result["rounding"].update({
        "width_m_delta": width_eff - width,
        "height_m_delta": height_eff - height,
    })
    return result


def apply_ris_geometry_overrides(config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    if not overrides:
        return config
    ris_cfg = config.setdefault("ris", {})
    if overrides.get("geometry_mode") is not None:
        ris_cfg["geometry_mode"] = overrides.get("geometry_mode")
    if isinstance(overrides.get("size"), dict):
        size_cfg = ris_cfg.get("size", {}) if isinstance(ris_cfg.get("size"), dict) else {}
        size_cfg.update(overrides.get("size", {}))
        ris_cfg["size"] = size_cfg
    if isinstance(overrides.get("spacing"), dict):
        spacing_cfg = ris_cfg.get("spacing", {}) if isinstance(ris_cfg.get("spacing"), dict) else {}
        spacing_cfg.update(overrides.get("spacing", {}))
        ris_cfg["spacing"] = spacing_cfg
    return config
