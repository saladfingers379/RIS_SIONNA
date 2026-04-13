"""Objective helpers for RIS synthesis."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def _masked_values(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    mask_arr = np.asarray(mask, dtype=bool)
    if arr.shape != mask_arr.shape:
        raise ValueError("values and mask must have matching shapes")
    return arr[mask_arr]


def masked_mean_log_path_gain(path_gain_linear, mask, eps) -> float:
    masked = _masked_values(path_gain_linear, mask)
    if masked.size == 0:
        raise ValueError("ROI mask does not cover any cells")
    return float(np.mean(np.log(masked + float(eps))))


def masked_soft_coverage(rx_power_dbm, mask, threshold_dbm, temperature_db) -> float:
    masked = _masked_values(rx_power_dbm, mask)
    if masked.size == 0:
        raise ValueError("ROI mask does not cover any cells")
    scaled = (masked - float(threshold_dbm)) / max(float(temperature_db), 1.0e-9)
    return float(np.mean(1.0 / (1.0 + np.exp(-scaled))))


def compute_roi_metrics(path_gain_db, rx_power_dbm, mask, threshold_dbm) -> Dict[str, Any]:
    gain_masked = _masked_values(path_gain_db, mask)
    rx_masked = _masked_values(rx_power_dbm, mask)
    if gain_masked.size == 0:
        raise ValueError("ROI mask does not cover any cells")
    return {
        "num_masked_cells": int(rx_masked.size),
        "mean_path_gain_db": float(np.mean(gain_masked)),
        "mean_rx_power_dbm": float(np.mean(rx_masked)),
        "median_rx_power_dbm": float(np.median(rx_masked)),
        "p05_rx_power_dbm": float(np.percentile(rx_masked, 5.0)),
        "p95_rx_power_dbm": float(np.percentile(rx_masked, 95.0)),
        "coverage_fraction_above_threshold": float(np.mean(rx_masked >= float(threshold_dbm))),
    }
