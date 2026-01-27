import pytest

from app.ris.ris_geometry import build_ris_geometry


def test_size_driven_derives_counts_and_spacing() -> None:
    ris_cfg = {
        "geometry_mode": "size_driven",
        "size": {"width_m": 0.2, "height_m": 0.1, "target_dx_m": 0.02, "target_dy_m": 0.01},
    }
    geom = build_ris_geometry(ris_cfg, obj_cfg={"num_rows": 4, "num_cols": 5})
    assert geom["nx"] == 11
    assert geom["ny"] == 11
    assert pytest.approx(geom["dx_m"], rel=1e-6) == 0.02
    assert pytest.approx(geom["dy_m"], rel=1e-6) == 0.01
    assert pytest.approx(geom["width_m"], rel=1e-6) == 0.2
    assert pytest.approx(geom["height_m"], rel=1e-6) == 0.1


def test_spacing_driven_with_size_derives_counts() -> None:
    ris_cfg = {
        "geometry_mode": "spacing_driven",
        "spacing": {"dx_m": 0.01, "dy_m": 0.02, "width_m": 0.2, "height_m": 0.2},
    }
    geom = build_ris_geometry(ris_cfg)
    assert geom["nx"] == 21
    assert geom["ny"] == 11
    assert pytest.approx(geom["width_m"], rel=1e-6) == 0.2
    assert pytest.approx(geom["height_m"], rel=1e-6) == 0.2


def test_spacing_driven_with_counts_derives_size() -> None:
    ris_cfg = {
        "geometry_mode": "spacing_driven",
        "spacing": {"dx_m": 0.01, "dy_m": 0.02, "num_cells_x": 10, "num_cells_y": 5},
    }
    geom = build_ris_geometry(ris_cfg)
    assert geom["nx"] == 10
    assert geom["ny"] == 5
    assert pytest.approx(geom["width_m"], rel=1e-6) == 0.09
    assert pytest.approx(geom["height_m"], rel=1e-6) == 0.08


def test_legacy_preserves_counts() -> None:
    ris_cfg = {"geometry_mode": "legacy"}
    geom = build_ris_geometry(ris_cfg, obj_cfg={"num_rows": 12, "num_cols": 8})
    assert geom["mode"] == "legacy"
    assert geom["nx"] == 12
    assert geom["ny"] == 8


def test_invalid_missing_fields() -> None:
    with pytest.raises(ValueError):
        build_ris_geometry({"geometry_mode": "size_driven"})
