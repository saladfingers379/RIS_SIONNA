from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import tensorflow as tf

from app.config import load_config
from app.scene import _resolve_array_pattern, _resolve_custom_radio_material_library


def _pattern_gain_db(pattern, theta_deg: float, phi_deg: float) -> float:
    theta = tf.constant([np.deg2rad(theta_deg)], dtype=tf.float32)
    phi = tf.constant([np.deg2rad(phi_deg)], dtype=tf.float32)
    c_theta, c_phi = pattern(theta, phi)
    gain = tf.abs(c_theta) ** 2 + tf.abs(c_phi) ** 2
    return float(10.0 * np.log10(float(gain.numpy()[0])))


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


def test_default_absorber_material_is_ideal_matched_boundary() -> None:
    materials = _resolve_custom_radio_material_library({})

    assert materials["itu_absorber"]["relative_permittivity"] == 1.0
    assert materials["itu_absorber"]["conductivity"] == 0.0
    assert materials["itu_absorber"]["scattering_coefficient"] == 0.0
    assert materials["itu_absorber"]["xpd_coefficient"] == 0.0


def test_ideal_foam_chamber_floor_uses_absorber_material_and_has_no_stools() -> None:
    tree = ET.parse(Path("scenes/anechoic_chamber_foam_ideal/scene.xml"))
    root = tree.getroot()

    floor = root.find("./shape[@id='metal_floor']")
    assert floor is not None
    floor_material = floor.find("./ref[@name='bsdf']")
    assert floor_material is not None
    assert floor_material.attrib["id"] == "mat-itu_absorber"
    assert root.find("./shape[@id='wooden_stool']") is None
    assert root.find("./shape[@id='wooden_stool001']") is None


def test_floor_only_chamber_scene_contains_only_metal_floor() -> None:
    tree = ET.parse(Path("scenes/anechoic_chamber_floor_only/scene.xml"))
    root = tree.getroot()

    shapes = root.findall("./shape")
    assert [shape.attrib["id"] for shape in shapes] == ["metal_floor"]

    floor = shapes[0]
    mesh = floor.find("./string[@name='filename']")
    assert mesh is not None
    assert mesh.attrib["value"] == "../anechoic_chamber_foam/meshes/metal_floor.ply"

    floor_material = floor.find("./ref[@name='bsdf']")
    assert floor_material is not None
    assert floor_material.attrib["id"] == "mat-itu_metal"


def test_resolve_array_pattern_maps_horn_to_callable() -> None:
    pattern, polarization = _resolve_array_pattern("horn_15dbi", "V")

    assert callable(pattern)
    assert polarization is None


def test_resolve_array_pattern_maps_front_suffix_as_full_horn_alias() -> None:
    pattern, polarization = _resolve_array_pattern("horn_15dbi_front", "V")

    assert callable(pattern)
    assert polarization is None


def test_front_suffix_horn_applies_rear_hemisphere_cutoff() -> None:
    full_pattern, _ = _resolve_array_pattern("horn_15dbi", "V")
    alias_pattern, _ = _resolve_array_pattern("horn_15dbi_front", "V")

    full_back_db = _pattern_gain_db(full_pattern, 90.0, 180.0)
    alias_back_db = _pattern_gain_db(alias_pattern, 90.0, 180.0)
    full_boresight_db = _pattern_gain_db(full_pattern, 90.0, 0.0)
    alias_boresight_db = _pattern_gain_db(alias_pattern, 90.0, 0.0)

    assert alias_back_db < -100.0
    assert full_back_db > alias_back_db + 50.0
    assert abs(alias_boresight_db - full_boresight_db) < 1e-3


def test_ieee_tap_chamber_uses_front_only_horns_for_campaign_maps() -> None:
    cfg = load_config("configs/indoor_box_ieee_tap_chamber.yaml").data
    arrays = cfg["scene"]["arrays"]

    assert arrays["tx"]["pattern"] == "horn_15dbi_front"
    assert arrays["rx"]["pattern"] == "horn_22dbi_front"


def test_resolve_array_pattern_leaves_builtin_pattern_unchanged() -> None:
    pattern, polarization = _resolve_array_pattern("tr38901", "V")

    assert pattern == "tr38901"
    assert polarization == "V"
