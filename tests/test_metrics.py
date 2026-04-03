from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app.metrics import compute_path_metrics


class _FakePaths:
    RIS = 4

    def __init__(self) -> None:
        self.a = np.array([[[[[[[1.0], [2.0], [3.0]]]]]]], dtype=np.complex64)
        self.types = np.array([[0, 1, 1]], dtype=np.int32)
        self.objects = np.array([[[[-1, 7, -1]]]], dtype=np.int32)
        self.mask = np.array([[[[True, True, True]]]], dtype=bool)
        self.tau = np.array([0.0, 1.0e-9, 2.0e-9], dtype=float)


def test_compute_path_metrics_uses_ris_object_ids_when_types_do_not_mark_ris() -> None:
    scene = SimpleNamespace(ris={"ris1": SimpleNamespace(object_id=7)})
    metrics = compute_path_metrics(_FakePaths(), tx_power_dbm=0.0, scene=scene)

    assert metrics["num_ris_paths"] == 1
    assert metrics["ris_path_gain_linear"] == 4.0
    assert metrics["non_ris_path_gain_linear"] == 10.0
