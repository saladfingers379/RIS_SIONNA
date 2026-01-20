"""Core RIS math primitives for geometry and phase control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np


@dataclass(frozen=True)
class RisFrame:
    """Right-handed local frame for the RIS surface."""

    u: np.ndarray
    v: np.ndarray
    w: np.ndarray


@dataclass(frozen=True)
class RisGeometry:
    """RIS element centers and local frame."""

    centers: np.ndarray
    frame: RisFrame


_DEFAULT_NORMAL = np.array([0.0, 0.0, 1.0], dtype=float)
_DEFAULT_X_AXIS = np.array([1.0, 0.0, 0.0], dtype=float)
_ALT_X_AXIS = np.array([0.0, 1.0, 0.0], dtype=float)


def _normalize(vec: np.ndarray, name: str) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm <= 0.0:
        raise ValueError(f"{name} must be a non-zero vector")
    return vec / norm


def compute_local_frame(
    normal: Optional[Iterable[float]] = None,
    x_axis_hint: Optional[Iterable[float]] = None,
) -> RisFrame:
    """Return a stable, right-handed local frame for a surface."""

    w = _normalize(
        np.array(_DEFAULT_NORMAL if normal is None else normal, dtype=float), "normal"
    )
    hint = np.array(_DEFAULT_X_AXIS if x_axis_hint is None else x_axis_hint, dtype=float)
    hint = _normalize(hint, "x_axis_hint")
    if abs(np.dot(hint, w)) > 0.99:
        hint = _ALT_X_AXIS
        if abs(np.dot(hint, w)) > 0.99:
            hint = _DEFAULT_X_AXIS
    u = _normalize(hint - np.dot(hint, w) * w, "x_axis_hint")
    v = np.cross(w, u)
    return RisFrame(u=u, v=v, w=w)


def compute_element_centers(
    nx: int,
    ny: int,
    dx: float,
    dy: float,
    origin: Optional[Iterable[float]] = None,
    normal: Optional[Iterable[float]] = None,
    x_axis_hint: Optional[Iterable[float]] = None,
) -> RisGeometry:
    """Compute RIS element centers with stable ordering (row-major)."""

    if nx <= 0 or ny <= 0:
        raise ValueError("nx and ny must be positive")
    if dx <= 0.0 or dy <= 0.0:
        raise ValueError("dx and dy must be positive")

    frame = compute_local_frame(normal=normal, x_axis_hint=x_axis_hint)
    origin_vec = np.array(origin if origin is not None else [0.0, 0.0, 0.0], dtype=float)

    x_offsets = (np.arange(nx, dtype=float) - (nx - 1) / 2.0) * dx
    y_offsets = (np.arange(ny, dtype=float) - (ny - 1) / 2.0) * dy

    centers = (
        origin_vec
        + x_offsets[None, :, None] * frame.u[None, None, :]
        + y_offsets[:, None, None] * frame.v[None, None, :]
    )
    return RisGeometry(centers=centers, frame=frame)


def synthesize_uniform_phase(shape: tuple[int, int], phase_rad: float = 0.0) -> np.ndarray:
    """Return a uniform phase map."""

    return np.full(shape, float(phase_rad), dtype=float)


def synthesize_custom_phase(phase_rad: np.ndarray, shape: Optional[tuple[int, int]] = None) -> np.ndarray:
    """Validate and return a custom phase map."""

    phase = np.array(phase_rad, dtype=float)
    if shape is not None and phase.shape != shape:
        raise ValueError(f"custom phase shape {phase.shape} does not match {shape}")
    return phase


def synthesize_steering_phase(
    centers: np.ndarray,
    wavelength: float,
    direction: Iterable[float],
    incident_direction: Optional[Iterable[float]] = None,
) -> np.ndarray:
    """Far-field steering phase for a desired direction, optionally compensating for incidence."""

    k = 2.0 * np.pi / float(wavelength)
    direction_vec = _normalize(np.array(direction, dtype=float), "direction")
    
    # Phase gradient to align emission towards 'direction'
    # Phase required: -k * (r . r_out)
    phase_out = -k * np.tensordot(centers, direction_vec, axes=([2], [0]))

    if incident_direction is not None:
        # Compensate for incident phase: -k * (r . r_inc)
        # We want: Phase_RIS = Phase_out - Phase_inc
        # But wait, the physical phase at the element is Phase_inc.
        # So Total_Phase = Phase_inc + Phase_RIS.
        # We want Total_Phase to equal Phase_out (the planar gradient).
        # So Phase_RIS = Phase_out - Phase_inc.
        inc_vec = _normalize(np.array(incident_direction, dtype=float), "incident_direction")
        phase_inc = -k * np.tensordot(centers, inc_vec, axes=([2], [0]))
        return phase_out - phase_inc

    return phase_out


def synthesize_focusing_phase(
    centers: np.ndarray,
    wavelength: float,
    focal_point: Iterable[float],
    incident_direction: Optional[Iterable[float]] = None,
) -> np.ndarray:
    """Near-field focusing phase towards a focal point, optionally compensating for incidence."""

    k = 2.0 * np.pi / float(wavelength)
    focal = np.array(focal_point, dtype=float)
    # Distance from each element to focal point
    distances = np.linalg.norm(centers - focal[None, None, :], axis=2)
    # Phase to focus: proportional to distance (conjugate phase)
    phase_out = k * distances # Focusing usually adds positive phase to delay center relative to edges

    # Actually, standard focusing phase is -k * distance (to advance phase) or +k * distance?
    # To focus at F, we want waves from all elements to arrive at F in phase.
    # Path length L_i = distance(element_i, F).
    # Phase accumulation = -k * L_i.
    # To align them, we need Element_Phase_i such that -k * L_i + Element_Phase_i = Constant.
    # So Element_Phase_i = k * L_i + C. 
    # Let's stick to k * distances.
    
    phase_out = k * distances

    if incident_direction is not None:
        inc_vec = _normalize(np.array(incident_direction, dtype=float), "incident_direction")
        phase_inc = -k * np.tensordot(centers, inc_vec, axes=([2], [0]))
        return phase_out - phase_inc

    return phase_out


def quantize_phase(phase_rad: np.ndarray, bits: Optional[int]) -> np.ndarray:
    """Quantize phase in radians using 1-bit or 2-bit levels."""

    if bits in (None, 0):
        return np.array(phase_rad, dtype=float, copy=True)
    if bits not in (1, 2):
        raise ValueError("quantization_bits must be one of {0, 1, 2}")

    phase = np.array(phase_rad, dtype=float)
    step = 2.0 * np.pi / (2**bits)
    levels = np.arange(2**bits, dtype=float) * step
    phase_wrapped = np.mod(phase, 2.0 * np.pi)
    diffs = np.abs(phase_wrapped[..., None] - levels)
    indices = np.argmin(diffs, axis=-1)
    return levels[indices]


def radians_to_degrees(angle_rad: np.ndarray) -> np.ndarray:
    """Convert radians to degrees."""

    return np.rad2deg(angle_rad)


def degrees_to_radians(angle_deg: np.ndarray) -> np.ndarray:
    """Convert degrees to radians."""

    return np.deg2rad(angle_deg)
