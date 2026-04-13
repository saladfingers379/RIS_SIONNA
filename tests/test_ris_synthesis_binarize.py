from __future__ import annotations

import numpy as np

from app.ris.rt_synthesis_binarize import (
    greedy_flip_refine,
    project_1bit_offset_sweep,
    project_nbit_offset_sweep,
)


def test_project_1bit_offset_sweep_picks_best_candidate() -> None:
    phase = np.array([[0.10 * np.pi, 0.90 * np.pi]], dtype=float)

    def scorer(candidate: np.ndarray) -> float:
        bits = (np.mod(candidate, 2.0 * np.pi) >= np.pi / 2.0).astype(int)
        return 10.0 if np.array_equal(bits, np.array([[1, 0]])) else 1.0

    result = project_1bit_offset_sweep(phase, scorer, num_offset_samples=16)

    assert result["best_score"] == 10.0
    assert result["best_bits"].tolist() == [[1, 0]]


def test_project_1bit_offset_sweep_rejects_non_finite_input() -> None:
    with np.testing.assert_raises_regex(
        ValueError,
        "finite values",
    ):
        project_1bit_offset_sweep(
            np.array([[0.0, np.nan]], dtype=float),
            lambda candidate: 0.0,
            num_offset_samples=4,
        )


def test_greedy_flip_refine_improves_or_preserves_score() -> None:
    target = np.array([[1, 1, 0, 0]], dtype=np.int8)

    def scorer(bits: np.ndarray) -> float:
        return -float(np.sum(np.abs(bits - target)))

    start = np.array([[0, 1, 0, 0]], dtype=np.int8)
    result = greedy_flip_refine(start, scorer, candidate_budget=4, max_passes=3)

    assert result["best_score"] >= scorer(start)
    assert result["best_bits"].tolist() == target.tolist()


def test_project_nbit_offset_sweep_picks_best_candidate() -> None:
    phase = np.array([[0.10 * np.pi, 0.65 * np.pi, 1.20 * np.pi]], dtype=float)
    target_levels = np.array([[1, 4, 6]], dtype=np.int16)

    def scorer(candidate: np.ndarray) -> float:
        levels = (np.round(np.mod(candidate, 2.0 * np.pi) / (np.pi / 4.0)).astype(int) % 8).astype(np.int16)
        return 10.0 if np.array_equal(levels, target_levels) else -1.0

    result = project_nbit_offset_sweep(phase, scorer, num_offset_samples=32, bits=3)

    assert result["best_score"] == 10.0
    assert result["best_levels"].tolist() == target_levels.tolist()
    assert result["bits"] == 3
    assert result["levels"] == 8
