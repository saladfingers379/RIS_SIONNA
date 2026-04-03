import numpy as np
import pytest

from app.plots import _radio_map_plane_projection, _radio_map_title


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
