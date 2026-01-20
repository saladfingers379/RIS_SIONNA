import json
import tempfile
import unittest
from pathlib import Path

import yaml

from app.ris.ris_config import (
    compute_ris_lab_config_hash,
    resolve_and_snapshot_ris_lab_config,
    resolve_ris_lab_config,
)


class TestRisLabConfig(unittest.TestCase):
    def test_minimal_config_resolves_defaults(self) -> None:
        resolved = resolve_ris_lab_config(
            {"geometry": {"nx": 4, "ny": 2, "dx": 0.5, "dy": 0.25}}
        )
        self.assertEqual(resolved["control"]["mode"], "uniform")
        self.assertEqual(resolved["quantization"]["bits"], 0)
        self.assertEqual(resolved["validation"]["rmse_db_max"], 2.0)
        self.assertEqual(resolved["output"]["base_dir"], "outputs")

    def test_missing_geometry_fields_reports_required(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_ris_lab_config({"geometry": {"nx": 4}})
        message = str(ctx.exception)
        self.assertIn("geometry.ny", message)
        self.assertIn("geometry.dx", message)
        self.assertIn("geometry.dy", message)

    def test_snapshot_writes_config_files_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "ris.yaml"
            yaml.safe_dump(
                {
                    "geometry": {"nx": 2, "ny": 2, "dx": 0.1, "dy": 0.2},
                    "output": {"base_dir": tmpdir, "run_id": "unit-test"},
                },
                config_path.open("w", encoding="utf-8"),
                sort_keys=False,
            )

            config, output_dir, summary = resolve_and_snapshot_ris_lab_config(config_path)
            self.assertEqual(output_dir, tmp_path / "unit-test")
            self.assertTrue((output_dir / "config.yaml").exists())
            self.assertTrue((output_dir / "config.json").exists())
            self.assertTrue((output_dir / "summary.json").exists())
            self.assertEqual(summary["config"]["hash_sha256"], compute_ris_lab_config_hash(config))

            loaded = json.loads((output_dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["geometry"]["nx"], 2)


if __name__ == "__main__":
    unittest.main()
