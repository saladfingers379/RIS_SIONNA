from pathlib import Path


def test_campaign2_run_all_uses_chunk_label_and_refreshes_before_submit() -> None:
    html = Path("app/sim_web/index.html").read_text(encoding="utf-8")
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert '<button id="campaign2RunAll" type="button">Run All Chunks</button>' in html
    assert 'ui.campaign2RunAll.textContent = locked ? "Running All Chunks..." : "Run All Chunks";' in js
    assert "await refreshCampaign2Jobs();" in js
    assert "Submitting chunk ${chunkIndex}" in js


def test_campaign2_run_all_handles_resume_and_live_running_jobs() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "function resolveCampaign2ResumeRunId()" in js
    assert "function syncCampaign2ResumeSelection(runId)" in js
    assert "async function getLiveCampaign2RunningJob(preferredRunId = \"\")" in js
    assert "Waiting for running chunk ${chunkIndex} in ${activeRunId}..." in js
    assert "syncCampaign2ResumeSelection(data.run_id);" in js
