from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path


def _impute_zero_csi(data: np.ndarray) -> np.ndarray:
    """Impute zero-power CSI snapshots from nearest nonzero temporal neighbours.

    Positions with no received signal (e.g. fully shadowed from all TX) produce
    all-zero CSI.  These are degenerate for cosine-based dissimilarity because
    they look maximally different from everything *and* from each other, which
    wrecks the embedding.

    Strategy: for each zero-power snapshot, copy the CSI from the closest
    nonzero temporal neighbour.  If both sides have signal, linearly interpolate.
    This preserves sequential topology without inventing fake structure.
    """
    # data: [T, ...]
    t = data.shape[0]
    flat = data.reshape(t, -1)
    power = np.sum(np.abs(flat) ** 2, axis=1)
    zero_mask = power == 0
    if not np.any(zero_mask):
        return data  # nothing to impute

    nonzero_idx = np.where(~zero_mask)[0]
    if nonzero_idx.size == 0:
        return data  # everything is zero; can't impute

    out = data.copy()
    for i in np.where(zero_mask)[0]:
        # Find nearest nonzero neighbours on each side
        left = nonzero_idx[nonzero_idx < i]
        right = nonzero_idx[nonzero_idx > i]
        if left.size > 0 and right.size > 0:
            li, ri = left[-1], right[0]
            # Linear interpolation weight
            w = (i - li) / (ri - li)
            out[i] = (1.0 - w) * data[li] + w * data[ri]
        elif left.size > 0:
            out[i] = data[left[-1]]
        else:
            out[i] = data[right[0]]
    return out


def _adp_dissimilarity_single(h: np.ndarray, max_taps: int | None) -> np.ndarray:
    """ADP cosine dissimilarity for a single TX source.

    h: [T, ant, K]  — antenna × subcarrier for one coherent channel.
    Returns: [T, T] dissimilarity matrix.
    """
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


def _compute_adp_dissimilarity_matrix(csi: Dict[str, Any], max_taps: int | None = None) -> np.ndarray:
    data = csi.get("data")
    if data is None or data.size == 0:
        return np.zeros((0, 0))
    if data.ndim < 6:
        raise ValueError("CSI data has unexpected shape")

    # Impute zero-power snapshots before computing dissimilarity so that
    # shadowed positions don't create degenerate all-equal distances.
    data = _impute_zero_csi(data)

    # Use first RX/TX for now.
    h = data[:, 0, :, 0, :, :]  # [T, rx_ant, tx_ant, K_total]
    h = h.reshape(h.shape[0], -1, h.shape[-1])  # [T, ant, K_total]

    # Detect multi-source CSI (measurement antennas concatenated along freq axis).
    # frequencies_hz stores the base subcarrier grid — K_total / K_base = n_sources.
    freqs = csi.get("frequencies_hz")
    k_total = h.shape[-1]
    if freqs is not None and hasattr(freqs, '__len__'):
        k_base = len(freqs)
    else:
        k_base = k_total
    n_sources = max(1, k_total // k_base) if k_base > 0 else 1

    if n_sources > 1 and k_base * n_sources == k_total:
        # Split into per-source views and compute dissimilarity for each,
        # then average.  This prevents the IFFT from mixing CSI that came
        # from different TX positions into a single delay-domain transform.
        d_sum = None
        for src_idx in range(n_sources):
            h_src = h[:, :, src_idx * k_base : (src_idx + 1) * k_base]
            d_src = _adp_dissimilarity_single(h_src, max_taps)
            if d_sum is None:
                d_sum = d_src
            else:
                d_sum += d_src
        return d_sum / n_sources
    else:
        return _adp_dissimilarity_single(h, max_taps)


def _temporal_smooth_dissimilarity(d: np.ndarray, bandwidth: int = 3) -> np.ndarray:
    """Apply temporal smoothing to the dissimilarity matrix.

    Points that are temporally close should have similar dissimilarity
    patterns.  We smooth each row with a 1-D Gaussian kernel along the
    temporal axis to reduce single-point noise.
    """
    if bandwidth < 1 or d.shape[0] < 3:
        return d
    from scipy.ndimage import gaussian_filter1d
    d_smooth = gaussian_filter1d(d, sigma=bandwidth, axis=0)
    d_smooth = gaussian_filter1d(d_smooth, sigma=bandwidth, axis=1)
    # Keep symmetric and zero diagonal
    d_smooth = 0.5 * (d_smooth + d_smooth.T)
    np.fill_diagonal(d_smooth, 0.0)
    return np.maximum(d_smooth, 0.0)


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

    # Temporal smoothing of dissimilarity matrix to reduce noise
    smooth_bw = int(dis_cfg.get("temporal_smooth_bandwidth", 3))
    if smooth_bw > 0:
        d = _temporal_smooth_dissimilarity(d, bandwidth=smooth_bw)

    if bool(dis_cfg.get("fuse_time", True)) and times.size:
        window_s = float(dis_cfg.get("time_window_s", 2.0))
        weight = float(dis_cfg.get("time_weight", 0.6))
        d = fuse_time_dissimilarity(d, times, window_s, weight)

    if bool(dis_cfg.get("use_geodesic", True)):
        k = int(dis_cfg.get("knn", 20))
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
