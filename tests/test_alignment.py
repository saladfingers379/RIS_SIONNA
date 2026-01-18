import unittest

import numpy as np

from app.plots import compute_radio_map_extent


class TestRadioMapExtent(unittest.TestCase):
    def test_extent_includes_half_cell(self) -> None:
        centers = np.array(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
            ],
            dtype=float,
        )
        extent = compute_radio_map_extent(centers)
        self.assertEqual(extent, (-0.5, 1.5, -0.5, 1.5))

    def test_extent_single_cell(self) -> None:
        centers = np.array([[[2.0, -3.0, 0.0]]], dtype=float)
        extent = compute_radio_map_extent(centers)
        self.assertEqual(extent, (2.0, 2.0, -3.0, -3.0))


if __name__ == "__main__":
    unittest.main()
