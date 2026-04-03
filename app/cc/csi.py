from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np


def _to_numpy(x):
    try:
        return x.numpy()
    except AttributeError:
        return np.asarray(x)


def _as_complex(arr: Any) -> np.ndarray:
    if isinstance(arr, (tuple, list)) and len(arr) == 2:
        return _to_numpy(arr[0]) + 1j * _to_numpy(arr[1])
    arr = _to_numpy(arr)
    if np.iscomplexobj(arr):
        return arr
    return arr.astype(np.complex64)


def _expand_mask(mask: np.ndarray, target: np.ndarray) -> np.ndarray | None:
    if mask.ndim == target.ndim:
        return mask
    if mask.shape[-1] != target.shape[-1]:
        return None
    shape = [1] * target.ndim
    shape[-1] = target.shape[-1]
    remaining = list(mask.shape)
    for i in range(target.ndim - 1):
        if remaining and target.shape[i] == remaining[0]:
            shape[i] = remaining.pop(0)
    if remaining:
        return None
    return mask.reshape(shape)


def _paths_cfr_from_a_tau(
    paths: Any,
    freqs: np.ndarray,
    num_rx: int,
    rx_ant: int,
    num_tx: int,
    tx_ant: int,
) -> np.ndarray:
    """Compute CFR from raw path coefficients and delays.

    Sionna 0.19.2 shapes:
      paths.a   : [batch, num_rx, rx_ant, num_tx, tx_ant, max_paths, time_steps]
      paths.tau  : [batch, num_rx, num_tx, max_paths]

    tau has NO antenna dimensions — delays are shared across antenna elements.
    """
    target = (num_rx, rx_ant, num_tx, tx_ant, freqs.shape[0])
    a_raw = _as_complex(getattr(paths, "a"))
    tau_raw = _to_numpy(getattr(paths, "tau"))

    if a_raw.ndim == 0 or a_raw.size == 0:
        return np.zeros(target, dtype=np.complex64)

    # --- Apply path mask if available ---
    mask = None
    for attr in ("mask", "targets_sources_mask"):
        if hasattr(paths, attr):
            try:
                mask = _to_numpy(getattr(paths, attr)).astype(float)
            except Exception:
                mask = None
            break

    # --- Squeeze leading batch dim (exactly one) ---
    # Sionna 0.19.2 prepends a batch dim of size 1:
    #   a  : [batch, num_rx, rx_ant, num_tx, tx_ant, max_paths, time_steps]
    #   tau: [batch, num_rx, num_tx, max_paths]
    a = a_raw
    tau = tau_raw
    # a: expect 7-d with batch; squeeze to 6-d
    if a.ndim == 7 and a.shape[0] == 1:
        a = a[0]  # → (num_rx, rx_ant, num_tx, tx_ant, max_paths, time)
    # tau: expect 4-d with batch; squeeze to 3-d
    if tau.ndim == 4 and tau.shape[0] == 1:
        tau = tau[0]  # → (num_rx, num_tx, max_paths)

    # --- Collapse trailing time dim if present ---
    # a expected after squeeze: (num_rx, rx_ant, num_tx, tx_ant, num_paths, time)
    if a.ndim == 6:
        a = a[..., 0]  # → (num_rx, rx_ant, num_tx, tx_ant, num_paths)

    # Apply mask (broadcast-safe)
    if mask is not None:
        try:
            em = _expand_mask(mask, a)
            if em is not None:
                a = a * em
        except Exception:
            pass

    # --- Determine number of paths ---
    num_paths = a.shape[-1] if a.ndim >= 1 else 0
    if num_paths == 0:
        return np.zeros(target, dtype=np.complex64)

    # --- Normalize a to 5-d: (num_rx, rx_ant, num_tx, tx_ant, num_paths) ---
    try:
        a_5d = a.reshape(num_rx, rx_ant, num_tx, tx_ant, num_paths)
    except Exception:
        # Fallback: flatten and pad/trim
        a_flat = a.reshape(-1, num_paths)
        needed = num_rx * rx_ant * num_tx * tx_ant
        if a_flat.shape[0] >= needed:
            a_5d = a_flat[:needed].reshape(num_rx, rx_ant, num_tx, tx_ant, num_paths)
        else:
            padded = np.zeros((needed, num_paths), dtype=a.dtype)
            padded[: a_flat.shape[0]] = a_flat
            a_5d = padded.reshape(num_rx, rx_ant, num_tx, tx_ant, num_paths)

    # --- Normalize tau to 3-d: (num_rx, num_tx, num_paths) ---
    # tau does NOT have antenna dims in Sionna 0.19.2
    # tau's last dim should match a's num_paths; reconcile if different
    tau_num_paths = tau.shape[-1] if tau.ndim >= 1 else 0
    if tau_num_paths != num_paths:
        # Path count mismatch — pad or trim tau to match a's path count
        if tau.ndim >= 2:
            tau_flat = tau.reshape(-1, tau_num_paths)
        else:
            tau_flat = tau.reshape(1, -1)
        if tau_num_paths > num_paths:
            tau = tau_flat[:, :num_paths]
        else:
            padded = np.zeros((tau_flat.shape[0], num_paths))
            padded[:, :tau_num_paths] = tau_flat
            tau = padded
    try:
        tau_3d = tau.reshape(num_rx, num_tx, num_paths)
    except Exception:
        tau_flat = tau.ravel()
        needed = num_rx * num_tx * num_paths
        if tau_flat.size >= needed:
            tau_3d = tau_flat[:needed].reshape(num_rx, num_tx, num_paths)
        else:
            padded = np.zeros(needed)
            padded[: min(tau_flat.size, needed)] = tau_flat[: min(tau_flat.size, needed)]
            tau_3d = padded.reshape(num_rx, num_tx, num_paths)

    # Broadcast tau to (num_rx, 1, num_tx, 1, num_paths) for antenna dims
    tau_5d = tau_3d[:, np.newaxis, :, np.newaxis, :]

    # --- Compute CFR: H(f) = sum_paths a * exp(-j2pi*f*tau) ---
    # a_5d:  (num_rx, rx_ant, num_tx, tx_ant, num_paths)
    # tau_5d: (num_rx, 1,      num_tx, 1,      num_paths)
    # freqs:  (num_freq,)
    # exp → (num_rx, 1, num_tx, 1, num_paths, num_freq) via broadcasting
    exp = np.exp(-1j * 2.0 * np.pi * tau_5d[..., np.newaxis] * freqs[np.newaxis, :])
    # a_5d[..., np.newaxis] → (num_rx, rx_ant, num_tx, tx_ant, num_paths, num_freq)
    h = np.sum(a_5d[..., np.newaxis] * exp, axis=-2)
    # h shape: (num_rx, rx_ant, num_tx, tx_ant, num_freq)
    return h


