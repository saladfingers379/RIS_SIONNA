from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app.metrics import build_paths_table, compute_path_metrics


class _FakePaths:
    RIS = 4

    def __init__(self) -> None:
        self.a = np.array([[[[[[[1.0], [2.0], [3.0]]]]]]], dtype=np.complex64)
        self.types = np.array([[0, 1, 1]], dtype=np.int32)
        self.objects = np.array([[[[-1, 7, -1]]]], dtype=np.int32)
        self.mask = np.array([[[[True, True, True]]]], dtype=bool)
        self.tau = np.array([0.0, 1.0e-9, 2.0e-9], dtype=float)


class _EmptyPaths:
    RIS = 4

    def __init__(self) -> None:
        self.a = np.zeros((1, 1, 1, 1, 1, 1, 0), dtype=np.complex64)
        self.types = np.zeros((1, 0), dtype=np.int32)
        self.mask = np.zeros((1, 1, 1, 0), dtype=bool)
        self.tau = np.zeros((0,), dtype=float)
        self.vertices = np.zeros((0, 1, 1, 0, 3), dtype=float)
        self.objects = np.zeros((0, 1, 1, 0), dtype=np.int32)
        self.interactions = np.zeros((0, 1, 1, 0), dtype=np.int32)


def test_compute_path_metrics_uses_ris_object_ids_when_types_do_not_mark_ris() -> None:
    scene = SimpleNamespace(ris={"ris1": SimpleNamespace(object_id=7)})
    metrics = compute_path_metrics(_FakePaths(), tx_power_dbm=0.0, scene=scene)

    assert metrics["num_ris_paths"] == 1
    assert metrics["ris_path_gain_linear"] == 4.0
    assert metrics["non_ris_path_gain_linear"] == 10.0


def test_compute_path_metrics_handles_zero_path_results() -> None:
    metrics = compute_path_metrics(_EmptyPaths(), tx_power_dbm=0.0)

    assert metrics["total_path_gain_linear"] == 0.0
    assert metrics["num_valid_paths"] == 0
    assert metrics["num_ris_paths"] == 0
    assert "ris_path_gain_linear" not in metrics


def test_build_paths_table_handles_zero_path_results() -> None:
    table = build_paths_table(_EmptyPaths(), tx_power_dbm=0.0)

    assert table["rows"] == []
