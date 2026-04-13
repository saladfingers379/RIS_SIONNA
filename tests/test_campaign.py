from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from app.campaign import (
    _enrich_qub_sample_from_summary,
    _extract_measurement,
    _qub_cut_series_keys,
    _qub_rx_power_series_key,
    _qub_specular_measurement_angle_deg,
    _qub_specular_turntable_angle_deg,
    run_absorber_sweep,
    run_campaign,
)
from app.io import create_output_dir


def _write_campaign_config(path: Path, *, base_dir: Path, run_id: str, max_angles_per_job: int) -> None:
    config = {
        "runtime": {"prefer_gpu": False, "force_cpu": True, "require_cuda": False},
        "simulation": {"compute_paths": True},
        "scene": {
            "type": "file",
            "file": "scenes/anechoic_chamber_nofoam/scene.xml",
            "tx": {"position": [0.0, -0.98, 1.5], "look_at": [0.0, 0.0, 1.5]},
            "rx": {"position": [0.0, 0.98, 1.5]},
        },
        "radio_map": {"enabled": True, "cell_size": [0.05, 0.05]},
        "render": {"enabled": True},
        "visualization": {"ray_paths": {"enabled": True}},
        "output": {"base_dir": str(base_dir), "run_id": run_id},
        "campaign": {
            "sweep_device": "rx",
            "radius_m": 1.0,
            "arc_height_offset_m": 0.0,
            "pivot": [0.0, 0.0, 1.5],
            "start_angle_deg": -2.0,
            "stop_angle_deg": 2.0,
            "step_deg": 1.0,
            "max_angles_per_job": max_angles_per_job,
            "compact_output": True,
            "disable_render": True,
            "prune_angle_outputs": True,
            "coarse_cell_size_m": 0.2,
        },
    }
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def test_qub_specular_path_angles_use_campaign2_geometry() -> None:
    campaign_cfg = {"tx_incidence_angle_deg": -30.0}

    assert _qub_specular_measurement_angle_deg(campaign_cfg) == pytest.approx(30.0)
    assert _qub_specular_turntable_angle_deg(0.0, campaign_cfg) == pytest.approx(-30.0)
    assert _qub_specular_turntable_angle_deg(45.0, campaign_cfg) == pytest.approx(15.0)


def test_qub_combined_cut_uses_absolute_labels() -> None:
    _, _, ylabel, on_label, off_label = _qub_cut_series_keys(
        [
            {
                "total_path_gain_db": -20.0,
                "ris_off_total_path_gain_db": -55.0,
            }
        ]
    )

    assert ylabel == "Path gain [dB]"
    assert on_label == "RIS on"
    assert off_label == "RIS off"


def test_qub_combined_cut_prefers_radio_map_peak_series() -> None:
    _, _, ylabel, on_label, off_label = _qub_cut_series_keys(
        [
            {
                "total_path_gain_db": -60.0,
                "ris_off_total_path_gain_db": -55.0,
                "radio_map_path_gain_db_max": -52.0,
                "ris_off_radio_map_path_gain_db_max": -79.0,
            }
        ]
    )

    assert ylabel == "Radio-map peak path gain [dB]"
    assert on_label == "RIS on radio-map peak"
    assert off_label == "RIS off radio-map peak"


def test_qub_combined_cut_prefers_radio_map_measurement_cell_over_global_peak() -> None:
    on_key, off_key, ylabel, on_label, off_label = _qub_cut_series_keys(
        [
            {
                "total_path_gain_db": -60.0,
                "ris_off_total_path_gain_db": -55.0,
                "radio_map_path_gain_db_max": -30.0,
                "ris_off_radio_map_path_gain_db_max": -30.0,
                "radio_map_measurement_path_gain_db": -48.0,
                "ris_off_radio_map_measurement_path_gain_db": -72.0,
            }
        ]
    )

    assert on_key == "radio_map_measurement_path_gain_db"
    assert off_key == "ris_off_radio_map_measurement_path_gain_db"
    assert ylabel == "Radio-map measurement path gain [dB]"
    assert on_label == "RIS on radio-map measurement"
    assert off_label == "RIS off radio-map measurement"


def test_qub_combined_cut_falls_back_when_radio_map_measurement_has_no_contrast() -> None:
    on_key, off_key, ylabel, on_label, off_label = _qub_cut_series_keys(
        [
            {
                "measurement_angle_deg": 0.0,
                "status": "completed",
                "total_path_gain_db": -58.0,
                "ris_off_total_path_gain_db": -62.0,
                "radio_map_measurement_path_gain_db": -90.0,
                "ris_off_radio_map_measurement_path_gain_db": -90.0,
                "radio_map_path_gain_db_max": -38.0,
                "ris_off_radio_map_path_gain_db_max": -40.0,
            },
            {
                "measurement_angle_deg": 10.0,
                "status": "completed",
                "total_path_gain_db": -57.0,
                "ris_off_total_path_gain_db": -65.0,
                "radio_map_measurement_path_gain_db": -95.0,
                "ris_off_radio_map_measurement_path_gain_db": -95.0,
                "radio_map_path_gain_db_max": -39.0,
                "ris_off_radio_map_path_gain_db_max": -42.0,
            },
        ]
    )

    assert on_key == "total_path_gain_db"
    assert off_key == "ris_off_total_path_gain_db"
    assert ylabel == "Path gain [dB]"
    assert on_label == "RIS on"
    assert off_label == "RIS off"


