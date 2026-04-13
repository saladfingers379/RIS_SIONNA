from __future__ import annotations

import numpy as np
import pytest

from app.link_level import (
    coerce_link_eval_for_seed,
    _delay_profile_from_cir,
    _plot_variant_delay_histograms,
    _prepare_seed_run_config,
    prepare_link_seed_config,
    resolve_link_variants,
    _resolve_link_trace_config,
    _scale_cir_to_reference_gain,
    validate_link_seed_variants,
)


def test_resolve_link_variants_defaults_to_off_when_seed_has_no_ris() -> None:
    variants = resolve_link_variants({"ris": {"enabled": False}}, {})

    assert [variant["key"] for variant in variants] == ["ris_off"]


def test_resolve_link_variants_keeps_requested_ris_modes_when_enabled() -> None:
    variants = resolve_link_variants(
        {"ris": {"enabled": True}},
        {"ris_variants": ["ris_off", "ris_configured", "ris_flat"]},
    )

    assert [variant["key"] for variant in variants] == ["ris_off", "ris_configured", "ris_flat"]


def test_prepare_link_seed_config_coerces_arrays_to_single_stream() -> None:
    prepared, warnings = prepare_link_seed_config(
        {
            "scene": {
                "arrays": {
                    "tx": {"num_rows": 2, "num_cols": 4},
                    "rx": {"num_rows": 1, "num_cols": 8},
                }
            },
            "render": {"enabled": True},
            "radio_map": {"enabled": True},
        }
    )

    assert prepared["scene"]["arrays"]["tx"]["num_rows"] == 1
    assert prepared["scene"]["arrays"]["tx"]["num_cols"] == 1
    assert prepared["scene"]["arrays"]["rx"]["num_rows"] == 1
    assert prepared["scene"]["arrays"]["rx"]["num_cols"] == 1
    assert prepared["render"]["enabled"] is False
    assert prepared["radio_map"]["enabled"] is False
    assert warnings


def test_validate_link_seed_variants_rejects_ris_compare_without_ris() -> None:
    with pytest.raises(ValueError, match="ris.enabled=false"):
        validate_link_seed_variants(
            {"ris": {"enabled": False}},
            {"ris_variants": ["ris_off", "ris_configured"]},
        )


def test_coerce_link_eval_for_seed_reduces_to_ris_off_without_ris() -> None:
    eval_cfg, warnings = coerce_link_eval_for_seed(
        {"ris": {"enabled": False}},
        {"ris_variants": ["ris_off", "ris_configured", "ris_flat"]},
    )

    assert eval_cfg["ris_variants"] == ["ris_off"]
    assert warnings


def test_scale_cir_to_reference_gain_preserves_relative_ratio() -> None:
    a = np.ones((1, 1, 1, 1, 1, 1, 2), dtype=np.complex64)

    scaled = _scale_cir_to_reference_gain(
        a,
        path_gain_linear=1.0e-2,
        reference_gain_linear=1.0e-1,
    )

    assert scaled.shape == a.shape
    assert np.isclose(np.abs(scaled[0, 0, 0, 0, 0, 0, 0]), np.sqrt(10.0), atol=1e-6)


def test_resolve_link_trace_config_inherits_seed_settings_by_default() -> None:
    sim_cfg, warnings, meta = _resolve_link_trace_config(
        {"simulation": {"max_depth": 6, "samples_per_src": 2_000_000}},
        {},
    )

    assert sim_cfg["max_depth"] == 6
    assert sim_cfg["samples_per_src"] == 2_000_000
    assert warnings == []
    assert meta["rt_max_depth"] == 6
    assert meta["rt_samples_per_src"] == 2_000_000


def test_resolve_link_trace_config_warns_on_lower_overrides() -> None:
    sim_cfg, warnings, meta = _resolve_link_trace_config(
        {"simulation": {"max_depth": 6, "samples_per_src": 2_000_000}},
        {"max_depth": 4, "samples_per_src": 120_000},
    )

    assert sim_cfg["max_depth"] == 4
    assert sim_cfg["samples_per_src"] == 120_000
    assert len(warnings) == 2
    assert "max_depth override" in warnings[0]
    assert "samples_per_src override" in warnings[1]
    assert meta["seed_rt_max_depth"] == 6
    assert meta["seed_rt_samples_per_src"] == 2_000_000


def test_plot_variant_delay_histograms_writes_png(tmp_path) -> None:
    output_path = tmp_path / "variant_path_delay_hist_ns.png"

    _plot_variant_delay_histograms(
        {
            "ris_off": {
                "label": "RIS Off",
                "delays_s": np.array([1.0e-8, 2.0e-8, 2.5e-8], dtype=float),
                "weights": np.array([1.0, 0.5, 0.25], dtype=float),
            },
            "ris_on": {
                "label": "RIS Configured",
                "delays_s": np.array([1.5e-8, 2.2e-8], dtype=float),
                "weights": np.array([0.8, 0.3], dtype=float),
            },
        },
        output_path,
    )

    assert output_path.exists()


def test_delay_profile_from_cir_returns_weighted_spread() -> None:
    a = np.zeros((1, 1, 1, 1, 1, 2, 3), dtype=np.complex64)
    a[..., 0, :] = 1.0 + 0.0j
    a[..., 1, :] = 2.0 + 0.0j
    tau = np.array([[[[1.0e-8, 3.0e-8]]]], dtype=np.float32)

    profile = _delay_profile_from_cir(a, tau)

    assert profile["delays_s"].shape == (2,)
    assert profile["weights"].shape == (2,)
    assert profile["rms_delay_spread_ns"] is not None
    assert profile["rms_delay_spread_ns"] > 0.0


def test_prepare_seed_run_config_disables_radio_map(tmp_path) -> None:
    config_path, run_id = _prepare_seed_run_config(
        seed_cfg={"radio_map": {"enabled": True}},
        link_output_dir=tmp_path,
        link_run_id="link-run",
        base_dir="outputs",
    )

    assert run_id == "link-run__seed"
    saved = config_path.read_text(encoding="utf-8")
    assert "enabled: false" in saved
