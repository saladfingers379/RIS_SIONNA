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


def test_campaign2_rx_position_is_synced_from_fixed_campaign2_geometry() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "function getCampaign2FixedRxPosition(config = getIndoorChamberConfig())" in js
    assert "function syncCampaign2FixedRxPosition(config = getIndoorChamberConfig(), options = {})" in js
    assert "syncCampaign2FixedRxPosition(getIndoorChamberConfig(), { force: true, rebuild: false });" in js
    assert "syncCampaign2FixedRxPosition(getIndoorChamberConfig(), { force: true });" in js
    assert "const targetZOffset = Array.isArray(state.markers.rx)" in js


def test_campaign2_specular_path_toggle_is_wired_to_payload_and_preview() -> None:
    html = Path("app/sim_web/index.html").read_text(encoding="utf-8")
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert 'id="campaign2ShowSpecularPath"' in html
    assert "show_specular_path: ui.campaign2ShowSpecularPath ? ui.campaign2ShowSpecularPath.checked : true" in js
    assert "function getCampaign2SpecularTurntableAngleDeg(targetAngleDeg, txIncidenceAngleDeg)" in js
    assert "new THREE.LineDashedMaterial" in js
    assert "specularLine.computeLineDistances();" in js


def test_campaign2_plot_images_bust_cache_for_regenerated_chunks() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "ui.campaign2PlotImage.src = `/runs/${runId}/plots/${file}?v=${Date.now()}`;" in js


def test_campaign2_loads_angle_radio_map_manifest() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "fetchJsonMaybe(`/runs/${runId}/data/campaign_angle_radio_maps.json`)" in js
    assert "const availablePlots = [...aggregatePlots, ...anglePlots];" in js


def test_heatmap_overlay_uses_cell_center_geometry() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "function buildHeatmapGeometryFromCenters(centers, cellSize = [0, 0])" in js
    assert "const grid = buildHeatmapGeometryFromCenters(centers, active.cell_size || [0, 0]);" in js
