import unittest

from app.sim_tuning import apply_similarity_and_sampling


class TestSimTuning(unittest.TestCase):
    def test_similarity_scaling_updates_frequency_and_geometry(self) -> None:
        cfg = {
            "simulation": {
                "frequency_hz": 28.0e9,
                "scale_similarity": {"enabled": True, "factor": 10.0},
            },
            "scene": {
                "tx": {"position": [1.0, 2.0, 3.0], "look_at": [4.0, 5.0, 6.0]},
                "rx": {"position": [7.0, 8.0, 9.0]},
                "camera": {"position": [0.5, 1.0, 1.5]},
                "procedural": {
                    "ground": {"size": [10.0, 20.0], "elevation": 2.0},
                    "boxes": [{"center": [1.0, 1.0, 1.0], "size": [2.0, 2.0, 2.0]}],
                },
            },
            "radio_map": {
                "center": [0.0, 0.0, 1.0],
                "size": [10.0, 10.0],
                "cell_size": [1.0, 1.0],
                "auto_padding": 2.0,
            },
            "ris": {"enabled": True, "sionna": {"position": [1.0, 0.0, 0.0]}},
        }
        tuned, summary = apply_similarity_and_sampling(cfg)
        self.assertAlmostEqual(tuned["simulation"]["frequency_hz"], 2.8e9)
        self.assertEqual(tuned["scene"]["tx"]["position"], [10.0, 20.0, 30.0])
        self.assertEqual(tuned["scene"]["tx"]["look_at"], [40.0, 50.0, 60.0])
        self.assertEqual(tuned["scene"]["rx"]["position"], [70.0, 80.0, 90.0])
        self.assertEqual(tuned["scene"]["camera"]["position"], [5.0, 10.0, 15.0])
        self.assertEqual(tuned["radio_map"]["cell_size"], [10.0, 10.0])
        self.assertTrue(summary["scale_similarity"]["effective_enabled"])

    def test_sampling_boost_applies_multipliers(self) -> None:
        cfg = {
            "simulation": {
                "samples_per_src": 1000,
                "max_num_paths_per_src": 2000,
                "max_depth": 2,
                "sampling_boost": {
                    "enabled": True,
                    "map_resolution_multiplier": 2,
                    "ray_samples_multiplier": 3,
                    "max_depth_add": 1,
                },
            },
            "radio_map": {
                "cell_size": [4.0, 4.0],
                "samples_per_tx": 500,
                "max_depth": 1,
            },
        }
        tuned, summary = apply_similarity_and_sampling(cfg)
        self.assertEqual(tuned["radio_map"]["cell_size"], [2.0, 2.0])
        self.assertEqual(tuned["simulation"]["samples_per_src"], 3000)
        self.assertEqual(tuned["simulation"]["max_num_paths_per_src"], 6000)
        self.assertEqual(tuned["simulation"]["max_depth"], 3)
        self.assertEqual(tuned["radio_map"]["samples_per_tx"], 1500)
        self.assertEqual(tuned["radio_map"]["max_depth"], 2)
        self.assertTrue(summary["sampling_boost"]["effective_enabled"])

    def test_defaults_preserve_behavior(self) -> None:
        cfg = {"simulation": {"frequency_hz": 28.0e9}}
        tuned, summary = apply_similarity_and_sampling(cfg)
        self.assertEqual(tuned["simulation"]["frequency_hz"], 28.0e9)
        self.assertFalse(summary["scale_similarity"]["effective_enabled"])
        self.assertFalse(summary["sampling_boost"]["effective_enabled"])


if __name__ == "__main__":
    unittest.main()
