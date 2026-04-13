from pathlib import Path


def test_ris_synthesis_results_selection_can_detach_from_active_job() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "selectedRunId: null," in js
    assert "followActiveRun: true," in js
    assert 'syncRisSynthesisSelectedRun(data.run_id, { followActive: true });' in js
    assert 'syncRisSynthesisSelectedRun(ui.risSynthRunSelect.value, { followActive: false });' in js
    assert "await loadRisSynthesisResults(state.risSynthesis.selectedRunId);" in js
    assert "ui.risSynthRunSelect.value = state.risSynthesis.activeRunId;" not in js


def test_ris_synthesis_manual_overlay_is_preserved_across_shared_viewer_refresh() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "function hasActiveRisSynthesisViewerOverlay(scope = getRunScopeForTab())" in js
    assert "(state.risSynthesis.viewerOverlayRunId || state.risSynthesis.pendingViewerOverlayRunId)" in js
    assert "const preserveTargetRegionViewer = isActiveScope && hasActiveRisSynthesisViewerOverlay(scope);" in js
    assert "&& hasActiveRisSynthesisViewerOverlay(scope)" in js


def test_ris_synthesis_overlay_requests_cancel_stale_viewer_writes() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "viewerOverlayRequestToken: 0," in js
    assert "if (state.risSynthesis.viewerOverlayRequestToken !== requestToken) {" in js
    assert "state.risSynthesis.pendingViewerOverlayRunId = runId;" in js
    assert "clearRisSynthesisViewerOverlay();" in js


def test_ris_synthesis_new_draw_session_replaces_previous_roi_set() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")
    html = Path("app/sim_web/index.html").read_text(encoding="utf-8")

    assert "replaceOnNextDraw: false," in js
    assert "state.risSynthesis.replaceOnNextDraw = Boolean(enabled && (state.risSynthesis.drawnBoxes || []).length);" in js
    assert "if (state.risSynthesis.replaceOnNextDraw) {" in js
    assert "state.risSynthesis.drawnBoxes = [box];" in js
    assert "The next box will replace the current target set" in js
    assert "The first new box replaces the current target" in html


def test_ris_synthesis_submit_revalidates_roi_textarea_before_start() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert 'if (!syncRisSynthesisBoxesStateFromTextarea({ quiet: true })) {' in js
    assert 'setRisSynthesisStatus("Config error: fix the ROI JSON before starting a new run.");' in js
    assert "const roiValidation = await validateRisSynthesisBoxesAgainstSeedGrid(payload.config_data.target_region.boxes);" in js
    assert "ROI boxes do not hit any seed-grid cells" in js


def test_ris_synthesis_draw_and_top_down_auto_sync_to_seed_viewer() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "async function ensureRisSynthesisViewerMatchesSeedRun()" in js
    assert "await loadRisSynthesisViewerRun(true);" in js
    assert "const synced = await ensureRisSynthesisViewerMatchesSeedRun();" in js
    assert 'setRisSynthesisViewerStatus("Load the seed run into the viewer before drawing ROIs.");' in js
    assert 'setRisSynthesisViewerStatus("Load a seed run with a heatmap before switching to top-down view.");' in js


def test_ris_synthesis_auto_sized_seed_runs_skip_stale_config_bounds_check() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "function hasStaticCoverageMapBounds(config)" in js
    assert "return !Boolean(radio.auto_size);" in js
    assert "const bounds = hasStaticCoverageMapBounds(seedConfigObject)" in js


def test_ris_synthesis_seed_path_prefers_effective_run_config_when_available() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "function getRunSeedConfigPath(runId, details = null)" in js
    assert "if (runDetails && runDetails.effective_config)" in js
    assert "return `outputs/${runId}/config.yaml`;" in js
