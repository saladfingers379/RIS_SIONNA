from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np


def _to_numpy(x):
    try:
        return x.numpy()
    except AttributeError:
        return np.asarray(x)


def _paths_coefficients(paths) -> np.ndarray:
    a = paths.a
    if isinstance(a, (tuple, list)) and len(a) == 2:
        a_real, a_imag = a
        return _to_numpy(a_real) + 1j * _to_numpy(a_imag)
    return _to_numpy(a)


def _paths_mask(paths) -> Optional[np.ndarray]:
    for attr in ("valid", "mask", "targets_sources_mask"):
        if hasattr(paths, attr):
            try:
                return _to_numpy(getattr(paths, attr)).astype(bool)
            except Exception:
                continue
    return None


def _count_ris_paths(paths, scene: Optional[Any] = None) -> Optional[int]:
    try:
        objects = _to_numpy(getattr(paths, "objects", None))
    except Exception:
        objects = None
    if scene is not None and objects is not None and hasattr(scene, "ris") and objects is not None:
        try:
            ris_ids = [int(getattr(ris, "object_id")) for ris in scene.ris.values()]
        except Exception:
            ris_ids = []
        ris_ids = [rid for rid in ris_ids if rid is not None]
        if ris_ids and getattr(objects, "size", 0):
            if objects.ndim >= 4:
                inter = objects[:, 0, 0, :]
            elif objects.ndim == 2:
                inter = objects
            else:
                inter = None
            if inter is not None:
                ris_hit = np.isin(inter, ris_ids)
                per_path = np.any(ris_hit, axis=0)
                mask = _paths_mask(paths)
                if mask is not None and mask.shape[-1] == per_path.shape[-1]:
                    per_path = per_path & mask.reshape(-1, per_path.shape[-1]).any(axis=0)
                return int(np.sum(per_path))
    try:
        interactions = _to_numpy(paths.interactions)
    except Exception:
        interactions = None
    if interactions is None or interactions.size == 0:
        return None
    type_map = _interaction_type_map()
    ris_ids = [k for k, v in type_map.items() if v == "ris"]
    if not ris_ids:
        return None
    mask = _paths_mask(paths)
    if mask is None:
        return None
    # interactions shape: [num_vertices, num_rx, num_tx, num_paths]
    if interactions.ndim >= 4:
        inter = interactions[:, 0, 0, :]
    elif interactions.ndim == 2:
        inter = interactions
    else:
        return None
    ris_hit = np.isin(inter, ris_ids)
    per_path = np.any(ris_hit, axis=0)
    if mask.ndim >= 1 and mask.shape[-1] == per_path.shape[-1]:
        per_path = per_path & mask.reshape(-1, per_path.shape[-1]).any(axis=0)
    return int(np.sum(per_path))


def compute_path_metrics(paths, tx_power_dbm: float, scene: Optional[Any] = None) -> Dict[str, Any]:
    """Compute simple, report-friendly metrics from Sionna RT Paths."""
    a = _paths_coefficients(paths)

    # Sum over all paths and antennas to get a total path gain proxy.
    power_linear = np.abs(a) ** 2
    total_path_gain_linear = float(power_linear.sum())
    total_path_gain_db = 10.0 * np.log10(total_path_gain_linear + 1e-12)

    mask = _paths_mask(paths)
    num_valid_paths = int(mask.sum()) if mask is not None else None

    tx_power_dbm = _to_numpy(tx_power_dbm).item()
    metrics = {
        "total_path_gain_linear": total_path_gain_linear,
        "total_path_gain_db": total_path_gain_db,
        "rx_power_dbm_estimate": tx_power_dbm + total_path_gain_db,
        "num_valid_paths": num_valid_paths,
    }
    ris_count = _count_ris_paths(paths, scene=scene)
    if ris_count is not None:
        metrics["num_ris_paths"] = ris_count

    try:
        tau = _to_numpy(paths.tau)
        metrics["min_delay_s"] = float(np.min(tau))
        metrics["max_delay_s"] = float(np.max(tau))
    except Exception:
        pass

    return metrics


