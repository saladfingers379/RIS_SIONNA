"""RIS comparison runner: QUB model (Machado) vs optional Sionna RT."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.io import save_json
from app.metrics import compute_path_metrics
from app.ris.ris_config import resolve_and_snapshot_ris_lab_config
from app.ris.ris_core import compute_element_centers
from app.ris.ris_lab import (
    _DB_FLOOR,
    _SPEED_OF_LIGHT_M_S,
    _apply_normalization,
    _compute_received_power,
    _compute_ris_center,
    _compute_tx_position,
    _plot_phase_map,
    _resolve_phase_map,
    _resolve_tx_angle_deg,
    _write_progress,
)
from app.ris.ris_sionna import apply_workbench_to_ris, build_workbench_phase_map
from app.utils.system import (
    assert_mitsuba_variant,
    configure_tensorflow_for_mitsuba_variant,
    configure_tensorflow_memory_growth,
    select_mitsuba_variant,
)

logger = logging.getLogger(__name__)


def _write_metrics(output_dir: Path, metrics: Dict[str, Any]) -> None:
    save_json(output_dir / "metrics.json", metrics)


def _curve_metrics(theta_deg: np.ndarray, a_db: np.ndarray, b_db: np.ndarray) -> Dict[str, Optional[float]]:
    mask = np.isfinite(a_db) & np.isfinite(b_db)
    if not np.any(mask):
        return {
            "rmse_db": None,
            "mean_bias_db": None,
            "peak_angle_error_deg": None,
            "peak_db_error": None,
        }
    a = a_db[mask]
    b = b_db[mask]
    theta = theta_deg[mask]
    peak_a = int(np.argmax(a))
    peak_b = int(np.argmax(b))
    return {
        "rmse_db": float(np.sqrt(np.mean((a - b) ** 2))),
        "mean_bias_db": float(np.mean(a - b)),
        "peak_angle_error_deg": float(abs(theta[peak_a] - theta[peak_b])),
        "peak_db_error": float(abs(a[peak_a] - b[peak_b])),
    }


def _sample_angles(theta_deg: np.ndarray, n: int) -> np.ndarray:
    n_clamped = max(3, min(int(n), int(theta_deg.size)))
    if n_clamped >= theta_deg.size:
        return np.array(theta_deg, dtype=float)
    idx = np.linspace(0, theta_deg.size - 1, n_clamped).round().astype(int)
    return np.array(theta_deg[idx], dtype=float)


def _aggregate_coverage_cells(path_gain: Any, mode: str) -> float:
    values = np.asarray(path_gain, dtype=float).reshape(-1)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan")
    mode_l = str(mode).strip().lower()
    if mode_l == "mean":
        return float(np.mean(finite))
    if mode_l == "median":
        return float(np.median(finite))
    return float(np.max(finite))


def _sionna_path_gain_curve(
    config: Dict[str, Any],
    theta_deg: np.ndarray,
    ris_center: np.ndarray,
    tx_position: np.ndarray,
    rx_distance_m: float,
    *,
    num_angles: int,
    include_paths: bool,
    include_coverage: bool,
) -> Dict[str, Any]:
    sionna_cfg = (config.get("compare") or {}).get("sionna", {}) or {}
    prefer_gpu = bool(sionna_cfg.get("prefer_gpu", True))
    forced_variant = str(sionna_cfg.get("forced_variant", "auto"))
    tf_mode = str(sionna_cfg.get("tensorflow_import", "auto"))
    path_samples = int(sionna_cfg.get("path_num_samples", 4096))
    cov_samples = int(sionna_cfg.get("coverage_num_samples", 20000))
    cov_cell_m = float(sionna_cfg.get("coverage_cell_size_m", 0.25))
    cov_window_cells = int(sionna_cfg.get("coverage_window_cells", 5))
    cov_aggregation = str(sionna_cfg.get("coverage_aggregation", "max"))
    cov_isolate_ris = bool(sionna_cfg.get("coverage_isolate_ris", True))
    max_depth = int(sionna_cfg.get("max_depth", 1))
    min_num_angles = int(sionna_cfg.get("min_num_angles", 21))
    if include_coverage and num_angles < min_num_angles:
        logger.warning(
            "num_angles=%s is too low for stable coverage_map; raising to %s",
            num_angles,
            min(min_num_angles, int(theta_deg.size)),
        )
        num_angles = min(min_num_angles, int(theta_deg.size))

    out: Dict[str, Any] = {
        "enabled": True,
        "selected_variant": None,
        "rt_backend": None,
        "theta_sampled_deg": [],
        "path_gain_linear_compute_paths": None,
        "path_gain_linear_coverage_map": None,
        "coverage_isolate_ris": cov_isolate_ris,
        "coverage_aggregation": cov_aggregation,
        "coverage_window_cells": cov_window_cells,
        "errors": [],
    }

    try:
        variant = select_mitsuba_variant(
            prefer_gpu=prefer_gpu,
            forced_variant=forced_variant,
            require_cuda=False,
        )
        assert_mitsuba_variant(variant, context="ris_compare")
        out["selected_variant"] = variant
        out["rt_backend"] = "cuda/optix" if "cuda" in (variant or "") else "cpu/llvm"
    except Exception as exc:
        out["errors"].append(f"variant selection failed: {exc}")
        return out

    try:
        configure_tensorflow_for_mitsuba_variant(out["selected_variant"])
        configure_tensorflow_memory_growth(mode=tf_mode)
    except Exception:
        pass

    try:
        import sionna.rt as rt  # pylint: disable=import-error
    except Exception as exc:
        out["errors"].append(f"sionna.rt import failed: {exc}")
        return out

    sample_theta = _sample_angles(theta_deg, num_angles)
    out["theta_sampled_deg"] = sample_theta.tolist()
    path_curve = np.full(sample_theta.shape, np.nan, dtype=float)
    cov_curve = np.full(sample_theta.shape, np.nan, dtype=float)
    cov_window_cells = max(3, cov_window_cells)
    if cov_window_cells % 2 == 0:
        cov_window_cells += 1
    cov_size_m = cov_cell_m * float(cov_window_cells)

    try:
        scene = rt.load_scene()
        scene.frequency = float(config["experiment"]["frequency_hz"])
        scene.tx_array = rt.PlanarArray(
            num_rows=1,
            num_cols=1,
            vertical_spacing=0.5,
            horizontal_spacing=0.5,
            pattern="iso",
            polarization="V",
        )
        scene.rx_array = rt.PlanarArray(
            num_rows=1,
            num_cols=1,
            vertical_spacing=0.5,
            horizontal_spacing=0.5,
            pattern="iso",
            polarization="V",
        )
        tx_power_dbm = float(config["experiment"].get("tx_power_dbm", 28.0))
        tx = rt.Transmitter(name="tx", position=np.array(tx_position, dtype=float), power_dbm=tx_power_dbm)
        rx = rt.Receiver(name="rx", position=np.array(ris_center, dtype=float))
        scene.add(tx)
        scene.add(rx)

        wb = build_workbench_phase_map(config)
        ris = rt.RIS(
            name="ris",
            position=np.array(ris_center, dtype=float),
            num_rows=int(wb.num_rows),
            num_cols=int(wb.num_cols),
            num_modes=1,
            orientation=np.array([0.0, 0.0, 0.0], dtype=float),
        )
        scene.add(ris)
        apply_workbench_to_ris(ris, wb)
    except Exception as exc:
        out["errors"].append(f"sionna scene build failed: {exc}")
        return out

    frame = compute_element_centers(
        nx=int(config["geometry"]["nx"]),
        ny=int(config["geometry"]["ny"]),
        dx=float(config["geometry"]["dx"]),
        dy=float(config["geometry"]["dy"]),
        origin=config["geometry"].get("origin"),
        normal=config["geometry"].get("normal"),
        x_axis_hint=config["geometry"].get("x_axis_hint"),
    ).frame
    dirs = np.cos(np.deg2rad(sample_theta))[:, None] * frame.w + np.sin(np.deg2rad(sample_theta))[:, None] * frame.u
    rx_positions = np.array(ris_center, dtype=float)[None, :] + float(rx_distance_m) * dirs

    for idx, rx_pos in enumerate(rx_positions):
        try:
            rx.position = np.array(rx_pos, dtype=float)
        except Exception:
            pass

        if include_paths:
            try:
                paths = scene.compute_paths(
                    max_depth=max_depth,
                    method="fibonacci",
                    num_samples=path_samples,
                    los=False,
                    reflection=False,
                    diffraction=False,
                    scattering=False,
                    ris=True,
                )
                m = compute_path_metrics(paths, tx_power_dbm=tx_power_dbm, scene=scene)
                pg_lin = m.get("ris_path_gain_linear")
                if pg_lin is None:
                    pg_lin = m.get("total_path_gain_linear")
                if pg_lin is not None:
                    path_curve[idx] = max(float(pg_lin), 0.0)
            except Exception as exc:
                out["errors"].append(f"compute_paths theta={float(sample_theta[idx]):.2f}: {exc}")

        if include_coverage:
            try:
                cov_on = scene.coverage_map(
                    cm_center=[float(rx_pos[0]), float(rx_pos[1]), float(rx_pos[2])],
                    cm_orientation=[0.0, 0.0, 0.0],
                    cm_size=[cov_size_m, cov_size_m],
                    cm_cell_size=[cov_cell_m, cov_cell_m],
                    num_samples=cov_samples,
                    max_depth=max_depth,
                    los=True,
                    reflection=True,
                    diffraction=False,
                    scattering=False,
                    ris=True,
                )
                pg_on = np.asarray(cov_on.path_gain, dtype=float)
                if cov_isolate_ris:
                    cov_off = scene.coverage_map(
                        cm_center=[float(rx_pos[0]), float(rx_pos[1]), float(rx_pos[2])],
                        cm_orientation=[0.0, 0.0, 0.0],
                        cm_size=[cov_size_m, cov_size_m],
                        cm_cell_size=[cov_cell_m, cov_cell_m],
                        num_samples=cov_samples,
                        max_depth=max_depth,
                        los=True,
                        reflection=True,
                        diffraction=False,
                        scattering=False,
                        ris=False,
                    )
                    pg_off = np.asarray(cov_off.path_gain, dtype=float)
                    pg_use = np.maximum(pg_on - pg_off, 0.0)
                else:
                    pg_use = pg_on
                cov_curve[idx] = _aggregate_coverage_cells(pg_use, cov_aggregation)
            except Exception as exc:
                out["errors"].append(f"coverage_map theta={float(sample_theta[idx]):.2f}: {exc}")

    def _interp_to_full(sample: np.ndarray) -> np.ndarray:
        valid = np.isfinite(sample)
        if np.sum(valid) < 2:
            return np.full(theta_deg.shape, np.nan, dtype=float)
        return np.interp(theta_deg, sample_theta[valid], sample[valid], left=np.nan, right=np.nan)

    if include_paths:
        valid_path = np.isfinite(path_curve) & (path_curve > 0.0)
        if np.sum(valid_path) < 2:
            out["errors"].append("compute_paths produced fewer than two positive samples; omitting curve")
        else:
            out["path_gain_linear_compute_paths"] = _interp_to_full(path_curve).tolist()
    if include_coverage:
        valid_cov = np.isfinite(cov_curve) & (cov_curve > 0.0)
        if np.sum(valid_cov) < 2:
            out["errors"].append("coverage_map produced fewer than two positive RIS samples; omitting curve")
        else:
            out["path_gain_linear_coverage_map"] = _interp_to_full(cov_curve).tolist()
    return out


def _plot_overlay(
    theta_deg: np.ndarray,
    curves_db: Dict[str, Optional[np.ndarray]],
    output_path: Path,
    title: str,
    ylabel: str,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = {
        "qub_model": "#005f73",
        "sionna_compute_paths": "#0a9396",
        "sionna_coverage_map": "#9b2226",
    }
    for name, values in curves_db.items():
        if values is None:
            continue
        arr = np.asarray(values, dtype=float)
        if not np.any(np.isfinite(arr)):
            continue
        ax.plot(theta_deg, arr, linewidth=2.0, label=name, color=colors.get(name))
    ax.set_title(title)
    ax.set_xlabel("Rx angle [deg]")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    if ax.lines:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _plot_error(
    theta_deg: np.ndarray,
    qub_norm_db: np.ndarray,
    sionna_paths_norm_db: Optional[np.ndarray],
    sionna_cov_norm_db: Optional[np.ndarray],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    any_curve = False
    if sionna_paths_norm_db is not None:
        ax.plot(
            theta_deg,
            qub_norm_db - sionna_paths_norm_db,
            color="#0a9396",
            linewidth=2.0,
            label="qub_model - sionna_compute_paths",
        )
        any_curve = True
    if sionna_cov_norm_db is not None:
        ax.plot(
            theta_deg,
            qub_norm_db - sionna_cov_norm_db,
            color="#9b2226",
            linewidth=2.0,
            label="qub_model - sionna_coverage_map",
        )
        any_curve = True
    ax.axhline(0.0, color="#475569", linewidth=1.0, linestyle="--")
    if not any_curve:
        ax.text(
            0.5,
            0.5,
            "No Sionna curve available for error comparison",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=11,
            color="#334155",
        )
    ax.set_title("QUB vs Sionna Error")
    ax.set_xlabel("Rx angle [deg]")
    ax.set_ylabel("Delta Gain [dB]")
    ax.grid(True, alpha=0.3)
    if any_curve:
        ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def run_ris_model_compare(config_path: str) -> Path:
    config, output_dir, summary = resolve_and_snapshot_ris_lab_config(config_path)
    output_dir = Path(output_dir)
    progress_path = output_dir / "progress.json"
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    compare_cfg = config.get("compare", {}) or {}
    sionna_cfg = compare_cfg.get("sionna", {}) or {}

    steps = [
        "Initialize",
        "Resolve phase map",
        "Run QUB model",
        "Run Sionna models",
        "Write artifacts",
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
        quant_bits = config.get("quantization", {}).get("bits")
        _plot_phase_map(phase_map, plots_dir, geometry, quant_bits)
        np.save(data_dir / "phase_map.npy", phase_map)

        sweep_cfg = config["pattern_mode"]["rx_sweep_deg"]
        theta_deg = np.arange(
            float(sweep_cfg["start"]),
            float(sweep_cfg["stop"]) + float(sweep_cfg["step"]) * 0.5,
            float(sweep_cfg["step"]),
        )

        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        qub_linear = _compute_received_power(
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

        sionna_enabled = bool(sionna_cfg.get("enabled", False))
        include_paths = bool(sionna_cfg.get("compute_paths", True))
        include_coverage = bool(sionna_cfg.get("coverage_map", True))
        sionna_out: Dict[str, Any] = {"enabled": False, "errors": []}
        if sionna_enabled and (include_paths or include_coverage):
            step_index += 1
            _write_progress(progress_path, steps, step_index, "running")
            default_num_angles = max(25, min(int(theta_deg.size), 91))
            sionna_out = _sionna_path_gain_curve(
                config,
                theta_deg,
                ris_center,
                tx_position,
                rx_distance_m,
                num_angles=int(sionna_cfg.get("num_angles", default_num_angles)),
                include_paths=include_paths,
                include_coverage=include_coverage,
            )
        else:
            step_index += 1
            _write_progress(progress_path, steps, step_index, "running")

        normalization = compare_cfg.get(
            "normalization",
            config.get("pattern_mode", {}).get("normalization", "peak_0db"),
        )
        if normalization in {"", "none", None}:
            normalization = None

        qub_norm = _apply_normalization(qub_linear, normalization)
        qub_norm_db = 10.0 * np.log10(qub_norm + _DB_FLOOR)
        qub_abs_db = 10.0 * np.log10(qub_linear + _DB_FLOOR)

        sionna_paths_lin = None
        sionna_cov_lin = None
        sionna_paths_lin_aligned = None
        sionna_cov_lin_aligned = None
        sionna_paths_norm_db = None
        sionna_cov_norm_db = None
        sionna_paths_abs_db = None
        sionna_cov_abs_db = None
        sionna_gain_offset_db = 0.0
        if bool(compare_cfg.get("sionna_apply_tx_rx_gains", True)):
            sionna_gain_offset_db = float(tx_gain_dbi + rx_gain_dbi)
        sionna_gain_scale = 10.0 ** (sionna_gain_offset_db / 10.0)

        if sionna_out.get("path_gain_linear_compute_paths") is not None:
            sionna_paths_lin = np.array(sionna_out["path_gain_linear_compute_paths"], dtype=float)
            sionna_paths_lin_aligned = sionna_paths_lin * sionna_gain_scale
            sionna_paths_norm_db = 10.0 * np.log10(
                _apply_normalization(sionna_paths_lin, normalization) + _DB_FLOOR
            )
            sionna_paths_abs_db = 10.0 * np.log10(sionna_paths_lin_aligned + _DB_FLOOR)

        if sionna_out.get("path_gain_linear_coverage_map") is not None:
            sionna_cov_lin = np.array(sionna_out["path_gain_linear_coverage_map"], dtype=float)
            sionna_cov_lin_aligned = sionna_cov_lin * sionna_gain_scale
            sionna_cov_norm_db = 10.0 * np.log10(
                _apply_normalization(sionna_cov_lin, normalization) + _DB_FLOOR
            )
            sionna_cov_abs_db = 10.0 * np.log10(sionna_cov_lin_aligned + _DB_FLOOR)

        step_index += 1
        _write_progress(progress_path, steps, step_index, "running")
        np.savez_compressed(
            data_dir / "model_compare.npz",
            theta_deg=theta_deg,
            qub_model_linear=qub_linear,
            qub_model_norm_db=qub_norm_db,
            # Backward-compatible alias
            machado_linear=qub_linear,
            machado_norm_db=qub_norm_db,
            sionna_compute_paths_linear=sionna_paths_lin if sionna_paths_lin is not None else np.array([]),
            sionna_compute_paths_linear_aligned=sionna_paths_lin_aligned if sionna_paths_lin_aligned is not None else np.array([]),
            sionna_coverage_map_linear=sionna_cov_lin if sionna_cov_lin is not None else np.array([]),
            sionna_coverage_map_linear_aligned=sionna_cov_lin_aligned if sionna_cov_lin_aligned is not None else np.array([]),
        )

        _plot_overlay(
            theta_deg,
            {
                "qub_model": qub_norm_db,
                "sionna_compute_paths": sionna_paths_norm_db,
                "sionna_coverage_map": sionna_cov_norm_db,
            },
            plots_dir / "compare_overlay_norm_db.png",
            title="QUB vs Sionna (Normalized)",
            ylabel="Gain [dB]",
        )

        _plot_overlay(
            theta_deg,
            {
                "qub_model": qub_abs_db,
                "sionna_compute_paths": sionna_paths_abs_db,
                "sionna_coverage_map": sionna_cov_abs_db,
            },
            plots_dir / "compare_overlay_abs_db.png",
            title="QUB vs Sionna (Absolute)",
            ylabel="Path gain [dB]",
        )

        _plot_error(
            theta_deg,
            qub_norm_db,
            sionna_paths_norm_db,
            sionna_cov_norm_db,
            plots_dir / "compare_error_db.png",
        )

        metrics = {
            "run_id": output_dir.name,
            "mode": "compare",
            "model_name": "QUB vs Sionna",
            "source_model": "QUB model (Machado)",
            "output_dir": str(output_dir),
            "config_hash": summary["config"]["hash_sha256"],
            "normalization": normalization or "none",
            "sionna_absolute_gain_offset_db": sionna_gain_offset_db,
            "models": {
                "qub_model": {
                    "peak_db": float(np.nanmax(qub_norm_db)),
                    "peak_angle_deg": float(theta_deg[int(np.nanargmax(qub_norm_db))]),
                    "peak_abs_db": float(np.nanmax(qub_abs_db)),
                },
            },
            "pairwise": {},
            "pairwise_absolute": {},
            "sionna": sionna_out,
        }
        if sionna_paths_norm_db is not None:
            metrics["pairwise"]["qub_model_vs_sionna_compute_paths"] = _curve_metrics(
                theta_deg, qub_norm_db, sionna_paths_norm_db
            )
        if sionna_cov_norm_db is not None:
            metrics["pairwise"]["qub_model_vs_sionna_coverage_map"] = _curve_metrics(
                theta_deg, qub_norm_db, sionna_cov_norm_db
            )
        if sionna_paths_abs_db is not None:
            metrics["pairwise_absolute"]["qub_model_vs_sionna_compute_paths"] = _curve_metrics(
                theta_deg, qub_abs_db, sionna_paths_abs_db
            )
        if sionna_cov_abs_db is not None:
            metrics["pairwise_absolute"]["qub_model_vs_sionna_coverage_map"] = _curve_metrics(
                theta_deg, qub_abs_db, sionna_cov_abs_db
            )

        _write_metrics(output_dir, metrics)

        report_lines = [
            "# QUB vs Sionna",
            "",
            f"- run_id: `{output_dir.name}`",
            "- qub_model: `Machado path-loss formulation`",
            f"- normalization: `{metrics['normalization']}`",
            f"- sionna_enabled: `{bool(sionna_out.get('enabled', False))}`",
            f"- sionna_absolute_gain_offset_db: `{sionna_gain_offset_db:.2f}`",
            "",
            "## Pairwise Metrics",
            "",
        ]
        if metrics["pairwise"]:
            for name, vals in metrics["pairwise"].items():
                report_lines.append(f"- {name}: {vals}")
        else:
            report_lines.append("- none")
        if metrics["pairwise_absolute"]:
            report_lines.extend(["", "## Pairwise Absolute Metrics", ""])
            for name, vals in metrics["pairwise_absolute"].items():
                report_lines.append(f"- {name}: {vals}")
        if sionna_out.get("errors"):
            report_lines.extend(["", "## Sionna Notes", ""])
            for err in sionna_out["errors"]:
                report_lines.append(f"- {err}")
        (output_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")

        _write_progress(progress_path, steps, len(steps), "completed")
        logger.info("QUB vs Sionna run_id=%s output_dir=%s", output_dir.name, output_dir)
        return output_dir
    except Exception as exc:
        logger.exception("QUB vs Sionna compare failed")
        _write_progress(progress_path, steps, step_index, "failed", error=str(exc))
        raise
