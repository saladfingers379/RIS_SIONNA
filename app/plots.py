from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import numpy as np


def _load_npz(path: Path) -> Dict[str, Any]:
    with np.load(path) as data:
        return {k: data[k] for k in data.files}


def _infer_cell_size(cell_centers: np.ndarray) -> Tuple[float, float]:
    if cell_centers.ndim < 3:
        return 0.0, 0.0
    xs = cell_centers[:, :, 0]
    ys = cell_centers[:, :, 1]
    x_diffs = np.diff(xs, axis=1).ravel()
    y_diffs = np.diff(ys, axis=0).ravel()
    x_nonzero = x_diffs[x_diffs != 0]
    y_nonzero = y_diffs[y_diffs != 0]
    x_step = np.median(np.abs(x_nonzero)) if x_nonzero.size else 0.0
    y_step = np.median(np.abs(y_nonzero)) if y_nonzero.size else 0.0
    return float(x_step or 0.0), float(y_step or 0.0)


def compute_radio_map_extent(cell_centers: np.ndarray) -> Tuple[float, float, float, float]:
    xs = cell_centers[:, :, 0]
    ys = cell_centers[:, :, 1]
    cell_size_x, cell_size_y = _infer_cell_size(cell_centers)
    return (
        float(xs.min() - cell_size_x * 0.5),
        float(xs.max() + cell_size_x * 0.5),
        float(ys.min() - cell_size_y * 0.5),
        float(ys.max() + cell_size_y * 0.5),
    )


def _normalize(vec: np.ndarray) -> np.ndarray | None:
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return None
    return vec / norm


