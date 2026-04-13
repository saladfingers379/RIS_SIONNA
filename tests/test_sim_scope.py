from app.sim_jobs import (
    infer_run_scope_from_config,
    infer_run_scope_from_job,
    normalize_run_scope,
)
from app.config import load_config
import math
import pytest


def test_normalize_run_scope_defaults_to_sim() -> None:
    assert normalize_run_scope(None) == "sim"


def test_normalize_run_scope_preserves_indoor() -> None:
    assert normalize_run_scope("indoor") == "indoor"


def test_normalize_run_scope_infers_legacy_indoor_profile() -> None:
    assert normalize_run_scope(None, profile="indoor_box_high") == "indoor"


def test_infer_run_scope_from_job_legacy_profile() -> None:
    assert infer_run_scope_from_job({"kind": "run", "profile": "indoor_box_high"}) == "indoor"


def test_infer_run_scope_from_job_non_run_kind() -> None:
    assert infer_run_scope_from_job({"kind": "ris_lab"}) == "ris_lab"


def test_infer_run_scope_from_config_job_scope() -> None:
    cfg = {"job": {"kind": "run", "scope": "indoor", "profile": "indoor_box_high"}}
    assert infer_run_scope_from_config(cfg) == "indoor"


def test_infer_run_scope_from_config_defaults_to_sim() -> None:
    assert infer_run_scope_from_config({"scene": {"builtin": "etoile"}}) == "sim"


def test_indoor_box_high_defaults_to_anechoic_chamber_scene() -> None:
    cfg = load_config("configs/indoor_box_high.yaml").data

    assert cfg["scene"]["type"] == "file"
    assert cfg["scene"]["file"] == "scenes/anechoic_chamber_foam_ideal/scene.xml"
    assert "floor_elevation" not in cfg["scene"]


def test_ieee_tap_chamber_config_matches_paper_geometry() -> None:
    cfg = load_config("configs/indoor_box_ieee_tap_chamber.yaml").data

    tx = cfg["scene"]["tx"]["position"]
    rx = cfg["scene"]["rx"]["position"]
    ris = cfg["ris"]["objects"][0]["position"]

    tx_ris = math.dist(tx, ris)
    rx_ris = math.dist(rx, ris)

    assert tx_ris == pytest.approx(0.4, abs=1e-4)
    assert rx_ris == pytest.approx(1.1, abs=1e-9)
    assert cfg["scene"]["tx"]["power_dbm"] == pytest.approx(28.0)
    assert cfg["ris"]["size"]["width_m"] == pytest.approx(0.0926)
    assert cfg["ris"]["size"]["height_m"] == pytest.approx(0.0926)
    assert cfg["ris"]["size"]["target_dx_m"] == pytest.approx(0.0049)
    assert cfg["ris"]["size"]["target_dy_m"] == pytest.approx(0.0049)
    assert cfg["ris"]["objects"][0]["profile"]["amplitude"] == pytest.approx(0.84)
    assert "phase_bits" not in cfg["ris"]["objects"][0]["profile"]
    assert cfg["campaign"]["pivot"] == pytest.approx(ris)
    assert cfg["ris"]["objects"][0]["profile"]["auto_aim"] is True
