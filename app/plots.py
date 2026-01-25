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


def plot_radio_map(
    metric_map: np.ndarray,
    cell_centers: np.ndarray,
    output_dir: Path,
    metric_label: str,
    filename_prefix: str,
    tx_pos: np.ndarray | None = None,
    rx_pos: np.ndarray | None = None,
) -> Tuple[Path, Path]:
    # metric_map: [num_tx, y, x] or [y, x]
    # cell_centers: [y, x, 3]

    extent = compute_radio_map_extent(cell_centers)

    fig, ax = plt.subplots(figsize=(7, 5))
    data = metric_map[0] if metric_map.ndim == 3 else metric_map
    im = ax.imshow(data, origin="lower", extent=extent, cmap="viridis")
    ax.set_title(f"Radio Map ({metric_label})")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    if tx_pos is not None:
        ax.scatter([tx_pos[0]], [tx_pos[1]], color="#dc322f", s=30, label="Tx")
    if rx_pos is not None:
        ax.scatter([rx_pos[0]], [rx_pos[1]], color="#268bd2", s=30, label="Rx")
    if tx_pos is not None or rx_pos is not None:
        ax.legend(loc="upper right")
    fig.colorbar(im, ax=ax, label=metric_label)
    fig.tight_layout()

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
