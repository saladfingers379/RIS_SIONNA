"""RIS Lab runners for pattern and validation modes."""

from __future__ import annotations

import csv
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.io import save_json
from app.ris.ris_config import resolve_and_snapshot_ris_lab_config
from app.ris.ris_core import (
    compute_element_centers,
    quantize_phase,
    synthesize_custom_phase,
    synthesize_focusing_phase,
    synthesize_reflectarray_phase,
    synthesize_uniform_phase,
)

logger = logging.getLogger(__name__)

_SPEED_OF_LIGHT_M_S = 299_792_458.0
_DB_FLOOR = 1e-12


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
                raise ValueError(
                    "steer control requires direction or azimuth_deg/elevation_deg"
                )
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


def _compute_received_power(
    centers: np.ndarray,
    phase_map: np.ndarray,
    frame: Any,
    wavelength: float,
    theta_deg: np.ndarray,
    tx_position: np.ndarray,
    ris_center: np.ndarray,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    tx_power_dbm: float,
    reflection_coeff: float,
    element_area_m2: float,
    tx_distance_m: float,
    rx_distance_m: float,
) -> np.ndarray:
    k = 2.0 * np.pi / float(wavelength)
    centers_flat = centers.reshape(-1, 3)

    tx_position = np.array(tx_position, dtype=float)
    ris_center = np.array(ris_center, dtype=float)

    # Tx->element distances
    rt = np.linalg.norm(centers_flat - tx_position[None, :], axis=1)
    d1_center = float(np.linalg.norm(tx_position - ris_center))
    if d1_center <= 0.0:
        raise ValueError("tx_distance_m must be > 0")

    # Element offset from RIS center (remove normal component)
    v_rel = centers_flat - ris_center
    v_normal = (v_rel @ frame.w)[:, None] * frame.w[None, :]
    d_nm = np.linalg.norm(v_rel - v_normal, axis=1)

    cos_theta_nm_t = np.abs((centers_flat - tx_position[None, :]) @ frame.w) / rt
    cos_theta_nm_t = np.clip(cos_theta_nm_t, 0.0, 1.0)
    cos_theta_nm_tx = (d1_center**2 + rt**2 - d_nm**2) / (2.0 * d1_center * rt)
    cos_theta_nm_tx = np.clip(cos_theta_nm_tx, 0.0, 1.0)

    # Gains (linear)
    Gt = 10.0 ** (float(tx_gain_dbi) / 10.0)
    Gr = 10.0 ** (float(rx_gain_dbi) / 10.0)
    Pt_W = 10.0 ** ((float(tx_power_dbm) - 30.0) / 10.0)

    alpha_t = (Gt / 2.0) - 1.0
    alpha_r = (Gr / 2.0) - 1.0

    theta_rad = np.deg2rad(np.array(theta_deg, dtype=float))
    directions_out = np.cos(theta_rad)[:, None] * frame.w + np.sin(theta_rad)[:, None] * frame.u
    rx_positions = ris_center[None, :] + rx_distance_m * directions_out

    gamma_on = float(reflection_coeff) * np.exp(1j * phase_map.reshape(-1))
    denom_tx = rt

    power = np.zeros(theta_rad.shape[0], dtype=float)
    for idx, rx_pos in enumerate(rx_positions):
        rr = np.linalg.norm(centers_flat - rx_pos[None, :], axis=1)
        d2_center = float(np.linalg.norm(rx_pos - ris_center))

        cos_theta_nm_r = np.abs((centers_flat - rx_pos[None, :]) @ frame.w) / rr
        cos_theta_nm_r = np.clip(cos_theta_nm_r, 0.0, 1.0)
        cos_theta_nm_rx = (d2_center**2 + rr**2 - d_nm**2) / (2.0 * d2_center * rr)
        cos_theta_nm_rx = np.clip(cos_theta_nm_rx, 0.0, 1.0)

        F_combine = (
            (cos_theta_nm_tx ** alpha_t)
            * cos_theta_nm_t
            * cos_theta_nm_r
            * (cos_theta_nm_rx ** alpha_r)
        )
        F_combine = np.maximum(F_combine, 0.0)

        phase_term = np.exp(-1j * k * (rt + rr))
        denom = denom_tx * rr

        sum_on = np.sum(np.sqrt(F_combine) * gamma_on / denom * phase_term)

        power[idx] = (
            Pt_W
            * Gt
            * Gr
            * (element_area_m2**2)
            / (16.0 * np.pi**2)
            * (np.abs(sum_on) ** 2)
        )

    return power


