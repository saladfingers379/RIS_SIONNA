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


def smooth_track(points: np.ndarray, cfg: Dict) -> Dict[str, np.ndarray]:
    if points.size == 0:
        return {"smoothed": points}
    enabled = bool(cfg.get("enabled", True))
    method = str(cfg.get("method", "ema"))
    if not enabled:
        return {"smoothed": points}
    if method == "ema":
        alpha = float(cfg.get("alpha", 0.2))
        return {"smoothed": ema_smooth(points, alpha)}
    return {"smoothed": points}
