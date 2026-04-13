from __future__ import annotations

import numpy as np
import pytest

from app.ris.rt_synthesis_phase_manifold import (
    build_seeded_quadratic_phase,
    panel_coordinates_from_cell_positions,
    phase_field_diagnostics,
    quadratic_panel_basis,
    unwrap_panel_phase,
)


def test_panel_coordinates_from_flat_sionna_order() -> None:
    cell_positions = np.array(
        [
            [-0.75, 0.5],
            [-0.75, 0.0],
            [-0.75, -0.5],
            [-0.25, 0.5],
            [-0.25, 0.0],
            [-0.25, -0.5],
            [0.25, 0.5],
            [0.25, 0.0],
            [0.25, -0.5],
            [0.75, 0.5],
            [0.75, 0.0],
            [0.75, -0.5],
        ],
        dtype=float,
    )

    coords = panel_coordinates_from_cell_positions(
        cell_positions,
        num_rows=3,
        num_cols=4,
    )

    assert coords["x"].shape == (3, 4)
    assert coords["y"].shape == (3, 4)
    assert np.allclose(coords["x"][0], np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0]))
    assert np.allclose(coords["y"][:, 0], np.array([1.0, 0.0, -1.0]))


def test_build_seeded_quadratic_phase_preserves_seed_for_zero_coefficients() -> None:
    seed = np.arange(12, dtype=float).reshape(1, 3, 4)
    yy, xx = np.mgrid[-1.0:1.0:3j, -1.0:1.0:4j]
    basis = quadratic_panel_basis(xx, yy)
    coeffs = np.zeros((1, basis.shape[0]), dtype=float)

    out = build_seeded_quadratic_phase(seed, basis, coeffs)

    assert np.allclose(out, seed)


def test_unwrap_panel_phase_returns_continuous_surface() -> None:
    wrapped = np.array([[0.1, 2.0 * np.pi - 0.1, 2.0 * np.pi - 0.2]], dtype=float)

    unwrapped = unwrap_panel_phase(wrapped)

    assert np.all(np.isfinite(unwrapped))
    assert np.all(np.abs(np.diff(unwrapped, axis=1)) < 0.5)


def test_phase_field_diagnostics_reports_non_finite() -> None:
    diagnostics = phase_field_diagnostics(np.array([[0.0, np.nan]], dtype=float))

    assert diagnostics["num_non_finite"] == 1
    assert diagnostics["finite_fraction"] == pytest.approx(0.5)
