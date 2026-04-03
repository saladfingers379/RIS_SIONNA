from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from app.campaign import run_campaign, run_absorber_sweep
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
    assert seen_rx_look_at[0] == pytest.approx([0.0, 1.3, 1.5], abs=1e-6)


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
        return output_dir

    monkeypatch.setattr("app.campaign.run_simulation", fake_run_simulation)

    output_dir = run_campaign(str(config_path))

    copied = list((output_dir / "plots" / "qub_angle_radio_maps").glob("*/*.png"))
    assert len(copied) == 1
    angle_manifest = json.loads((output_dir / "data" / "campaign_angle_radio_maps.json").read_text(encoding="utf-8"))
    assert len(angle_manifest["plots"]) == 1
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["metrics"]["angle_radio_map_plots"] == 1


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
    assert seen_radio_map["z_stack"]["enabled"] is False
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