def _apply_normalization(linear: np.ndarray, mode: str | None) -> np.ndarray:
    if mode is None:
        return linear
    if mode == "peak_0db":
        peak = np.max(linear)
        return linear / peak if peak > 0 else linear
    if mode == "unit_power":
        mean = np.mean(linear)
        return linear / mean if mean > 0 else linear
    raise ValueError(f"Unsupported normalization mode: {mode}")


def _plot_phase_map(
    phase_map: np.ndarray,
    output_dir: Path,
    geometry: Any,
    quant_bits: Optional[int],
) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 5.2))

    if quant_bits == 1:
        cmap = plt.cm.get_cmap("bwr", 2)
        vmin, vmax = 0.0, np.pi
        ticks = [0.0, np.pi]
        tick_labels = ["0", "π"]
    elif quant_bits and quant_bits > 1:
        cmap = "hsv"
        vmin, vmax = 0.0, 2.0 * np.pi
        ticks = [0.0, np.pi, 2.0 * np.pi]
        tick_labels = ["0", "π", "2π"]
    else:
        cmap = "twilight"
        vmin, vmax = None, None
        ticks = None
        tick_labels = None

    centers = geometry.centers
    frame = geometry.frame
    origin = centers.reshape(-1, 3).mean(axis=0)
    u_coords = (centers - origin) @ frame.u
    v_coords = (centers - origin) @ frame.v

    extent = [
        float(u_coords.min() * 1000.0),
        float(u_coords.max() * 1000.0),
        float(v_coords.min() * 1000.0),
        float(v_coords.max() * 1000.0),
    ]

    im = ax.imshow(
        phase_map,
        origin="lower",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        extent=extent,
        aspect="equal",
    )
    ax.set_title("RIS Phase Map [rad]")
    ax.set_xlabel("u (mm)")
    ax.set_ylabel("v (mm)")
    cb = fig.colorbar(im, ax=ax, label="Phase [rad]")
    if ticks is not None:
        cb.set_ticks(ticks)
        cb.set_ticklabels(tick_labels)
    fig.tight_layout()
    path = output_dir / "phase_map.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def _plot_pattern(theta_deg: np.ndarray, pattern_db: np.ndarray, output_dir: Path) -> Tuple[Path, Path]:
    _validate_theta_pattern_lengths(theta_deg, pattern_db, "pattern_db")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(theta_deg, pattern_db, color="#005f73", linewidth=2.0)
    ax.set_title("RIS Pattern (Normalized)")
    ax.set_xlabel("Rx angle [deg]")
    ax.set_ylabel("Gain [dB]")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    cartesian_path = output_dir / "pattern_cartesian.png"
    fig.savefig(cartesian_path, dpi=200)
    plt.close(fig)

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="polar")
    ax.plot(np.deg2rad(theta_deg), pattern_db, color="#0a9396", linewidth=2.0)
    ax.set_title("RIS Pattern (Polar)")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    fig.tight_layout()
    polar_path = output_dir / "pattern_polar.png"
    fig.savefig(polar_path, dpi=200)
    plt.close(fig)
    return cartesian_path, polar_path


def _load_reference_csv(path: Path) -> Tuple[np.ndarray, np.ndarray, str]:
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Reference CSV must include header row")
        field_map = {name.strip(): name for name in reader.fieldnames}
        fields = set(field_map.keys())
        missing = []
        if "theta_deg" not in fields:
            missing.append("theta_deg")
        if "pattern_db" not in fields and "pattern_linear" not in fields:
            missing.append("pattern_db or pattern_linear")
        if missing:
            field_list = ", ".join(sorted(fields)) if fields else "(none)"
            missing_list = ", ".join(missing)
            raise ValueError(
                "Reference CSV missing required column(s): "
                f"{missing_list}. Found columns: {field_list}"
            )

        theta_vals = []
        pattern_vals = []
        pattern_kind = "pattern_db" if "pattern_db" in fields else "pattern_linear"
        theta_key = field_map["theta_deg"]
        pattern_key = field_map[pattern_kind]
        for row in reader:
            theta_vals.append(float(row[theta_key]))
            pattern_vals.append(float(row[pattern_key]))
    return np.array(theta_vals, dtype=float), np.array(pattern_vals, dtype=float), pattern_kind


