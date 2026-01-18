# Simulator Status (Handoff)

## What’s implemented
- Omniverse-lite simulator: stdlib HTTP server + static frontend (`app/sim_server.py`, `app/sim_web/*`).
- Background job runner: submits `python -m app run --config <generated>` as a subprocess (`app/sim_jobs.py`).
- Viewer artifacts exported per run (`app/viewer.py`):
  - `viewer/scene_manifest.json`, `viewer/markers.json`, `viewer/paths.json`, `viewer/heatmap.json`.
- Path table CSV now includes order/type/path length/power/interaction list (`app/metrics.py`, `app/simulate.py`).
- Procedural scenes: registry + street canyon preset + material library (`app/scene.py`, `configs/procedural.yaml`).
- UI: run selector, scene source selector, job buttons, path table, stats, glossary, heatmap dB sliders.
- Perf trace captured in `docs/trace_viewer.json`, summary in `docs/perf.md`.

## Known issues (needs work)
- Heatmap alignment still incorrect for rotated scenes (Arc de Triomphe scene shows rotated mismatch).
  - Current logic applies `radio_map.orientation` in the viewer, but the heatmap plane still doesn’t match mesh rotation.
  - May need full transform from radio map coordinates → world (or use scene transform / Mitsuba world to align).
- UI clunky; missing features still expected (per user feedback).
- New runs sometimes don’t load; UI now auto-loads newest completed run, but needs more validation.

## How heatmap is generated
- `app/simulate.py` saves `radio_map.npz` (path gain + rx power + cell centers).
- `app/viewer.py` writes `viewer/heatmap.json`:
  - `metric` is `rx_power_dbm` if available, else `path_gain_db`.
  - Includes `grid_shape`, `values`, `cell_centers`, `center`, `size`, `cell_size`, `orientation`.
- `app/sim_web/app.js` builds a textured plane from `values` and uses:
  - Plane size from cell centers (fallback to size/center).
  - Rotation from `heatmap.orientation` (currently insufficient for correct alignment).

## UI scene selection
- Scene source dropdown uses `/api/run/<id>` to fetch config/summary.
- Jobs use the scene from that selected run, with Tx/Rx positions overridden.

## Useful files
- Backend: `app/sim_server.py`, `app/sim_jobs.py`
- Simulation: `app/simulate.py`, `app/scene.py`, `app/metrics.py`
- Viewer artifacts: `app/viewer.py`
- UI: `app/sim_web/index.html`, `app/sim_web/styles.css`, `app/sim_web/app.js`
- Configs: `configs/*.yaml`

## Suggested next steps
- Fix heatmap alignment with proper world transform (likely use cell center positions to build the plane geometry directly, or bake a mesh in world coords).
- Add more UI controls + responsiveness polish.
- Extend stats: reflections/diffractions counts already in UI, add full solver settings + timings.
