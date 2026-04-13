import json
from pathlib import Path

from app.sim_jobs import JobManager, _job_output_exists, _load_run_config, _reconcile_loaded_jobs


def test_reconcile_loaded_jobs_marks_stale_running_job_completed(tmp_path) -> None:
    output_dir = tmp_path / "run_completed"
    output_dir.mkdir()
    (output_dir / "progress.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")

    jobs = {
        "job-a": {
            "job_id": "job-a",
            "run_id": "run_completed",
            "status": "running",
            "output_dir": str(output_dir),
        }
    }

    reconciled = _reconcile_loaded_jobs(jobs)

    assert reconciled["job-a"]["status"] == "completed"
    assert reconciled["job-a"]["return_code"] == 0


def test_reconcile_loaded_jobs_marks_stale_running_job_failed_without_progress(tmp_path) -> None:
    output_dir = tmp_path / "run_stale"
    output_dir.mkdir()

    jobs = {
        "job-b": {
            "job_id": "job-b",
            "run_id": "run_stale",
            "status": "running",
            "output_dir": str(output_dir),
        }
    }

    reconciled = _reconcile_loaded_jobs(jobs)

    assert reconciled["job-b"]["status"] == "failed"
    assert reconciled["job-b"]["return_code"] == 1
    assert reconciled["job-b"]["error"] == "Job was interrupted before completion."


def test_job_output_exists_rejects_stale_completed_job(tmp_path) -> None:
    output_dir = tmp_path / "deleted_run"

    assert _job_output_exists({"output_dir": str(output_dir), "status": "completed"}) is False


def test_job_output_exists_accepts_existing_output_dir(tmp_path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir()

    assert _job_output_exists({"output_dir": str(output_dir), "status": "completed"}) is True


def test_load_run_config_prefers_job_config(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    run_dir = output_root / "run-a"
    run_dir.mkdir(parents=True)
    (run_dir / "job_config.yaml").write_text("runtime:\n  prefer_gpu: false\n", encoding="utf-8")
    (run_dir / "config.yaml").write_text("runtime:\n  prefer_gpu: true\n", encoding="utf-8")

    cfg = _load_run_config(output_root, "run-a")

    assert cfg["runtime"]["prefer_gpu"] is False


def test_create_link_level_job_uses_seed_run_config(tmp_path, monkeypatch) -> None:
    output_root = tmp_path / "outputs"
    seed_dir = output_root / "seed-run"
    seed_dir.mkdir(parents=True)
    (seed_dir / "config.yaml").write_text(
        "runtime:\n  prefer_gpu: true\nscene:\n  tx:\n    position: [0,0,1]\n",
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

    job = manager.create_job({"kind": "link_level", "seed_type": "run", "seed_run_id": "seed-run"})

    assert job["kind"] == "link_level"
    assert job["seed_run_id"] == "seed-run"
    assert launched["cmd"][:4] == [
        launched["cmd"][0],
        "-m",
        "app",
        "link",
    ]


def test_create_link_level_job_from_config_sets_prepare_seed_run(tmp_path, monkeypatch) -> None:
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True)
    config_path = tmp_path / "scene.yaml"
    config_path.write_text(
        "runtime:\n  prefer_gpu: true\nris:\n  enabled: true\nscene:\n  tx:\n    position: [0,0,1]\n",
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

    job = manager.create_job(
        {
            "kind": "link_level",
            "seed_type": "config",
            "seed_config_path": str(config_path),
        }
    )

    saved_cfg = json.loads(Path(job["output_dir"], "job.json").read_text(encoding="utf-8"))
    assert saved_cfg["kind"] == "link_level"
    job_cfg_path = Path(job["config_path"])
    assert "prepare_seed_run: true" in job_cfg_path.read_text(encoding="utf-8")