def test_extract_measurement_records_radio_map_peak_delta() -> None:
    row = _extract_measurement(
        {
            "metrics": {
                "total_path_gain_db": -60.0,
                "rx_power_dbm_estimate": -32.0,
                "ris_link_probe": {
                    "off_total_path_gain_db": -55.0,
                    "off_rx_power_dbm_estimate": -27.0,
                },
                "radio_map": [
                    {
                        "label": "default",
                        "stats": {
                            "path_gain_db_max": -52.0,
                            "rx_power_dbm_max": -24.0,
                        },
                    },
                    {
                        "label": "ris_off",
                        "suffix": "ris_off",
                        "stats": {
                            "path_gain_db_max": -79.0,
                            "rx_power_dbm_max": -51.0,
                        },
                    },
                ],
            }
        },
        angle_deg=0.0,
        run_id="sample",
        position=[0.0, 0.0, 1.5],
    )

    assert row["radio_map_path_gain_db_max"] == pytest.approx(-52.0)
    assert row["ris_off_radio_map_path_gain_db_max"] == pytest.approx(-79.0)
    assert row["radio_map_delta_path_gain_db_max"] == pytest.approx(27.0)
    assert _qub_rx_power_series_key([row]) == "radio_map_rx_power_dbm_max"


def test_extract_measurement_prefers_strongest_matching_radio_map_slice() -> None:
    row = _extract_measurement(
        {
            "metrics": {
                "radio_map": [
                    {
                        "label": "default",
                        "suffix": None,
                        "plane_center_z_m": 1.50,
                        "stats": {
                            "path_gain_db_max": -88.0,
                            "rx_power_dbm_max": -60.0,
                        },
                    },
                    {
                        "label": "zm0p02m",
                        "suffix": "zm0p02m",
                        "plane_center_z_m": 1.48,
                        "stats": {
                            "path_gain_db_max": -42.0,
                            "rx_power_dbm_max": -14.0,
                        },
                    },
                    {
                        "label": "ris_off",
                        "suffix": "ris_off",
                        "plane_center_z_m": 1.50,
                        "stats": {
                            "path_gain_db_max": -80.0,
                            "rx_power_dbm_max": -52.0,
                        },
                    },
                    {
                        "label": "ris_off_zm0p02m",
                        "suffix": "ris_off_zm0p02m",
                        "plane_center_z_m": 1.48,
                        "stats": {
                            "path_gain_db_max": -70.0,
                            "rx_power_dbm_max": -42.0,
                        },
                    },
                ]
            }
        },
        angle_deg=0.0,
        run_id="sample",
        position=[0.0, 0.0, 1.5],
    )

    assert row["radio_map_path_gain_db_max"] == pytest.approx(-42.0)
    assert row["ris_off_radio_map_path_gain_db_max"] == pytest.approx(-70.0)
    assert row["radio_map_delta_path_gain_db_max"] == pytest.approx(28.0)
    assert row["radio_map_suffix"] == "zm0p02m"
    assert row["radio_map_plane_z_m"] == pytest.approx(1.48)