def extract_path_data(paths) -> Dict[str, Any]:
    """Extract per-path arrays for plotting and advanced metrics."""
    a = _paths_coefficients(paths)
    power = np.abs(a) ** 2
    if power.ndim < 1:
        return {
            "delays_s": np.array([]),
            "aoa_azimuth_rad": np.array([]),
            "aoa_elevation_rad": np.array([]),
            "weights": np.array([]),
            "metrics": {},
        }

    # Sum over all axes except path axis (last)
    sum_axes = tuple(range(power.ndim - 1))
    path_power = power.sum(axis=sum_axes)

    mask = _paths_mask(paths)
    tau = _to_numpy(paths.tau)
    theta_r = _to_numpy(paths.theta_r)
    phi_r = _to_numpy(paths.phi_r)

    if mask is None or mask.ndim < 1:
        delays = np.array([])
        aoa_el = np.array([])
        aoa_az = np.array([])
        weights = np.array([])
    else:
        # Broadcast path_power to mask shape if needed
        try:
            weights = path_power * mask
            delays = tau[mask]
            aoa_el = theta_r[mask]
            aoa_az = phi_r[mask]
            weights = weights[mask]
        except Exception:
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
    a = _paths_coefficients(paths)
    power = np.abs(a) ** 2
    if power.ndim >= 1:
        sum_axes = tuple(range(power.ndim - 1))
        path_power = power.sum(axis=sum_axes)
    else:
        path_power = np.array([])

    mask = _paths_mask(paths)
    tau = _to_numpy(paths.tau)
    verts = _to_numpy(paths.vertices)
    objects = _to_numpy(getattr(paths, "objects", np.array([])))
    interactions = _to_numpy(getattr(paths, "interactions", np.array([])))

    try:
        sources = _to_numpy(paths.sources)
        targets = _to_numpy(paths.targets)
    except Exception:
        sources = None
        targets = None

    type_map = _interaction_type_map()
    rows = []
    if mask is None or mask.ndim < 1:
        return {"rows": rows, "tx_power_dbm": float(_to_numpy(tx_power_dbm).item())}

    num_paths = mask.shape[-1]
    per_path = np.any(mask.reshape(-1, num_paths), axis=0)
    num_vertices = verts.shape[0] if verts.size else 0
    for p in range(num_paths):
        if not per_path[p]:
            continue

        pts = []
        if sources is not None and sources.size:
            pts.append(sources[0])
        if targets is not None and targets.size:
            tgt = targets[0]
        else:
            tgt = None

        if num_vertices:
            v = verts[:, 0, 0, p, :] if verts.ndim >= 5 else verts[:, p, :]
        else:
            v = None
        interaction_names = []
        if interactions.size:
            inter = interactions[:, 0, 0, p] if interactions.ndim >= 4 else interactions[:, p]
            for i in range(num_vertices):
                if inter[i] != 0:
                    if v is not None:
                        pts.append(v[i])
                    interaction_names.append(type_map.get(int(inter[i]), f"interaction_{int(inter[i])}"))
        elif objects.size:
            inter = objects[:, 0, 0, p] if objects.ndim >= 4 else objects[:, p]
            for i in range(num_vertices):
                if inter[i] != -1:
                    if v is not None:
                        pts.append(v[i])
                    interaction_names.append(f"object_{int(inter[i])}")
        if tgt is not None:
            pts.append(tgt)

        order = len(interaction_names)
        path_type = "LOS" if order == 0 else "+".join(sorted(set(interaction_names))) or "NLOS"

        length_m = 0.0
        if len(pts) >= 2:
            for i in range(len(pts) - 1):
                length_m += float(np.linalg.norm(np.asarray(pts[i + 1]) - np.asarray(pts[i])))

        try:
            power_linear = float(path_power[p])
        except Exception:
            power_linear = 0.0
        power_db = 10.0 * np.log10(power_linear + 1e-12)

        delay_s = 0.0
        if tau.size:
            tau_flat = tau.reshape(-1, num_paths)
            vals = tau_flat[:, p]
            vals = vals[np.isfinite(vals)]
            vals = vals[vals >= 0]
            if vals.size:
                delay_s = float(vals[0])

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
