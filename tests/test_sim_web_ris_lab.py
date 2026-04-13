from pathlib import Path


def test_ris_lab_results_selection_can_detach_from_active_job() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "selectedRunId: null," in js
    assert "followActiveRun: true," in js
    assert "function syncRisSelectedRun(runId, options = {})" in js
    assert 'syncRisSelectedRun(data.run_id, { followActive: true });' in js
    assert 'syncRisSelectedRun(ui.risRunSelect.value, { followActive: false });' in js
    assert "await loadRisResults(state.ris.selectedRunId);" in js
    assert "ui.risRunSelect.value = state.ris.activeRunId;" not in js


def test_ris_lab_result_plot_resets_to_phase_map_when_mode_changes() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "const RIS_PLOT_FILES_BY_MODE = {" in js
    assert 'pattern: new Set(["phase_map.png", "pattern_cartesian.png", "pattern_polar.png"]),' in js
    assert 'validate: new Set(["phase_map.png", "validation_overlay.png"]),' in js
    assert 'compare: new Set([' in js
    assert 'const defaultPlot = !metrics' in js
    assert '? "phase_map.png"' in js
    assert ': "phase_map.png";' in js
