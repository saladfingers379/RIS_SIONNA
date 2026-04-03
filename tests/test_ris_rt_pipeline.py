import pytest


def _has_sionna_rt():
    try:
        import mitsuba as mi
        variants = list(mi.variants())
        for candidate in (
            "llvm_ad_rgb",
            "llvm_ad_spectral",
            "llvm_ad_mono",
            "scalar_spectral",
            "scalar_rgb",
        ):
            if candidate in variants:
                mi.set_variant(candidate)
                break
        import sionna.rt  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_sionna_rt(), reason="sionna.rt not available")
def test_ris_config_parsing_build_scene():
    from app.config import load_config
    from app.scene import build_scene
    from app.utils.system import select_mitsuba_variant

    cfg = load_config("configs/ris_preview.yaml")
    variant = select_mitsuba_variant(prefer_gpu=False, forced_variant="auto")
    from app.utils.system import configure_tensorflow_for_mitsuba_variant
    configure_tensorflow_for_mitsuba_variant(variant)
    scene = build_scene(cfg.data, mitsuba_variant=variant)

    ris_summary = getattr(scene, "_ris_runtime", None)
    assert isinstance(ris_summary, list)
    assert ris_summary and ris_summary[0]["name"] == "ris1"


@pytest.mark.skipif(not _has_sionna_rt(), reason="sionna.rt not available")
def test_no_variant_mixing_after_diagnose():
    from app.utils.system import assert_mitsuba_variant, diagnose_environment, select_mitsuba_variant
    from app.scene import build_scene

    diagnose_environment(prefer_gpu=False, forced_variant="auto", tensorflow_mode="skip", run_smoke=True)

    variant = select_mitsuba_variant(prefer_gpu=False, forced_variant="auto")
    from app.utils.system import configure_tensorflow_for_mitsuba_variant
    configure_tensorflow_for_mitsuba_variant(variant)
    assert_mitsuba_variant(variant, context="test_no_variant_mixing")

    from sionna.rt import Camera

    assert variant in Camera.mi_2_sionna.__class__.__module__

    cfg = {
        "scene": {"type": "builtin", "builtin": "etoile"},
        "simulation": {"frequency_hz": 28.0e9},
    }
    scene = build_scene(cfg, mitsuba_variant=variant)
    assert scene is not None


@pytest.mark.skipif(not _has_sionna_rt(), reason="sionna.rt not available")
def test_file_scene_custom_absorber_material_is_preserved():
    from app.config import load_config
    from app.scene import build_scene
    from app.utils.system import select_mitsuba_variant

    cfg = load_config("configs/indoor_box_high.yaml").data
    cfg["runtime"]["force_cpu"] = True
    cfg["runtime"]["prefer_gpu"] = False
    cfg["scene"]["type"] = "file"
    cfg["scene"]["file"] = "scenes/anechoic_chamber_nofoam/scene.xml"

    variant = select_mitsuba_variant(prefer_gpu=False, forced_variant="auto")
    from app.utils.system import configure_tensorflow_for_mitsuba_variant

    configure_tensorflow_for_mitsuba_variant(variant)
    scene = build_scene(cfg, mitsuba_variant=variant)

    absorber = scene.get("absorber_back")
    absorber_mat = absorber.radio_material
    assert absorber_mat.name == "itu_absorber"
    assert absorber_mat.is_placeholder is False
    assert float(absorber_mat.relative_permittivity.numpy()) == pytest.approx(1.0)
    assert float(absorber_mat.conductivity.numpy()) == pytest.approx(0.2)

    floor = scene.get("metal_floor")
    floor_mat = floor.radio_material
    assert floor_mat.name == "itu_metal"


@pytest.mark.skipif(not _has_sionna_rt(), reason="sionna.rt not available")
def test_file_scene_horn_pattern_builds_for_indoor_chamber():
    from app.config import load_config
    from app.scene import build_scene
    from app.utils.system import select_mitsuba_variant

    cfg = load_config("configs/indoor_box_ieee_tap_chamber.yaml").data
    cfg["runtime"]["force_cpu"] = True
    cfg["runtime"]["prefer_gpu"] = False

    variant = select_mitsuba_variant(prefer_gpu=False, forced_variant="auto")
    from app.utils.system import configure_tensorflow_for_mitsuba_variant

    configure_tensorflow_for_mitsuba_variant(variant)
    scene = build_scene(cfg, mitsuba_variant=variant)

    tx_patterns = getattr(scene.tx_array.antenna, "patterns", [])
    rx_patterns = getattr(scene.rx_array.antenna, "patterns", [])
    assert len(tx_patterns) == 1
    assert len(rx_patterns) == 1


@pytest.mark.skipif(not _has_sionna_rt(), reason="sionna.rt not available")
def test_blank_scene_builds_for_los_only_testing():
    from app.config import load_config
    from app.scene import build_scene
    from app.utils.system import select_mitsuba_variant

    cfg = load_config("configs/blank_los.yaml").data
    cfg["runtime"]["force_cpu"] = True
    cfg["runtime"]["prefer_gpu"] = False

    variant = select_mitsuba_variant(prefer_gpu=False, forced_variant="auto")
    from app.utils.system import configure_tensorflow_for_mitsuba_variant

    configure_tensorflow_for_mitsuba_variant(variant)
    scene = build_scene(cfg, mitsuba_variant=variant)

    assert scene is not None
    assert scene.get("blank_anchor") is not None
    rx = scene.receivers["rx"]
    look_at_attr = getattr(rx, "look_at", None)
    assert callable(look_at_attr)
