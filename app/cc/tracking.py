from __future__ import annotations

from typing import Dict

import numpy as np


def ema_smooth(points: np.ndarray, alpha: float) -> np.ndarray:
    if points.size == 0:
        return points
    alpha = float(np.clip(alpha, 0.0, 1.0))
    out = np.zeros_like(points)
    out[0] = points[0]
    for i in range(1, points.shape[0]):
        out[i] = alpha * points[i] + (1.0 - alpha) * out[i - 1]
    return out


def ema_smooth_bidirectional(points: np.ndarray, alpha: float) -> np.ndarray:
    """Forward-backward EMA: smooth forward, smooth backward, average.

    This eliminates the phase lag of standard EMA and produces much
    smoother trajectories by cancelling oscillations from both directions.
    """
    if points.size == 0 or points.shape[0] < 2:
        return points
    alpha = float(np.clip(alpha, 0.0, 1.0))
    # Forward pass
    fwd = np.zeros_like(points)
    fwd[0] = points[0]
    for i in range(1, points.shape[0]):
        fwd[i] = alpha * points[i] + (1.0 - alpha) * fwd[i - 1]
    # Backward pass
    bwd = np.zeros_like(points)
    bwd[-1] = points[-1]
    for i in range(points.shape[0] - 2, -1, -1):
        bwd[i] = alpha * points[i] + (1.0 - alpha) * bwd[i + 1]
    # Average
    return 0.5 * (fwd + bwd)


def savgol_smooth(points: np.ndarray, window: int, polyorder: int) -> np.ndarray:
    """Savitzky-Golay filter: fits local polynomials for smooth curves."""
    if points.size == 0 or points.shape[0] < max(window, 4):
        return points
    # Ensure window is odd
    if window % 2 == 0:
        window += 1
    window = min(window, points.shape[0])
    if window % 2 == 0:
        window -= 1
    polyorder = min(polyorder, window - 1)
    try:
        from scipy.signal import savgol_filter
        return savgol_filter(points, window_length=window, polyorder=polyorder, axis=0)
    except ImportError:
        # Fallback to bidirectional EMA
        return ema_smooth_bidirectional(points, 0.15)


def smooth_track(points: np.ndarray, cfg: Dict) -> Dict[str, np.ndarray]:
    if points.size == 0:
        return {"smoothed": points}
    enabled = bool(cfg.get("enabled", True))
    method = str(cfg.get("method", "ema"))
    if not enabled:
        return {"smoothed": points}

    if method == "ema_bidirectional" or method == "ema_bidi":
        alpha = float(cfg.get("alpha", 0.15))
        return {"smoothed": ema_smooth_bidirectional(points, alpha)}

    if method == "savgol":
        window = int(cfg.get("savgol_window", 21))
        polyorder = int(cfg.get("savgol_polyorder", 3))
        return {"smoothed": savgol_smooth(points, window, polyorder)}

    if method == "multi":
        # Multi-pass: bidirectional EMA then Savitzky-Golay for extra polish
        alpha = float(cfg.get("alpha", 0.15))
        s = ema_smooth_bidirectional(points, alpha)
        window = int(cfg.get("savgol_window", 15))
        polyorder = int(cfg.get("savgol_polyorder", 3))
        return {"smoothed": savgol_smooth(s, window, polyorder)}

    if method == "ema":
        alpha = float(cfg.get("alpha", 0.2))
        return {"smoothed": ema_smooth(points, alpha)}

    return {"smoothed": points}
