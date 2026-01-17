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


def plot_radio_map(
    metric_map: np.ndarray,
    cell_centers: np.ndarray,
    output_dir: Path,
    metric_label: str,
    filename_prefix: str,
) -> Tuple[Path, Path]:
    # metric_map: [num_tx, y, x]
    # cell_centers: [y, x, 3]

    xs = cell_centers[:, :, 0]
    ys = cell_centers[:, :, 1]
    extent = [xs.min(), xs.max(), ys.min(), ys.max()]

    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(metric_map[0], origin="lower", extent=extent, cmap="viridis")
    ax.set_title(f"Radio Map ({metric_label})")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
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
