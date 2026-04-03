import json

from app.sim_jobs import _reconcile_loaded_jobs


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
