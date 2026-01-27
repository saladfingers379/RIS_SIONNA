from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_SAMPLES_PER_SRC = 5_000_000
_MAX_SAMPLES_PER_TX = 10_000_000
_MAX_NUM_PATHS_PER_SRC = 5_000_000
_MAX_DEPTH = 20
_MAX_MAP_RES_MULT = 100.0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def _scale_sequence(value: Any, factor: float) -> Any:
    if isinstance(value, (list, tuple)) and value and all(_is_number(v) for v in value):
        return [float(v) * factor for v in value]
    return value


def _scale_vector_list(value: Any, factor: float) -> Any:
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        scaled = []
        for item in value:
            if isinstance(item, (list, tuple)) and len(item) == 3 and all(_is_number(v) for v in item):
                scaled.append([float(v) * factor for v in item])
            else:
                scaled.append(item)
        return scaled
    return value


def _scale_scene_config(scene_cfg: Dict[str, Any], factor: float) -> None:
    tx_cfg = scene_cfg.get("tx", {})
    if "position" in tx_cfg:
        tx_cfg["position"] = _scale_sequence(tx_cfg.get("position"), factor)
    if "look_at" in tx_cfg:
        tx_cfg["look_at"] = _scale_sequence(tx_cfg.get("look_at"), factor)

    rx_cfg = scene_cfg.get("rx", {})
    if "position" in rx_cfg:
        rx_cfg["position"] = _scale_sequence(rx_cfg.get("position"), factor)

    cam_cfg = scene_cfg.get("camera", {})
    if "position" in cam_cfg:
        cam_cfg["position"] = _scale_sequence(cam_cfg.get("position"), factor)

    proc_cfg = scene_cfg.get("procedural", {})
    ground_cfg = proc_cfg.get("ground", {})
    if "size" in ground_cfg:
        ground_cfg["size"] = _scale_sequence(ground_cfg.get("size"), factor)
    if "elevation" in ground_cfg and _is_number(ground_cfg.get("elevation")):
        ground_cfg["elevation"] = float(ground_cfg.get("elevation")) * factor

    boxes = proc_cfg.get("boxes")
    if isinstance(boxes, list):
        for box in boxes:
            if not isinstance(box, dict):
                continue
            if "center" in box:
                box["center"] = _scale_sequence(box.get("center"), factor)
            if "size" in box:
                box["size"] = _scale_sequence(box.get("size"), factor)

    proxy_cfg = scene_cfg.get("proxy", {})
    proxy_ground = proxy_cfg.get("ground", {})
    if "size" in proxy_ground:
        proxy_ground["size"] = _scale_sequence(proxy_ground.get("size"), factor)
    if "elevation" in proxy_ground and _is_number(proxy_ground.get("elevation")):
        proxy_ground["elevation"] = float(proxy_ground.get("elevation")) * factor

    proxy_boxes = proxy_cfg.get("boxes")
    if isinstance(proxy_boxes, list):
        for box in proxy_boxes:
            if not isinstance(box, dict):
                continue
            if "center" in box:
                box["center"] = _scale_sequence(box.get("center"), factor)
            if "size" in box:
                box["size"] = _scale_sequence(box.get("size"), factor)


def _scale_radio_map_config(radio_cfg: Dict[str, Any], factor: float) -> None:
    if "center" in radio_cfg:
        radio_cfg["center"] = _scale_sequence(radio_cfg.get("center"), factor)
    if "size" in radio_cfg:
        radio_cfg["size"] = _scale_sequence(radio_cfg.get("size"), factor)
    if "cell_size" in radio_cfg:
        radio_cfg["cell_size"] = _scale_sequence(radio_cfg.get("cell_size"), factor)
    if "auto_padding" in radio_cfg and _is_number(radio_cfg.get("auto_padding")):
        radio_cfg["auto_padding"] = float(radio_cfg.get("auto_padding")) * factor


def _scale_profile_xyz(profile_cfg: Dict[str, Any], factor: float) -> None:
    if "sources" in profile_cfg:
        sources = profile_cfg.get("sources")
        if isinstance(sources, (list, tuple)) and len(sources) == 3 and all(_is_number(v) for v in sources):
            profile_cfg["sources"] = _scale_sequence(sources, factor)
        else:
            profile_cfg["sources"] = _scale_vector_list(sources, factor)
    if "targets" in profile_cfg:
        targets = profile_cfg.get("targets")
        if isinstance(targets, (list, tuple)) and len(targets) == 3 and all(_is_number(v) for v in targets):
            profile_cfg["targets"] = _scale_sequence(targets, factor)
        else:
            profile_cfg["targets"] = _scale_vector_list(targets, factor)


