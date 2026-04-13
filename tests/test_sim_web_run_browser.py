from pathlib import Path


def test_run_browser_markup_is_present_in_topbar_and_modal() -> None:
    html = Path("app/sim_web/index.html").read_text(encoding="utf-8")

    assert '<button id="runBrowserToggle" type="button">Browse Runs</button>' in html
    assert 'class="run-browser-modal" id="runBrowserModal"' in html
    assert 'id="runBrowserSearch"' in html
    assert 'id="runBrowserPreviewImage"' in html
    assert 'id="runBrowserOpenRun"' in html


def test_run_browser_js_wires_selection_preview_and_open_flow() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "function renderRunBrowserList()" in js
    assert "async function selectRunBrowserRun(runId)" in js
    assert "async function activateRunFromBrowser(runId)" in js
    assert "ui.runBrowserToggle.addEventListener(\"click\", () => {" in js
    assert "ui.runBrowserOpenRun.addEventListener(\"click\", () => {" in js
    assert "ui.runBrowserSearch.addEventListener(\"input\", () => {" in js
    assert "ui.runBrowserPreviewImage.src = `${thumbnailPath}?v=${encodeURIComponent(run.run_id)}`;" in js
    assert 'item.setAttribute("role", "button");' in js
    assert 'item.addEventListener("keydown", (event) => {' in js
    assert '<span class="run-browser-item-id-text">${escapeHtml(run.run_id)}</span>' in js


def test_sim_viewer_js_caches_geometry_templates_for_heavy_mesh_scenes() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "geometryTemplateCache: new Map()" in js
    assert "geometryTemplatePromises: new Map()" in js
    assert "async function getOrBuildGeometryTemplate(assetKey, builder)" in js
    assert "async function loadPlyGeometry(loader, url)" in js
    assert "geometryGroup.add(cloneGeometryTemplate(template));" in js


def test_sim_viewer_js_colors_ris_rays_red() -> None:
    js = Path("app/sim_web/app.js").read_text(encoding="utf-8")

    assert "const risColor = new THREE.Color(0xef4444);" in js
    assert "const color = p && p.has_ris ? risColor : defaultColor;" in js


def test_run_browser_styles_constrain_long_card_text() -> None:
    css = Path("app/sim_web/styles.css").read_text(encoding="utf-8")

    assert ".run-browser-item {" in css
    assert "display: grid;" in css
    assert "flex: 0 0 auto;" in css
    assert "height: auto;" in css
    assert "cursor: pointer;" in css
    assert "overflow: hidden;" in css
    assert "grid-template-columns: minmax(0, 1fr) fit-content(128px);" in css
    assert "text-overflow: ellipsis;" in css
    assert ".run-browser-item-id {" in css
    assert ".run-browser-item-id-text {" in css
    assert "overflow: visible;" in css
    assert "min-height: 34px;" in css
    assert "line-height: 1.35;" in css
