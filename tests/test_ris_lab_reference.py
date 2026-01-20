import tempfile
import unittest
from unittest import mock
from pathlib import Path

import numpy as np

from app.ris.ris_lab import _load_reference_mat, _load_reference_npz

try:
    import scipy  # noqa: F401
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False


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

    def test_load_reference_mat_missing_scipy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "ref.mat"
            path.write_bytes(b"")
            original_import = __import__

            def _blocked_import(name, *args, **kwargs):
                if name.startswith("scipy"):
                    raise ImportError("No module named scipy")
                return original_import(name, *args, **kwargs)

            with mock.patch("builtins.__import__", side_effect=_blocked_import):
                with self.assertRaisesRegex(RuntimeError, r"scipy is required for MAT reference imports"):
                    _load_reference_mat(path)

    @unittest.skipUnless(SCIPY_AVAILABLE, "scipy not installed")
    def test_load_reference_mat_pattern_db(self) -> None:
        from scipy.io import savemat

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "ref.mat"
            savemat(path, {"theta_deg": np.array([0.0, 5.0]), "pattern_db": np.array([0.0, -3.0])})
            theta, pattern, kind = _load_reference_mat(path)

        np.testing.assert_allclose(theta, np.array([0.0, 5.0]))
        np.testing.assert_allclose(pattern, np.array([0.0, -3.0]))
        self.assertEqual(kind, "pattern_db")