def _scale_ris_config(ris_cfg: Dict[str, Any], factor: float) -> None:
    base_cfg = ris_cfg.get("sionna", {})
    if "position" in base_cfg:
        base_cfg["position"] = _scale_sequence(base_cfg.get("position"), factor)
    if "look_at" in base_cfg:
        base_cfg["look_at"] = _scale_sequence(base_cfg.get("look_at"), factor)

    size_cfg = ris_cfg.get("size")
    if isinstance(size_cfg, dict):
        if "width_m" in size_cfg and _is_number(size_cfg.get("width_m")):
            size_cfg["width_m"] = float(size_cfg.get("width_m")) * factor
        if "height_m" in size_cfg and _is_number(size_cfg.get("height_m")):
            size_cfg["height_m"] = float(size_cfg.get("height_m")) * factor
        if "target_dx_m" in size_cfg and _is_number(size_cfg.get("target_dx_m")):
            size_cfg["target_dx_m"] = float(size_cfg.get("target_dx_m")) * factor
        if "target_dy_m" in size_cfg and _is_number(size_cfg.get("target_dy_m")):
            size_cfg["target_dy_m"] = float(size_cfg.get("target_dy_m")) * factor

    spacing_cfg = ris_cfg.get("spacing")
    if isinstance(spacing_cfg, dict):
        if "dx_m" in spacing_cfg and _is_number(spacing_cfg.get("dx_m")):
            spacing_cfg["dx_m"] = float(spacing_cfg.get("dx_m")) * factor
        if "dy_m" in spacing_cfg and _is_number(spacing_cfg.get("dy_m")):
            spacing_cfg["dy_m"] = float(spacing_cfg.get("dy_m")) * factor
        if "width_m" in spacing_cfg and _is_number(spacing_cfg.get("width_m")):
            spacing_cfg["width_m"] = float(spacing_cfg.get("width_m")) * factor
        if "height_m" in spacing_cfg and _is_number(spacing_cfg.get("height_m")):
            spacing_cfg["height_m"] = float(spacing_cfg.get("height_m")) * factor

    obj_cfgs = ris_cfg.get("objects")
    if isinstance(obj_cfgs, list):
        for obj in obj_cfgs:
            if not isinstance(obj, dict):
                continue
            if "position" in obj:
                obj["position"] = _scale_sequence(obj.get("position"), factor)
            if "look_at" in obj:
                obj["look_at"] = _scale_sequence(obj.get("look_at"), factor)
            profile_cfg = obj.get("profile")
            if isinstance(profile_cfg, dict):
                _scale_profile_xyz(profile_cfg, factor)



def _apply_map_resolution_multiplier(radio_cfg: Dict[str, Any], multiplier: float) -> Dict[str, Any]:
    applied = {}
    if multiplier <= 1.0:
        return applied
    capped_mult = min(multiplier, _MAX_MAP_RES_MULT)
    if capped_mult != multiplier:
        applied["map_resolution_multiplier_capped"] = capped_mult
    cell_size = radio_cfg.get("cell_size")
    if isinstance(cell_size, (list, tuple)) and cell_size:
        new_cell = []
        for val in cell_size:
            if _is_number(val):
                new_cell.append(float(val) / capped_mult)
            else:
                new_cell.append(val)
        radio_cfg["cell_size"] = new_cell
        applied["cell_size"] = {"from": cell_size, "to": new_cell}
    elif _is_number(cell_size):
        new_cell = float(cell_size) / capped_mult
        radio_cfg["cell_size"] = new_cell
        applied["cell_size"] = {"from": cell_size, "to": new_cell}
    else:
        applied["cell_size"] = "missing"
    return applied


def _apply_sample_multiplier(target_cfg: Dict[str, Any], key: str, multiplier: float, cap: int) -> Optional[Dict[str, Any]]:
    if multiplier <= 1.0:
        return None
    if key not in target_cfg:
        return None
    original = target_cfg.get(key)
    if not _is_number(original):
        return None
    new_value = int(max(1, round(float(original) * multiplier)))
    capped_value = min(new_value, cap)
    target_cfg[key] = capped_value
    result = {"from": original, "to": capped_value}
    if capped_value != new_value:
        result["capped"] = new_value
    return result


def _apply_depth_add(target_cfg: Dict[str, Any], key: str, add: int, cap: int) -> Optional[Dict[str, Any]]:
    if add <= 0 or key not in target_cfg:
        return None
    original = target_cfg.get(key)
    if not _is_number(original):
        return None
    new_value = int(round(float(original) + add))
    capped_value = min(new_value, cap)
    target_cfg[key] = capped_value
    result = {"from": original, "to": capped_value}
    if capped_value != new_value:
        result["capped"] = new_value
    return result


