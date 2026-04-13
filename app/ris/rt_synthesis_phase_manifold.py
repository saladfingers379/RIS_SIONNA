"""Continuous phase manifold helpers for RT-side RIS synthesis."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

PANEL_BASIS_NAMES = ("bias", "x", "y", "x2", "xy", "y2")


def ensure_finite_array(values: Any, *, name: str) -> np.ndarray:
    """Return a float array or raise if any element is NaN/Inf."""

    arr = np.asarray(values, dtype=float)
    invalid = ~np.isfinite(arr)
    if np.any(invalid):
        raise ValueError(
            f"{name} contains {int(np.count_nonzero(invalid))} non-finite values out of {int(arr.size)}"
        )
    return arr


def unwrap_panel_phase(phase_map: Any) -> np.ndarray:
    """Unwrap a 2D wrapped phase map into a smooth continuous surface."""

    phase = ensure_finite_array(phase_map, name="phase_map")
    if phase.ndim != 2:
        raise ValueError("phase_map must be a 2D array")
    return np.unwrap(np.unwrap(phase, axis=0), axis=1)


def panel_coordinates_from_cell_positions(
    cell_positions: Any,
    *,
    num_rows: int,
    num_cols: int,
) -> Dict[str, np.ndarray | float]:
    """Map Sionna RIS cell positions into [rows, cols] normalized coordinates."""

    coords = ensure_finite_array(cell_positions, name="RIS cell positions")
    if coords.ndim == 2:
        expected_shape = (int(num_rows) * int(num_cols), 2)
        if coords.shape != expected_shape:
            raise ValueError(
                f"RIS cell positions must be shape {expected_shape} or ({num_rows}, {num_cols}, 2)"
            )
        coords = coords.reshape(int(num_cols), int(num_rows), 2).transpose(1, 0, 2)
    elif coords.ndim == 3:
        expected_shape = (int(num_rows), int(num_cols), 2)
        if coords.shape != expected_shape:
            raise ValueError(
                f"RIS cell positions must be shape ({num_rows}, {num_cols}, 2)"
            )
    else:
        raise ValueError("RIS cell positions must be a 2D or 3D array")

    x = np.asarray(coords[..., 0], dtype=float)
    y = np.asarray(coords[..., 1], dtype=float)
    x_centered = x - float(np.mean(x))
    y_centered = y - float(np.mean(y))
    x_scale = max(float(np.max(np.abs(x_centered))), 1.0e-9)
    y_scale = max(float(np.max(np.abs(y_centered))), 1.0e-9)
    return {
        "x": x_centered / x_scale,
        "y": y_centered / y_scale,
        "x_scale": x_scale,
        "y_scale": y_scale,
    }


def quadratic_panel_basis(x_coords: Any, y_coords: Any) -> np.ndarray:
    """Return a low-order smooth basis over the RIS panel."""

    x = ensure_finite_array(x_coords, name="x_coords")
    y = ensure_finite_array(y_coords, name="y_coords")
    if x.shape != y.shape:
        raise ValueError("x_coords and y_coords must have matching shapes")
    return np.stack(
        [
            np.ones_like(x, dtype=float),
            x,
            y,
            x * x,
            x * y,
            y * y,
        ],
        axis=0,
    )


def build_seeded_quadratic_phase(
    seed_phase_unwrapped: Any,
    basis_stack: Any,
    coefficients: Any,
) -> np.ndarray:
    """Build a smooth unwrapped phase field from a seed plus low-order residual."""

    seed = ensure_finite_array(seed_phase_unwrapped, name="seed_phase_unwrapped")
    basis = ensure_finite_array(basis_stack, name="basis_stack")
    coeffs = ensure_finite_array(coefficients, name="coefficients")
    if seed.ndim != 3:
        raise ValueError("seed_phase_unwrapped must be shaped [num_modes, num_rows, num_cols]")
    if basis.ndim != 3:
        raise ValueError("basis_stack must be shaped [num_basis, num_rows, num_cols]")
    if coeffs.ndim != 2:
        raise ValueError("coefficients must be shaped [num_modes, num_basis]")
    if seed.shape[1:] != basis.shape[1:]:
        raise ValueError("seed_phase_unwrapped and basis_stack spatial shapes must match")
    if coeffs.shape != (seed.shape[0], basis.shape[0]):
        raise ValueError("coefficients shape must match [num_modes, num_basis]")
    residual = np.einsum("mb,bij->mij", coeffs, basis)
    return seed + residual


def phase_field_diagnostics(
    phase_wrapped: Any,
    *,
    phase_unwrapped: Any | None = None,
) -> Dict[str, Any]:
    """Summarize phase validity and smoothness for reporting."""

    wrapped = np.asarray(phase_wrapped, dtype=float)
    invalid = ~np.isfinite(wrapped)
    diagnostics: Dict[str, Any] = {
        "shape": list(wrapped.shape),
        "num_non_finite": int(np.count_nonzero(invalid)),
        "finite_fraction": float(np.mean(~invalid)) if wrapped.size else 1.0,
    }
    finite = wrapped[~invalid]
    if finite.size:
        diagnostics["wrapped_min_rad"] = float(np.min(finite))
        diagnostics["wrapped_max_rad"] = float(np.max(finite))

    if phase_unwrapped is None:
        return diagnostics

    unwrapped = ensure_finite_array(phase_unwrapped, name="phase_unwrapped")
    if unwrapped.ndim == 3:
        base = unwrapped[0]
    elif unwrapped.ndim == 2:
        base = unwrapped
    else:
        raise ValueError("phase_unwrapped must be a 2D or 3D array")
    dx = np.diff(base, axis=1)
    dy = np.diff(base, axis=0)
    diagnostics["smoothness"] = {
        "dx_mean_abs_rad": float(np.mean(np.abs(dx))) if dx.size else 0.0,
        "dx_p95_abs_rad": float(np.percentile(np.abs(dx), 95.0)) if dx.size else 0.0,
        "dy_mean_abs_rad": float(np.mean(np.abs(dy))) if dy.size else 0.0,
        "dy_p95_abs_rad": float(np.percentile(np.abs(dy), 95.0)) if dy.size else 0.0,
    }
    return diagnostics