def _radio_map_plane_projection(
    cell_centers: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if cell_centers.ndim < 3 or cell_centers.shape[-1] < 3:
        raise ValueError("cell_centers must have shape [y, x, 3]")

    origin = np.asarray(cell_centers[0, 0], dtype=float)
    u_vec = None
    v_vec = None
    if cell_centers.shape[1] > 1:
        u_vec = np.asarray(cell_centers[0, 1], dtype=float) - origin
    if cell_centers.shape[0] > 1:
        v_vec = np.asarray(cell_centers[1, 0], dtype=float) - origin

    u_unit = _normalize(u_vec) if u_vec is not None else None
    if u_unit is None:
        u_unit = np.array([1.0, 0.0, 0.0], dtype=float)

    if v_vec is not None:
        v_vec = v_vec - float(np.dot(v_vec, u_unit)) * u_unit
    v_unit = _normalize(v_vec) if v_vec is not None else None
    if v_unit is None:
        fallback = np.array([0.0, 0.0, 1.0], dtype=float)
        if abs(float(np.dot(fallback, u_unit))) > 0.9:
            fallback = np.array([0.0, 1.0, 0.0], dtype=float)
        v_unit = fallback - float(np.dot(fallback, u_unit)) * u_unit
        v_unit = _normalize(v_unit)
    if v_unit is None:
        v_unit = np.array([0.0, 1.0, 0.0], dtype=float)

    rel = np.asarray(cell_centers, dtype=float) - origin[None, None, :]
    u_coords = np.tensordot(rel, u_unit, axes=([-1], [0]))
    v_coords = np.tensordot(rel, v_unit, axes=([-1], [0]))
    return u_coords, v_coords, origin, u_unit, v_unit


def _compute_projected_extent(u_coords: np.ndarray, v_coords: np.ndarray) -> Tuple[float, float, float, float]:
    u_step = 0.0
    v_step = 0.0
    if u_coords.ndim >= 2:
        u_diffs = np.diff(u_coords, axis=1).ravel()
        u_nonzero = u_diffs[np.abs(u_diffs) > 0]
        if u_nonzero.size:
            u_step = float(np.median(np.abs(u_nonzero)))
        v_diffs = np.diff(v_coords, axis=0).ravel()
        v_nonzero = v_diffs[np.abs(v_diffs) > 0]
        if v_nonzero.size:
            v_step = float(np.median(np.abs(v_nonzero)))
    return (
        float(np.min(u_coords) - 0.5 * u_step),
        float(np.max(u_coords) + 0.5 * u_step),
        float(np.min(v_coords) - 0.5 * v_step),
        float(np.max(v_coords) + 0.5 * v_step),
    )


def _project_point_to_plane_axes(
    point: np.ndarray,
    origin: np.ndarray,
    u_unit: np.ndarray,
    v_unit: np.ndarray,
) -> Tuple[float, float]:
    rel = np.asarray(point, dtype=float) - origin
    return float(np.dot(rel, u_unit)), float(np.dot(rel, v_unit))


def _radio_map_title(metric_label: str, title_suffix: str | None = None) -> str:
    title = f"Radio Map ({metric_label})"
    if title_suffix:
        return f"{title}\n{title_suffix}"
    return title


def plot_radio_map(
    metric_map: np.ndarray,
    cell_centers: np.ndarray,
    output_dir: Path,
    metric_label: str,
    filename_prefix: str,
    tx_pos: np.ndarray | None = None,
    rx_pos: np.ndarray | None = None,
    ris_positions: list[np.ndarray] | None = None,
    axis_labels: Tuple[str, str] = ("x [m]", "y [m]"),
    title_suffix: str | None = None,
) -> Tuple[Path, Path]:
    # metric_map: [num_tx, y, x] or [y, x]
    # cell_centers: [y, x, 3]

    u_coords, v_coords, origin, u_unit, v_unit = _radio_map_plane_projection(cell_centers)
    extent = _compute_projected_extent(u_coords, v_coords)

    fig, ax = plt.subplots(figsize=(7, 5))
    data = metric_map[0] if metric_map.ndim == 3 else metric_map
    im = ax.imshow(data, origin="lower", extent=extent, cmap="viridis")
    ax.set_title(_radio_map_title(metric_label, title_suffix=title_suffix))
    ax.set_xlabel(axis_labels[0])
    ax.set_ylabel(axis_labels[1])
    if tx_pos is not None:
        tx_u, tx_v = _project_point_to_plane_axes(np.asarray(tx_pos, dtype=float), origin, u_unit, v_unit)
        ax.scatter([tx_u], [tx_v], color="#dc322f", s=30, label="Tx")
    if rx_pos is not None:
        rx_u, rx_v = _project_point_to_plane_axes(np.asarray(rx_pos, dtype=float), origin, u_unit, v_unit)
        ax.scatter([rx_u], [rx_v], color="#268bd2", s=30, label="Rx")
    if ris_positions:
        for idx, pos in enumerate(ris_positions):
            label = "RIS" if idx == 0 else None
            ris_u, ris_v = _project_point_to_plane_axes(np.asarray(pos, dtype=float), origin, u_unit, v_unit)
            ax.scatter([ris_u], [ris_v], color="#000000", s=40, marker="*", label=label)
    if tx_pos is not None or rx_pos is not None or ris_positions:
        ax.legend(loc="upper right")
    fig.colorbar(im, ax=ax, label=metric_label)
    fig.tight_layout()

    png_path = output_dir / f"{filename_prefix}.png"
    svg_path = output_dir / f"{filename_prefix}.svg"
    fig.savefig(png_path, dpi=200)
    fig.savefig(svg_path)
    plt.close(fig)

    return png_path, svg_path


def plot_radio_map_sionna(
    coverage_map: Any,
    output_dir: Path,
    metric: str,
    filename_prefix: str,
    tx: int | str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    show_tx: bool = True,
    show_rx: bool = False,
    show_ris: bool = False,
    title_suffix: str | None = None,
) -> Tuple[Path, Path]:
    fig = coverage_map.show(
        metric=metric,
        tx=tx,
        vmin=vmin,
        vmax=vmax,
        show_tx=show_tx,
        show_rx=show_rx,
        show_ris=show_ris,
    )
    if title_suffix:
        axes = fig.axes or []
        if axes:
            current = axes[0].get_title() or ""
            axes[0].set_title(f"{current}\n{title_suffix}" if current else title_suffix)
    png_path = output_dir / f"{filename_prefix}.png"
    svg_path = output_dir / f"{filename_prefix}.svg"
    fig.savefig(png_path, dpi=200)
    fig.savefig(svg_path)
    plt.close(fig)
    return png_path, svg_path


def plot_radio_map_from_npz(
    npz_path: Path,
    output_dir: Path,
    metric_key: str,
    metric_label: str,
    filename_prefix: str,
) -> Tuple[Path, Path]:
    data = _load_npz(npz_path)
    return plot_radio_map(
        metric_map=data[metric_key],
        cell_centers=data["cell_centers"],
        output_dir=output_dir,
        metric_label=metric_label,
        filename_prefix=filename_prefix,
    )


def plot_histogram(
    data: np.ndarray,
    weights: np.ndarray | None,
    output_dir: Path,
    title: str,
    xlabel: str,
    filename_prefix: str,
    bins: int = 50,
) -> Tuple[Path, Path]:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(data, bins=bins, weights=weights, color="#1f77b4", alpha=0.85)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Weighted count" if weights is not None else "Count")
    fig.tight_layout()

    png_path = output_dir / f"{filename_prefix}.png"
    svg_path = output_dir / f"{filename_prefix}.svg"
    fig.savefig(png_path, dpi=200)
    fig.savefig(svg_path)
    plt.close(fig)
    return png_path, svg_path


def plot_rays_3d(
    segments: np.ndarray,
    tx_pos: np.ndarray,
    rx_pos: np.ndarray,
    output_dir: Path,
    filename_prefix: str = "ray_paths_3d",
) -> Tuple[Path, Path]:
    fig = plt.figure(figsize=(7, 5))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_title("RF Ray Paths (3D)")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_zlabel("z [m]")

    for row in segments:
        _, x0, y0, z0, x1, y1, z1 = row
        ax.plot([x0, x1], [y0, y1], [z0, z1], color="#ff9750", alpha=0.7, linewidth=1.0)

    ax.scatter([tx_pos[0]], [tx_pos[1]], [tx_pos[2]], color="#dc322f", s=30, label="Tx")
    ax.scatter([rx_pos[0]], [rx_pos[1]], [rx_pos[2]], color="#268bd2", s=30, label="Rx")
    ax.legend(loc="upper right")

    fig.tight_layout()
    png_path = output_dir / f"{filename_prefix}.png"
    svg_path = output_dir / f"{filename_prefix}.svg"
    fig.savefig(png_path, dpi=200)
    fig.savefig(svg_path)
    plt.close(fig)
    return png_path, svg_path
