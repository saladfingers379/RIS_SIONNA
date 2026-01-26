#!/usr/bin/env python3
"""Minimal RIS demo for Sionna RT v0.19.2."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from app.metrics import compute_path_metrics
from app.ris.ris_sionna import apply_workbench_to_ris, build_workbench_phase_map


def _build_scene(rt):
    scene = rt.load_scene()
    scene.frequency = 28.0e9
    scene.tx_array = rt.PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    scene.rx_array = rt.PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    return scene


def _add_devices(scene, rt):
    tx = rt.Transmitter(name="tx", position=np.array([-5.0, -4.0, 3.0]), power_dbm=30.0)
    rx = rt.Receiver(name="rx", position=np.array([8.0, 4.0, 1.5]))
    scene.add(tx)
    scene.add(rx)
    return tx, rx


def _add_ris(scene, rt, config_path: Path):
    ris_lab_cfg = config_path.read_text(encoding="utf-8")
    import yaml

    config = yaml.safe_load(ris_lab_cfg)
    workbench = build_workbench_phase_map(config)
    ris = rt.RIS(
        name="ris",
        position=np.array([0.0, 0.0, 2.0]),
        num_rows=workbench.num_rows,
        num_cols=workbench.num_cols,
        num_modes=1,
        orientation=np.array([0.0, 0.0, 0.0]),
    )
    apply_workbench_to_ris(ris, workbench)
    scene.add(ris)
    return ris, workbench


def _compute_paths(scene):
    return scene.compute_paths(
        max_depth=2,
        method="fibonacci",
        num_samples=20000,
        los=True,
        reflection=True,
        diffraction=False,
        scattering=False,
        ris=True,
    )

def _assign_profile_values(profile, values):
    try:
        assign = getattr(profile.values, "assign", None)
        if callable(assign):
            assign(values)
            return
    except Exception:
        pass
    profile.values = values


def main() -> None:
    parser = argparse.ArgumentParser(description="RIS demo using Sionna RT v0.19.2")
    parser.add_argument(
        "--ris-config",
        default="configs/ris_lab_example.yaml",
        help="Path to RIS Lab config YAML",
    )
    args = parser.parse_args()

    import sionna.rt as rt
    import tensorflow as tf

    scene = _build_scene(rt)
    tx, _ = _add_devices(scene, rt)
    ris, workbench = _add_ris(scene, rt, Path(args.ris_config))

    # RIS ON
    paths_on = _compute_paths(scene)
    metrics_on = compute_path_metrics(paths_on, tx_power_dbm=tx.power_dbm)

    # RIS OFF (flat phase, same amplitude)
    phase_values = tf.zeros_like(ris.phase_profile.values)
    _assign_profile_values(ris.phase_profile, phase_values)
    amp_values = tf.ones_like(ris.amplitude_profile.values) * tf.cast(
        workbench.amplitude, ris.amplitude_profile.values.dtype
    )
    _assign_profile_values(ris.amplitude_profile, amp_values)
    paths_off = _compute_paths(scene)
    metrics_off = compute_path_metrics(paths_off, tx_power_dbm=tx.power_dbm)

    print("RIS ON total_path_gain_db:", metrics_on.get("total_path_gain_db"))
    print("RIS OFF total_path_gain_db:", metrics_off.get("total_path_gain_db"))


if __name__ == "__main__":
    main()
