import numpy as np
import pytest

from app.radio_map_grid import (
    align_center_to_anchor,
    assess_ris_plane_visibility,
    coverage_plane_normal,
    derive_tx_ris_incidence_slice,
    diagnose_ris_map_sampling_issue,
    radio_map_z_slice_offsets,
)


def _axis_centers(center: float, size: float, cell: float) -> np.ndarray:
    n = max(1, int(round(size / cell)))
    start = center - 0.5 * (n - 1) * cell
    return start + np.arange(n) * cell


def test_align_even_grid_places_anchor_on_cell_center() -> None:
    center, info = align_center_to_anchor(
        center=[0.0, 0.0, 1.5],
        size=[40.0, 40.0],
        cell_size=[4.0, 4.0],
        anchor=[0.0, 0.0, 2.0],
    )
    assert center is not None
    assert info is not None
    assert info["applied"] is True

    xs = _axis_centers(center[0], 40.0, 4.0)
    ys = _axis_centers(center[1], 40.0, 4.0)
    assert np.isclose(np.min(np.abs(xs - 0.0)), 0.0)
    assert np.isclose(np.min(np.abs(ys - 0.0)), 0.0)


def test_align_odd_grid_leaves_already_aligned_center() -> None:
    center, info = align_center_to_anchor(
        center=[0.0, 0.0, 1.5],
        size=[45.0, 45.0],
        cell_size=[5.0, 5.0],
        anchor=[0.0, 0.0, 2.0],
    )
    assert center == [0.0, 0.0, 1.5]
    assert info is not None
    assert info["applied"] is False


def test_align_skips_anchor_outside_map() -> None:
    center, info = align_center_to_anchor(
        center=[30.0, 30.0, 1.5],
        size=[40.0, 40.0],
        cell_size=[4.0, 4.0],
        anchor=[0.0, 0.0, 2.0],
    )
    assert center == [30.0, 30.0, 1.5]
    assert info is not None
    assert info["applied"] is False


def test_align_invalid_inputs_noop() -> None:
    center, info = align_center_to_anchor(
        center=None,
        size=[40.0, 40.0],
        cell_size=[4.0, 4.0],
        anchor=[0.0, 0.0, 2.0],
    )
    assert center is None
    assert info is None


def test_coverage_plane_normal_defaults_to_positive_z() -> None:
    normal = coverage_plane_normal([0.0, 0.0, 0.0])
    assert normal is not None
    assert normal == [0.0, 0.0, 1.0]


def test_assess_ris_plane_visibility_flags_in_plane_beam() -> None:
    info = assess_ris_plane_visibility(
        ris_position=[0.0, 1.6, 0.7],
        rx_position=[1.1, 0.98, 0.7],
        plane_orientation=[0.0, 0.0, 0.0],
    )
    assert info is not None
    assert info["beam_parallel_to_plane"] is True
    assert info["ris_to_rx_angle_from_plane_deg"] == pytest.approx(0.0)


def test_assess_ris_plane_visibility_allows_vertical_beam() -> None:
    info = assess_ris_plane_visibility(
        ris_position=[0.0, 0.0, 0.0],
        rx_position=[0.0, 0.0, 1.0],
        plane_orientation=[0.0, 0.0, 0.0],
    )
    assert info is not None
    assert info["beam_parallel_to_plane"] is False
    assert info["ris_to_rx_angle_from_plane_deg"] == pytest.approx(90.0)


def test_diagnose_ris_map_sampling_issue_flags_parallel_plane_floor_map() -> None:
    visibility = assess_ris_plane_visibility(
        ris_position=[0.0, 0.0, 1.5],
        rx_position=[1.0, 0.5, 1.5],
        plane_orientation=[0.0, 0.0, 0.0],
    )

    issue = diagnose_ris_map_sampling_issue(
        {"path_gain_db_max": -120.0},
        visibility,
        {"delta_total_path_gain_db": 12.0},
    )

    assert issue is not None
    assert issue["kind"] == "beam_parallel_to_plane"
    assert issue["ris_link_probe_delta_db"] == pytest.approx(12.0)


def test_diagnose_ris_map_sampling_issue_flags_flat_map_with_strong_link_delta() -> None:
    issue = diagnose_ris_map_sampling_issue(
        {"path_gain_db_max": -120.0},
        None,
        {"delta_total_path_gain_db": 8.0},
    )

    assert issue is not None
    assert issue["kind"] == "slice_missed_ris_energy"


def test_diagnose_ris_map_sampling_issue_ignores_non_floor_maps() -> None:
    issue = diagnose_ris_map_sampling_issue(
        {"path_gain_db_max": -70.0},
        None,
        {"delta_total_path_gain_db": 8.0},
    )

    assert issue is None


def test_derive_tx_ris_incidence_slice_builds_vertical_plane_through_link() -> None:
    derived = derive_tx_ris_incidence_slice(
        tx_position=[-0.2, 0.9536, 1.5],
        ris_position=[0.0, 1.3, 1.5],
        radio_map_cfg={"size": [2.2, 2.2], "cell_size": [0.05, 0.05]},
    )

    assert derived is not None
    assert derived["center"] == pytest.approx([-0.1, 1.1268, 1.5])
    assert derived["size"][0] == pytest.approx(np.linalg.norm([0.2, 0.3464, 0.0]) + 0.4)
    assert derived["size"][1] == pytest.approx(2.2)
    assert derived["auto_size"] is False
    assert derived["align_grid_to_anchor"] is False
    assert derived["plot_axis_labels"] == ["Tx->RIS distance [m]", "z [m]"]

    normal = np.asarray(coverage_plane_normal(derived["orientation"]), dtype=float)
    link = np.asarray([0.2, 0.3464, 0.0], dtype=float)
    assert abs(float(np.dot(normal, link))) < 1e-6
    assert normal[2] == pytest.approx(0.0, abs=1e-6)


def test_derive_tx_ris_incidence_slice_respects_min_height_padding() -> None:
    derived = derive_tx_ris_incidence_slice(
        tx_position=[0.0, 0.0, 1.0],
        ris_position=[1.0, 0.0, 1.0],
        radio_map_cfg={"size": [0.8, 0.8], "cell_size": [0.05, 0.05]},
        slice_cfg={"vertical_padding_m": 0.1, "min_height_m": 1.4},
    )

    assert derived is not None
    assert derived["size"][1] == pytest.approx(1.4)


def test_derive_slices_accept_numpy_positions() -> None:
    tx = np.array([-0.2, 0.9536, 1.5], dtype=float)
    ris = np.array([0.0, 1.3, 1.5], dtype=float)

    incidence = derive_tx_ris_incidence_slice(tx, ris, radio_map_cfg={"cell_size": [0.01, 0.01], "size": [2.93, 3.66]})

    assert incidence is not None


def test_radio_map_z_slice_offsets_build_symmetric_stack() -> None:
    offsets = radio_map_z_slice_offsets(
        {
            "z_stack": {
                "enabled": True,
                "num_below": 3,
                "num_above": 3,
                "spacing_m": 0.05,
            }
        }
    )

    assert offsets == pytest.approx([-0.15, -0.10, -0.05, 0.05, 0.10, 0.15])


def test_radio_map_z_slice_offsets_accepts_explicit_offsets_and_skips_zero() -> None:
    offsets = radio_map_z_slice_offsets(
        {
            "z_stack": {
                "enabled": True,
                "offsets_m": [0.10, -0.05, 0.0, 0.10, -0.15],
            }
        }
    )

    assert offsets == pytest.approx([-0.15, -0.05, 0.10])
