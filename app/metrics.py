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