def _load_reference_npz(path: Path) -> Tuple[np.ndarray, np.ndarray, str]:
    with np.load(path, allow_pickle=False) as data:
        keys = set(data.files)
        missing = []
        if "theta_deg" not in keys:
            missing.append("theta_deg")
        if "pattern_db" not in keys and "pattern_linear" not in keys:
            missing.append("pattern_db or pattern_linear")
        if missing:
            key_list = ", ".join(sorted(keys)) if keys else "(none)"
            missing_list = ", ".join(missing)
            raise ValueError(
                "Reference NPZ missing required key(s): "
                f"{missing_list}. Expected keys: theta_deg + (pattern_db or pattern_linear). "
                f"Found keys: {key_list}"
            )
        pattern_kind = "pattern_db" if "pattern_db" in keys else "pattern_linear"
        theta = np.asarray(data["theta_deg"], dtype=float).reshape(-1)
        pattern = np.asarray(data[pattern_kind], dtype=float).reshape(-1)
    return theta, pattern, pattern_kind


def _load_reference_mat(path: Path) -> Tuple[np.ndarray, np.ndarray, str]:
    try:
        from scipy.io import loadmat
    except Exception as exc:
        raise RuntimeError(
            "scipy is required for MAT reference imports. "
            "Install with: pip install 'ris_sionna[mat]'"
        ) from exc

    data = loadmat(path)
    keys = {key for key in data.keys() if not key.startswith("__")}
    missing = []
    if "theta_deg" not in keys:
        missing.append("theta_deg")
    if "pattern_db" not in keys and "pattern_linear" not in keys:
        missing.append("pattern_db or pattern_linear")
    if missing:
        key_list = ", ".join(sorted(keys)) if keys else "(none)"
        missing_list = ", ".join(missing)
        raise ValueError(
            "Reference MAT missing required key(s): "
            f"{missing_list}. Expected keys: theta_deg + (pattern_db or pattern_linear). "
            f"Found keys: {key_list}"
        )
    pattern_kind = "pattern_db" if "pattern_db" in keys else "pattern_linear"
    theta = np.asarray(data["theta_deg"], dtype=float).reshape(-1)
    pattern = np.asarray(data[pattern_kind], dtype=float).reshape(-1)
    return theta, pattern, pattern_kind


def _validate_theta_pattern_lengths(
    theta_deg: np.ndarray, pattern: np.ndarray, pattern_name: str
) -> None:
    if len(theta_deg) != len(pattern):
        raise ValueError(
            "theta_deg length does not match "
            f"{pattern_name} length: {len(theta_deg)} != {len(pattern)}"
        )


def _compute_sidelobe_metrics(
    theta_deg: np.ndarray, pattern_db: np.ndarray
) -> Dict[str, Any]:
    _validate_theta_pattern_lengths(theta_deg, pattern_db, "pattern_db")
    if len(pattern_db) < 2:
        return {
            "sidelobe_level_db": None,
            "sidelobe_peak_db": None,
            "sidelobe_definition": "undefined for fewer than 2 samples",
        }
    peak_idx = int(np.argmax(pattern_db))
    sidelobe_mask = np.ones_like(pattern_db, dtype=bool)
    sidelobe_mask[peak_idx] = False
    sidelobe_peak_db = float(np.max(pattern_db[sidelobe_mask]))
    peak_db = float(pattern_db[peak_idx])
    return {
        "sidelobe_level_db": float(peak_db - sidelobe_peak_db),
        "sidelobe_peak_db": sidelobe_peak_db,
        "sidelobe_definition": "peak_db - max(pattern_db excluding peak index)",
    }


def _write_metrics(output_dir: Path, metrics: Dict[str, Any]) -> None:
    save_json(output_dir / "metrics.json", metrics)


