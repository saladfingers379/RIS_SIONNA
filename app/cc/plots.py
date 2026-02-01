from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_chart(
    coords: np.ndarray,
    output_dir: Path,
    title: str,
    filename: str,
    color: Optional[np.ndarray] = None,
    gt: Optional[np.ndarray] = None,
) -> Optional[Path]:
    if coords.size == 0:
        return None
    fig = plt.figure(figsize=(6, 5))
    if coords.shape[1] >= 3:
        ax = fig.add_subplot(1, 1, 1, projection="3d")
        c = color if color is not None else np.arange(coords.shape[0])
        ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2], c=c, cmap="viridis", s=12)
        if gt is not None and gt.shape[1] >= 3:
            ax.plot(gt[:, 0], gt[:, 1], gt[:, 2], color="#e76f51", linewidth=1.5, label="GT")
            ax.legend(loc="best")
        ax.set_zlabel("dim-3")
    else:
        ax = fig.add_subplot(1, 1, 1)
        if coords.shape[1] >= 2:
            c = color if color is not None else np.arange(coords.shape[0])
            sc = ax.scatter(coords[:, 0], coords[:, 1], c=c, cmap="viridis", s=14)
            fig.colorbar(sc, ax=ax, label="time")
            if gt is not None and gt.shape[1] >= 2:
                ax.plot(gt[:, 0], gt[:, 1], color="#e76f51", linewidth=1.5, label="GT")
                ax.legend(loc="best")
        else:
            ax.plot(coords[:, 0])
    ax.set_title(title)
    ax.set_xlabel("dim-1")
    ax.set_ylabel("dim-2")
    out_path = output_dir / filename
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def plot_feature_summary(features: np.ndarray, output_dir: Path, filename: str) -> Optional[Path]:
    if features.size == 0:
        return None
    fig = plt.figure(figsize=(7, 4))
    ax = fig.add_subplot(1, 1, 1)
    ax.imshow(features.T, aspect="auto", interpolation="nearest", origin="lower")
    ax.set_title("Feature heatmap")
    ax.set_xlabel("time step")
    ax.set_ylabel("feature index")
    out_path = output_dir / filename
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def plot_losses(history: Dict[str, list], output_dir: Path, filename: str) -> Optional[Path]:
    if not history:
        return None
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_subplot(1, 1, 1)
    for key, values in history.items():
        if not values:
            continue
        ax.plot(values, label=key)
    ax.set_title("Training losses")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.legend(loc="best")
    out_path = output_dir / filename
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def plot_trajectory_compare(
    gt: np.ndarray,
    est: np.ndarray,
    output_dir: Path,
    filename: str,
    title: str = "UE trajectory vs estimate",
) -> Optional[Path]:
    if gt.size == 0 or est.size == 0:
        return None
    fig = plt.figure(figsize=(6, 5))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(gt[:, 0], gt[:, 1], color="#2563eb", linewidth=2, label="GT")
    ax.plot(est[:, 0], est[:, 1], color="#f97316", linewidth=2, label="Estimated")
    ax.scatter(gt[0, 0], gt[0, 1], color="#1d4ed8", s=30, label="GT start")
    ax.scatter(est[0, 0], est[0, 1], color="#ea580c", s=30, label="Est start")
    ax.set_title(title)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.legend(loc="best")
    out_path = output_dir / filename
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path
