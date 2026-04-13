from pathlib import Path

from app.viewer import _radio_map_plot_label, _radio_map_plot_priority, _scene_ris_interaction_names, _write_run_thumbnail


def test_radio_map_plot_priority_prefers_primary_tx_inclusive_maps() -> None:
    ordered = sorted(
        [
            "radio_map_diff_path_gain_db.png",
            "radio_map_path_loss_db.png",
            "radio_map_rx_power_dbm.png",
            "radio_map_path_gain_db.png",
            "radio_map_no_ris_path_gain_db.png",
        ],
        key=_radio_map_plot_priority,
    )

    assert ordered == [
        "radio_map_rx_power_dbm.png",
        "radio_map_path_gain_db.png",
        "radio_map_path_loss_db.png",
        "radio_map_no_ris_path_gain_db.png",
        "radio_map_diff_path_gain_db.png",
    ]


def test_radio_map_plot_label_names_ris_delta_explicitly() -> None:
    assert _radio_map_plot_label("radio_map_diff_path_gain_db.png") == "RIS delta path gain [dB]"


def test_radio_map_plot_label_names_ris_off_metal_baseline_explicitly() -> None:
    assert (
        _radio_map_plot_label("radio_map_ris_off_path_gain_db.png")
        == "Radio map RIS-off metal baseline path gain [dB]"
    )


def test_radio_map_plot_label_names_z_slice_explicitly() -> None:
    assert (
        _radio_map_plot_label("radio_map_path_gain_db_z1p55m.png")
        == "Radio map path gain [dB] @ z=1.55 m"
    )


def test_radio_map_plot_priority_groups_z_slices_by_metric() -> None:
    ordered = sorted(
        [
            "radio_map_path_loss_db_zm0p05m.png",
            "radio_map_rx_power_dbm_z1p60m.png",
            "radio_map_path_gain_db_z1p55m.png",
            "radio_map_path_loss_db_z1p50m.png",
            "radio_map_rx_power_dbm_z1p50m.png",
            "radio_map_path_gain_db_z1p50m.png",
        ],
        key=_radio_map_plot_priority,
    )

    assert ordered == [
        "radio_map_rx_power_dbm_z1p50m.png",
        "radio_map_rx_power_dbm_z1p60m.png",
        "radio_map_path_gain_db_z1p50m.png",
        "radio_map_path_gain_db_z1p55m.png",
        "radio_map_path_loss_db_z1p50m.png",
        "radio_map_path_loss_db_zm0p05m.png",
    ]


def test_write_run_thumbnail_preserves_existing_thumbnail(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    viewer_dir = output_dir / "viewer"
    viewer_dir.mkdir(parents=True)
    (viewer_dir / "thumbnail.png").write_bytes(b"thumb")

    result = _write_run_thumbnail(output_dir, viewer_dir, scene=None)

    assert result == viewer_dir / "thumbnail.png"
    assert (viewer_dir / "thumbnail.png").read_bytes() == b"thumb"


def test_write_run_thumbnail_returns_none_without_scene_or_existing_thumbnail(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    viewer_dir = output_dir / "viewer"
    viewer_dir.mkdir(parents=True)

    result = _write_run_thumbnail(output_dir, viewer_dir, scene=None)

    assert result is None
    assert not (viewer_dir / "thumbnail.png").exists()


def test_scene_ris_interaction_names_uses_ris_object_ids() -> None:
    class DummyRis:
        def __init__(self, object_id: int) -> None:
            self.object_id = object_id

    class DummyScene:
        ris = {"r0": DummyRis(17), "r1": DummyRis(23)}

    assert _scene_ris_interaction_names(DummyScene()) == {"object_17", "object_23"}
