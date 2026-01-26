import numpy as np
import pytest


def _has_sionna_rt():
    try:
        import sionna.rt  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_sionna_rt(), reason="sionna.rt not available")
def test_ris_smoke_paths():
    import mitsuba as mi
    variants = list(mi.variants())
    for candidate in ("llvm_ad_rgb", "llvm_ad_spectral", "llvm_ad_mono"):
        if candidate in variants:
            mi.set_variant(candidate)
            from app.utils.system import configure_tensorflow_for_mitsuba_variant
            configure_tensorflow_for_mitsuba_variant(candidate)
            break

    import sionna.rt as rt

    # Verify expected exports for v0.19.2
    assert hasattr(rt, "RIS")
    assert hasattr(rt, "DiscretePhaseProfile")
    assert hasattr(rt, "DiscreteAmplitudeProfile")

    scene = rt.load_scene()
    scene.frequency = 28.0e9
    scene.tx_array = rt.PlanarArray(
        num_rows=1,
        num_cols=1,
        vertical_spacing=0.5,
        horizontal_spacing=0.5,
        pattern="iso",
        polarization="V",
    )
    scene.rx_array = rt.PlanarArray(
        num_rows=1,
        num_cols=1,
        vertical_spacing=0.5,
        horizontal_spacing=0.5,
        pattern="iso",
        polarization="V",
    )

    tx = rt.Transmitter(name="tx", position=np.array([-5.0, -4.0, 3.0]), power_dbm=30.0)
    rx = rt.Receiver(name="rx", position=np.array([8.0, 4.0, 1.5]))
    scene.add(tx)
    scene.add(rx)

    ris = rt.RIS(
        name="ris",
        position=np.array([0.0, 0.0, 2.0]),
        num_rows=10,
        num_cols=10,
        num_modes=1,
        orientation=np.array([0.0, 0.0, 0.0]),
    )
    scene.add(ris)
    ris.phase_gradient_reflector(
        [np.array(tx.position, dtype=float)],
        [np.array(rx.position, dtype=float)],
    )

    paths = scene.compute_paths(
        max_depth=1,
        method="fibonacci",
        num_samples=2000,
        los=True,
        reflection=True,
        diffraction=False,
        scattering=False,
        ris=True,
    )
    assert paths is not None
    types = getattr(paths, "types", None)
    if types is not None and hasattr(paths, "RIS"):
        types_np = np.asarray(types)
        assert np.any(types_np == int(paths.RIS))
