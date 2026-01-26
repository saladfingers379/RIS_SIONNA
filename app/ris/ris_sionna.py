"""Sionna RT RIS adapter for workbench phase maps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import logging
import numpy as np

from app.ris.ris_config import resolve_ris_lab_config
from app.ris.ris_core import (
    compute_element_centers,
    quantize_phase,
    synthesize_custom_phase,
    synthesize_focusing_phase,
    synthesize_reflectarray_phase,
    synthesize_uniform_phase,
)

_SPEED_OF_LIGHT_M_S = 299_792_458.0
logger = logging.getLogger(__name__)

_PHASE_PROFILE_KINDS = {
    "phase_gradient_reflector",
    "focusing_lens",
    "manual",
    "flat",
    "uniform",
}

def _assign_profile_values(profile: Any, values: Any) -> None:
    """Assign profile values across TF variable / property setter variants."""
    try:
        assign = getattr(profile.values, "assign", None)
        if callable(assign):
            assign(values)
            return
    except Exception:
        pass
    profile.values = values


def _direction_from_angles(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    az = float(azimuth_deg)
    el = float(elevation_deg)
    az_rad = np.deg2rad(az)
    el_rad = np.deg2rad(el)
    return np.array(
        [
            np.cos(el_rad) * np.cos(az_rad),
            np.cos(el_rad) * np.sin(az_rad),
            np.sin(el_rad),
        ],
        dtype=float,
    )


def _resolve_tx_angle_deg(experiment_cfg: Dict[str, Any]) -> float:
    if "tx_angle_deg" in experiment_cfg:
        return float(experiment_cfg["tx_angle_deg"])
    return float(experiment_cfg.get("tx_incident_angle_deg", 0.0))


def _compute_ris_center(geometry: Any) -> np.ndarray:
    return geometry.centers.reshape(-1, 3).mean(axis=0)


def _compute_tx_position(
    geometry: Any,
    ris_center: np.ndarray,
    tx_distance_m: float,
    tx_angle_deg: float,
) -> np.ndarray:
    theta_rad = np.deg2rad(float(tx_angle_deg))
    direction = np.cos(theta_rad) * geometry.frame.w + np.sin(theta_rad) * geometry.frame.u
    return ris_center + float(tx_distance_m) * direction


def _resolve_phase_map(
    config: Dict[str, Any],
    geometry: Any,
    wavelength: float,
    tx_position: np.ndarray,
    ris_center: np.ndarray,
) -> np.ndarray:
    geometry_cfg = config["geometry"]
    control_cfg = config.get("control", {})
    mode = control_cfg.get("mode", "uniform")
    params = control_cfg.get("params", {}) or {}
    shape = (int(geometry_cfg["ny"]), int(geometry_cfg["nx"]))

    if mode == "uniform":
        if "phase_rad" in params:
            phase = synthesize_uniform_phase(shape, float(params["phase_rad"]))
        elif "phase_deg" in params:
            phase = synthesize_uniform_phase(shape, float(np.deg2rad(params["phase_deg"])))
        else:
            phase = synthesize_uniform_phase(shape, 0.0)
    elif mode == "steer":
        direction = params.get("direction")
        if direction is None:
            az = params.get("azimuth_deg")
            el = params.get("elevation_deg")
            if az is None or el is None:
                raise ValueError("steer control requires direction or azimuth_deg/elevation_deg")
            direction = _direction_from_angles(float(az), float(el))
        phase_offset = float(params.get("phase_offset_rad", 0.0))
        if "phase_offset_deg" in params:
            phase_offset = float(np.deg2rad(params["phase_offset_deg"]))
        phase = synthesize_reflectarray_phase(
            geometry.centers,
            wavelength,
            tx_position,
            direction,
            phase_offset_rad=phase_offset,
            ris_center=ris_center,
        )
    elif mode == "focus":
        focal_point = params.get("focal_point")
        if focal_point is None:
            raise ValueError("focus control requires focal_point")
        phase = synthesize_focusing_phase(geometry.centers, wavelength, focal_point, None)
    elif mode == "custom":
        phase_map = params.get("phase_map")
        if phase_map is None:
            raise ValueError("custom control requires phase_map")
        phase = synthesize_custom_phase(np.array(phase_map, dtype=float), shape=shape)
    else:
        raise ValueError(f"Unsupported control mode: {mode}")

    quant_bits = config.get("quantization", {}).get("bits")
    phase = quantize_phase(phase, quant_bits)
    return phase


def _quantize_keys(values: np.ndarray, tol: float) -> np.ndarray:
    scale = 1.0 / float(tol)
    return np.round(values * scale).astype(int)


def _map_phase_to_sionna_order(
    phase_map: np.ndarray,
    centers: np.ndarray,
    tol: float = 1e-6,
) -> np.ndarray:
    ys = centers[:, :, 1]
    zs = centers[:, :, 2]
    y_keys = _quantize_keys(ys, tol)
    z_keys = _quantize_keys(zs, tol)

    unique_y = sorted(set(y_keys.reshape(-1).tolist()))
    unique_z = sorted(set(z_keys.reshape(-1).tolist()), reverse=True)

    y_index = {val: idx for idx, val in enumerate(unique_y)}
    z_index = {val: idx for idx, val in enumerate(unique_z)}

    out = np.zeros((len(unique_z), len(unique_y)), dtype=float)
    for row in range(phase_map.shape[0]):
        for col in range(phase_map.shape[1]):
            out[z_index[z_keys[row, col]], y_index[y_keys[row, col]]] = phase_map[row, col]
    return out


@dataclass(frozen=True)
class RisWorkbenchResult:
    phase_map: np.ndarray
    amplitude: float
    num_rows: int
    num_cols: int
    geometry_centers: np.ndarray
    geometry: Any


def build_workbench_phase_map(
    raw_config: Dict[str, Any],
    geometry_override: Optional[Dict[str, Any]] = None,
) -> RisWorkbenchResult:
    config = resolve_ris_lab_config(raw_config)
    if geometry_override:
        config = dict(config)
        geometry = dict(config.get("geometry", {}))
        geometry.update(geometry_override)
        config["geometry"] = geometry

    geometry_cfg = config["geometry"]
    experiment_cfg = config.get("experiment", {})

    frequency_hz = float(experiment_cfg.get("frequency_hz", 28_000_000_000.0))
    wavelength = _SPEED_OF_LIGHT_M_S / frequency_hz

    normal = np.array(geometry_cfg.get("normal", [1.0, 0.0, 0.0]), dtype=float)
    x_axis_hint = np.array(geometry_cfg.get("x_axis_hint", [0.0, 1.0, 0.0]), dtype=float)
    if np.linalg.norm(normal) > 0:
        normal = normal / np.linalg.norm(normal)
    if np.linalg.norm(x_axis_hint) > 0:
        x_axis_hint = x_axis_hint / np.linalg.norm(x_axis_hint)
    if not np.allclose(normal, [1.0, 0.0, 0.0], atol=1e-3) or not np.allclose(
        x_axis_hint, [0.0, 1.0, 0.0], atol=1e-3
    ):
        logger.warning(
            "RIS workbench geometry normal/x_axis_hint not aligned to +x/+y. "
            "Mapping assumes yz-plane ordering."
        )

    geometry = compute_element_centers(
        nx=int(geometry_cfg["nx"]),
        ny=int(geometry_cfg["ny"]),
        dx=float(geometry_cfg["dx"]),
        dy=float(geometry_cfg["dy"]),
        origin=geometry_cfg.get("origin"),
        normal=geometry_cfg.get("normal"),
        x_axis_hint=geometry_cfg.get("x_axis_hint"),
    )
    ris_center = _compute_ris_center(geometry)
    tx_pos = _compute_tx_position(
        geometry,
        ris_center,
        tx_distance_m=float(experiment_cfg.get("tx_distance_m", 0.4)),
        tx_angle_deg=_resolve_tx_angle_deg(experiment_cfg),
    )
    phase_map = _resolve_phase_map(config, geometry, wavelength, tx_pos, ris_center)

    amplitude = float(experiment_cfg.get("reflection_coeff", 1.0))
    return RisWorkbenchResult(
        phase_map=phase_map,
        amplitude=amplitude,
        num_rows=int(geometry_cfg["ny"]),
        num_cols=int(geometry_cfg["nx"]),
        geometry_centers=geometry.centers,
        geometry=geometry,
    )


def apply_workbench_to_ris(
    ris: Any,
    workbench: RisWorkbenchResult,
    mapping: Optional[Dict[str, Any]] = None,
    amplitude_override: Optional[float] = None,
) -> None:
    import tensorflow as tf

    mapping = mapping or {}
    tol = float(mapping.get("position_tol", 1e-6))
    phase_map = _map_phase_to_sionna_order(workbench.phase_map, workbench.geometry_centers, tol=tol)
    if mapping.get("flip_rows"):
        phase_map = np.flipud(phase_map)
    if mapping.get("flip_cols"):
        phase_map = np.fliplr(phase_map)

    if phase_map.shape != (ris.num_rows, ris.num_cols):
        raise ValueError(
            f"Phase map shape {phase_map.shape} does not match RIS "
            f"({ris.num_rows}, {ris.num_cols})"
        )

    values = np.tile(phase_map[None, :, :], (ris.num_modes, 1, 1))
    phase_dtype = ris.phase_profile.values.dtype
    amp_dtype = ris.amplitude_profile.values.dtype

    amplitude = workbench.amplitude if amplitude_override is None else float(amplitude_override)
    device = _tf_device_for_variant()
    if device:
        with tf.device(device):
            _assign_profile_values(ris.phase_profile, tf.cast(values, phase_dtype))
            _assign_profile_values(
                ris.amplitude_profile,
                tf.cast(np.full_like(values, amplitude, dtype=float), amp_dtype),
            )
    else:
        _assign_profile_values(ris.phase_profile, tf.cast(values, phase_dtype))
        _assign_profile_values(
            ris.amplitude_profile,
            tf.cast(np.full_like(values, amplitude, dtype=float), amp_dtype),
        )

def _ensure_xyz_list(value: Any, name: str) -> List[np.ndarray]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)) and len(value) == 3 and not isinstance(value[0], (list, tuple)):
        return [np.array(value, dtype=float)]
    if isinstance(value, (list, tuple)):
        coords = []
        for idx, item in enumerate(value):
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise ValueError(f"{name}[{idx}] must be a 3-element list")
            coords.append(np.array(item, dtype=float))
        return coords
    raise ValueError(f"{name} must be a 3-element list or list of 3-element lists")


def _load_manual_values(values: Any, name: str) -> np.ndarray:
    if values is None:
        raise ValueError(f"manual {name} values must be provided for manual profile")
    if isinstance(values, (str, Path)):
        path = Path(values)
        if not path.exists():
            raise FileNotFoundError(f"manual {name} values file not found: {path}")
        data = np.load(path)
        if isinstance(data, np.lib.npyio.NpzFile):
            raise ValueError(f"manual {name} values must be a .npy array, not .npz")
        return np.array(data)
    return np.array(values, dtype=float)


def _broadcast_profile(values: np.ndarray, num_modes: int, num_rows: int, num_cols: int, label: str) -> np.ndarray:
    if values.ndim == 2:
        if values.shape != (num_rows, num_cols):
            raise ValueError(f"{label} must be shape ({num_rows}, {num_cols}) or ({num_modes}, {num_rows}, {num_cols})")
        return np.tile(values[None, :, :], (num_modes, 1, 1))
    if values.ndim == 3:
        if values.shape != (num_modes, num_rows, num_cols):
            raise ValueError(f"{label} must be shape ({num_modes}, {num_rows}, {num_cols})")
        return values
    raise ValueError(f"{label} must be 2D or 3D array")


def _quantize_phase_values(values: Any, bits: Optional[int]) -> Any:
    if bits is None:
        return values
    bits_int = int(bits)
    if bits_int <= 0:
        return values
    import tensorflow as tf

    two_pi = tf.constant(2.0 * np.pi, dtype=values.dtype)
    levels = float(2 ** bits_int)
    step = two_pi / tf.constant(levels, dtype=values.dtype)
    wrapped = tf.math.floormod(values, two_pi)
    return tf.round(wrapped / step) * step


def _tf_device_for_variant() -> Optional[str]:
    try:
        import mitsuba as mi
        variant = mi.variant()
    except Exception:
        return None
    if variant and "cuda" in variant:
        return None
    return "/CPU:0"


def _apply_phase_profile(ris: Any, profile: Dict[str, Any], scene: Any | None = None) -> None:
    kind = profile.get("kind") or "flat"
    if kind not in _PHASE_PROFILE_KINDS:
        raise ValueError(f"Unsupported RIS profile kind '{kind}'")

    sources = _ensure_xyz_list(profile.get("sources"), "profile.sources")
    targets = _ensure_xyz_list(profile.get("targets"), "profile.targets")

    if profile.get("auto_aim") and scene is not None:
        try:
            tx = next(iter(scene.transmitters.values()))
            rx = next(iter(scene.receivers.values()))
            sources = [np.array(tx.position, dtype=float)]
            targets = [np.array(rx.position, dtype=float)]
        except Exception:
            pass

    if kind in {"flat", "uniform"}:
        import tensorflow as tf

        device = _tf_device_for_variant()
        zeros = np.zeros((ris.num_modes, ris.num_rows, ris.num_cols), dtype=float)
        if device:
            with tf.device(device):
                _assign_profile_values(ris.phase_profile, tf.cast(zeros, ris.phase_profile.values.dtype))
        else:
            _assign_profile_values(ris.phase_profile, tf.cast(zeros, ris.phase_profile.values.dtype))
    elif kind == "phase_gradient_reflector":
        if not sources or not targets:
            raise ValueError("phase_gradient_reflector requires profile.sources and profile.targets")
        ris.phase_gradient_reflector(sources, targets)
    elif kind == "focusing_lens":
        if not sources or not targets:
            raise ValueError("focusing_lens requires profile.sources and profile.targets")
        ris.focusing_lens(sources, targets)
    elif kind == "manual":
        import tensorflow as tf

        phase_values = _load_manual_values(profile.get("manual_phase_values"), "phase")
        amp_values = _load_manual_values(profile.get("manual_amp_values"), "amplitude")
        phase_values = _broadcast_profile(phase_values, ris.num_modes, ris.num_rows, ris.num_cols, "manual_phase_values")
        amp_values = _broadcast_profile(amp_values, ris.num_modes, ris.num_rows, ris.num_cols, "manual_amp_values")
        device = _tf_device_for_variant()
        if device:
            with tf.device(device):
                _assign_profile_values(ris.phase_profile, tf.cast(phase_values, ris.phase_profile.values.dtype))
                _assign_profile_values(ris.amplitude_profile, tf.cast(amp_values, ris.amplitude_profile.values.dtype))
        else:
            _assign_profile_values(ris.phase_profile, tf.cast(phase_values, ris.phase_profile.values.dtype))
            _assign_profile_values(ris.amplitude_profile, tf.cast(amp_values, ris.amplitude_profile.values.dtype))

    if profile.get("phase_bits") is not None:
        import tensorflow as tf

        device = _tf_device_for_variant()
        if device:
            with tf.device(device):
                phase_values = _quantize_phase_values(ris.phase_profile.values, profile.get("phase_bits"))
                _assign_profile_values(ris.phase_profile, tf.cast(phase_values, ris.phase_profile.values.dtype))
        else:
            phase_values = _quantize_phase_values(ris.phase_profile.values, profile.get("phase_bits"))
            _assign_profile_values(ris.phase_profile, tf.cast(phase_values, ris.phase_profile.values.dtype))

    amplitude = profile.get("amplitude")
    if amplitude is not None:
        import tensorflow as tf

        if isinstance(amplitude, (list, tuple)):
            if len(amplitude) != ris.num_modes:
                raise ValueError("profile.amplitude list length must match num_modes")
            base = np.array(amplitude, dtype=float)[:, None, None]
            values = np.tile(base, (1, ris.num_rows, ris.num_cols))
        else:
            values = np.full((ris.num_modes, ris.num_rows, ris.num_cols), float(amplitude), dtype=float)
        device = _tf_device_for_variant()
        if device:
            with tf.device(device):
                _assign_profile_values(ris.amplitude_profile, tf.cast(values, ris.amplitude_profile.values.dtype))
        else:
            _assign_profile_values(ris.amplitude_profile, tf.cast(values, ris.amplitude_profile.values.dtype))

    mode_powers = profile.get("mode_powers")
    if mode_powers is not None:
        ris.amplitude_profile.mode_powers = [float(v) for v in mode_powers]


def _build_ris_object(obj_cfg: Dict[str, Any]) -> Any:
    import sionna.rt as rt

    name = obj_cfg.get("name", "ris")
    position = np.array(obj_cfg.get("position", [0.0, 0.0, 0.0]), dtype=float)
    orientation = obj_cfg.get("orientation")
    look_at = obj_cfg.get("look_at")
    if orientation is None and look_at is None:
        orientation = [0.0, 0.0, 0.0]

    num_rows = int(obj_cfg.get("num_rows", 8))
    num_cols = int(obj_cfg.get("num_cols", 8))
    num_modes = int(obj_cfg.get("num_modes", 1))

    ris = rt.RIS(
        name=name,
        position=position,
        num_rows=num_rows,
        num_cols=num_cols,
        num_modes=num_modes,
        orientation=np.array(orientation, dtype=float) if orientation is not None else None,
        look_at=np.array(look_at, dtype=float) if look_at is not None else None,
    )
    return ris


def _ris_runtime_summary(ris: Any, profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": getattr(ris, "name", "ris"),
        "num_rows": int(getattr(ris, "num_rows", 0)),
        "num_cols": int(getattr(ris, "num_cols", 0)),
        "num_modes": int(getattr(ris, "num_modes", 0)),
        "profile_kind": profile.get("kind", "phase_gradient_reflector"),
        "mode_powers": profile.get("mode_powers"),
    }


def add_ris_from_config(scene: Any, cfg: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    ris_cfg = cfg.get("ris", {})
    if not isinstance(ris_cfg, dict) or not ris_cfg.get("enabled"):
        return None

    ris_objects_cfg = ris_cfg.get("objects")
    summaries: List[Dict[str, Any]] = []
    if isinstance(ris_objects_cfg, list) and ris_objects_cfg:
        logger.info("RIS enabled: %d objects", len(ris_objects_cfg))
        for obj_cfg in ris_objects_cfg:
            if not isinstance(obj_cfg, dict):
                raise ValueError("ris.objects entries must be mappings")
            profile_cfg = obj_cfg.get("profile", {}) or {}
            ris = _build_ris_object(obj_cfg)
            scene.add(ris)
            _apply_phase_profile(ris, profile_cfg, scene=scene)
            summary = _ris_runtime_summary(ris, profile_cfg)
            summaries.append(summary)
            logger.info(
                "RIS %s: %dx%d, modes=%d, profile=%s",
                summary["name"],
                summary["num_rows"],
                summary["num_cols"],
                summary["num_modes"],
                summary["profile_kind"],
            )
        return summaries

    # Backward-compatible workbench mode
    import sionna.rt as rt

    mode = ris_cfg.get("mode", "workbench")
    base_cfg = ris_cfg.get("sionna", {})
    name = base_cfg.get("name", "ris")
    position = np.array(base_cfg.get("position", [0.0, 0.0, 0.0]), dtype=float)
    orientation = base_cfg.get("orientation", [0.0, 0.0, 0.0])
    look_at = base_cfg.get("look_at")
    if look_at is not None:
        look_at = np.array(look_at, dtype=float)

    num_modes = int(base_cfg.get("num_modes", 1))

    workbench_cfg = ris_cfg.get("workbench", {})
    if mode == "workbench":
        config_path = workbench_cfg.get("config_path")
        if not config_path:
            raise ValueError("ris.workbench.config_path must be set when mode=workbench")
        from app.ris.ris_config import load_ris_lab_config

        ris_lab_cfg = load_ris_lab_config(config_path)
        geometry_override = workbench_cfg.get("geometry_override")
        workbench = build_workbench_phase_map(ris_lab_cfg, geometry_override=geometry_override)
        try:
            exp_freq = float(ris_lab_cfg.get("experiment", {}).get("frequency_hz", 0.0))
            scene_freq = float(getattr(scene, "frequency", 0.0))
            if exp_freq and scene_freq and abs(exp_freq - scene_freq) / exp_freq > 0.01:
                logger.warning(
                    "RIS workbench frequency %.3e Hz differs from scene frequency %.3e Hz",
                    exp_freq,
                    scene_freq,
                )
        except Exception:
            pass
        num_rows = int(base_cfg.get("num_rows", workbench.num_rows))
        num_cols = int(base_cfg.get("num_cols", workbench.num_cols))
    else:
        num_rows = int(base_cfg.get("num_rows", 8))
        num_cols = int(base_cfg.get("num_cols", 8))

    ris = rt.RIS(
        name=name,
        position=position,
        num_rows=num_rows,
        num_cols=num_cols,
        num_modes=num_modes,
        orientation=orientation,
        look_at=look_at,
    )

    if mode == "workbench":
        mapping = workbench_cfg.get("mapping", {})
        amplitude_override = workbench_cfg.get("amplitude")
        apply_workbench_to_ris(
            ris,
            workbench,
            mapping=mapping,
            amplitude_override=amplitude_override,
        )
    elif mode == "flat":
        import tensorflow as tf

        phase_values = tf.zeros(ris.phase_profile.values.shape, ris.phase_profile.values.dtype)
        _assign_profile_values(ris.phase_profile, phase_values)
        amp = float(ris_cfg.get("amplitude", 1.0))
        amp_values = tf.ones_like(ris.amplitude_profile.values) * tf.cast(
            amp, ris.amplitude_profile.values.dtype
        )
        _assign_profile_values(ris.amplitude_profile, amp_values)

    scene.add(ris)
    summaries.append(
        {
            "name": name,
            "num_rows": int(num_rows),
            "num_cols": int(num_cols),
            "num_modes": int(num_modes),
            "profile_kind": mode,
            "mode_powers": None,
        }
    )
    logger.info("RIS enabled: 1 object")
    logger.info("RIS %s: %dx%d, modes=%d, profile=%s", name, num_rows, num_cols, num_modes, mode)
    return summaries
