"""Binarization helpers for RIS synthesis."""

from __future__ import annotations

from typing import Any, Callable, Dict

import numpy as np

from app.ris.ris_core import quantize_phase


def _phase_to_bits(phase: np.ndarray) -> np.ndarray:
    wrapped = np.mod(np.asarray(phase, dtype=float), 2.0 * np.pi)
    return (wrapped >= np.pi / 2.0).astype(np.int8)


def _bits_to_phase(bits: np.ndarray) -> np.ndarray:
    return np.asarray(bits, dtype=float) * np.pi


def _phase_to_levels(phase: np.ndarray, bits: int) -> np.ndarray:
    levels = 2 ** int(bits)
    wrapped = np.mod(np.asarray(phase, dtype=float), 2.0 * np.pi)
    step = 2.0 * np.pi / float(levels)
    return (np.round(wrapped / step).astype(int) % levels).astype(np.int16)


def project_nbit_offset_sweep(phase_continuous, scorer, num_offset_samples, bits) -> dict:
    phase = np.asarray(phase_continuous, dtype=float)
    if not np.all(np.isfinite(phase)):
        raise ValueError("phase_continuous must contain only finite values before n-bit projection")
    bits_int = int(bits)
    if bits_int < 1:
        raise ValueError("bits must be >= 1 for n-bit projection")

    sample_count = max(1, int(num_offset_samples))
    levels = 2 ** bits_int
    offset_period = 2.0 * np.pi / float(levels)
    offsets = np.linspace(0.0, offset_period, sample_count, endpoint=False, dtype=float)

    best_score = None
    best_phase = None
    best_offset = None
    sweep_rows = []
    for offset in offsets:
        candidate = quantize_phase(phase + float(offset), bits_int)
        score = float(scorer(candidate))
        sweep_rows.append({"offset_rad": float(offset), "score": score})
        if best_score is None or score > best_score:
            best_score = score
            best_phase = np.array(candidate, copy=True)
            best_offset = float(offset)

    if best_phase is None:
        raise ValueError("Offset sweep did not produce any candidate")

    return {
        "best_phase": best_phase,
        "best_levels": _phase_to_levels(best_phase, bits_int),
        "best_score": float(best_score),
        "best_offset_rad": float(best_offset),
        "offset_sweep": sweep_rows,
        "bits": bits_int,
        "levels": levels,
    }


def project_1bit_offset_sweep(phase_continuous, scorer, num_offset_samples) -> dict:
    result = project_nbit_offset_sweep(phase_continuous, scorer, num_offset_samples, 1)
    return {
        "best_phase": result["best_phase"],
        "best_bits": _phase_to_bits(result["best_phase"]),
        "best_score": result["best_score"],
        "best_offset_rad": result["best_offset_rad"],
        "offset_sweep": result["offset_sweep"],
    }


def greedy_flip_refine(bits, scorer, candidate_budget, max_passes) -> dict:
    best_bits = np.array(bits, dtype=np.int8, copy=True)
    best_score = float(scorer(best_bits))
    history = [{"pass_index": 0, "score": best_score, "accepted_index": None}]
    flat_size = int(best_bits.size)
    budget = max(1, min(int(candidate_budget), flat_size))
    max_passes_int = max(1, int(max_passes))

    for pass_index in range(max_passes_int):
        improved = False
        best_candidate_score = best_score
        best_candidate_index = None
        flat = best_bits.reshape(-1)
        for flat_index in range(budget):
            candidate = flat.copy()
            candidate[flat_index] = 1 - candidate[flat_index]
            candidate_bits = candidate.reshape(best_bits.shape)
            score = float(scorer(candidate_bits))
            if score > best_candidate_score:
                best_candidate_score = score
                best_candidate_index = flat_index
        if best_candidate_index is None:
            history.append(
                {
                    "pass_index": pass_index + 1,
                    "score": float(best_score),
                    "accepted_index": None,
                }
            )
            break
        flat[best_candidate_index] = 1 - flat[best_candidate_index]
        best_bits = flat.reshape(best_bits.shape)
        best_score = float(best_candidate_score)
        improved = True
        history.append(
            {
                "pass_index": pass_index + 1,
                "score": float(best_score),
                "accepted_index": int(best_candidate_index),
            }
        )
        if not improved:
            break

    return {
        "best_bits": best_bits,
        "best_phase": _bits_to_phase(best_bits),
        "best_score": float(best_score),
        "history": history,
    }
