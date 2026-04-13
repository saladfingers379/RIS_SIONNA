from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from app.ris.rt_synthesis import (
    _build_viewer_seed_config,
    _write_default_radio_map_artifacts,
    _write_promoted_sionna_configs,
)
from app.ris.rt_synthesis_artifacts import write_objective_trace, write_phase_artifacts


def test_write_phase_artifacts_writes_continuous_manual_arrays(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    (output_dir / "data").mkdir(parents=True)
    (output_dir / "plots").mkdir(parents=True)

    phase = np.zeros((1, 2, 3), dtype=float)
    phase_unwrapped = np.ones((1, 2, 3), dtype=float)
    amp = np.ones((1, 2, 3), dtype=float)

    write_phase_artifacts(
        output_dir,
        phase,
        amp_continuous=amp,
        phase_continuous_unwrapped=phase_unwrapped,
    )

    saved_phase = np.load(output_dir / "data" / "manual_profile_phase_continuous.npy")
    saved_amp = np.load(output_dir / "data" / "manual_profile_amp_continuous.npy")
    saved_phase_unwrapped = np.load(output_dir / "data" / "phase_continuous_unwrapped.npy")

    assert saved_phase.shape == (1, 2, 3)
    assert saved_amp.shape == (1, 2, 3)
    assert saved_phase_unwrapped.shape == (1, 2, 3)
    assert np.allclose(saved_phase, phase)
    assert np.allclose(saved_amp, amp)
    assert np.allclose(saved_phase_unwrapped, phase_unwrapped)
    assert (output_dir / "plots" / "phase_continuous.png").exists()


def test_write_promoted_sionna_configs_writes_manual_continuous_seed(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir(parents=True)
    phase_path = output_dir / "data" / "manual_profile_phase_continuous.npy"
    amp_path = output_dir / "data" / "manual_profile_amp_continuous.npy"
    phase_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(phase_path, np.zeros((1, 2, 2), dtype=float))
    np.save(amp_path, np.ones((1, 2, 2), dtype=float))

    seed_cfg = {
        "scene": {"type": "file", "file": "scenes/south_belfast/scene.xml"},
        "ris": {
            "objects": [
                {
                    "name": "ris",
                    "position": [0.0, 0.0, 0.0],
                    "profile": {"kind": "phase_gradient_reflector"},
                }
            ]
        },
        "output": {"base_dir": "outputs", "run_id": "seed-run"},
        "job": {"kind": "run"},
    }

    artifacts = _write_promoted_sionna_configs(
        output_dir,
        seed_cfg,
        "ris",
        continuous_phase_path=phase_path,
        continuous_amp_path=amp_path,
    )

    assert artifacts["continuous_profile_snippet_path"] == "ris_profile_continuous.yaml"
    assert artifacts["continuous_seed_config_path"] == "seed_config_continuous.yaml"

    promoted_cfg = yaml.safe_load((output_dir / "seed_config_continuous.yaml").read_text(encoding="utf-8"))
    promoted_ris = promoted_cfg["ris"]["objects"][0]["profile"]

    assert promoted_ris["kind"] == "manual"
    assert promoted_ris["manual_phase_values"] == str(phase_path)
    assert promoted_ris["manual_amp_values"] == str(amp_path)
    assert "job" not in promoted_cfg
    assert "run_id" not in promoted_cfg["output"]


def test_write_objective_trace_accepts_extra_fields(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    (output_dir / "data").mkdir(parents=True)
    (output_dir / "plots").mkdir(parents=True)

    rows = [
        {"iteration": 0, "objective": -1.0, "stage": "seed"},
        {
            "iteration": 1,
            "objective": -0.5,
            "stage": "coarse",
            "azimuth_deg": 12.0,
            "elevation_deg": 3.0,
            "target_point_xyz": [1.0, 2.0, 3.0],
        },
    ]

    write_objective_trace(output_dir, rows)

    text = (output_dir / "data" / "objective_trace.csv").read_text(encoding="utf-8")
    assert "stage" in text
    assert "azimuth_deg" in text
    assert (output_dir / "plots" / "objective_trace.png").exists()


def test_write_phase_artifacts_writes_quantized_levels_array(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    (output_dir / "data").mkdir(parents=True)
    (output_dir / "plots").mkdir(parents=True)

    continuous = np.zeros((1, 2, 2), dtype=float)
    quantized = np.array([[[0.0, np.pi], [1.5 * np.pi, 0.5 * np.pi]]], dtype=float)

    write_phase_artifacts(
        output_dir,
        continuous,
        phase_quantized=quantized,
        quantized_bits=2,
    )

    saved_levels = np.load(output_dir / "data" / "levels_quantized.npy")

    assert saved_levels.shape == (1, 2, 2)
    assert saved_levels.tolist() == [[[0, 2], [3, 1]]]
    assert (output_dir / "plots" / "phase_quantized.png").exists()


def test_write_default_radio_map_artifacts_writes_viewer_heatmap_arrays(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    evaluation = {
        "path_gain_linear": np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float),
        "path_gain_db": np.array([[0.0, 1.0], [2.0, 3.0]], dtype=float),
        "rx_power_dbm": np.array([[-10.0, -9.0], [-8.0, -7.0]], dtype=float),
        "path_loss_db": np.array([[10.0, 9.0], [8.0, 7.0]], dtype=float),
        "cell_centers": np.array(
            [
                [[0.0, 0.0, 1.5], [1.0, 0.0, 1.5]],
                [[0.0, 1.0, 1.5], [1.0, 1.0, 1.5]],
            ],
            dtype=float,
        ),
    }
    diff_vs_off = np.array([[0.5, 0.25], [0.0, -0.25]], dtype=float)

    _write_default_radio_map_artifacts(output_dir, evaluation, diff_vs_off=diff_vs_off)

    with np.load(output_dir / "data" / "radio_map.npz") as payload:
        assert np.allclose(payload["path_gain_linear"], evaluation["path_gain_linear"])
        assert np.allclose(payload["path_gain_db"], evaluation["path_gain_db"])
        assert np.allclose(payload["rx_power_dbm"], evaluation["rx_power_dbm"])
        assert np.allclose(payload["path_loss_db"], evaluation["path_loss_db"])
        assert np.allclose(payload["cell_centers"], evaluation["cell_centers"])
    with np.load(output_dir / "data" / "radio_map_diff.npz") as payload:
        assert np.allclose(payload["path_gain_db"], diff_vs_off)
        assert np.allclose(payload["cell_centers"], evaluation["cell_centers"])
    csv_text = (output_dir / "data" / "radio_map.csv").read_text(encoding="utf-8")
    assert "x,y,z,path_gain_db" in csv_text


def test_build_viewer_seed_config_uses_frozen_plane() -> None:
    seed_cfg = {
        "scene": {"type": "builtin", "builtin": "box"},
        "radio_map": {
            "enabled": True,
            "center": [1.0, 2.0, 3.0],
            "size": [4.0, 5.0],
            "cell_size": [0.5, 0.5],
            "orientation": [0.0, 0.0, 0.0],
        },
    }
    fixed_plane = {
        "center": [10.0, 20.0, 1.5],
        "size": [30.0, 40.0],
        "cell_size": [1.0, 2.0],
        "orientation": [0.0, 0.0, 1.5708],
    }

    viewer_cfg = _build_viewer_seed_config(seed_cfg, fixed_plane)

    assert viewer_cfg["radio_map"]["center"] == fixed_plane["center"]
    assert viewer_cfg["radio_map"]["size"] == fixed_plane["size"]
    assert viewer_cfg["radio_map"]["cell_size"] == fixed_plane["cell_size"]
    assert viewer_cfg["radio_map"]["orientation"] == fixed_plane["orientation"]
    assert viewer_cfg["viewer"]["enabled"] is True
    assert seed_cfg["radio_map"]["center"] == [1.0, 2.0, 3.0]