def _write_progress(
    progress_path: Path,
    steps: list[str],
    step_index: int,
    status: str,
    error: str | None = None,
) -> None:
    total = len(steps)
    step_name = steps[step_index] if step_index < total else "Complete"
    payload = {
        "status": status,
        "step_index": step_index,
        "step_name": step_name,
        "total_steps": total,
        "progress": min(step_index / total, 1.0) if total else 1.0,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if error:
        payload["error"] = error
    save_json(progress_path, payload)


def run_ris_lab(config_path: str, mode: str) -> Path:
    config, output_dir, summary = resolve_and_snapshot_ris_lab_config(config_path)
    output_dir = Path(output_dir)
    progress_path = output_dir / "progress.json"
    if mode == "pattern":
        steps = ["Initialize", "Resolve phase map", "Compute pattern", "Write metrics"]
    elif mode == "link":
        steps = ["Initialize", "Resolve phase map", "Compute link", "Write metrics"]
    else:
        raise ValueError(f"Unsupported run mode: {mode}")

    step_index = 0
    _write_progress(progress_path, steps, step_index, "running")
    try:
        geometry_cfg = config["geometry"]
        geometry = compute_element_centers(
            nx=int(geometry_cfg["nx"]),
            ny=int(geometry_cfg["ny"]),
            dx=float(geometry_cfg["dx"]),
            dy=float(geometry_cfg["dy"]),
            origin=geometry_cfg.get("origin"),
            normal=geometry_cfg.get("normal"),
            x_axis_hint=geometry_cfg.get("x_axis_hint"),
        )
        frequency_hz = float(config["experiment"]["frequency_hz"])
        wavelength = _SPEED_OF_LIGHT_M_S / frequency_hz

        experiment_cfg = config.get("experiment", {})
        tx_angle_deg = _resolve_tx_angle_deg(experiment_cfg)
        tx_distance_m = float(experiment_cfg.get("tx_distance_m", 0.4))
        rx_distance_m = float(experiment_cfg.get("rx_distance_m", 2.0))
        tx_gain_dbi = float(experiment_cfg.get("tx_gain_dbi", 15.0))
        rx_gain_dbi = float(experiment_cfg.get("rx_gain_dbi", 22.0))
        tx_power_dbm = float(experiment_cfg.get("tx_power_dbm", 28.0))
        reflection_coeff = float(experiment_cfg.get("reflection_coeff", 0.84))
        if experiment_cfg.get("element_area_m2") is not None:
            element_area_m2 = float(experiment_cfg["element_area_m2"])
        elif experiment_cfg.get("element_size_m") is not None:
            size = float(experiment_cfg["element_size_m"])
            element_area_m2 = size * size
        else:
            element_area_m2 = float(geometry_cfg["dx"]) * float(geometry_cfg["dy"])

        ris_center = _compute_ris_center(geometry)
        tx_position = _compute_tx_position(geometry, ris_center, tx_distance_m, tx_angle_deg)

        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        phase_map = _resolve_phase_map(config, geometry, wavelength, tx_position, ris_center)
        plots_dir = output_dir / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)
        data_dir = output_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        quant_bits = config.get("quantization", {}).get("bits")
        _plot_phase_map(phase_map, plots_dir, geometry, quant_bits)
        np.save(data_dir / "phase_map.npy", phase_map)

        run_id = output_dir.name

        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        if mode == "pattern":
            sweep_cfg = config["pattern_mode"]["rx_sweep_deg"]
            theta_deg = np.arange(
                float(sweep_cfg["start"]),
                float(sweep_cfg["stop"]) + float(sweep_cfg["step"]) * 0.5,
                float(sweep_cfg["step"]),
            )
            linear = _compute_received_power(
                geometry.centers,
                phase_map,
                geometry.frame,
                wavelength,
                theta_deg,
                tx_position,
                ris_center,
                tx_gain_dbi,
                rx_gain_dbi,
                tx_power_dbm,
                reflection_coeff,
                element_area_m2,
                tx_distance_m,
                rx_distance_m,
            )
            normalization = config["pattern_mode"].get("normalization", "peak_0db")
            linear_norm = _apply_normalization(linear, normalization)
            pattern_db = 10.0 * np.log10(linear_norm + _DB_FLOOR)
            _validate_theta_pattern_lengths(theta_deg, linear_norm, "pattern_linear")
            _validate_theta_pattern_lengths(theta_deg, pattern_db, "pattern_db")
            np.save(data_dir / "theta_deg.npy", theta_deg)
            np.save(data_dir / "pattern_linear.npy", linear_norm)
            np.save(data_dir / "pattern_db.npy", pattern_db)
            _plot_pattern(theta_deg, pattern_db, plots_dir)

            peak_idx = int(np.argmax(pattern_db))
            sidelobe_metrics = _compute_sidelobe_metrics(theta_deg, pattern_db)
            metrics = {
                "run_id": run_id,
                "mode": mode,
                "output_dir": str(output_dir),
                "config_hash": summary["config"]["hash_sha256"],
                "normalization": normalization,
                "peak_angle_deg": float(theta_deg[peak_idx]),
                "peak_db": float(pattern_db[peak_idx]),
                "peak_linear": float(linear_norm[peak_idx]),
                **sidelobe_metrics,
            }
        elif mode == "link":
            link_cfg = config.get("link_mode", {})
            rx_angle = float(link_cfg.get("rx_angle_deg", 0.0))
            linear = _compute_received_power(
                geometry.centers,
                phase_map,
                geometry.frame,
                wavelength,
                np.array([rx_angle], dtype=float),
                tx_position,
                ris_center,
                tx_gain_dbi,
                rx_gain_dbi,
                tx_power_dbm,
                reflection_coeff,
                element_area_m2,
                tx_distance_m,
                rx_distance_m,
            )
            metrics = {
                "run_id": run_id,
                "mode": mode,
                "output_dir": str(output_dir),
                "config_hash": summary["config"]["hash_sha256"],
                "rx_angle_deg": rx_angle,
                "link_gain_linear": float(linear[0]),
                "link_gain_db": float(10.0 * np.log10(linear[0] + _DB_FLOOR)),
            }
        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        _write_metrics(output_dir, metrics)
        _write_progress(progress_path, steps, len(steps), "completed")
        logger.info("RIS Lab run_id=%s mode=%s output_dir=%s", run_id, mode, output_dir)
        return output_dir
    except Exception as exc:
        logger.exception("RIS Lab run failed")
        _write_progress(progress_path, steps, step_index, "failed", error=str(exc))
        raise


