from __future__ import annotations

import numpy as np
import pytest
import tensorflow as tf
import yaml
from pathlib import Path

from app.ris import rt_synthesis


def test_coordinate_search_fallback_improves_objective(monkeypatch) -> None:
    target = np.array([[0.4, -0.2, 0.1, 0.0, 0.0, 0.0]], dtype=float)
    parameterization = {
        "variable": tf.Variable(np.zeros_like(target), dtype=tf.float32),
    }

    def fake_evaluate(scene, ris_obj, kwargs, mask_tf, objective_cfg, parameterization_local):
        coeffs = parameterization_local["variable"].numpy()
        score = -float(np.sum((coeffs - target) ** 2))
        phase = np.zeros((1, 1, 1), dtype=float)
        return score, phase, phase

    monkeypatch.setattr(rt_synthesis, "_evaluate_parameterized_objective", fake_evaluate)

    start_objective, _, _ = fake_evaluate(None, None, {}, None, {}, parameterization)
    result = rt_synthesis._optimize_continuous_phase_coordinate_search(
        None,
        None,
        {},
        {},
        parameterization,
        None,
        iterations=18,
        log_every=50,
        learning_rate=0.2,
        progress_cb=lambda *_args, **_kwargs: None,
        trace_prefix=[],
        start_iteration=0,
        current_objective=start_objective,
        fallback_reason="test",
    )

    assert result["optimizer"]["mode"] == "coordinate_search"
    assert result["optimizer"]["gradient_fallback_used"] is True
    assert result["trace"][-1]["objective"] > start_objective


def test_steering_search_prefers_best_angle(monkeypatch) -> None:
    desired_azimuth_deg = 20.0
    desired_elevation_deg = 4.0

    class FakeProfile:
        def __init__(self) -> None:
            self.values = np.zeros((1, 1, 1), dtype=float)

    class FakeRis:
        def __init__(self) -> None:
            self.position = np.array([0.0, 0.0, 0.0], dtype=float)
            self.world_normal = np.array([1.0, 0.0, 0.0], dtype=float)
            self.phase_profile = FakeProfile()
            self.last_target = None

        def phase_gradient_reflector(self, sources, targets) -> None:
            self.last_target = np.asarray(targets[0], dtype=float)
            self.phase_profile.values = np.full((1, 1, 1), 0.5, dtype=float)

    class FakeTx:
        def __init__(self) -> None:
            self.position = np.array([-1.0, 0.0, 0.0], dtype=float)

    class FakeScene:
        def __init__(self) -> None:
            self.transmitters = {"tx": FakeTx()}

    fake_ris = FakeRis()
    fake_scene = FakeScene()
    desired_direction = rt_synthesis._direction_from_az_el_deg(
        desired_azimuth_deg,
        desired_elevation_deg,
    )

    def fake_evaluate_variant(scene, kwargs, tx_power_dbm, *, title):
        if fake_ris.last_target is None:
            score = -10.0
        else:
            direction = fake_ris.last_target / np.linalg.norm(fake_ris.last_target)
            score = 2.0 - float(np.sum((direction - desired_direction) ** 2))
        return {
            "path_gain_linear": np.array([[np.exp(score)]], dtype=float),
            "cell_centers": np.array([[[10.0, 0.0, 0.0]]], dtype=float),
            "title": title,
        }

    monkeypatch.setattr(rt_synthesis, "_evaluate_variant", fake_evaluate_variant)

    config = {
        "parameterization": {"kind": "steering_search"},
        "objective": {"eps": 1.0e-12},
        "target_region": {
            "boxes": [
                {
                    "name": "roi_1",
                    "u_min_m": 9.5,
                    "u_max_m": 10.5,
                    "v_min_m": -0.5,
                    "v_max_m": 0.5,
                }
            ]
        },
        "search": {
            "azimuth_span_deg": 40.0,
            "elevation_span_deg": 12.0,
            "coarse_num_azimuth": 5,
            "coarse_num_elevation": 3,
            "coarse_cell_scale": 4.0,
            "coarse_sample_scale": 0.2,
            "refine_top_k": 2,
            "refine_num_azimuth": 5,
            "refine_num_elevation": 3,
            "refine_cell_scale": 2.0,
            "refine_sample_scale": 0.5,
        },
    }

    result = rt_synthesis._search_steering_phase(
        fake_scene,
        fake_ris,
        {"cm_cell_size": [1.0, 1.0], "num_samples": 100},
        np.array([[True]], dtype=bool),
        np.array([[[10.0, 0.0, 0.0]]], dtype=float),
        config,
        lambda *_args, **_kwargs: None,
    )

    best = result["parameterization"]["best_candidate"]
    assert result["optimizer"]["mode"] == "steering_search"
    assert best["stage"] == "final"
    assert best["azimuth_deg"] == pytest.approx(desired_azimuth_deg, abs=5.0)
    assert best["elevation_deg"] == pytest.approx(desired_elevation_deg, abs=3.0)


