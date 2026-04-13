from __future__ import annotations

from pathlib import Path

import pytest

from app.ris.rt_synthesis_config import (
    compute_ris_synthesis_config_hash,
    resolve_and_snapshot_ris_synthesis_config,
    resolve_ris_synthesis_quantization_config,
    resolve_ris_synthesis_config,
)


def test_resolve_ris_synthesis_config_applies_defaults() -> None:
    cfg = resolve_ris_synthesis_config(
        {
            "seed": {"config_path": "configs/ris_doc_street_canyon.yaml"},
            "target_region": {
                "boxes": [{"u_min_m": 0.0, "u_max_m": 1.0, "v_min_m": -1.0, "v_max_m": 1.0}]
            },
        }
    )

    assert cfg["schema_version"] == 1
    assert cfg["seed"]["ris_name"] == "ris"
    assert cfg["objective"]["kind"] == "mean_log_path_gain"
    assert cfg["parameterization"]["kind"] == "steering_search"
    assert cfg["parameterization"]["basis"] == "quadratic"
    assert cfg["search"]["coarse_num_azimuth"] == 9
    assert cfg["search"]["refine_top_k"] == 5
    assert cfg["optimizer"]["algorithm"] == "adam"
    assert cfg["binarization"]["num_offset_samples"] == 181


def test_resolve_ris_synthesis_config_requires_boxes() -> None:
    with pytest.raises(ValueError, match="target_region.boxes"):
        resolve_ris_synthesis_config(
            {
                "seed": {"config_path": "configs/ris_doc_street_canyon.yaml"},
                "target_region": {"boxes": []},
            }
        )


def test_resolve_and_snapshot_ris_synthesis_config_writes_files(tmp_path: Path) -> None:
    config_path = tmp_path / "ris_synth.yaml"
    config_path.write_text(
        "\n".join(
            [
                "seed:",
                "  config_path: configs/ris_doc_street_canyon.yaml",
                "target_region:",
                "  boxes:",
                "    - u_min_m: 0.0",
                "      u_max_m: 1.0",
                "      v_min_m: 0.0",
                "      v_max_m: 1.0",
            ]
        ),
        encoding="utf-8",
    )

    cfg, output_dir, summary = resolve_and_snapshot_ris_synthesis_config(config_path, output_dir=tmp_path / "out")

    assert cfg["seed"]["config_path"] == "configs/ris_doc_street_canyon.yaml"
    assert (output_dir / "config.yaml").exists()
    assert summary["config"]["hash_sha256"] == compute_ris_synthesis_config_hash(cfg)


def test_resolve_ris_synthesis_config_falls_back_to_effective_run_config(tmp_path: Path) -> None:
    run_dir = tmp_path / "outputs" / "run123"
    run_dir.mkdir(parents=True)
    effective_config = run_dir / "config.yaml"
    effective_config.write_text(
        "\n".join(
            [
                "scene:",
                "  type: builtin",
                "  builtin: etoile",
            ]
        ),
        encoding="utf-8",
    )

    cfg = resolve_ris_synthesis_config(
        {
            "seed": {"config_path": str(run_dir / "job_config.yaml")},
            "target_region": {
                "boxes": [{"u_min_m": 0.0, "u_max_m": 1.0, "v_min_m": -1.0, "v_max_m": 1.0}]
            },
        }
    )

    assert cfg["seed"]["config_path"] == str(effective_config)


def test_resolve_ris_synthesis_quantization_config_applies_defaults() -> None:
    cfg = resolve_ris_synthesis_quantization_config(
        {
            "source": {"run_id": "20260412_203929_938869"},
        }
    )

    assert cfg["source"]["run_id"] == "20260412_203929_938869"
    assert cfg["quantization"]["bits"] == 2
    assert cfg["quantization"]["method"] == "global_offset_sweep"
    assert cfg["quantization"]["num_offset_samples"] == 181