def validate_ris_lab(config_path: str, ref_path: str) -> Path:
    config, output_dir, summary = resolve_and_snapshot_ris_lab_config(config_path)
    output_dir = Path(output_dir)
    progress_path = output_dir / "progress.json"
    steps = [
        "Initialize",
        "Resolve phase map",
        "Load reference",
        "Compute metrics",
        "Write metrics",
    ]
    step_index = 0
    _write_progress(progress_path, steps, step_index, "running")

    try:
        geometry_cfg = config["geometry"]
        geometry = compute_element_centers(
            nx=int(geometry_cfg["nx"]),
            ny=int(geometry_cfg["ny"]),
            dx=float(geometry_cfg["dx"]),
            dy=float(geometry_cfg["dy"]),
            origin=geometry_cfg.get("origin"),
            normal=geometry_cfg.get("normal"),
            x_axis_hint=geometry_cfg.get("x_axis_hint"),
        )
        frequency_hz = float(config["experiment"]["frequency_hz"])
        wavelength = _SPEED_OF_LIGHT_M_S / frequency_hz

        experiment_cfg = config.get("experiment", {})
        tx_angle_deg = _resolve_tx_angle_deg(experiment_cfg)
        tx_distance_m = float(experiment_cfg.get("tx_distance_m", 0.4))
        rx_distance_m = float(experiment_cfg.get("rx_distance_m", 2.0))
        tx_gain_dbi = float(experiment_cfg.get("tx_gain_dbi", 15.0))
        rx_gain_dbi = float(experiment_cfg.get("rx_gain_dbi", 22.0))
        tx_power_dbm = float(experiment_cfg.get("tx_power_dbm", 28.0))
        reflection_coeff = float(experiment_cfg.get("reflection_coeff", 0.84))
        if experiment_cfg.get("element_area_m2") is not None:
            element_area_m2 = float(experiment_cfg["element_area_m2"])
        elif experiment_cfg.get("element_size_m") is not None:
            size = float(experiment_cfg["element_size_m"])
            element_area_m2 = size * size
        else:
            element_area_m2 = float(geometry_cfg["dx"]) * float(geometry_cfg["dy"])

        ris_center = _compute_ris_center(geometry)
        tx_position = _compute_tx_position(geometry, ris_center, tx_distance_m, tx_angle_deg)

        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        phase_map = _resolve_phase_map(config, geometry, wavelength, tx_position, ris_center)
        plots_dir = output_dir / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)
        quant_bits = config.get("quantization", {}).get("bits")
        _plot_phase_map(phase_map, plots_dir, geometry, quant_bits)

        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        ref_path = Path(ref_path)
        if not ref_path.exists():
            raise FileNotFoundError(f"Reference file not found: {ref_path}")
        suffix = ref_path.suffix.lower()
        if suffix not in {".csv", ".npz", ".mat"}:
            raise ValueError("Reference file must be a CSV, NPZ, or MAT")

        if suffix == ".csv":
            theta_ref, ref_vals, ref_kind = _load_reference_csv(ref_path)
        elif suffix == ".npz":
            theta_ref, ref_vals, ref_kind = _load_reference_npz(ref_path)
        else:
            theta_ref, ref_vals, ref_kind = _load_reference_mat(ref_path)
        sim_linear = _compute_received_power(
            geometry.centers,
            phase_map,
            geometry.frame,
            wavelength,
            theta_ref,
            tx_position,
            ris_center,
            tx_gain_dbi,
            rx_gain_dbi,
            tx_power_dbm,
            reflection_coeff,
            element_area_m2,
            tx_distance_m,
            rx_distance_m,
        )

        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        normalization = config.get("validation", {}).get(
            "normalization", config["pattern_mode"].get("normalization", "peak_0db")
        )
        sim_linear_norm = _apply_normalization(sim_linear, normalization)
        sim_db = 10.0 * np.log10(sim_linear_norm + _DB_FLOOR)

        if ref_kind == "pattern_db":
            ref_linear = 10.0 ** (ref_vals / 10.0)
        else:
            ref_linear = ref_vals
        ref_linear_norm = _apply_normalization(ref_linear, normalization)
        ref_db = 10.0 * np.log10(ref_linear_norm + _DB_FLOOR)

        rmse_db = float(np.sqrt(np.mean((sim_db - ref_db) ** 2)))
        sim_peak_idx = int(np.argmax(sim_db))
        ref_peak_idx = int(np.argmax(ref_db))
        peak_angle_error = float(abs(theta_ref[sim_peak_idx] - theta_ref[ref_peak_idx]))
        peak_db_error = float(abs(sim_db[sim_peak_idx] - ref_db[ref_peak_idx]))

        thresholds = config.get("validation", {})
        rmse_max = float(thresholds.get("rmse_db_max", 2.0))
        peak_angle_max = float(thresholds.get("peak_angle_err_deg_max", 2.0))
        peak_db_max = float(thresholds.get("peak_db_err_max", 1.5))
        passed = rmse_db <= rmse_max and peak_angle_error <= peak_angle_max and peak_db_error <= peak_db_max

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(theta_ref, ref_db, color="#9b2226", linewidth=2.0, label="Reference")
        ax.plot(theta_ref, sim_db, color="#005f73", linewidth=2.0, label="Sim")
        ax.set_title("RIS Validation Overlay")
        ax.set_xlabel("Rx angle [deg]")
        ax.set_ylabel("Gain [dB]")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(plots_dir / "validation_overlay.png", dpi=200)
        plt.close(fig)

        metrics = {
            "run_id": output_dir.name,
            "mode": "validate",
            "output_dir": str(output_dir),
            "config_hash": summary["config"]["hash_sha256"],
            "reference_path": str(ref_path),
            "normalization": normalization,
            "rmse_db": rmse_db,
            "peak_angle_error_deg": peak_angle_error,
            "peak_db_error": peak_db_error,
            "thresholds": {
                "rmse_db_max": rmse_max,
                "peak_angle_err_deg_max": peak_angle_max,
                "peak_db_err_max": peak_db_max,
            },
            "passed": bool(passed),
        }
        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        _write_metrics(output_dir, metrics)
        _write_progress(progress_path, steps, len(steps), "completed")
        logger.info(
            "RIS Lab run_id=%s mode=validate output_dir=%s", output_dir.name, output_dir
        )
        return output_dir
    except Exception as exc:
        logger.exception("RIS Lab validation failed")
        _write_progress(progress_path, steps, step_index, "failed", error=str(exc))
        raise