def test_load_realized_fixed_plane_prefers_seed_run_radio_map(tmp_path: Path) -> None:
    run_dir = tmp_path / "outputs" / "run123"
    (run_dir / "data").mkdir(parents=True)
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "radio_map": {
                    "enabled": True,
                    "auto_size": True,
                    "center": [30.0, 30.0, 1.5],
                    "size": [80.0, 80.0],
                    "cell_size": [2.0, 2.0],
                    "orientation": [0.0, 0.0, 0.0],
                }
            }
        ),
        encoding="utf-8",
    )
    cell_centers = np.array(
        [
            [[-4.0, 10.0, 1.5], [-2.0, 10.0, 1.5], [0.0, 10.0, 1.5]],
            [[-4.0, 12.0, 1.5], [-2.0, 12.0, 1.5], [0.0, 12.0, 1.5]],
        ],
        dtype=float,
    )
    np.savez_compressed(run_dir / "data" / "radio_map.npz", cell_centers=cell_centers)

    seed_cfg = {
        "radio_map": {
            "enabled": True,
            "auto_size": True,
            "center": [30.0, 30.0, 1.5],
            "size": [80.0, 80.0],
            "cell_size": [2.0, 2.0],
            "orientation": [0.0, 0.0, 0.0],
        }
    }
    synth_cfg = {
        "seed": {
            "config_path": str(run_dir / "config.yaml"),
            "source_run_id": "run123",
        }
    }

    plane = rt_synthesis._load_realized_fixed_plane(seed_cfg, synth_cfg)

    assert plane is not None
    assert plane["derived_from"] == "seed_run_radio_map"
    assert plane["center"] == pytest.approx([-2.0, 11.0, 1.5])
    assert plane["size"] == pytest.approx([6.0, 4.0])
    assert plane["cell_size"] == pytest.approx([2.0, 2.0])


def test_apply_radio_map_autosize_matches_scene_bbox() -> None:
    plane = {
        "center": [30.0, 30.0, 1.5],
        "size": [80.0, 80.0],
        "cell_size": [2.0, 2.0],
        "orientation": [0.0, 0.0, 0.0],
    }
    seed_cfg = {
        "radio_map": {
            "enabled": True,
            "auto_size": True,
            "auto_padding": 10.0,
        }
    }

    class _BBox:
        min = type("Min", (), {"x": -95.0, "y": -60.0})()
        max = type("Max", (), {"x": 93.0, "y": 58.0})()

    class _MiScene:
        @staticmethod
        def bbox():
            return _BBox()

    class _Scene:
        mi_scene = _MiScene()

    resized = rt_synthesis._apply_radio_map_autosize(seed_cfg, plane, _Scene())

    assert resized["derived_from"] == "seed_config_auto_size"
    assert resized["center"] == pytest.approx([-1.0, -1.0, 1.5])
    assert resized["size"] == pytest.approx([208.0, 138.0])