def apply_similarity_and_sampling(
    config: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    cfg = copy.deepcopy(config)
    sim_cfg = cfg.setdefault("simulation", {})

    scale_cfg = copy.deepcopy(sim_cfg.get("scale_similarity", {}) or {})
    sampling_cfg = copy.deepcopy(sim_cfg.get("sampling_boost", {}) or {})
    if overrides:
        scale_cfg.update(overrides.get("scale_similarity", {}) or {})
        sampling_cfg.update(overrides.get("sampling_boost", {}) or {})

    scale_enabled = bool(scale_cfg.get("enabled", False))
    scale_factor = float(scale_cfg.get("factor", 1.0))
    if scale_factor < 1.0:
        raise ValueError("simulation.scale_similarity.factor must be >= 1.0")

    already_applied = bool(scale_cfg.get("applied", False))
    effective_scale = scale_enabled and scale_factor > 1.0
    if scale_enabled and scale_factor == 1.0:
        logger.warning("Similarity scaling enabled with factor=1.0; treating as disabled.")
    if already_applied:
        if scale_enabled:
            logger.warning(
                "Similarity scaling already applied in config; skipping to avoid compounding. "
                "Use a base (unscaled) config to change scale factor."
            )
        else:
            logger.warning(
                "Similarity scaling disabled but config appears already scaled (applied=true). "
                "Use a base (unscaled) config to revert."
            )
        effective_scale = False

    original_freq = sim_cfg.get("frequency_hz")
    scaled_freq = original_freq
    if effective_scale:
        if original_freq is not None:
            scaled_freq = float(original_freq) / scale_factor
            sim_cfg["frequency_hz"] = scaled_freq

        scene_cfg = cfg.get("scene", {})
        if isinstance(scene_cfg, dict):
            _scale_scene_config(scene_cfg, scale_factor)

        radio_cfg = cfg.get("radio_map", {})
        if isinstance(radio_cfg, dict):
            _scale_radio_map_config(radio_cfg, scale_factor)

        ris_cfg = cfg.get("ris", {})
        if isinstance(ris_cfg, dict):
            _scale_ris_config(ris_cfg, scale_factor)

    warning = None
    if effective_scale and original_freq is not None:
        try:
            original_freq_ghz = float(original_freq) / 1e9
            warning = f"Results correspond to original electrical size at {original_freq_ghz:.3g} GHz."
        except (TypeError, ValueError):
            warning = "Results correspond to original electrical size at the original frequency."

    scale_meta = {
        "enabled": scale_enabled,
        "factor": scale_factor,
        "effective_enabled": effective_scale,
        "applied": effective_scale or already_applied,
        "already_applied": already_applied,
        "original_frequency_hz": original_freq,
        "scaled_frequency_hz": scaled_freq,
        "interpretation_warning": warning,
        "note": "Similarity scaling assumes materials are not strongly frequency-dispersive.",
    }
    sim_cfg["scale_similarity"] = scale_meta

    sampling_enabled = bool(sampling_cfg.get("enabled", False))
    map_mult = float(sampling_cfg.get("map_resolution_multiplier", 1.0))
    ray_mult = float(sampling_cfg.get("ray_samples_multiplier", 1.0))
    depth_add = int(sampling_cfg.get("max_depth_add", 0))

    if map_mult < 1.0:
        raise ValueError("sampling_boost.map_resolution_multiplier must be >= 1")
    if ray_mult < 1.0:
        raise ValueError("sampling_boost.ray_samples_multiplier must be >= 1")
    if depth_add < 0:
        raise ValueError("sampling_boost.max_depth_add must be >= 0")

    effective_sampling = sampling_enabled and (map_mult > 1.0 or ray_mult > 1.0 or depth_add > 0)
    if sampling_enabled and not effective_sampling:
        logger.warning("Sampling boost enabled but multipliers are neutral; treating as disabled.")

    sampling_applied: Dict[str, Any] = {}
    if effective_sampling:
        radio_cfg = cfg.setdefault("radio_map", {})
        if isinstance(radio_cfg, dict):
            sampling_applied.update(_apply_map_resolution_multiplier(radio_cfg, map_mult))
            result = _apply_sample_multiplier(radio_cfg, "samples_per_tx", ray_mult, _MAX_SAMPLES_PER_TX)
            if result:
                sampling_applied["samples_per_tx"] = result
            result = _apply_depth_add(radio_cfg, "max_depth", depth_add, _MAX_DEPTH)
            if result:
                sampling_applied["radio_map_max_depth"] = result

        result = _apply_sample_multiplier(sim_cfg, "samples_per_src", ray_mult, _MAX_SAMPLES_PER_SRC)
        if result:
            sampling_applied["samples_per_src"] = result
        result = _apply_sample_multiplier(sim_cfg, "max_num_paths_per_src", ray_mult, _MAX_NUM_PATHS_PER_SRC)
        if result:
            sampling_applied["max_num_paths_per_src"] = result
        result = _apply_depth_add(sim_cfg, "max_depth", depth_add, _MAX_DEPTH)
        if result:
            sampling_applied["max_depth"] = result

    sampling_meta = {
        "enabled": sampling_enabled,
        "map_resolution_multiplier": map_mult,
        "ray_samples_multiplier": ray_mult,
        "max_depth_add": depth_add,
        "effective_enabled": effective_sampling,
        "applied": sampling_applied,
    }
    sim_cfg["sampling_boost"] = sampling_meta

    tuning_summary = {
        "scale_similarity": scale_meta,
        "sampling_boost": sampling_meta,
    }
    return cfg, tuning_summary
