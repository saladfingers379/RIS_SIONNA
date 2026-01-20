import unittest

import numpy as np

from app.ris.ris_core import (
    compute_element_centers,
    compute_local_frame,
    quantize_phase,
)


class TestRisGeometry(unittest.TestCase):
    def test_element_centers_2x2(self) -> None:
        geom = compute_element_centers(nx=2, ny=2, dx=1.0, dy=1.0)
        expected = np.array(
            [
                [[-0.5, -0.5, 0.0], [0.5, -0.5, 0.0]],
                [[-0.5, 0.5, 0.0], [0.5, 0.5, 0.0]],
            ],
            dtype=float,
        )
        self.assertTrue(np.allclose(geom.centers, expected))

    def test_local_frame_default(self) -> None:
        frame = compute_local_frame()
        self.assertTrue(np.allclose(frame.u, np.array([1.0, 0.0, 0.0])))
        self.assertTrue(np.allclose(frame.v, np.array([0.0, 1.0, 0.0])))
        self.assertTrue(np.allclose(frame.w, np.array([0.0, 0.0, 1.0])))

    def test_local_frame_handles_colinear_hint(self) -> None:
        frame = compute_local_frame(normal=[1.0, 0.0, 0.0], x_axis_hint=[1.0, 0.0, 0.0])
        self.assertAlmostEqual(np.dot(frame.u, frame.w), 0.0, places=6)
        self.assertAlmostEqual(np.dot(frame.v, frame.w), 0.0, places=6)
        self.assertAlmostEqual(np.linalg.norm(frame.u), 1.0, places=6)
        self.assertAlmostEqual(np.linalg.norm(frame.v), 1.0, places=6)
        self.assertAlmostEqual(np.linalg.norm(frame.w), 1.0, places=6)


class TestRisQuantization(unittest.TestCase):
    def test_quantize_invalid_bits(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            quantize_phase(np.array([0.1]), bits=3)
        self.assertIn("quantization_bits", str(ctx.exception))

    def test_quantize_1bit(self) -> None:
        phases = np.array([0.1, 3.0])
        quantized = quantize_phase(phases, bits=1)
        self.assertTrue(np.allclose(quantized, np.array([0.0, np.pi])))

    def test_quantize_2bit(self) -> None:
        phases = np.array([0.1, 1.8, 3.2, 5.0])
        quantized = quantize_phase(phases, bits=2)
        expected = np.array([0.0, np.pi / 2, np.pi, 3 * np.pi / 2])
        self.assertTrue(np.allclose(quantized, expected))


if __name__ == "__main__":
    unittest.main()
