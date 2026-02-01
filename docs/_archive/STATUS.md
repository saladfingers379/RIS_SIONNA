# Simulator Status (Handoff)

## What’s implemented
- Omniverse-lite simulator: stdlib HTTP server + static frontend (`app/sim_server.py`, `app/sim_web/*`).
- Background job runner: submits `python -m app run --config <generated>` as a subprocess (`app/sim_jobs.py`).
- Viewer artifacts exported per run (`app/viewer.py`):
  - `viewer/scene_manifest.json`, `viewer/markers.json`, `viewer/paths.json`, `viewer/heatmap.json`.
- Path table CSV now includes order/type/path length/power/interaction list (`app/metrics.py`, `app/simulate.py`).
- Procedural scenes: registry + street canyon preset + material library (`app/scene.py`, `configs/procedural.yaml`).
- UI: run selector, scene source selector, job buttons, path table, stats, glossary, heatmap controls.
- Viewer UX: collapsible left-panel sections, top heatmap scale bar, keyboard navigation (WASD/QE) + right-drag pan.
- Alignment aids: guides toggle (off by default) and heatmap/mesh rotation defaults set to 0.
- Marker tools: randomize Tx/Rx button (avoids proxy boxes when available).
- Perf trace captured in `docs/trace_viewer.json`, summary in `docs/perf.md`.
- Sionna RT v0.19.2 integration with RIS adapter (`app/ris/ris_sionna.py`).

## Known issues (needs work)
- UI still needs polish; more responsive layouts + better defaults needed.
- Randomized Tx/Rx avoids proxy boxes only; if a scene has no proxy geometry, points may still land inside mesh volume.
- New runs sometimes don’t load; UI now auto-loads newest completed run, but needs more validation.

## How heatmap is generated
- `app/simulate.py` saves `radio_map.npz` (path gain + rx power + cell centers).
- `app/viewer.py` writes `viewer/heatmap.json`:
  - `metric` is `rx_power_dbm` if available, else `path_gain_db`.
  - Includes `grid_shape`, `values`, `cell_centers`, `center`, `size`, `cell_size`, `orientation`.
- `app/sim_web/app.js` builds a textured plane from `values` and uses:
  - Plane size from cell centers (fallback to size/center).
  - Rotation from `heatmap.orientation` + UI override (defaults to 0).

## UI scene selection
- Scene source dropdown uses `/api/run/<id>` to fetch config/summary.
- Jobs use the scene from that selected run, with Tx/Rx positions overridden.

## Useful files
- Backend: `app/sim_server.py`, `app/sim_jobs.py`
- Simulation: `app/simulate.py`, `app/scene.py`, `app/metrics.py`
- Viewer artifacts: `app/viewer.py`
- UI: `app/sim_web/index.html`, `app/sim_web/styles.css`, `app/sim_web/app.js`
- Configs: `configs/*.yaml`
- RIS adapter: `app/ris/ris_sionna.py`
- RIS demo: `configs/ris_rt_demo.yaml`, `scripts/demo_ris_in_scene.py`

## Suggested next steps
- If alignment issues reappear, consider baking a heatmap mesh in world coords using cell centers.
- Improve randomization by using mesh intersection tests when proxies are absent.
- Extend stats: reflections/diffractions counts already in UI, add full solver settings + timings.
