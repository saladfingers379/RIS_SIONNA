from __future__ import annotations

from app.scene import _resolve_array_pattern, _resolve_custom_radio_material_library


def test_resolve_custom_radio_material_library_applies_scene_overrides() -> None:
    cfg = {
        "scene": {
            "custom_radio_materials": {
                "itu_absorber": {"conductivity": 2.5},
                "custom_test": {"relative_permittivity": 3.0, "conductivity": 0.2},
            }
        }
    }

    materials = _resolve_custom_radio_material_library(cfg)

    assert materials["itu_absorber"]["relative_permittivity"] == 1.0
    assert materials["itu_absorber"]["conductivity"] == 2.5
    assert materials["itu_absorber"]["scattering_coefficient"] == 0.0
    assert materials["custom_test"]["relative_permittivity"] == 3.0
    assert materials["custom_test"]["conductivity"] == 0.2


def test_resolve_array_pattern_maps_horn_to_callable() -> None:
    pattern, polarization = _resolve_array_pattern("horn_15dbi", "V")

    assert callable(pattern)
    assert polarization is None


def test_resolve_array_pattern_maps_front_only_horn_to_callable() -> None:
    pattern, polarization = _resolve_array_pattern("horn_15dbi_front", "V")

    assert callable(pattern)
    assert polarization is None


def test_resolve_array_pattern_leaves_builtin_pattern_unchanged() -> None:
    pattern, polarization = _resolve_array_pattern("tr38901", "V")

    assert pattern == "tr38901"
    assert polarization == "V"
