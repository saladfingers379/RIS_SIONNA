from app.viewer import _radio_map_plot_label, _radio_map_plot_priority


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
