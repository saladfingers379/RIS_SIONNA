from __future__ import annotations

import copy
from typing import Any, Dict

from app.config import load_config
from app.io import save_yaml


DEFAULT_CHANNEL_CHARTING = {
    "enabled": True,
    "role": "downlink",  # downlink: tx fixed, rx moves; uplink: rx fixed, tx moves
    "trajectory": {
        "type": "straight",  # straight | waypoints
        "start": [0.0, 0.0, 1.5],
        "end": [20.0, 10.0, 1.5],
        "num_steps": 100,
        "dt_s": 0.1,
        "random_walk": {
            "step_std": 0.6,
            "smooth_alpha": 0.2,
            "drift": [0.0, 0.0, 0.0],
        },
        "spiral": {
            "center": [0.0, 0.0, 1.5],
            "radius_start": 1.0,
            "radius_end": 10.0,
            "turns": 2.0,
        },
    },
    "csi": {
        "type": "cfr",  # cfr | cir | taps
        "ofdm": {
            "num_subcarriers": 64,
            "subcarrier_spacing_hz": 150e3,
            "center_frequency_hz": None,
        },
        "cir": {
            "sampling_frequency_hz": 100e6,
            "num_time_steps": 1,
        },
        "taps": {
            "bandwidth_hz": 20e6,
            "l_min": -32,
            "l_max": 32,
        },
    },
    "features": {
        "type": "r2m",  # r2m | beamspace_mag
        "window": 1,
        "r2m": {
            "beamspace": True,
            "mode": "diag",  # diag | full
        },
        "beamspace_mag": {
            "beamspace": True,
            "power": True,
        },
    },
    "model": {
        "type": "autoencoder",
        "embedding_dim": 2,
        "hidden_dims": [128, 64],
        "epochs": 200,
        "learning_rate": 1e-3,
        "adjacency_weight": 0.2,
        "normalize_features": True,
        "seed": 7,
    },
    "tracking": {
        "enabled": True,
        "method": "ema",
        "alpha": 0.2,
    },
    "evaluation": {
        "align": "affine",
        "dims": 2,
    },
}


def _deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def normalize_channel_charting_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(cfg)
    cc_cfg = copy.deepcopy(DEFAULT_CHANNEL_CHARTING)
    _deep_update(cc_cfg, cfg.get("channel_charting", {}))
    cfg["channel_charting"] = cc_cfg
    return cfg


def load_channel_charting_config(path: str) -> Dict[str, Any]:
    config = load_config(path).data
    return normalize_channel_charting_config(config)


def snapshot_channel_charting_config(output_dir, cfg: Dict[str, Any]) -> None:
    save_yaml(output_dir / "config.yaml", cfg)
