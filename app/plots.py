from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
