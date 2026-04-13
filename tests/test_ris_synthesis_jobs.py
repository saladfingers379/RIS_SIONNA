from __future__ import annotations

import json
from pathlib import Path

from app.sim_jobs import JobManager


def test_create_ris_synthesis_job_from_config(monkeypatch, tmp_path) -> None:
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True)
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

    launched = {}

    class _DummyProcess:
        def poll(self):
            return None

    def _fake_popen(cmd, stdout=None, stderr=None):
        launched["cmd"] = cmd
        return _DummyProcess()

    monkeypatch.setattr("app.sim_jobs.subprocess.Popen", _fake_popen)
    manager = JobManager(output_root)

    job = manager.create_job({"kind": "ris_synthesis", "config_path": str(config_path)})

    saved_job = json.loads(Path(job["output_dir"], "job.json").read_text(encoding="utf-8"))
    assert saved_job["kind"] == "ris_synthesis"
    assert launched["cmd"][:5] == [launched["cmd"][0], "-m", "app", "ris-synth", "run"]
    assert Path(job["config_path"]).exists()


def test_create_ris_synthesis_quantization_job(monkeypatch, tmp_path) -> None:
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True)

    launched = {}

    class _DummyProcess:
        def poll(self):
            return None

    def _fake_popen(cmd, stdout=None, stderr=None):
        launched["cmd"] = cmd
        return _DummyProcess()

    monkeypatch.setattr("app.sim_jobs.subprocess.Popen", _fake_popen)
    manager = JobManager(output_root)

    job = manager.create_job(
        {
            "kind": "ris_synthesis",
            "action": "quantize",
            "source_run_id": "20260412_203929_938869",
            "bits": 3,
            "num_offset_samples": 64,
        }
    )

    saved_job = json.loads(Path(job["output_dir"], "job.json").read_text(encoding="utf-8"))
    assert saved_job["kind"] == "ris_synthesis"
    assert saved_job["action"] == "quantize"
    assert saved_job["bits"] == 3
    assert launched["cmd"][:5] == [launched["cmd"][0], "-m", "app", "ris-synth", "quantize"]
    assert Path(job["config_path"]).exists()
