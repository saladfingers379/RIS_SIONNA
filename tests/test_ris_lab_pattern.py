import unittest

import numpy as np

from app.ris.ris_lab import _compute_sidelobe_metrics, _validate_theta_pattern_lengths


class TestRisLabPattern(unittest.TestCase):
    def test_validate_theta_pattern_lengths_raises(self) -> None:
        theta = np.array([0.0, 1.0, 2.0])
        pattern = np.array([0.0, -3.0])
        with self.assertRaises(ValueError) as ctx:
            _validate_theta_pattern_lengths(theta, pattern, "pattern_db")
        self.assertIn("theta_deg length does not match", str(ctx.exception))

    def test_compute_sidelobe_metrics(self) -> None:
        theta = np.array([-10.0, 0.0, 10.0])
        pattern_db = np.array([-10.0, 0.0, -3.0])
        metrics = _compute_sidelobe_metrics(theta, pattern_db)
        self.assertAlmostEqual(metrics["sidelobe_peak_db"], -3.0)
        self.assertAlmostEqual(metrics["sidelobe_level_db"], 3.0)
        self.assertIn("peak_db - max", metrics["sidelobe_definition"])


if __name__ == "__main__":
    unittest.main()
