from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np


def _procrustes_align(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
    """Align x to y with optimal similarity transform (rotation + uniform scale + translation).

    Standard Procrustes analysis:
      1. Centre both point sets
      2. Normalise to unit Frobenius norm
      3. Find optimal rotation via SVD
      4. Compute optimal scale using trace of singular values
      5. Apply transform: x_aligned = (x_centred @ R) * scale + y_mean
    """
    x_mean = np.mean(x, axis=0)
    y_mean = np.mean(y, axis=0)
    x0 = x - x_mean
    y0 = y - y_mean

    norm_x = np.linalg.norm(x0, "fro")
    norm_y = np.linalg.norm(y0, "fro")
    if norm_x == 0 or norm_y == 0:
        return x, {"scale": 1.0}

    # Normalise to unit Frobenius norm
    x0n = x0 / norm_x
    y0n = y0 / norm_y

    # Optimal rotation
    u, s, vt = np.linalg.svd(x0n.T @ y0n)
    r = u @ vt

    # Optimal scale: trace(S) * norm_y / norm_x
    # trace(S) ∈ [0, d] measures alignment quality; for perfect fit trace(S) = d
    trace_s = float(np.sum(s))
    scale = trace_s * norm_y / norm_x

    # Apply: rotate un-normalised centred points, then scale and translate
    x_aligned = (x0 @ r) * scale + y_mean
    return x_aligned, {"scale": scale, "trace_s": trace_s}


def _affine_align(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    # Fit affine transform x -> y using least squares (y = x @ A + b).
    n, d = x.shape
    x_aug = np.hstack([x, np.ones((n, 1))])
    params, *_ = np.linalg.lstsq(x_aug, y, rcond=None)
    a = params[:-1, :]
    b = params[-1, :]
    x_aligned = x @ a + b
    return x_aligned, {"A": a.tolist(), "b": b.tolist()}


def evaluate_chart(
    embeddings: np.ndarray,
    ground_truth: np.ndarray,
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    if embeddings.size == 0 or ground_truth.size == 0:
        return metrics

    dims = int(cfg.get("dims", embeddings.shape[1]))
    dims = min(dims, embeddings.shape[1], ground_truth.shape[1])
    emb = embeddings[:, :dims]
    gt = ground_truth[:, :dims]

    aligned = emb
    align_mode = str(cfg.get("align", "procrustes"))
    if align_mode == "affine":
        aligned, align_meta = _affine_align(emb, gt)
        metrics["alignment"] = {"mode": "affine", **align_meta}
    elif align_mode == "procrustes":
        aligned, align_meta = _procrustes_align(emb, gt)
        metrics["alignment"] = {"mode": "procrustes", **align_meta}

    err = aligned - gt
    rmse = float(np.sqrt(np.mean(np.sum(err**2, axis=1))))
    mae = float(np.mean(np.linalg.norm(err, axis=1)))
    metrics.update(
        {
            "rmse_m": rmse,
            "mae_m": mae,
        }
    )
    return {"metrics": metrics, "aligned": aligned}
