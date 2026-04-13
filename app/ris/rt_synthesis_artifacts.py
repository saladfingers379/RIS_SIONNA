"""Artifacts and plots for RIS synthesis runs."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np

from app.io import save_json
from app.ris.rt_synthesis_phase_manifold import ensure_finite_array


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _cell_extents(cell_centers: np.ndarray) -> list[float]:
    centers = np.asarray(cell_centers, dtype=float)
    x = centers[..., 0]
    y = centers[..., 1]
    dx = float(np.median(np.diff(np.unique(np.round(x.reshape(-1), 9))))) if x.shape[1] > 1 else 1.0
    dy = float(np.median(np.diff(np.unique(np.round(y.reshape(-1), 9))))) if y.shape[0] > 1 else 1.0
    return [
        float(np.min(x) - dx / 2.0),
        float(np.max(x) + dx / 2.0),
        float(np.min(y) - dy / 2.0),
        float(np.max(y) + dy / 2.0),
    ]


def _plot_heatmap(
    values: np.ndarray,
    cell_centers: np.ndarray,
    output_path: Path,
    *,
    title: str,
    cbar_label: str,
    boxes: Optional[Iterable[dict]] = None,
    cmap: str = "viridis",
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    _ensure_parent(output_path)
    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    extent = _cell_extents(cell_centers)
    im = ax.imshow(
        np.asarray(values, dtype=float),
        origin="lower",
        extent=extent,
        aspect="auto",
        cmap=cmap,
    )
    for box in boxes or []:
        width = float(box["u_max_m"]) - float(box["u_min_m"])
        height = float(box["v_max_m"]) - float(box["v_min_m"])
        ax.add_patch(
            Rectangle(
                (float(box["u_min_m"]), float(box["v_min_m"])),
                width,
                height,
                fill=False,
                edgecolor="#f97316",
                linewidth=1.8,
            )
        )
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label=cbar_label)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _plot_phase(
    phase: np.ndarray,
    output_path: Path,
    *,
    title: str,
    quantized_bits: Optional[int] = None,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    _ensure_parent(output_path)
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    phase_wrapped = np.mod(np.asarray(phase, dtype=float), 2.0 * np.pi)
    if quantized_bits is None:
        image = ax.imshow(phase_wrapped, origin="lower", cmap="twilight")
    else:
        bits_int = max(1, int(quantized_bits))
        num_levels = 2 ** bits_int
        step = 2.0 * np.pi / float(num_levels)
        level_indices = (np.round(phase_wrapped / step).astype(int) % num_levels).astype(float)
        if num_levels == 2:
            cmap = ListedColormap(["#3b2aa6", "#f2df1d"])
        else:
            cmap = plt.get_cmap("viridis", num_levels)
        boundaries = np.arange(-0.5, num_levels + 0.5, 1.0)
        norm = BoundaryNorm(boundaries, cmap.N)
        image = ax.imshow(
            level_indices,
            origin="lower",
            cmap=cmap,
            norm=norm,
            interpolation="nearest",
            resample=False,
        )
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    ax.set_title(title)
    cbar = fig.colorbar(image, ax=ax)
    if quantized_bits is None:
        cbar.set_label("Phase [rad]")
    else:
        ticks = np.arange(0, 2 ** int(quantized_bits), dtype=float)
        labels = [f"{tick * (2.0 * np.pi / float(2 ** int(quantized_bits))):.2f}" for tick in ticks]
        cbar.set_ticks(ticks)
        cbar.set_ticklabels(labels)
        cbar.set_label("Quantized phase [rad]")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _plot_trace(rows: list[dict], output_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _ensure_parent(output_path)
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot([row["iteration"] for row in rows], [row["objective"] for row in rows], color="#0f766e", linewidth=2.0)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Objective")
    ax.set_title("Continuous Optimization Trace")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _plot_cdf(series: Dict[str, np.ndarray], output_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _ensure_parent(output_path)
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    for label, values in series.items():
        samples = np.sort(np.asarray(values, dtype=float).reshape(-1))
        if samples.size == 0:
            continue
        y = np.linspace(0.0, 1.0, samples.size, endpoint=True)
        ax.plot(samples, y, linewidth=2.0, label=label)
    ax.set_xlabel("ROI Rx power [dBm]")
    ax.set_ylabel("CDF")
    ax.set_title("ROI Rx Power CDF")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_target_region_artifacts(output_dir: Path, boxes, mask, cell_centers) -> None:
    data_dir = output_dir / "data"
    plots_dir = output_dir / "plots"
    data_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)
    save_json(data_dir / "target_boxes.json", {"boxes": list(boxes)})
    np.save(data_dir / "target_mask.npy", np.asarray(mask, dtype=bool))
    _plot_heatmap(
        np.asarray(mask, dtype=float),
        np.asarray(cell_centers, dtype=float),
        plots_dir / "target_region_overlay.png",
        title="Target Region Overlay",
        cbar_label="ROI mask",
        boxes=boxes,
        cmap="magma",
    )


def write_phase_artifacts(
    output_dir: Path,
    phase_continuous,
    phase_1bit=None,
    *,
    amp_continuous=None,
    amp_1bit=None,
    phase_continuous_unwrapped=None,
    phase_quantized=None,
    amp_quantized=None,
    quantized_bits: Optional[int] = None,
) -> None:
    data_dir = output_dir / "data"
    plots_dir = output_dir / "plots"
    phase_continuous_arr = ensure_finite_array(phase_continuous, name="continuous phase artifacts")
    np.save(data_dir / "phase_continuous.npy", phase_continuous_arr)
    np.save(data_dir / "manual_profile_phase_continuous.npy", phase_continuous_arr)
    if phase_continuous_unwrapped is not None:
        np.save(
            data_dir / "phase_continuous_unwrapped.npy",
            ensure_finite_array(phase_continuous_unwrapped, name="continuous unwrapped phase artifacts"),
        )
    if amp_continuous is None:
        amp_continuous = np.ones_like(phase_continuous_arr, dtype=float)
    amp_continuous_arr = ensure_finite_array(amp_continuous, name="continuous amplitude artifacts")
    np.save(data_dir / "amp_continuous.npy", amp_continuous_arr)
    np.save(data_dir / "manual_profile_amp_continuous.npy", amp_continuous_arr)
    _plot_phase(
        phase_continuous_arr[0] if phase_continuous_arr.ndim == 3 else phase_continuous_arr,
        plots_dir / "phase_continuous.png",
        title="Continuous RIS Phase",
    )
    if phase_1bit is not None:
        phase_1bit_arr = ensure_finite_array(phase_1bit, name="1-bit phase artifacts")
        np.save(data_dir / "phase_1bit.npy", phase_1bit_arr)
        np.save(data_dir / "manual_profile_phase.npy", phase_1bit_arr)
        np.save(data_dir / "manual_profile_phase_1bit.npy", phase_1bit_arr)
        if amp_1bit is None:
            amp_1bit = np.ones_like(phase_1bit_arr, dtype=float)
        amp_1bit_arr = ensure_finite_array(amp_1bit, name="1-bit amplitude artifacts")
        np.save(data_dir / "amp_1bit.npy", amp_1bit_arr)
        np.save(data_dir / "manual_profile_amp_1bit.npy", amp_1bit_arr)
        bits = (np.mod(phase_1bit_arr, 2.0 * np.pi) >= np.pi / 2.0).astype(np.int8)
        np.save(data_dir / "bits_1bit.npy", bits)
        _plot_phase(
            phase_1bit_arr[0] if phase_1bit_arr.ndim == 3 else phase_1bit_arr,
            plots_dir / "phase_1bit.png",
            title="1-Bit RIS Phase",
            quantized_bits=1,
        )
    if phase_quantized is not None:
        phase_quantized_arr = ensure_finite_array(phase_quantized, name="quantized phase artifacts")
        np.save(data_dir / "phase_quantized.npy", phase_quantized_arr)
        np.save(data_dir / "manual_profile_phase_quantized.npy", phase_quantized_arr)
        if amp_quantized is None:
            amp_quantized = np.ones_like(phase_quantized_arr, dtype=float)
        amp_quantized_arr = ensure_finite_array(amp_quantized, name="quantized amplitude artifacts")
        np.save(data_dir / "amp_quantized.npy", amp_quantized_arr)
        np.save(data_dir / "manual_profile_amp_quantized.npy", amp_quantized_arr)
        bits_int = max(1, int(quantized_bits or 1))
        levels = 2 ** bits_int
        step = 2.0 * np.pi / float(levels)
        levels_arr = (np.round(np.mod(phase_quantized_arr, 2.0 * np.pi) / step).astype(int) % levels).astype(np.int16)
        np.save(data_dir / "levels_quantized.npy", levels_arr)
        _plot_phase(
            phase_quantized_arr[0] if phase_quantized_arr.ndim == 3 else phase_quantized_arr,
            plots_dir / "phase_quantized.png",
            title=f"{bits_int}-Bit RIS Phase",
            quantized_bits=bits_int,
        )


def write_objective_trace(output_dir: Path, rows: list[dict]) -> None:
    data_dir = output_dir / "data"
    csv_path = data_dir / "objective_trace.csv"
    _ensure_parent(csv_path)
    fieldnames = ["iteration", "objective"]
    extra_keys = []
    seen = set(fieldnames)
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            extra_keys.append(key)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames + extra_keys)
        writer.writeheader()
        writer.writerows(rows)
    _plot_trace(rows, output_dir / "plots" / "objective_trace.png")


def write_offset_sweep(output_dir: Path, rows: list[dict]) -> None:
    data_dir = output_dir / "data"
    csv_path = data_dir / "offset_sweep.csv"
    _ensure_parent(csv_path)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["offset_rad", "score"])
        writer.writeheader()
        writer.writerows(rows)


def write_eval_artifacts(
    output_dir: Path,
    *,
    key: str,
    evaluation: dict,
    boxes,
    diff_vs_off: Optional[np.ndarray] = None,
    diff_vs_continuous: Optional[np.ndarray] = None,
) -> None:
    data_dir = output_dir / "data"
    plots_dir = output_dir / "plots"
    np.savez_compressed(
        data_dir / f"eval_{key}.npz",
        path_gain_linear=np.asarray(evaluation["path_gain_linear"]),
        path_gain_db=np.asarray(evaluation["path_gain_db"]),
        rx_power_dbm=np.asarray(evaluation["rx_power_dbm"]),
        path_loss_db=np.asarray(evaluation["path_loss_db"]),
        cell_centers=np.asarray(evaluation["cell_centers"]),
    )
    _plot_heatmap(
        np.asarray(evaluation["path_gain_db"]),
        np.asarray(evaluation["cell_centers"]),
        plots_dir / f"radio_map_{key}.png",
        title=evaluation.get("title") or key,
        cbar_label="Path gain [dB]",
        boxes=boxes,
    )
    if diff_vs_off is not None:
        _plot_heatmap(
            np.asarray(diff_vs_off),
            np.asarray(evaluation["cell_centers"]),
            plots_dir / f"radio_map_diff_{key}_vs_off.png",
            title=f"{key} vs RIS-off",
            cbar_label="Path gain delta [dB]",
            boxes=boxes,
            cmap="coolwarm",
        )
    if diff_vs_continuous is not None:
        _plot_heatmap(
            np.asarray(diff_vs_continuous),
            np.asarray(evaluation["cell_centers"]),
            plots_dir / f"radio_map_diff_{key}_vs_continuous.png",
            title=f"{key} vs continuous",
            cbar_label="Path gain delta [dB]",
            boxes=boxes,
            cmap="coolwarm",
        )


def write_cdf_plot(output_dir: Path, series: Dict[str, np.ndarray]) -> None:
    _plot_cdf(series, output_dir / "plots" / "cdf_roi_rx_power.png")


def write_summary(output_dir: Path, summary: dict, metrics: dict) -> None:
    save_json(output_dir / "summary.json", summary)
    save_json(output_dir / "metrics.json", metrics)