def _reshape_with_leading_ones(arr: np.ndarray, target_ndim: int) -> np.ndarray:
    if arr.ndim >= target_ndim:
        return arr
    shape = (1,) * (target_ndim - arr.ndim) + arr.shape
    return arr.reshape(shape)


def _coerce_to_shape(arr: np.ndarray, target_shape: tuple[int, ...]) -> np.ndarray:
    if arr.shape == target_shape:
        return arr
    target_size = int(np.prod(target_shape))
    if arr.size == 0:
        return np.zeros(target_shape, dtype=arr.dtype if arr.size else np.complex64)
    if arr.size == target_size:
        return arr.reshape(target_shape)
    arr = _reshape_with_leading_ones(arr, len(target_shape))
    out = np.zeros(target_shape, dtype=arr.dtype)
    slices = tuple(slice(0, min(a, b)) for a, b in zip(arr.shape, target_shape))
    out[slices] = arr[slices]
    return out


def _force_cfr_shape(
    h: np.ndarray,
    num_rx: int,
    num_tx: int,
    num_freq: int,
    rx_ant: int = 1,
    tx_ant: int = 1,
) -> np.ndarray:
    # Collapse any unexpected middle dimensions into the target shape:
    #   (num_rx, rx_ant, num_tx, tx_ant, num_freq)
    target = (max(1, num_rx), max(1, rx_ant), max(1, num_tx), max(1, tx_ant), num_freq)
    target_size = int(np.prod(target))
    if h.ndim == 0 or h.size == 0:
        return np.zeros(target, dtype=np.complex64)
    if h.shape[-1] != num_freq:
        for idx, size in enumerate(h.shape):
            if size == num_freq:
                h = np.moveaxis(h, idx, -1)
                break
    if h.size == target_size:
        return h.reshape(target)
    # Flatten to (links, freq) and pad/trim to match target
    flat = h.reshape(-1, h.shape[-1])
    needed = target[0] * target[1] * target[2] * target[3]
    if flat.shape[0] >= needed:
        trimmed = flat[:needed]
    else:
        trimmed = np.zeros((needed, flat.shape[-1]), dtype=flat.dtype)
        trimmed[: flat.shape[0]] = flat
    return trimmed.reshape(target)


