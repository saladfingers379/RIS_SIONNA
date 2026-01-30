from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np


def _infer_array_shape(cfg: Dict[str, Any]) -> Tuple[int, int]:
    rows = int(cfg.get("num_rows", 1)) if isinstance(cfg, dict) else 1
    cols = int(cfg.get("num_cols", 1)) if isinstance(cfg, dict) else 1
    rows = max(1, rows)
    cols = max(1, cols)
    return rows, cols


def _reshape_to_grid(h: np.ndarray, rows: int, cols: int) -> np.ndarray:
    # h: [..., ant, ...]
    ant = h.shape[-2]
    if rows * cols != ant:
        rows, cols = ant, 1
    return h.reshape(*h.shape[:-2], rows, cols, h.shape[-1])


def _apply_beamspace(h: np.ndarray, rx_shape: Tuple[int, int], tx_shape: Tuple[int, int]) -> np.ndarray:
    rx_rows, rx_cols = rx_shape
    tx_rows, tx_cols = tx_shape
    # h: [T, rx_ant, tx_ant, K]
    rx_ant = h.shape[1]
    tx_ant = h.shape[2]
    if rx_rows * rx_cols != rx_ant:
        rx_rows, rx_cols = rx_ant, 1
    if tx_rows * tx_cols != tx_ant:
        tx_rows, tx_cols = tx_ant, 1
    h = h.reshape(h.shape[0], rx_rows, rx_cols, tx_rows, tx_cols, h.shape[-1])
    h = np.fft.fft(h, axis=1)
    h = np.fft.fft(h, axis=2)
    h = np.fft.fft(h, axis=3)
    h = np.fft.fft(h, axis=4)
    return h


def _moving_average(x: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return x
    out = np.zeros_like(x)
    for idx in range(x.shape[0]):
        start = max(0, idx - window + 1)
        out[idx] = np.mean(x[start : idx + 1], axis=0)
    return out


def extract_features(
    csi: Dict[str, Any],
    cfg: Dict[str, Any],
    array_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    cc_cfg = cfg.get("channel_charting", {})
    feat_cfg = cc_cfg.get("features", {})
    feat_type = str(feat_cfg.get("type", "r2m"))
    window = int(feat_cfg.get("window", 1))

    data = csi.get("data")
    if data is None or data.size == 0:
        return {"features": np.zeros((0,)), "feature_type": feat_type}

    # Use first TX/RX if multiple
    # Expected: [T, num_rx, rx_ant, num_tx, tx_ant, K]
    if data.ndim < 6:
        raise ValueError("CSI data has unexpected shape")
    h = data[:, 0, :, 0, :, :]

    rx_shape = _infer_array_shape(array_cfg.get("rx", {}))
    tx_shape = _infer_array_shape(array_cfg.get("tx", {}))

    if feat_type == "beamspace_mag":
        beam_cfg = feat_cfg.get("beamspace_mag", {})
        use_beamspace = bool(beam_cfg.get("beamspace", True))
        power = bool(beam_cfg.get("power", True))
        if use_beamspace:
            h_use = _apply_beamspace(h, rx_shape, tx_shape)
        else:
            h_use = h
        mag = np.abs(h_use) ** 2 if power else np.abs(h_use)
        feat = np.mean(mag, axis=-1)
        feat = feat.reshape(feat.shape[0], -1)
    else:
        r2m_cfg = feat_cfg.get("r2m", {})
        use_beamspace = bool(r2m_cfg.get("beamspace", True))
        mode = str(r2m_cfg.get("mode", "diag"))
        h_use = _apply_beamspace(h, rx_shape, tx_shape) if use_beamspace else h
        t, rx_r, rx_c, tx_r, tx_c, k = h_use.shape
        h_vec = h_use.reshape(t, rx_r * rx_c * tx_r * tx_c, k)
        if mode == "full":
            feats = []
            for i in range(t):
                vec = h_vec[i]
                r = (vec @ np.conjugate(vec.T)) / float(k)
                feats.append(np.abs(r).reshape(-1))
            feat = np.stack(feats, axis=0)
        else:
            power = np.mean(np.abs(h_vec) ** 2, axis=-1)
            feat = power

    feat = _moving_average(feat, window)
    return {
        "features": feat,
        "feature_type": feat_type,
        "window": window,
    }
