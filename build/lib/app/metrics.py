from __future__ import annotations

from typing import Any, Dict

import numpy as np


def _to_numpy(x):
    try:
        return x.numpy()
    except AttributeError:
        return np.asarray(x)


def compute_path_metrics(paths, tx_power_dbm: float) -> Dict[str, Any]:
    """Compute simple, report-friendly metrics from Sionna RT Paths."""
    a_real, a_imag = paths.a
    a = _to_numpy(a_real) + 1j * _to_numpy(a_imag)

    # Sum over all paths and antennas to get a total path gain proxy.
    power_linear = np.abs(a) ** 2
    total_path_gain_linear = float(power_linear.sum())
    total_path_gain_db = 10.0 * np.log10(total_path_gain_linear + 1e-12)

    try:
        valid = _to_numpy(paths.valid)
        num_valid_paths = int(valid.sum())
    except Exception:
        num_valid_paths = None

    tx_power_dbm = _to_numpy(tx_power_dbm).item()
    metrics = {
        "total_path_gain_linear": total_path_gain_linear,
        "total_path_gain_db": total_path_gain_db,
        "rx_power_dbm_estimate": tx_power_dbm + total_path_gain_db,
        "num_valid_paths": num_valid_paths,
    }

    try:
        tau = _to_numpy(paths.tau)
        metrics["min_delay_s"] = float(np.min(tau))
        metrics["max_delay_s"] = float(np.max(tau))
    except Exception:
        pass

    return metrics


def extract_path_data(paths) -> Dict[str, Any]:
    """Extract per-path arrays for plotting and advanced metrics."""
    a_real, a_imag = paths.a
    a = _to_numpy(a_real) + 1j * _to_numpy(a_imag)
    power = np.abs(a) ** 2
    # Sum over rx/tx antennas to get power per path
    path_power = power.sum(axis=(1, 3))  # [num_rx, num_tx, num_paths]

    valid = _to_numpy(paths.valid).astype(bool)
    tau = _to_numpy(paths.tau)
    theta_r = _to_numpy(paths.theta_r)
    phi_r = _to_numpy(paths.phi_r)

    mask = valid
    if mask.ndim == 3:
        weights = path_power * mask
        delays = tau[mask]
        aoa_el = theta_r[mask]
        aoa_az = phi_r[mask]
        weights = weights[mask]
    else:
        delays = np.array([])
        aoa_el = np.array([])
        aoa_az = np.array([])
        weights = np.array([])

    metrics: Dict[str, Any] = {}
    if delays.size > 0 and np.any(weights > 0):
        wsum = weights.sum()
        mean_delay = float(np.sum(weights * delays) / wsum)
        rms_delay = float(np.sqrt(np.sum(weights * (delays - mean_delay) ** 2) / wsum))
        metrics["mean_delay_s"] = mean_delay
        metrics["rms_delay_spread_s"] = rms_delay
        metrics["aoa_azimuth_mean_deg"] = float(np.degrees(np.sum(weights * aoa_az) / wsum))
        metrics["aoa_elevation_mean_deg"] = float(np.degrees(np.sum(weights * aoa_el) / wsum))

    return {
        "delays_s": delays,
        "aoa_azimuth_rad": aoa_az,
        "aoa_elevation_rad": aoa_el,
        "weights": weights,
        "metrics": metrics,
    }


def _interaction_type_map() -> Dict[int, str]:
    try:
        from sionna.rt import InteractionType  # pylint: disable=import-error
    except Exception:
        return {}

    mapping: Dict[int, str] = {}
    for name in dir(InteractionType):
        if not name.isupper():
            continue
        value = getattr(InteractionType, name)
        try:
            mapping[int(value)] = name.lower()
        except Exception:
            continue
    return mapping


def build_paths_table(paths, tx_power_dbm: float) -> Dict[str, Any]:
    """Create a table-friendly view of path geometry and power."""
    a_real, a_imag = paths.a
    a = _to_numpy(a_real) + 1j * _to_numpy(a_imag)
    power = np.abs(a) ** 2
    path_power = power.sum(axis=(1, 3))  # [num_rx, num_tx, num_paths]

    valid = _to_numpy(paths.valid).astype(bool)
    tau = _to_numpy(paths.tau)
    verts = _to_numpy(paths.vertices)
    interactions = _to_numpy(paths.interactions)

    try:
        src = _to_numpy(paths.sources).reshape(3)
        tgt = _to_numpy(paths.targets).reshape(3)
    except Exception:
        src = None
        tgt = None

    type_map = _interaction_type_map()
    rows = []
    num_paths = valid.shape[-1]
    num_vertices = verts.shape[0]
    for p in range(num_paths):
        if not valid[0, 0, p]:
            continue
        pts = []
        if src is not None:
            pts.append(src)
        inter = interactions[:, 0, 0, p]
        v = verts[:, 0, 0, p, :]
        interaction_names = []
        for i in range(num_vertices):
            if inter[i] != 0:
                pts.append(v[i])
                interaction_names.append(type_map.get(int(inter[i]), f"interaction_{int(inter[i])}"))
        if tgt is not None:
            pts.append(tgt)

        order = int(np.sum(inter != 0))
        path_type = "LOS" if order == 0 else "+".join(sorted(set(interaction_names))) or "NLOS"

        length_m = 0.0
        if len(pts) >= 2:
            for i in range(len(pts) - 1):
                length_m += float(np.linalg.norm(np.asarray(pts[i + 1]) - np.asarray(pts[i])))

        power_linear = float(path_power[0, 0, p])
        power_db = 10.0 * np.log10(power_linear + 1e-12)
        delay_s = float(tau[0, 0, p])

        rows.append(
            {
                "path_id": int(p),
                "order": order,
                "type": path_type,
                "path_length_m": length_m,
                "delay_s": delay_s,
                "power_linear": power_linear,
                "power_db": power_db,
                "interactions": interaction_names,
            }
        )

    return {
        "rows": rows,
        "tx_power_dbm": float(_to_numpy(tx_power_dbm).item()),
    }
