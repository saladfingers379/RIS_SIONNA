from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class Config:
    data: Dict[str, Any]

    @property
    def runtime(self) -> Dict[str, Any]:
        return self.data.get("runtime", {})

    @property
    def simulation(self) -> Dict[str, Any]:
        return self.data.get("simulation", {})

    @property
    def scene(self) -> Dict[str, Any]:
        return self.data.get("scene", {})

    @property
    def radio_map(self) -> Dict[str, Any]:
        return self.data.get("radio_map", {})

    @property
    def output(self) -> Dict[str, Any]:
        return self.data.get("output", {})

    @property
    def quality(self) -> Dict[str, Any]:
        return self.data.get("quality", {})

    @property
    def ris(self) -> Dict[str, Any]:
        return self.data.get("ris", {})


QUALITY_PRESETS = {
    "preview": {
        "simulation": {
            "max_depth": 2,
            "max_num_paths_per_src": 50000,
            "samples_per_src": 50000,
        },
        "radio_map": {
            "samples_per_tx": 80000,
            "max_depth": 2,
        },
    },
    "standard": {
        "simulation": {
            "max_depth": 3,
            "max_num_paths_per_src": 200000,
            "samples_per_src": 200000,
        },
        "radio_map": {
            "samples_per_tx": 200000,
            "max_depth": 3,
        },
    },
    "high": {
        "simulation": {
            "max_depth": 5,
            "max_num_paths_per_src": 1000000,
            "samples_per_src": 1000000,
        },
        "radio_map": {
            "samples_per_tx": 2000000,
            "max_depth": 5,
        },
    },
    "benchmark": {
        "simulation": {
            "max_depth": 6,
            "max_num_paths_per_src": 2000000,
            "samples_per_src": 2000000,
        },
        "radio_map": {
            "samples_per_tx": 4000000,
            "max_depth": 6,
        },
    },
}


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("Config must be a YAML mapping")

    data = apply_quality_preset(data)
    return Config(data=data)


def apply_quality_preset(config: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(config)
    preset = cfg.get("quality", {}).get("preset")
    if not preset:
        return cfg
    if preset not in QUALITY_PRESETS:
        return cfg

    overrides = QUALITY_PRESETS[preset]
    for section, values in overrides.items():
        cfg.setdefault(section, {})
        for key, value in values.items():
            cfg[section].setdefault(key, value)
    return cfg
