import numpy as np
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

def _assign_profile_values(profile, values):
    try:
        assign = getattr(profile.values, "assign", None)
        if callable(assign):
            assign(values)
            return
    except Exception:
        pass
    profile.values = values


@pytest.mark.skipif(not _has_sionna_rt(), reason="sionna.rt not available")
def test_ris_on_off_paths_smoke():
    import mitsuba as mi
    variants = list(mi.variants())
    for candidate in ("llvm_ad_rgb", "llvm_ad_spectral", "llvm_ad_mono"):
        if candidate in variants:
            mi.set_variant(candidate)
            from app.utils.system import configure_tensorflow_for_mitsuba_variant
            configure_tensorflow_for_mitsuba_variant(candidate)
            break

    import sionna.rt as rt
    import tensorflow as tf

    from app.metrics import compute_path_metrics
    from app.ris.ris_sionna import apply_workbench_to_ris, build_workbench_phase_map

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

    ris_cfg = {
        "geometry": {
            "nx": 10,
            "ny": 10,
            "dx": 0.00535,
            "dy": 0.00535,
            "origin": [0.0, 0.0, 2.0],
            "normal": [1.0, 0.0, 0.0],
            "x_axis_hint": [0.0, 1.0, 0.0],
        },
        "control": {"mode": "uniform", "params": {"phase_rad": 0.0}},
        "quantization": {"bits": 0},
        "experiment": {"frequency_hz": 28_000_000_000, "reflection_coeff": 0.84},
    }
    workbench = build_workbench_phase_map(ris_cfg)
    ris = rt.RIS(
        name="ris",
        position=np.array([0.0, 0.0, 2.0]),
        num_rows=workbench.num_rows,
        num_cols=workbench.num_cols,
        num_modes=1,
        orientation=np.array([0.0, 0.0, 0.0]),
    )
    apply_workbench_to_ris(ris, workbench)
    scene.add(ris)

    paths_on = scene.compute_paths(
        max_depth=1,
        method="fibonacci",
        num_samples=2000,
        los=True,
        reflection=True,
        diffraction=False,
        scattering=False,
        ris=True,
    )
    metrics_on = compute_path_metrics(paths_on, tx_power_dbm=tx.power_dbm)

    _assign_profile_values(ris.phase_profile, tf.zeros_like(ris.phase_profile.values))
    _assign_profile_values(
        ris.amplitude_profile,
        tf.ones_like(ris.amplitude_profile.values)
        * tf.cast(workbench.amplitude, ris.amplitude_profile.values.dtype),
    )
    paths_off = scene.compute_paths(
        max_depth=1,
        method="fibonacci",
        num_samples=2000,
        los=True,
        reflection=True,
        diffraction=False,
        scattering=False,
        ris=True,
    )
    metrics_off = compute_path_metrics(paths_off, tx_power_dbm=tx.power_dbm)

    assert np.isfinite(metrics_on["total_path_gain_db"])
    assert np.isfinite(metrics_off["total_path_gain_db"])
