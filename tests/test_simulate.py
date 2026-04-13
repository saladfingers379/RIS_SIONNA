from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app.simulate import _compute_ris_link_probe, _extract_ray_path_segments


class _FakeTensor:
    def __init__(self, values):
        self._values = np.array(values, dtype=float)
        self.dtype = self._values.dtype

    def numpy(self):
        return self._values.copy()

    def assign(self, values):
        self._values = np.array(values, dtype=float)

    def __array__(self, dtype=None):
        return np.asarray(self._values, dtype=dtype)


class _FakeProfile:
    def __init__(self, values):
        self.values = _FakeTensor(values)
        self.mode_powers = [0.84]


class _FakeRis:
    def __init__(self):
        self.num_modes = 1
        self.phase_profile = _FakeProfile([[[0.5, 0.6]]])
        self.amplitude_profile = _FakeProfile([[[0.84, 0.84]]])


class _FakeRayPaths:
    def __init__(self, *, mask, vertices, interactions=None):
        self.vertices = np.asarray(vertices, dtype=float)
        self.mask = np.asarray(mask, dtype=bool)
        self.sources = np.array([[0.0, 0.0, 0.0]], dtype=float)
        self.targets = np.array([[2.0, 0.0, 0.0]], dtype=float)
        if interactions is None:
            interactions = np.ones(self.vertices.shape[:-1], dtype=np.int32)
        self.interactions = np.asarray(interactions, dtype=np.int32)
        self.objects = np.zeros((0, 1, 1, self.vertices.shape[3]), dtype=np.int32)


def test_compute_ris_link_probe_uses_flat_metal_baseline_and_restores_profiles(monkeypatch) -> None:
    scene = SimpleNamespace(ris={"ris1": _FakeRis()})
    tx_device = SimpleNamespace(power_dbm=30.0)
    metrics_on = {"total_path_gain_db": -50.0, "rx_power_dbm_estimate": -20.0}
    call_flags = []
    observed_phase = []
    observed_amplitude = []
    observed_tx_power_dbm = []

    def fake_compute_paths_with_current_flags(scene_arg, sim_cfg_arg, *, use_ris):
        call_flags.append(use_ris)
        ris = scene_arg.ris["ris1"]
        observed_phase.append(np.array(ris.phase_profile.values.numpy(), dtype=float))
        observed_amplitude.append(np.array(ris.amplitude_profile.values.numpy(), dtype=float))
        return object()

    def fake_compute_path_metrics(paths, tx_power_dbm, scene):
        observed_tx_power_dbm.append(tx_power_dbm)
        return {"total_path_gain_db": -60.0, "rx_power_dbm_estimate": -30.0}

    monkeypatch.setattr("app.simulate._compute_paths_with_current_flags", fake_compute_paths_with_current_flags)
    monkeypatch.setattr("app.simulate.compute_path_metrics", fake_compute_path_metrics)

    probe = _compute_ris_link_probe(
        scene,
        {"ris_off_amplitude": 1.0},
        tx_device,
        metrics_on,
        has_ris=True,
        use_ris_paths=True,
    )

    assert call_flags == [True]
    assert observed_tx_power_dbm == [30.0]
    assert probe["off_mode"] == "metal_plate"
    assert probe["off_total_path_gain_db"] == -60.0
    assert probe["delta_total_path_gain_db"] == 10.0
    assert np.allclose(observed_phase[0], 0.0)
    assert np.allclose(observed_amplitude[0], 1.0)
    assert np.allclose(scene.ris["ris1"].phase_profile.values.numpy(), [[[0.5, 0.6]]])
    assert np.allclose(scene.ris["ris1"].amplitude_profile.values.numpy(), [[[0.84, 0.84]]])
    assert scene.ris["ris1"].amplitude_profile.mode_powers == [0.84]


def test_extract_ray_path_segments_filters_rear_launches_for_front_only_horn() -> None:
    vertices = np.zeros((1, 1, 1, 3, 3), dtype=float)
    vertices[0, 0, 0, 0, :] = [1.0, 0.0, 0.0]
    vertices[0, 0, 0, 1, :] = [-1.0, 0.0, 0.0]
    vertices[0, 0, 0, 2, :] = [0.0, 1.0, 0.0]
    paths = _FakeRayPaths(mask=[[[True, True, True]]], vertices=vertices)

    export = _extract_ray_path_segments(
        paths,
        {
            "scene": {
                "tx": {"position": [0.0, 0.0, 0.0], "look_at": [1.0, 0.0, 0.0]},
                "arrays": {"tx": {"pattern": "horn_15dbi_front"}},
            }
        },
        {"max_paths": 10},
    )

    segments = export["segments"]
    assert export["exported_paths"] == 1
    assert export["filtered_rear_paths"] == 2
    assert segments.shape == (2, 7)
    assert np.unique(segments[:, 0]).tolist() == [0.0]


def test_extract_ray_path_segments_preserves_original_path_ids() -> None:
    vertices = np.zeros((1, 1, 1, 3, 3), dtype=float)
    vertices[0, 0, 0, 0, :] = [1.0, 0.0, 0.0]
    vertices[0, 0, 0, 1, :] = [1.0, 1.0, 0.0]
    vertices[0, 0, 0, 2, :] = [1.0, -1.0, 0.0]
    paths = _FakeRayPaths(mask=[[[False, True, True]]], vertices=vertices)

    export = _extract_ray_path_segments(
        paths,
        {
            "scene": {
                "tx": {"position": [0.0, 0.0, 0.0], "look_at": [1.0, 0.0, 0.0]},
                "arrays": {"tx": {"pattern": "horn_15dbi"}},
            }
        },
        {"max_paths": 10, "filter_tx_rear_paths": False},
    )

    assert export["exported_paths"] == 2
    assert export["filtered_rear_paths"] == 0
    assert np.unique(export["segments"][:, 0]).tolist() == [1.0, 2.0]