def _build_subcarrier_frequencies(cfg: Dict[str, Any], fallback_center: float) -> Tuple[np.ndarray, float]:
    ofdm = cfg.get("ofdm", {}) if isinstance(cfg, dict) else {}
    num_sc = int(ofdm.get("num_subcarriers", 64))
    spacing = float(ofdm.get("subcarrier_spacing_hz", 150e3))
    center = ofdm.get("center_frequency_hz")
    if center is None:
        center = fallback_center
    center = float(center)
    if num_sc < 1:
        num_sc = 1
    # Use baseband offsets; keep center frequency for bookkeeping.
    k = np.arange(num_sc, dtype=float) - (num_sc - 1) / 2.0
    return k * spacing, center


def _compute_paths(scene, sim_cfg: Dict[str, Any]) -> Any:
    return scene.compute_paths(
        max_depth=int(sim_cfg.get("max_depth", 3)),
        method=str(sim_cfg.get("method", "fibonacci")),
        num_samples=int(sim_cfg.get("samples_per_src", 200000)),
        los=bool(sim_cfg.get("los", True)),
        reflection=bool(sim_cfg.get("specular_reflection", True)),
        diffraction=bool(sim_cfg.get("diffraction", False)),
        scattering=bool(sim_cfg.get("diffuse_reflection", False)),
        ris=bool(sim_cfg.get("ris", False)),
    )


