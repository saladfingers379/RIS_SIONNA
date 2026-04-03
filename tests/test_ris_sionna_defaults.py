import numpy as np
from types import SimpleNamespace

from app.ris.ris_geometry import build_ris_geometry
from app.ris.ris_sionna import (
    _derive_ris_front_face_look_at,
    _nonlegacy_geometry_to_ris_panel_dims,
    _resolve_profile_endpoints,
)


def test_derive_ris_front_face_look_at_faces_source_and_target_side() -> None:
    ris_pos = np.array([0.0, 1.6, 0.7], dtype=float)
    tx = np.array([0.0, 0.0, 0.7], dtype=float)
    rx = np.array([1.1, 0.9765224933624267, 0.7], dtype=float)

    look_at = _derive_ris_front_face_look_at(ris_pos, [tx], [rx])

    assert look_at is not None
    normal = np.asarray(look_at, dtype=float) - ris_pos
    assert float(np.dot(normal, tx - ris_pos)) > 0.0
    assert float(np.dot(normal, rx - ris_pos)) > 0.0


def test_derive_ris_front_face_look_at_returns_none_without_endpoints() -> None:
    assert _derive_ris_front_face_look_at([0.0, 0.0, 0.0], [], []) is None


def test_resolve_profile_endpoints_preserves_explicit_sources_and_targets() -> None:
    profile = {
        "auto_aim": True,
        "sources": [9.0, 8.0, 7.0],
        "targets": [6.0, 5.0, 4.0],
    }
    scene = SimpleNamespace(
        transmitters={"tx": SimpleNamespace(position=[1.0, 2.0, 3.0])},
        receivers={"rx": SimpleNamespace(position=[4.0, 5.0, 6.0])},
    )

    sources, targets = _resolve_profile_endpoints(profile, scene=scene)

    assert len(sources) == 1
    assert len(targets) == 1
    assert np.allclose(sources[0], np.array([9.0, 8.0, 7.0]))
    assert np.allclose(targets[0], np.array([6.0, 5.0, 4.0]))


def test_resolve_profile_endpoints_fills_only_missing_target() -> None:
    profile = {
        "auto_aim": True,
        "sources": [9.0, 8.0, 7.0],
    }
    scene = SimpleNamespace(
        transmitters={"tx": SimpleNamespace(position=[1.0, 2.0, 3.0])},
        receivers={"rx": SimpleNamespace(position=[4.0, 5.0, 6.0])},
    )

    sources, targets = _resolve_profile_endpoints(profile, scene=scene)

    assert len(sources) == 1
    assert len(targets) == 1
    assert np.allclose(sources[0], np.array([9.0, 8.0, 7.0]))
    assert np.allclose(targets[0], np.array([4.0, 5.0, 6.0]))


def test_nonlegacy_geometry_maps_to_sionna_rows_then_cols() -> None:
    geometry = build_ris_geometry(
        {
            "geometry_mode": "spacing_driven",
            "spacing": {"dx_m": 0.01, "dy_m": 0.02, "width_m": 0.2, "height_m": 0.2},
        }
    )

    num_rows, num_cols = _nonlegacy_geometry_to_ris_panel_dims(geometry)

    assert geometry["nx"] == 21
    assert geometry["ny"] == 11
    assert num_rows == 11
    assert num_cols == 21
