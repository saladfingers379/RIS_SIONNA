from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path


def _compute_adp_dissimilarity_matrix(csi: Dict[str, Any], max_taps: int | None = None) -> np.ndarray:
    data = csi.get("data")
    if data is None or data.size == 0:
        return np.zeros((0, 0))
    if data.ndim < 6:
        raise ValueError("CSI data has unexpected shape")
    # Use first RX/TX for now.
    h = data[:, 0, :, 0, :, :]  # [T, rx_ant, tx_ant, K]
    h = h.reshape(h.shape[0], -1, h.shape[-1])  # [T, ant, K]
    h_delay = np.fft.ifft(h, axis=2)
    if max_taps is not None:
        h_delay = h_delay[:, :, :max_taps]
    # [T, ant, tau] -> [T, tau, ant]
    h_tau = np.transpose(h_delay, (0, 2, 1))

    t, num_tau, ant = h_tau.shape
    d = np.zeros((t, t), dtype=np.float64)
    eps = 1e-12
    for tau in range(num_tau):
        v = h_tau[:, tau, :]  # [T, ant]
        power = np.sum(np.abs(v) ** 2, axis=1, keepdims=True) + eps
        v_norm = v / np.sqrt(power)
        sim = np.abs(v_norm @ np.conjugate(v_norm.T)) ** 2
        d += 1.0 - sim
    return d


def fuse_time_dissimilarity(
    d_adp: np.ndarray,
    times: np.ndarray,
    window_s: float,
    weight: float,
) -> np.ndarray:
    t = times.reshape(-1, 1)
    d_time = np.abs(t - t.T)
    if window_s <= 0:
        return d_adp
    mask = d_time <= window_s
    if np.any(mask):
        scale = np.median(d_adp[mask]) / (np.median(d_time[mask]) + 1e-12)
    else:
        scale = np.median(d_adp) / (np.median(d_time) + 1e-12)
    d_time = d_time * scale
    return (1.0 - weight) * d_adp + weight * d_time


def geodesic_knn(d: np.ndarray, k: int) -> np.ndarray:
    n = d.shape[0]
    k = max(1, min(k, n - 1))
    rows = []
    cols = []
    vals = []
    for i in range(n):
        idx = np.argsort(d[i])[: k + 1]
        for j in idx:
            if i == j:
                continue
            rows.append(i)
            cols.append(j)
            vals.append(d[i, j])
    graph = csr_matrix((vals, (rows, cols)), shape=(n, n))
    # Symmetrize
    graph = graph.minimum(graph.T)
    dist = shortest_path(graph, directed=False, unweighted=False)
    return dist


def classical_mds(d: np.ndarray, dims: int) -> np.ndarray:
    n = d.shape[0]
    if n == 0:
        return np.zeros((0, dims))
    d2 = d ** 2
    j = np.eye(n) - np.ones((n, n)) / n
    b = -0.5 * j @ d2 @ j
    vals, vecs = np.linalg.eigh(b)
    idx = np.argsort(vals)[::-1]
    vals = np.maximum(vals[idx], 0.0)
    vecs = vecs[:, idx]
    coords = vecs[:, :dims] * np.sqrt(vals[:dims])
    return coords


def dissimilarity_charting(
    csi: Dict[str, Any],
    cfg: Dict[str, Any],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    dis_cfg = cfg.get("dissimilarity", {}) if isinstance(cfg, dict) else {}
    metric = str(dis_cfg.get("metric", "adp_cosine"))
    times = np.asarray(csi.get("times_s", []), dtype=float)

    if metric != "adp_cosine":
        raise ValueError("Only adp_cosine dissimilarity is supported")

    max_taps = dis_cfg.get("max_taps")
    d = _compute_adp_dissimilarity_matrix(csi, max_taps=max_taps)

    if bool(dis_cfg.get("fuse_time", True)) and times.size:
        window_s = float(dis_cfg.get("time_window_s", 2.0))
        weight = float(dis_cfg.get("time_weight", 0.35))
        d = fuse_time_dissimilarity(d, times, window_s, weight)

    if bool(dis_cfg.get("use_geodesic", True)):
        k = int(dis_cfg.get("knn", 10))
        d = geodesic_knn(d, k)

    dims = int(dis_cfg.get("dims", 2))
    coords = classical_mds(d, dims)

    meta = {
        "metric": metric,
        "dims": dims,
        "fuse_time": bool(dis_cfg.get("fuse_time", True)),
        "use_geodesic": bool(dis_cfg.get("use_geodesic", True)),
        "knn": int(dis_cfg.get("knn", 10)),
    }
    return coords, meta
