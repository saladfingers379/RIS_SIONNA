from __future__ import annotations

import numpy as np

from app.ris.rt_synthesis_roi import build_target_mask_from_boxes


def test_build_target_mask_from_boxes_marks_expected_cells() -> None:
    mask = build_target_mask_from_boxes(
        center=[0.0, 0.0, 1.5],
        size=[4.0, 4.0],
        cell_size=[1.0, 1.0],
        boxes=[{"u_min_m": -0.5, "u_max_m": 0.5, "v_min_m": -0.5, "v_max_m": 0.5}],
    )

    assert mask.shape == (4, 4)
    assert int(np.count_nonzero(mask)) == 4


def test_build_target_mask_from_boxes_unions_multiple_boxes() -> None:
    mask = build_target_mask_from_boxes(
        center=[0.0, 0.0, 0.0],
        size=[4.0, 4.0],
        cell_size=[1.0, 1.0],
        boxes=[
            {"u_min_m": -1.5, "u_max_m": -0.5, "v_min_m": -1.5, "v_max_m": -0.5},
            {"u_min_m": 0.5, "u_max_m": 1.5, "v_min_m": 0.5, "v_max_m": 1.5},
        ],
    )

    assert int(np.count_nonzero(mask)) == 8


def test_build_target_mask_from_boxes_clips_out_of_bounds() -> None:
    mask = build_target_mask_from_boxes(
        center=[0.0, 0.0, 0.0],
        size=[4.0, 4.0],
        cell_size=[1.0, 1.0],
        boxes=[{"u_min_m": -10.0, "u_max_m": 10.0, "v_min_m": -10.0, "v_max_m": 10.0}],
    )

    assert mask.shape == (4, 4)
    assert mask.all()
