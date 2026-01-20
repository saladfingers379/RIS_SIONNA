import csv
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from app.ris.ris_lab import validate_ris_lab


class TestRisLabValidationFixture(unittest.TestCase):
    def _write_config(self, base_dir: Path, run_id: str, thresholds: dict) -> Path:
        config = {
            "geometry": {"nx": 2, "ny": 2, "dx": 0.5, "dy": 0.5},
            "validation": thresholds,
            "output": {"base_dir": str(base_dir), "run_id": run_id},
        }
        config_path = base_dir / f"{run_id}.yaml"
        with config_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(config, handle, sort_keys=False)
        return config_path

    def _fixture_path(self) -> Path:
        return Path(__file__).resolve().parent / "fixtures" / "ris_validation_fixture.csv"

    def _load_fixture_rows(self) -> list[list[str]]:
        with self._fixture_path().open("r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
        return rows

    def test_validation_fixture_passes(self) -> None:
        thresholds = {
            "normalization": "peak_0db",
            "rmse_db_max": 0.05,
            "peak_angle_err_deg_max": 0.1,
            "peak_db_err_max": 0.1,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            config_path = self._write_config(base_dir, "fixture-pass", thresholds)
            output_dir = validate_ris_lab(str(config_path), str(self._fixture_path()))
            metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))

        self.assertTrue(metrics["passed"])
        self.assertLess(metrics["rmse_db"], 1e-6)
        self.assertLess(metrics["peak_angle_error_deg"], 1e-6)
        self.assertLess(metrics["peak_db_error"], 1e-6)
        self.assertEqual(metrics["thresholds"]["rmse_db_max"], thresholds["rmse_db_max"])

    def test_validation_fixture_fails_with_perturbed_data(self) -> None:
        thresholds = {
            "normalization": "peak_0db",
            "rmse_db_max": 0.05,
            "peak_angle_err_deg_max": 0.1,
            "peak_db_err_max": 0.1,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            config_path = self._write_config(base_dir, "fixture-fail", thresholds)
            perturbed_path = base_dir / "fixture_perturbed.csv"
            rows = self._load_fixture_rows()
            header, data_rows = rows[0], rows[1:]
            data_rows[-1][1] = "1.000000"
            with perturbed_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerows(data_rows)

            output_dir = validate_ris_lab(str(config_path), str(perturbed_path))
            metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))

        self.assertFalse(metrics["passed"])
        self.assertGreater(metrics["peak_angle_error_deg"], 1.0)


if __name__ == "__main__":
    unittest.main()
