import numpy as np
import pytest

from app.plots import _radio_map_plane_projection, _radio_map_title, plot_radio_map


def test_radio_map_plane_projection_handles_vertical_slice() -> None:
    centers = np.array(
        [
            [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0]],
            [[0.0, 0.0, 2.0], [1.0, 0.0, 2.0]],
        ],
        dtype=float,
    )

    u_coords, v_coords, origin, u_unit, v_unit = _radio_map_plane_projection(centers)

    assert origin.tolist() == pytest.approx([0.0, 0.0, 1.0])
    assert np.allclose(u_coords, np.array([[0.0, 1.0], [0.0, 1.0]], dtype=float))
    assert np.allclose(v_coords, np.array([[0.0, 0.0], [1.0, 1.0]], dtype=float))
    assert u_unit.tolist() == pytest.approx([1.0, 0.0, 0.0])
    assert v_unit.tolist() == pytest.approx([0.0, 0.0, 1.0])


def test_radio_map_title_appends_plane_height() -> None:
    assert _radio_map_title("Path gain [dB]", title_suffix="z=1.55 m") == "Radio Map (Path gain [dB])\nz=1.55 m"


def test_plot_radio_map_accepts_specular_guide_path(tmp_path) -> None:
    centers = np.array(
        [
            [[0.0, 0.0, 1.5], [1.0, 0.0, 1.5]],
            [[0.0, 1.0, 1.5], [1.0, 1.0, 1.5]],
        ],
        dtype=float,
    )
    metric = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=float)

    png_path, svg_path = plot_radio_map(
        metric,
        centers,
        tmp_path,
        metric_label="Path gain [dB]",
        filename_prefix="radio_map_path_gain_db",
        guide_paths=[
            {
                "label": "Specular path",
                "points": [[0.0, 0.0, 1.5], [0.5, 0.5, 1.5], [1.0, 1.0, 1.5]],
            }
        ],
    )

    assert png_path.exists()
    assert svg_path.exists()