def compute_csi(
    scene: Any,
    cfg: Dict[str, Any],
    positions: np.ndarray,
    times: np.ndarray,
    measurement_antennas: list | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    cc_cfg = cfg.get("channel_charting", {})
    csi_cfg = cc_cfg.get("csi", {})
    sim_cfg = cfg.get("simulation", {})
    csi_type = str(csi_cfg.get("type", "cfr"))

    role = str(cc_cfg.get("role", "downlink")).lower()
    move_tx = role == "uplink"

    # Resolve measurement antennas from config or argument
    if measurement_antennas is None:
        measurement_antennas = cc_cfg.get("measurement_antennas", [])
    if not measurement_antennas:
        measurement_antennas = []

    tx = next(iter(scene.transmitters.values()))
    rx = next(iter(scene.receivers.values()))

    freq_hz = float(sim_cfg.get("frequency_hz", 28e9))
    freqs, center = _build_subcarrier_frequencies(csi_cfg, freq_hz)

    csi_out: Dict[str, Any] = {
        "type": csi_type,
        "frequencies_hz": freqs,
        "center_frequency_hz": center,
        "times_s": times,
    }
    path_out: Dict[str, Any] = {
        "tau_s": [],
        "theta_r": [],
        "phi_r": [],
        "theta_t": [],
        "phi_t": [],
    }

    num_rx = len(scene.receivers)
    num_tx = len(scene.transmitters)

    # Sionna 0.19.2 PlanarArray has .num_ant but NOT .num_rows / .num_cols.
    # Prefer num_ant (total elements), falling back to rows * cols for newer
    # versions that may expose them.
    def _array_element_count(arr) -> int:
        na = getattr(arr, "num_ant", None)
        if na is not None:
            return max(1, int(na))
        rows = int(getattr(arr, "num_rows", 1))
        cols = int(getattr(arr, "num_cols", 1))
        return max(1, rows * cols)

    rx_ant = _array_element_count(scene.rx_array)
    tx_ant = _array_element_count(scene.tx_array)
    import logging as _log
    _log.getLogger(__name__).info(
        "CSI array config: num_rx=%d, rx_ant=%d, num_tx=%d, tx_ant=%d",
        num_rx, rx_ant, num_tx, tx_ant,
    )

    # When measurement antennas are provided, we collect CSI from each one
    # and concatenate along a new leading "antenna" axis so the feature
    # extractor sees richer multi-view observations.
    use_multi_antenna = len(measurement_antennas) > 0

    n_antenna_sources = 1 + len(measurement_antennas) if use_multi_antenna else 1
    num_freq_total = freqs.shape[0] * n_antenna_sources

    snapshots = []
    target_shape = None
    if csi_type == "cfr":
        target_shape = (num_rx, rx_ant, num_tx, tx_ant, num_freq_total)
    cir_tau = None
    taps_tau = None
    n_pos = len(positions)
    _csi_log = _log.getLogger(__name__)
    for idx, pos in enumerate(positions):
        if idx % max(1, n_pos // 10) == 0 or idx == n_pos - 1:
            _csi_log.info("CSI progress: %d/%d positions (%.0f%%)", idx + 1, n_pos, 100.0 * (idx + 1) / n_pos)
        if move_tx:
            tx.position = np.array(pos, dtype=float)
        else:
            rx.position = np.array(pos, dtype=float)
        paths = _compute_paths(scene, sim_cfg)

        try:
            path_out["tau_s"].append(_to_numpy(paths.tau))
        except Exception:
            path_out["tau_s"].append(np.array([]))
        for key, attr in [
            ("theta_r", "theta_r"),
            ("phi_r", "phi_r"),
            ("theta_t", "theta_t"),
            ("phi_t", "phi_t"),
        ]:
            try:
                path_out[key].append(_to_numpy(getattr(paths, attr)))
            except Exception:
                path_out[key].append(np.array([]))

        if csi_type == "cfr":
            try:
                if hasattr(paths, "cfr"):
                    cfr = paths.cfr(freqs, num_time_steps=1, out_type="numpy")
                    h = _as_complex(cfr)
                    # Sionna can return various shapes depending on version /
                    # array config.  Squeeze any leading batch dims of size 1,
                    # then collapse the time dimension (second-to-last) if
                    # present.
                    while h.ndim > 5 and h.shape[0] == 1:
                        h = h[0]
                    # After squeezing, expect:
                    #   5-d: (num_rx, rx_ant, num_tx, tx_ant, num_freq)
                    #   6-d: (num_rx, rx_ant, num_tx, tx_ant, time, num_freq)
                    if h.ndim == 6:
                        h = h[:, :, :, :, 0, :]
                    elif h.ndim > 6:
                        # Collapse unexpected middle dims
                        h = h.reshape(h.shape[0], h.shape[1], h.shape[2],
                                      h.shape[3], -1, h.shape[-1])
                        h = h[:, :, :, :, 0, :]
                else:
                    h = _paths_cfr_from_a_tau(paths, freqs, num_rx, rx_ant, num_tx, tx_ant)
            except Exception:
                h = np.zeros(target_shape, dtype=np.complex64)
            # Force to consistent per-antenna shape
            single_shape = (num_rx, rx_ant, num_tx, tx_ant, freqs.shape[0])
            if h.shape != single_shape:
                try:
                    h = _coerce_to_shape(h, single_shape)
                except Exception:
                    try:
                        h = _force_cfr_shape(h, num_rx, num_tx, freqs.shape[0], rx_ant, tx_ant)
                        if h.shape != single_shape:
                            h = _coerce_to_shape(h, single_shape)
                    except Exception:
                        h = np.zeros(single_shape, dtype=np.complex64)

            # Multi-antenna: collect CSI from each measurement antenna
            if use_multi_antenna:
                multi_h = [h]
                orig_pos = np.array(tx.position, dtype=float)
                for ma in measurement_antennas:
                    ma_pos = ma.get("position", ma) if isinstance(ma, dict) else ma
                    tx.position = np.array(ma_pos, dtype=float)
                    try:
                        ma_paths = _compute_paths(scene, sim_cfg)
                        ma_h = _paths_cfr_from_a_tau(ma_paths, freqs, num_rx, rx_ant, num_tx, tx_ant)
                    except Exception:
                        ma_h = np.zeros(single_shape, dtype=np.complex64)
                    if ma_h.shape != single_shape:
                        try:
                            ma_h = _coerce_to_shape(ma_h, single_shape)
                        except Exception:
                            ma_h = np.zeros(single_shape, dtype=np.complex64)
                    multi_h.append(ma_h)
                tx.position = orig_pos
                # Concatenate along frequency axis
                h = np.concatenate(multi_h, axis=-1)

            if target_shape is not None and h.shape != target_shape:
                h = _coerce_to_shape(h, target_shape)
            snapshots.append(h)
        elif csi_type == "cir":
            cir_cfg = csi_cfg.get("cir", {})
            sampling = float(cir_cfg.get("sampling_frequency_hz", 100e6))
            num_time_steps = int(cir_cfg.get("num_time_steps", 1))
            a, tau = paths.cir(sampling_frequency=sampling, num_time_steps=num_time_steps, out_type="numpy")
            a = _as_complex(a)
            tau = _to_numpy(tau)
            if num_time_steps > 1 and a.ndim >= 6:
                a = a[:, :, :, :, 0, :]
            if target_shape is None:
                if a.ndim >= 5:
                    target_shape = a.shape
                else:
                    last = a.shape[-1] if a.ndim >= 1 else 0
                    target_shape = (num_rx, rx_ant, num_tx, tx_ant, last)
            a = _coerce_to_shape(a, target_shape)
            snapshots.append(a)
            if cir_tau is None:
                cir_tau = tau
        else:
            taps_cfg = csi_cfg.get("taps", {})
            bandwidth = float(taps_cfg.get("bandwidth_hz", 20e6))
            l_min = int(taps_cfg.get("l_min", -32))
            l_max = int(taps_cfg.get("l_max", 32))
            a, tau = paths.taps(bandwidth=bandwidth, l_min=l_min, l_max=l_max, out_type="numpy")
            a = _as_complex(a)
            tau = _to_numpy(tau)
            if target_shape is None:
                if a.ndim >= 5:
                    target_shape = a.shape
                else:
                    last = a.shape[-1] if a.ndim >= 1 else 0
                    target_shape = (num_rx, rx_ant, num_tx, tx_ant, last)
            a = _coerce_to_shape(a, target_shape)
            snapshots.append(a)
            if taps_tau is None:
                taps_tau = tau

    # Ensure all snapshots share the same shape before stacking
    if snapshots:
        ref_shape = target_shape if target_shape is not None else snapshots[0].shape
        fixed = []
        for i, s in enumerate(snapshots):
            if s.shape != ref_shape:
                try:
                    fixed.append(_coerce_to_shape(s, ref_shape))
                except Exception:
                    fixed.append(np.zeros(ref_shape, dtype=np.complex64))
            else:
                fixed.append(s)
        csi_array = np.stack(fixed, axis=0)
    else:
        csi_array = np.zeros((0,))
    csi_out["data"] = csi_array
    if csi_type == "cir" and cir_tau is not None:
        csi_out["tau_s"] = cir_tau
    if csi_type == "taps" and taps_tau is not None:
        csi_out["tau_s"] = taps_tau

    # Stack path params for optional analysis
    for key in list(path_out.keys()):
        try:
            path_out[key] = np.array(path_out[key], dtype=object)
        except Exception:
            path_out[key] = np.array([], dtype=object)

    return csi_out, path_out
