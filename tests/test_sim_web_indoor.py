from pathlib import Path


def test_indoor_tabs_force_chamber_profile_and_scope() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "function isIndoorScopeTab(tabName = state.activeTab)" in js
    assert "function getActiveProfileKey(tabName = state.activeTab)" in js
    assert 'return RUN_PROFILES[getActiveProfileKey()] || RUN_PROFILES.cpu_only;' in js
    assert 'return isIndoorScopeTab(state.activeTab) || getActiveProfileKey() === "indoor_box_high" ? "indoor" : "sim";' in js
    assert "profile: profileKey," in js


def test_indoor_profile_selector_snaps_back_to_chamber_profile() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert 'if (isIndoorScopeTab(state.activeTab) && ui.runProfile.value !== "indoor_box_high") {' in js
    assert 'ui.runProfile.value = "indoor_box_high";' in js


def test_loading_indoor_runs_preserves_chamber_radio_map_defaults() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert 'const radioControlConfig = scope === "indoor" && isIndoorScopeTab(state.activeTab)' in js
    assert "applyRadioMapDefaults(radioControlConfig);" in js
    assert "Keep indoor/campaign submissions anchored to the chamber radio-map defaults" in js
