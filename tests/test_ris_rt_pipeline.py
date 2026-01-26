import pytest


def _has_sionna_rt():
    try:
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
