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


def _normalize_a_tau(
    a: np.ndarray,
    tau: np.ndarray,
    num_rx: int,
    rx_ant: int,
    num_tx: int,
    tx_ant: int,
) -> tuple[np.ndarray, np.ndarray]:
    total_links = max(1, num_rx * rx_ant * num_tx * tx_ant)
    a_flat = a.reshape(total_links, -1)
    tau_flat = tau.reshape(total_links, -1)
    num_paths = a_flat.shape[1]
    a_norm = a_flat.reshape(num_rx, rx_ant, num_tx, tx_ant, num_paths)
    tau_norm = tau_flat.reshape(num_rx, rx_ant, num_tx, tx_ant, num_paths)
    return a_norm, tau_norm


def _paths_cfr_from_a_tau(
    paths: Any,
    freqs: np.ndarray,
    num_rx: int,
    rx_ant: int,
    num_tx: int,
    tx_ant: int,
) -> np.ndarray:
    a = _as_complex(getattr(paths, "a"))
    tau = _to_numpy(getattr(paths, "tau"))

    mask = None
    for attr in ("mask", "targets_sources_mask"):
        if hasattr(paths, attr):
            try:
                mask = _to_numpy(getattr(paths, attr)).astype(float)
            except Exception:
                mask = None
            break
    if mask is not None:
        mask = _expand_mask(mask, a)
        if mask is not None:
            a = a * mask

    try:
        a_norm, tau_norm = _normalize_a_tau(a, tau, num_rx, rx_ant, num_tx, tx_ant)
    except Exception:
        a_norm = a
        tau_norm = tau

    num_paths = a_norm.shape[-1] if a_norm.ndim else 0
    if num_paths == 0:
        return np.zeros((num_rx, rx_ant, num_tx, tx_ant, freqs.shape[0]), dtype=np.complex64)

    exp = np.exp(-1j * 2.0 * np.pi * tau_norm[..., None] * freqs[None, ...])
    h = np.sum(a_norm[..., None] * exp, axis=-2)
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


def _force_cfr_shape(h: np.ndarray, num_rx: int, num_tx: int, num_freq: int) -> np.ndarray:
    # Collapse any unexpected middle dimensions into a single antenna dimension.
    if h.ndim == 0:
        return np.zeros((num_rx, 1, num_tx, 1, num_freq), dtype=np.complex64)
    if h.shape[-1] != num_freq:
        # If last dim is not frequency, try to move a matching dim to the end.
        for idx, size in enumerate(h.shape):
            if size == num_freq:
                h = np.moveaxis(h, idx, -1)
                break
    flat = h.reshape(-1, h.shape[-1])
    # Best effort: assign first dimension to num_rx and num_tx if possible.
    total_links = flat.shape[0]
    rx = max(1, num_rx)
    tx = max(1, num_tx)
    ant = max(1, total_links // (rx * tx))
    trimmed = flat[: rx * tx * ant].reshape(rx, ant, tx, 1, h.shape[-1])
    return trimmed


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
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    cc_cfg = cfg.get("channel_charting", {})
    csi_cfg = cc_cfg.get("csi", {})
    sim_cfg = cfg.get("simulation", {})
    csi_type = str(csi_cfg.get("type", "cfr"))

    role = str(cc_cfg.get("role", "downlink")).lower()
    move_tx = role == "uplink"

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
    rx_ant = int(getattr(scene.rx_array, "num_rows", 1)) * int(getattr(scene.rx_array, "num_cols", 1))
    tx_ant = int(getattr(scene.tx_array, "num_rows", 1)) * int(getattr(scene.tx_array, "num_cols", 1))

    snapshots = []
    target_shape = None
    if csi_type == "cfr":
        target_shape = (num_rx, rx_ant, num_tx, tx_ant, freqs.shape[0])
    cir_tau = None
    taps_tau = None
    for idx, pos in enumerate(positions):
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
            if hasattr(paths, "cfr"):
                cfr = paths.cfr(freqs, num_time_steps=1, out_type="numpy")
                h = _as_complex(cfr)
                # Shape: [num_rx, rx_ant, num_tx, tx_ant, time, num_freq]
                if h.ndim >= 6:
                    h = h[:, :, :, :, 0, :]
            else:
                h = _paths_cfr_from_a_tau(paths, freqs, num_rx, rx_ant, num_tx, tx_ant)
            if target_shape is not None:
                try:
                    h = _coerce_to_shape(h, target_shape)
                except Exception:
                    h = _force_cfr_shape(h, num_rx, num_tx, freqs.shape[0])
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

    csi_array = np.stack(snapshots, axis=0) if snapshots else np.zeros((0,))
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