def test_enrich_qub_sample_from_summary_backfills_radio_map_peak(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    sample_dir = output_dir / "cases" / "case_a" / "sample_a"
    sample_dir.mkdir(parents=True)
    (sample_dir / "summary.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "total_path_gain_db": -60.0,
                    "rx_power_dbm_estimate": -32.0,
                    "radio_map": [
                        {"label": "default", "stats": {"path_gain_db_max": -52.0, "rx_power_dbm_max": -24.0}},
                        {"label": "ris_off", "stats": {"path_gain_db_max": -79.0, "rx_power_dbm_max": -51.0}},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    row = _enrich_qub_sample_from_summary(
        output_dir,
        {
            "case_id": "case_a",
            "run_id": "sample_a",
            "measurement_angle_deg": 0.0,
            "position_x_m": 0.0,
            "position_y_m": 0.0,
            "position_z_m": 1.5,
        },
    )

    assert row["radio_map_path_gain_db_max"] == pytest.approx(-52.0)
    assert row["ris_off_radio_map_path_gain_db_max"] == pytest.approx(-79.0)


def test_enrich_qub_sample_from_summary_samples_nearest_radio_map_cell(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    sample_dir = output_dir / "cases" / "case_a" / "sample_a"
    data_dir = sample_dir / "data"
    data_dir.mkdir(parents=True)
    (sample_dir / "summary.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "total_path_gain_db": -60.0,
                    "rx_power_dbm_estimate": -32.0,
                    "radio_map": [
                        {
                            "label": "default",
                            "stats": {"path_gain_db_max": -30.0, "rx_power_dbm_max": -2.0},
                            "plane_center_z_m": 1.5,
                        },
                        {
                            "label": "ris_off",
                            "suffix": "ris_off",
                            "stats": {"path_gain_db_max": -30.0, "rx_power_dbm_max": -2.0},
                            "plane_center_z_m": 1.5,
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    cell_centers = np.array(
        [
            [[0.0, 0.0, 1.5], [0.1, 0.0, 1.5]],
            [[0.0, 0.1, 1.5], [0.1, 0.1, 1.5]],
        ],
        dtype=float,
    )
    np.savez_compressed(
        data_dir / "radio_map.npz",
        path_gain_db=np.array([[-48.0, -30.0], [-55.0, -40.0]], dtype=float),
        rx_power_dbm=np.array([[-20.0, -2.0], [-27.0, -12.0]], dtype=float),
        cell_centers=cell_centers,
    )
    np.savez_compressed(
        data_dir / "radio_map_ris_off.npz",
        path_gain_db=np.array([[-72.0, -30.0], [-75.0, -42.0]], dtype=float),
        rx_power_dbm=np.array([[-44.0, -2.0], [-47.0, -14.0]], dtype=float),
        cell_centers=cell_centers,
    )

    row = _enrich_qub_sample_from_summary(
        output_dir,
        {
            "case_id": "case_a",
            "run_id": "sample_a",
            "measurement_angle_deg": 0.0,
            "position_x_m": 0.02,
            "position_y_m": 0.01,
            "position_z_m": 1.5,
        },
    )

    assert row["radio_map_measurement_path_gain_db"] == pytest.approx(-48.0)
    assert row["ris_off_radio_map_measurement_path_gain_db"] == pytest.approx(-72.0)
    assert row["radio_map_measurement_delta_path_gain_db"] == pytest.approx(24.0)
    assert row["radio_map_measurement_rx_power_dbm"] == pytest.approx(-20.0)
    assert _qub_rx_power_series_key([row]) == "radio_map_measurement_rx_power_dbm"


def test_run_campaign_writes_chunked_summary_and_prunes(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_a", max_angles_per_job=3)

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        (output_dir / "data").mkdir(exist_ok=True)
        (output_dir / "plots").mkdir(exist_ok=True)
        (output_dir / "viewer").mkdir(exist_ok=True)
        rx_pos = cfg["scene"]["rx"]["position"]
        angle_value = round(rx_pos[1], 4)
        summary = {
            "metrics": {
                "total_path_gain_db": angle_value,
                "rx_power_dbm_estimate": angle_value + 10.0,
                "ris_link_probe": {
                    "off_total_path_gain_db": angle_value - 2.0,
                    "off_rx_power_dbm_estimate": angle_value + 8.0,
                    "delta_total_path_gain_db": 2.0,
                    "delta_rx_power_dbm_estimate": 2.0,
                },
                "num_valid_paths": 7,
                "radio_map": [
                    {
                        "stats": {
                            "path_gain_db_mean": angle_value - 1.0,
                            "rx_power_dbm_mean": angle_value + 2.0,
                            "path_loss_db_mean": 100.0 - angle_value,
                        }
                    }
                ],
            }
        }
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["kind"] == "campaign"
    assert summary["campaign_complete"] is False
    assert summary["metrics"]["completed_angles"] == 3
    assert summary["metrics"]["remaining_angles"] == 2

    rows = list(csv.DictReader((output_dir / "data" / "campaign_measurements.csv").open("r", encoding="utf-8")))
    assert len(rows) == 3
    assert float(rows[0]["ris_off_total_path_gain_db"]) == pytest.approx(float(rows[0]["total_path_gain_db"]) - 2.0)
    assert float(rows[0]["ris_delta_total_path_gain_db"]) == pytest.approx(2.0)
    assert float(rows[0]["ris_delta_rx_power_dbm_estimate"]) == pytest.approx(2.0)

    assert summary["metrics"]["ris_off_probe_angles"] == 3
    assert summary["metrics"]["ris_delta_total_path_gain_db"]["mean"] == pytest.approx(2.0)
    assert summary["metrics"]["ris_delta_rx_power_dbm_estimate"]["mean"] == pytest.approx(2.0)

    angle_dirs = sorted((output_dir / "angles").iterdir())
    assert angle_dirs
    assert not (angle_dirs[0] / "data").exists()
    assert not (angle_dirs[0] / "plots").exists()
    assert not (angle_dirs[0] / "viewer").exists()


def test_run_campaign_writes_reference_radio_map_manifest_when_angle_outputs_preserved(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "campaign_reference_plots.yaml"
    _write_campaign_config(
        config_path,
        base_dir=tmp_path / "outputs",
        run_id="campaign_reference",
        max_angles_per_job=5,
    )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"]["compact_output"] = False
    config["campaign"]["prune_angle_outputs"] = False
    config["campaign"]["start_angle_deg"] = -1.0
    config["campaign"]["stop_angle_deg"] = 1.0
    config["campaign"]["step_deg"] = 1.0
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        (output_dir / "plots").mkdir(exist_ok=True)
        rx_pos = cfg["scene"]["rx"]["position"]
        angle_value = round(rx_pos[1], 4)
        summary = {
            "metrics": {
                "total_path_gain_db": angle_value,
                "rx_power_dbm_estimate": angle_value + 10.0,
                "num_valid_paths": 5,
            }
        }
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        for name in (
            "radio_map_path_gain_db_z1p50m.png",
            "radio_map_rx_power_dbm_z1p50m.png",
            "radio_map_tx_ris_incidence_path_gain_db.png",
            "radio_map_tx_ris_incidence_rx_power_dbm.png",
        ):
            (output_dir / "plots" / name).write_bytes(b"png")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    manifest = json.loads((output_dir / "data" / "campaign_plots.json").read_text(encoding="utf-8"))
    plot_files = {item["file"] for item in manifest["plots"]}
    assert "campaign_reference_radio_map_path_gain_db.png" in plot_files
    assert "campaign_reference_tx_ris_incidence_path_gain_db.png" in plot_files
    assert (output_dir / "plots" / "campaign_reference_radio_map_path_gain_db.png").exists()
    assert (output_dir / "plots" / "campaign_reference_tx_ris_incidence_rx_power_dbm.png").exists()


def test_run_campaign_copies_per_angle_radio_map_before_pruning(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_angle_zmaps.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_angle_zmaps", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"]["start_angle_deg"] = 0.0
    config["campaign"]["stop_angle_deg"] = 0.0
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        (output_dir / "plots").mkdir(exist_ok=True)
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (output_dir / "plots" / "radio_map_path_gain_db_z1p50m.png").write_bytes(b"png")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    assert (output_dir / "plots" / "angle_radio_maps" / "angle_p000deg_radio_map_path_gain_db.png").exists()
    angle_manifest = json.loads((output_dir / "data" / "campaign_angle_radio_maps.json").read_text(encoding="utf-8"))
    assert angle_manifest["plots"][0]["file"] == "angle_radio_maps/angle_p000deg_radio_map_path_gain_db.png"
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["metrics"]["angle_radio_map_plots"] == 1


def test_run_campaign_resume_completes_remaining_angles(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_resume.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_b", max_angles_per_job=2)

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        rx_pos = cfg["scene"]["rx"]["position"]
        metric = float(rx_pos[0] + rx_pos[1])
        summary = {"metrics": {"total_path_gain_db": metric, "rx_power_dbm_estimate": metric + 5.0, "num_valid_paths": 3}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))
    output_dir = run_campaign(str(config_path))
    run_campaign(str(config_path))

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["campaign_complete"] is True
    assert summary["metrics"]["completed_angles"] == 5

    state = json.loads((output_dir / "campaign_state.json").read_text(encoding="utf-8"))
    assert len(state["measurements"]) == 5


def test_run_campaign_rejects_resume_when_angle_grid_changes(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_changed_grid.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_grid", max_angles_per_job=10)

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        rx_pos = cfg["scene"]["rx"]["position"]
        metric = float(rx_pos[0] + rx_pos[1])
        summary = {"metrics": {"total_path_gain_db": metric, "rx_power_dbm_estimate": metric + 5.0, "num_valid_paths": 3}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"]["step_deg"] = 2.0
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Existing campaign state is incompatible"):
        run_campaign(str(config_path))


def test_run_campaign_aligns_arc_with_ris_orientation(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_oriented.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_c", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"]["start_angle_deg"] = 0.0
    config["campaign"]["stop_angle_deg"] = 0.0
    config["campaign"]["radius_m"] = 1.0
    config["campaign"]["pivot"] = [0.0, 0.0, 1.5]
    config["ris"] = {"objects": [{"position": [0.0, 0.0, 1.5], "orientation": [3.141592653589793 / 2.0, 0.0, 0.0]}]}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_positions = []

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        rx_pos = cfg["scene"]["rx"]["position"]
        seen_positions.append(rx_pos)
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    assert len(seen_positions) == 1
    assert seen_positions[0][0] == pytest.approx(0.0, abs=1e-6)
    assert seen_positions[0][1] == pytest.approx(1.0, abs=1e-6)


def test_run_campaign_applies_arc_height_offset(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_arc_height.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_arc_z", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"]["start_angle_deg"] = 0.0
    config["campaign"]["stop_angle_deg"] = 0.0
    config["campaign"]["radius_m"] = 1.0
    config["campaign"]["pivot"] = [0.0, 0.0, 1.5]
    config["campaign"]["arc_height_offset_m"] = -0.35
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_positions = []

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        seen_positions.append(cfg["scene"]["rx"]["position"])
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    assert len(seen_positions) == 1
    assert seen_positions[0][0] == pytest.approx(1.0, abs=1e-6)
    assert seen_positions[0][1] == pytest.approx(0.0, abs=1e-6)
    assert seen_positions[0][2] == pytest.approx(1.15, abs=1e-6)


def test_run_campaign_updates_auto_aim_ris_targets_for_each_angle(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_autoaim.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_d", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"]["start_angle_deg"] = 0.0
    config["campaign"]["stop_angle_deg"] = 0.0
    config["campaign"]["radius_m"] = 1.0
    config["campaign"]["pivot"] = [0.0, 0.0, 1.5]
    config["campaign"]["reference_yaw_deg"] = 90.0
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 0.0, 1.5],
                "orientation": [0.0, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "sources": [9.0, 9.0, 9.0],
                    "targets": [8.0, 8.0, 8.0],
                },
            }
        ],
    }
    config["scene"]["tx"]["power_dbm"] = 28.0
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_targets = []
    seen_sources = []
    seen_rx = []

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        rx_pos = cfg["scene"]["rx"]["position"]
        profile = cfg["ris"]["objects"][0]["profile"]
        seen_rx.append(rx_pos)
        seen_sources.append(profile["sources"])
        seen_targets.append(profile["targets"])
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    assert len(seen_rx) == 1
    assert seen_rx[0][0] == pytest.approx(0.0, abs=1e-6)
    assert seen_rx[0][1] == pytest.approx(1.0, abs=1e-6)
    assert seen_targets[0] == pytest.approx(seen_rx[0], abs=1e-6)
    assert seen_sources[0] == pytest.approx([0.0, -0.98, 1.5], abs=1e-6)


def test_run_campaign_points_rx_to_pivot_for_each_angle(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_rx_lookat.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_e", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"]["start_angle_deg"] = 0.0
    config["campaign"]["stop_angle_deg"] = 0.0
    config["campaign"]["pivot"] = [0.0, 0.0, 1.5]
    config["campaign"]["radius_m"] = 1.0
    config["campaign"]["reference_yaw_deg"] = 0.0
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_rx_look_at = []

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        seen_rx_look_at.append(cfg["scene"]["rx"].get("look_at"))
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    assert len(seen_rx_look_at) == 1
    assert seen_rx_look_at[0] == pytest.approx([0.0, 0.0, 1.5], abs=1e-6)


def test_qub_campaign_points_rx_to_ris_by_default(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_qub_rx_lookat.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_qub_rx", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"] = {
        "mode": "qub_near_field",
        "start_angle_deg": 0.0,
        "stop_angle_deg": 0.0,
        "step_deg": 1.0,
        "max_cases_per_job": 1,
        "target_angles_deg": [45.0],
        "frequency_start_ghz": 28.0,
        "frequency_stop_ghz": 28.0,
        "frequency_step_ghz": 1.0,
        "polarizations": ["V"],
        "tx_ris_distance_m": 0.4,
        "target_distance_m": 1.1,
        "tx_incidence_angle_deg": -30.0,
        "compact_output": True,
        "prune_angle_outputs": True,
    }
    config["radio_map"]["z_stack"] = {"enabled": True, "num_below": 1, "num_above": 1, "spacing_m": 0.05}
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 1.3, 1.5],
                "orientation": [4.712389, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"] = {"position": [-0.2, 0.9536, 1.5], "look_at": [0.0, 1.3, 1.5]}
    config["scene"]["rx"] = {"position": [0.0, 0.2, 1.5]}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_rx_look_at = []
    seen_specular_paths = []

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        seen_rx_look_at.append(cfg["scene"]["rx"].get("look_at"))
        seen_specular_paths.append(cfg["radio_map"].get("specular_paths"))
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    assert len(seen_rx_look_at) == 1
    assert seen_rx_look_at[0] == pytest.approx([0.0, 1.3, 1.5], abs=1e-6)
    assert len(seen_specular_paths) == 1
    assert seen_specular_paths[0][0]["label"] == "Specular path"
    assert len(seen_specular_paths[0][0]["points"]) == 3
    assert seen_specular_paths[0][0]["points"][1] == pytest.approx([0.0, 1.3, 1.5], abs=1e-6)


def test_qub_campaign_copies_per_sample_radio_map_before_pruning(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_qub_zmaps.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_qub_zmaps", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"] = {
        "mode": "qub_near_field",
        "start_angle_deg": 0.0,
        "stop_angle_deg": 0.0,
        "step_deg": 1.0,
        "max_cases_per_job": 1,
        "target_angles_deg": [45.0],
        "frequency_start_ghz": 28.0,
        "frequency_stop_ghz": 28.0,
        "frequency_step_ghz": 1.0,
        "polarizations": ["V"],
        "tx_ris_distance_m": 0.4,
        "target_distance_m": 1.1,
        "tx_incidence_angle_deg": -30.0,
        "compact_output": True,
        "prune_angle_outputs": True,
    }
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 1.3, 1.5],
                "orientation": [4.712389, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"] = {"position": [-0.2, 0.9536, 1.5], "look_at": [0.0, 1.3, 1.5]}
    config["scene"]["rx"] = {"position": [0.0, 0.2, 1.5]}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        (output_dir / "plots").mkdir(exist_ok=True)
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (output_dir / "plots" / "radio_map_path_gain_db_z1p50m.png").write_bytes(b"png")
        (output_dir / "plots" / "radio_map_path_gain_db_z1p45m.png").write_bytes(b"png")
        (output_dir / "plots" / "radio_map_ris_off_path_gain_db_z1p50m.png").write_bytes(b"png")
        (output_dir / "plots" / "radio_map_ris_off_path_gain_db_z1p45m.png").write_bytes(b"png")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    copied = list((output_dir / "plots" / "qub_angle_radio_maps").glob("*/*.png"))
    assert len(copied) == 4
    assert any(path.name.endswith("_radio_map_ris_off_path_gain_db.png") for path in copied)
    assert any(path.name.endswith("_radio_map_path_gain_db_z1p45m.png") for path in copied)
    assert any(path.name.endswith("_radio_map_ris_off_path_gain_db_z1p45m.png") for path in copied)
    angle_manifest = json.loads((output_dir / "data" / "campaign_angle_radio_maps.json").read_text(encoding="utf-8"))
    assert len(angle_manifest["plots"]) == 4
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["metrics"]["angle_radio_map_plots"] == 4


def test_qub_campaign_writes_boost_plot_manifest_entry(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_qub_boost_plot.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_qub_boost_plot", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"] = {
        "mode": "qub_near_field",
        "start_angle_deg": -35.0,
        "stop_angle_deg": -25.0,
        "step_deg": 5.0,
        "max_cases_per_job": 1,
        "target_angles_deg": [0.0],
        "frequency_start_ghz": 28.0,
        "frequency_stop_ghz": 28.0,
        "frequency_step_ghz": 1.0,
        "polarizations": ["V"],
        "tx_ris_distance_m": 0.4,
        "target_distance_m": 1.1,
        "tx_incidence_angle_deg": -30.0,
        "compact_output": True,
        "prune_angle_outputs": True,
        "show_specular_path": True,
    }
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 1.3, 1.5],
                "orientation": [4.712389, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"] = {"position": [-0.2, 0.9536, 1.5], "look_at": [0.0, 1.3, 1.5]}
    config["scene"]["rx"] = {"position": [0.0, 0.2, 1.5]}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        summary = {
            "metrics": {
                "total_path_gain_db": -20.0,
                "rx_power_dbm_estimate": 8.0,
                "ris_link_probe": {
                    "off_total_path_gain_db": -55.0,
                    "off_rx_power_dbm_estimate": -27.0,
                    "delta_total_path_gain_db": 35.0,
                    "delta_rx_power_dbm_estimate": 35.0,
                },
                "num_valid_paths": 1,
            }
        }
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    manifest = json.loads((output_dir / "data" / "campaign_plots.json").read_text(encoding="utf-8"))
    plot_files = [item["file"] for item in manifest["plots"]]
    assert any(name.startswith("qub_boost__target_p000deg__28p0ghz__vpol") for name in plot_files)
    assert any(name.startswith("qub_cut__target_p000deg__28p0ghz__vpol") for name in plot_files)
    assert any(name.startswith("qub_peak_rx_power_vs_target_angle__28p0ghz__vpol") for name in plot_files)
    boost_file = next(name for name in plot_files if name.startswith("qub_boost__target_p000deg__28p0ghz__vpol"))
    cut_file = next(name for name in plot_files if name.startswith("qub_cut__target_p000deg__28p0ghz__vpol"))
    peak_power_file = next(name for name in plot_files if name.startswith("qub_peak_rx_power_vs_target_angle__28p0ghz__vpol"))
    boost_entry = next(item for item in manifest["plots"] if item["file"] == boost_file)
    cut_entry = next(item for item in manifest["plots"] if item["file"] == cut_file)
    peak_power_entry = next(item for item in manifest["plots"] if item["file"] == peak_power_file)
    assert boost_entry["show_specular_path"] is True
    assert boost_entry["specular_measurement_angle_deg"] == pytest.approx(30.0)
    assert boost_entry["specular_turntable_angle_deg"] == pytest.approx(-30.0)
    assert cut_entry["ris_target_measurement_angle_deg"] == pytest.approx(0.0)
    assert peak_power_entry["metric"] == "main_lobe_rx_power_dbm"
    assert peak_power_entry["reference_metric"] == "ris_off_main_lobe_rx_power_dbm"
    assert (output_dir / "plots" / boost_file).exists()
    assert (output_dir / "plots" / peak_power_file).exists()


def test_qub_campaign_honors_explicit_ris_profile_override(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_qub_profile_override.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_qub_profile_override", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"] = {
        "mode": "qub_near_field",
        "start_angle_deg": 0.0,
        "stop_angle_deg": 0.0,
        "step_deg": 1.0,
        "max_cases_per_job": 1,
        "target_angles_deg": [0.0],
        "frequency_start_ghz": 28.0,
        "frequency_stop_ghz": 28.0,
        "frequency_step_ghz": 1.0,
        "polarizations": ["V"],
        "tx_ris_distance_m": 0.4,
        "target_distance_m": 1.1,
        "tx_incidence_angle_deg": -30.0,
        "ris_profile_kind": "focusing_lens",
        "compact_output": True,
        "prune_angle_outputs": True,
    }
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 1.3, 1.5],
                "orientation": [4.712389, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"] = {"position": [-0.2, 0.9536, 1.5], "look_at": [0.0, 1.3, 1.5]}
    config["scene"]["rx"] = {"position": [0.0, 0.2, 1.6]}
    config["radio_map"] = {"enabled": False}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_runs = []

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        seen_runs.append(
            {
                "profile_kind": cfg["ris"]["objects"][0]["profile"]["kind"],
                "simulation_ris_off_amplitude": cfg["simulation"]["ris_off_amplitude"],
                "radio_map_ris_off_amplitude": cfg["radio_map"]["ris_off_amplitude"],
            }
        )
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    assert seen_runs == [
        {
            "profile_kind": "focusing_lens",
            "simulation_ris_off_amplitude": pytest.approx(0.9),
            "radio_map_ris_off_amplitude": pytest.approx(0.9),
        }
    ]


def test_qub_campaign_prefers_delta_series_when_ris_only_metric_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_qub_delta_fallback.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_qub_delta", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"] = {
        "mode": "qub_near_field",
        "start_angle_deg": -5.0,
        "stop_angle_deg": 5.0,
        "step_deg": 5.0,
        "max_cases_per_job": 1,
        "target_angles_deg": [0.0],
        "frequency_start_ghz": 28.0,
        "frequency_stop_ghz": 28.0,
        "frequency_step_ghz": 1.0,
        "polarizations": ["V"],
        "tx_ris_distance_m": 0.4,
        "target_distance_m": 1.1,
        "tx_incidence_angle_deg": -30.0,
        "compact_output": True,
        "prune_angle_outputs": True,
    }
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 1.3, 1.5],
                "orientation": [4.712389, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"] = {"position": [-0.2, 0.9536, 1.5], "look_at": [0.0, 1.3, 1.5]}
    config["scene"]["rx"] = {"position": [0.0, 0.2, 1.6]}
    config["radio_map"] = {"enabled": False}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        run_id = str(cfg["output"]["run_id"])
        if "__sample_000_" in run_id:
            total_path_gain_db = 0.0
            delta_total_path_gain_db = 10.0
        elif "__sample_001_" in run_id:
            total_path_gain_db = -5.0
            delta_total_path_gain_db = 95.0
        else:
            total_path_gain_db = -6.0
            delta_total_path_gain_db = 84.0
        summary = {
            "metrics": {
                "total_path_gain_db": total_path_gain_db,
                "rx_power_dbm_estimate": total_path_gain_db + 10.0,
                "ris_path_gain_db": -120.0,
                "non_ris_path_gain_db": total_path_gain_db,
                "ris_link_probe": {
                    "off_total_path_gain_db": None,
                    "off_rx_power_dbm_estimate": None,
                    "delta_total_path_gain_db": delta_total_path_gain_db,
                    "delta_rx_power_dbm_estimate": delta_total_path_gain_db,
                },
                "num_valid_paths": 3,
                "num_ris_paths": 1,
            }
        }
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    measurements = json.loads((output_dir / "data" / "campaign_measurements.json").read_text(encoding="utf-8"))
    case = measurements["cases"][0]
    assert case["response_metric_key"] == "ris_delta_total_path_gain_db"
    assert case["reference_metric_key"] == ""
    assert case["main_lobe_angle_deg"] == pytest.approx(0.0, abs=1e-4)

    plot_manifest = json.loads((output_dir / "data" / "campaign_plots.json").read_text(encoding="utf-8"))
    cut_entry = next(item for item in plot_manifest["plots"] if item["file"].startswith("qub_cut__target_p000deg"))
    assert cut_entry["metric"] == "ris_delta_total_path_gain_db"


def test_qub_campaign_prefers_ris_off_baseline_series_when_available(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_qub_ris_off_preferred.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_qub_ris_off", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"] = {
        "mode": "qub_near_field",
        "start_angle_deg": -5.0,
        "stop_angle_deg": 5.0,
        "step_deg": 5.0,
        "max_cases_per_job": 1,
        "target_angles_deg": [0.0],
        "frequency_start_ghz": 28.0,
        "frequency_stop_ghz": 28.0,
        "frequency_step_ghz": 1.0,
        "polarizations": ["V"],
        "tx_ris_distance_m": 0.4,
        "target_distance_m": 1.1,
        "tx_incidence_angle_deg": -30.0,
        "compact_output": True,
        "prune_angle_outputs": True,
    }
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 1.3, 1.5],
                "orientation": [4.712389, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"] = {"position": [-0.2, 0.9536, 1.5], "look_at": [0.0, 1.3, 1.5]}
    config["scene"]["rx"] = {"position": [0.0, 0.2, 1.6]}
    config["radio_map"] = {"enabled": False}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        run_id = str(cfg["output"]["run_id"])
        if "__sample_000_" in run_id:
            total_path_gain_db = -30.0
            off_total_path_gain_db = -40.0
        elif "__sample_001_" in run_id:
            total_path_gain_db = -25.0
            off_total_path_gain_db = -44.0
        else:
            total_path_gain_db = -27.0
            off_total_path_gain_db = -43.0
        summary = {
            "metrics": {
                "total_path_gain_db": total_path_gain_db,
                "rx_power_dbm_estimate": total_path_gain_db + 10.0,
                "ris_path_gain_db": total_path_gain_db - 1.0,
                "non_ris_path_gain_db": total_path_gain_db - 8.0,
                "ris_link_probe": {
                    "off_total_path_gain_db": off_total_path_gain_db,
                    "off_rx_power_dbm_estimate": off_total_path_gain_db + 10.0,
                    "delta_total_path_gain_db": total_path_gain_db - off_total_path_gain_db,
                    "delta_rx_power_dbm_estimate": total_path_gain_db - off_total_path_gain_db,
                },
                "num_valid_paths": 3,
                "num_ris_paths": 1,
            }
        }
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    measurements = json.loads((output_dir / "data" / "campaign_measurements.json").read_text(encoding="utf-8"))
    case = measurements["cases"][0]
    assert case["response_metric_key"] == "total_path_gain_db"
    assert case["reference_metric_key"] == "ris_off_total_path_gain_db"
    assert case["main_lobe_rx_power_metric_key"] == "rx_power_dbm_estimate"
    assert case["ris_off_main_lobe_rx_power_metric_key"] == "ris_off_rx_power_dbm_estimate"
    assert case["ris_off_main_lobe_rx_power_dbm"] == pytest.approx(-30.0)

    plot_manifest = json.loads((output_dir / "data" / "campaign_plots.json").read_text(encoding="utf-8"))
    cut_entry = next(item for item in plot_manifest["plots"] if item["file"].startswith("qub_cut__target_p000deg"))
    assert cut_entry["metric"] == "total_path_gain_db"


def test_qub_campaign_measurements_record_fixed_rx_position(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_qub_measurement_position.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_qub_measurement_pos", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"] = {
        "mode": "qub_near_field",
        "start_angle_deg": 0.0,
        "stop_angle_deg": 0.0,
        "step_deg": 1.0,
        "max_cases_per_job": 1,
        "target_angles_deg": [45.0],
        "frequency_start_ghz": 28.0,
        "frequency_stop_ghz": 28.0,
        "frequency_step_ghz": 1.0,
        "polarizations": ["V"],
        "tx_ris_distance_m": 0.4,
        "target_distance_m": 1.1,
        "tx_incidence_angle_deg": -30.0,
        "compact_output": True,
        "prune_angle_outputs": True,
    }
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 1.3, 1.5],
                "orientation": [4.712389, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"] = {"position": [-0.2, 0.9536, 1.5], "look_at": [0.0, 1.3, 1.5]}
    config["scene"]["rx"] = {"position": [0.0, 0.2, 1.6]}
    config["radio_map"] = {"enabled": False}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    measurements = json.loads((output_dir / "data" / "campaign_measurements.json").read_text(encoding="utf-8"))
    cases = measurements["cases"]
    assert len(cases) == 1
    samples = cases[0]["samples"]
    assert len(samples) == 1
    assert samples[0]["position_x_m"] == pytest.approx(0.0)
    assert samples[0]["position_y_m"] == pytest.approx(0.2)
    assert samples[0]["position_z_m"] == pytest.approx(1.6)


def test_run_campaign_compact_output_disables_extra_radio_map_products(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_compact_radio_map.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_compact_maps", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["radio_map"] = {
        "enabled": True,
        "cell_size": [0.05, 0.05],
        "diff_ris": True,
        "z_stack": {"enabled": True, "num_below": 2, "num_above": 2, "spacing_m": 0.05},
        "tx_ris_incidence": {"enabled": True},
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_radio_map = {}

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        seen_radio_map.update(cfg["radio_map"])
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    assert seen_radio_map["diff_ris"] is False
    assert seen_radio_map["z_stack"]["enabled"] is False
    assert seen_radio_map["tx_ris_incidence"]["enabled"] is False


def test_qub_campaign_compact_output_disables_extra_radio_map_products(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_qub_compact_radio_map.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_qub_compact_maps", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["campaign"] = {
        "mode": "qub_near_field",
        "start_angle_deg": 0.0,
        "stop_angle_deg": 0.0,
        "step_deg": 1.0,
        "max_cases_per_job": 1,
        "target_angles_deg": [45.0],
        "frequency_start_ghz": 28.0,
        "frequency_stop_ghz": 28.0,
        "frequency_step_ghz": 1.0,
        "polarizations": ["V"],
        "tx_ris_distance_m": 0.4,
        "target_distance_m": 1.1,
        "tx_incidence_angle_deg": -30.0,
        "compact_output": True,
        "prune_angle_outputs": True,
    }
    config["radio_map"] = {
        "enabled": True,
        "cell_size": [0.05, 0.05],
        "diff_ris": True,
        "z_stack": {"enabled": True, "num_below": 2, "num_above": 2, "spacing_m": 0.05},
        "tx_ris_incidence": {"enabled": True},
    }
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 1.3, 1.5],
                "orientation": [4.712389, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"] = {"position": [-0.2, 0.9536, 1.5], "look_at": [0.0, 1.3, 1.5]}
    config["scene"]["rx"] = {"position": [0.0, 0.2, 1.5]}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_radio_map = {}

    def fake_run_simulation(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        seen_radio_map.update(cfg["radio_map"])
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        summary = {"metrics": {"total_path_gain_db": 0.0, "rx_power_dbm_estimate": 0.0, "num_valid_paths": 1}}
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    run_campaign(str(config_path))

    assert seen_radio_map["diff_ris"] is False
    assert seen_radio_map["z_stack"]["enabled"] is True
    assert seen_radio_map["tx_ris_incidence"]["enabled"] is False


def test_run_absorber_sweep_writes_aggregate_summary(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_absorber_sweep.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_sweep", max_angles_per_job=3)

    seen_conductivities = []
    seen_ris_flags = []

    def fake_run_campaign(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        conductivity = float(cfg["scene"]["custom_radio_materials"]["itu_absorber"]["conductivity"])
        seen_conductivities.append(conductivity)
        seen_ris_flags.append(
            (
                cfg["simulation"]["ris"],
                cfg["radio_map"]["ris"],
                cfg["radio_map"]["diff_ris"],
                cfg["ris"]["enabled"],
            )
        )
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        (output_dir / "data").mkdir(exist_ok=True)
        summary = {
            "campaign_complete": True,
            "metrics": {
                "requested_angles": 3,
                "completed_angles": 3,
            },
        }
        measurements = [
            {
                "measurement_angle_deg": float(angle),
                "status": "completed",
                "total_path_gain_db": -(45.0 + conductivity + idx),
                "rx_power_dbm_estimate": -(20.0 + conductivity + idx),
            }
            for idx, angle in enumerate([-10.0, 0.0, 10.0])
        ]
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (output_dir / "data" / "campaign_measurements.json").write_text(
            json.dumps({"measurements": measurements}),
            encoding="utf-8",
        )
        return output_dir

    monkeypatch.setattr("app.campaign.run_campaign", fake_run_campaign)

    output_dir = run_absorber_sweep(str(config_path), [0.5, 5.0])

    assert seen_conductivities == [0.5, 5.0]
    assert seen_ris_flags == [(False, False, False, False), (False, False, False, False)]

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["kind"] == "campaign_absorber_sweep"
    assert summary["recommended_conductivity_s_per_m"] == pytest.approx(5.0)
    assert len(summary["variants"]) == 2

    rows = list(csv.DictReader((output_dir / "data" / "absorber_sweep_summary.csv").open("r", encoding="utf-8")))
    assert len(rows) == 2
    assert float(rows[0]["conductivity_s_per_m"]) == pytest.approx(0.5)
    assert (output_dir / "plots" / "absorber_sweep_path_gain_by_angle.png").exists()
    assert (output_dir / "plots" / "absorber_sweep_mean_path_gain_vs_conductivity.png").exists()


def test_run_absorber_sweep_uses_metal_plate_ris_baseline_when_ris_is_present(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "campaign_absorber_sweep_with_ris.yaml"
    _write_campaign_config(config_path, base_dir=tmp_path / "outputs", run_id="campaign_sweep_ris", max_angles_per_job=1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["ris"] = {
        "enabled": True,
        "objects": [
            {
                "name": "ris1",
                "enabled": True,
                "position": [0.0, 0.0, 1.5],
                "orientation": [0.0, 0.0, 0.0],
                "profile": {
                    "kind": "phase_gradient_reflector",
                    "auto_aim": True,
                    "amplitude": 0.84,
                },
            }
        ],
    }
    config["scene"]["tx"]["power_dbm"] = 28.0
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    seen_variants = []

    def fake_run_campaign(config_path_str: str) -> Path:
        cfg = yaml.safe_load(Path(config_path_str).read_text(encoding="utf-8"))
        seen_variants.append(
            {
                "simulation_ris": cfg["simulation"]["ris"],
                "radio_map_ris": cfg["radio_map"]["ris"],
                "radio_map_diff_ris": cfg["radio_map"]["diff_ris"],
                "ris_enabled": cfg["ris"]["enabled"],
                "profile_kind": cfg["ris"]["objects"][0]["profile"]["kind"],
                "profile_amplitude": cfg["ris"]["objects"][0]["profile"]["amplitude"],
                "profile_auto_aim": cfg["ris"]["objects"][0]["profile"]["auto_aim"],
                "tx_power_dbm": cfg["scene"]["tx"]["power_dbm"],
            }
        )
        output_dir = create_output_dir(cfg["output"]["base_dir"], run_id=cfg["output"]["run_id"])
        (output_dir / "data").mkdir(exist_ok=True)
        summary = {"campaign_complete": True, "metrics": {"requested_angles": 1, "completed_angles": 1}}
        measurements = [
            {
                "measurement_angle_deg": 0.0,
                "status": "completed",
                "total_path_gain_db": -50.0,
                "rx_power_dbm_estimate": -20.0,
            }
        ]
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (output_dir / "data" / "campaign_measurements.json").write_text(
            json.dumps({"measurements": measurements}),
            encoding="utf-8",
        )
        return output_dir

    monkeypatch.setattr("app.campaign.run_campaign", fake_run_campaign)

    output_dir = run_absorber_sweep(str(config_path), [0.5])

    assert seen_variants == [
        {
            "simulation_ris": True,
            "radio_map_ris": True,
            "radio_map_diff_ris": False,
            "ris_enabled": True,
            "profile_kind": "flat",
            "profile_amplitude": pytest.approx(1.0),
            "profile_auto_aim": False,
            "tx_power_dbm": pytest.approx(28.0),
        }
    ]
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["ris_baseline_mode"] == "metal_plate"
