import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.ris.ris_lab import _load_reference_npz


class TestRisLabReference(unittest.TestCase):
    def test_load_reference_npz_pattern_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "ref.npz"
            np.savez(path, theta_deg=np.array([0.0, 5.0]), pattern_db=np.array([0.0, -3.0]))
            theta, pattern, kind = _load_reference_npz(path)

        np.testing.assert_allclose(theta, np.array([0.0, 5.0]))
        np.testing.assert_allclose(pattern, np.array([0.0, -3.0]))
        self.assertEqual(kind, "pattern_db")

    def test_load_reference_npz_missing_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "ref.npz"
            np.savez(path, pattern_db=np.array([0.0, -3.0]))
            with self.assertRaisesRegex(ValueError, r"Expected keys: theta_deg \+ \(pattern_db or pattern_linear\)"):
                _load_reference_npz(path)
