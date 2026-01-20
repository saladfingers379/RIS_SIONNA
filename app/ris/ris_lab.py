"""RIS Lab runners for pattern and validation modes."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.io import save_json
from app.ris.ris_config import resolve_and_snapshot_ris_lab_config
from app.ris.ris_core import (
    compute_element_centers,
    degrees_to_radians,
    quantize_phase,
    synthesize_custom_phase,
    synthesize_focusing_phase,
    synthesize_steering_phase,
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


def _resolve_phase_map(
    config: Dict[str, Any], geometry: Any, wavelength: float
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
        phase = synthesize_steering_phase(geometry.centers, wavelength, direction)
    elif mode == "focus":
        focal_point = params.get("focal_point")
        if focal_point is None:
            raise ValueError("focus control requires focal_point")
        phase = synthesize_focusing_phase(geometry.centers, wavelength, focal_point)
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


def _compute_array_response(
    centers: np.ndarray,
    phase_map: np.ndarray,
    frame: Any,
    wavelength: float,
    theta_deg: np.ndarray,
) -> np.ndarray:
    theta_rad = degrees_to_radians(np.array(theta_deg, dtype=float))
    directions = np.cos(theta_rad)[:, None] * frame.w + np.sin(theta_rad)[:, None] * frame.u
    centers_flat = centers.reshape(-1, 3)
    phase_flat = phase_map.reshape(-1)
    phase_incident = centers_flat @ directions.T
    total_phase = (2.0 * np.pi / float(wavelength)) * phase_incident + phase_flat[:, None]
    response = np.exp(1j * total_phase).sum(axis=0)
    return np.abs(response) ** 2


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


def _plot_phase_map(phase_map: np.ndarray, output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(phase_map, origin="lower", cmap="twilight")
    ax.set_title("RIS Phase Map [rad]")
    ax.set_xlabel("Element X")
    ax.set_ylabel("Element Y")
    fig.colorbar(im, ax=ax, label="Phase [rad]")
    fig.tight_layout()
    path = output_dir / "phase_map.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def _plot_pattern(theta_deg: np.ndarray, pattern_db: np.ndarray, output_dir: Path) -> Tuple[Path, Path]:
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
        fields = {name.strip() for name in reader.fieldnames}
        if "theta_deg" not in fields:
            raise ValueError("Reference CSV missing required column: theta_deg")
        if "pattern_db" not in fields and "pattern_linear" not in fields:
            raise ValueError("Reference CSV missing required pattern_db or pattern_linear column")

        theta_vals = []
        pattern_vals = []
        pattern_kind = "pattern_db" if "pattern_db" in fields else "pattern_linear"
        for row in reader:
            theta_vals.append(float(row["theta_deg"]))
            pattern_vals.append(float(row[pattern_kind]))
    return np.array(theta_vals, dtype=float), np.array(pattern_vals, dtype=float), pattern_kind


def _write_metrics(output_dir: Path, metrics: Dict[str, Any]) -> None:
    save_json(output_dir / "metrics.json", metrics)


def run_ris_lab(config_path: str, mode: str) -> Path:
    config, output_dir, summary = resolve_and_snapshot_ris_lab_config(config_path)
    output_dir = Path(output_dir)

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

    phase_map = _resolve_phase_map(config, geometry, wavelength)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _plot_phase_map(phase_map, plots_dir)
    np.save(data_dir / "phase_map.npy", phase_map)

    run_id = output_dir.name

    if mode == "pattern":
        sweep_cfg = config["pattern_mode"]["rx_sweep_deg"]
        theta_deg = np.arange(
            float(sweep_cfg["start"]),
            float(sweep_cfg["stop"]) + float(sweep_cfg["step"]) * 0.5,
            float(sweep_cfg["step"]),
        )
        linear = _compute_array_response(
            geometry.centers, phase_map, geometry.frame, wavelength, theta_deg
        )
        normalization = config["pattern_mode"].get("normalization", "peak_0db")
        linear_norm = _apply_normalization(linear, normalization)
        pattern_db = 10.0 * np.log10(linear_norm + _DB_FLOOR)
        np.save(data_dir / "theta_deg.npy", theta_deg)
        np.save(data_dir / "pattern_linear.npy", linear_norm)
        np.save(data_dir / "pattern_db.npy", pattern_db)
        _plot_pattern(theta_deg, pattern_db, plots_dir)

        peak_idx = int(np.argmax(pattern_db))
        metrics = {
            "run_id": run_id,
            "mode": mode,
            "output_dir": str(output_dir),
            "config_hash": summary["config"]["hash_sha256"],
            "normalization": normalization,
            "peak_angle_deg": float(theta_deg[peak_idx]),
            "peak_db": float(pattern_db[peak_idx]),
            "peak_linear": float(linear_norm[peak_idx]),
        }
    elif mode == "link":
        link_cfg = config.get("link_mode", {})
        rx_angle = float(link_cfg.get("rx_angle_deg", 0.0))
        linear = _compute_array_response(
            geometry.centers,
            phase_map,
            geometry.frame,
            wavelength,
            np.array([rx_angle], dtype=float),
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
    else:
        raise ValueError(f"Unsupported run mode: {mode}")

    _write_metrics(output_dir, metrics)
    logger.info("RIS Lab run_id=%s mode=%s output_dir=%s", run_id, mode, output_dir)
    return output_dir


def validate_ris_lab(config_path: str, ref_path: str) -> Path:
    config, output_dir, summary = resolve_and_snapshot_ris_lab_config(config_path)
    output_dir = Path(output_dir)

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

    phase_map = _resolve_phase_map(config, geometry, wavelength)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    _plot_phase_map(phase_map, plots_dir)

    ref_path = Path(ref_path)
    if not ref_path.exists():
        raise FileNotFoundError(f"Reference file not found: {ref_path}")
    if ref_path.suffix.lower() != ".csv":
        raise ValueError("Reference file must be a CSV for now")

    theta_ref, ref_vals, ref_kind = _load_reference_csv(ref_path)
    sim_linear = _compute_array_response(
        geometry.centers, phase_map, geometry.frame, wavelength, theta_ref
    )

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
    _write_metrics(output_dir, metrics)
    logger.info(
        "RIS Lab run_id=%s mode=validate output_dir=%s", output_dir.name, output_dir
    )
    return output_dir
