# REPO_STATUS — audit + repro notes

## How to run current system
- CLI run: `python -m app run --config configs/preview.yaml`
- Simulator UI: `python -m app sim`
- Dashboard (visualization only): `python -m app dashboard`

## What works (verified)
- Preview run completes and writes outputs under `outputs/<run_id>/`.
- Radio map artifacts are generated (`data/radio_map.npz`, `viewer/heatmap.json`).
- Mesh export succeeds (`scene_mesh/*.ply`) for the builtin `etoile` scene.

## What is broken (reproduced)
- Coverage map overlay in the simulator is geometrically misaligned with the scene.
- Evidence from run `outputs/20260118_114723`:
  - Heatmap size from `viewer/heatmap.json`: `873.6628 x 696.1205` m (auto_size + 10 m padding).
  - Scene mesh bbox from `scene_mesh/*.ply`: `830.2225 x 764.8917` m.
  - Simulator uses mesh bbox size to place the heatmap plane, overriding the radio-map grid extents.

## Hypothesis (root cause)
- `app/sim_web/app.js` overrides heatmap width/height/center with the mesh bounding box, even when `cell_centers` (or `size/center`) are available. This discards radio-map padding and ignores orientation, which explains the misalignment (especially for rotated scenes).
- The plotting pipeline (`app/plots.py`) uses `cell_centers` directly and appears internally consistent; the UI overlay path is the likely culprit.

## Files/modules involved
- `app/simulate.py`: builds radio map, saves `cell_centers` + metrics.
- `app/viewer.py`: writes `viewer/heatmap.json` for the simulator.
- `app/sim_web/app.js`: renders the heatmap plane and currently overrides its size with mesh bbox.
- `app/plots.py`: uses `cell_centers` to set imshow extent.
- `app/scene.py`: scene construction + mesh export (for bbox).

## Notes
- Run used: `python -m app run --config configs/preview.yaml` (CPU) → output `outputs/20260118_114723`.
- Next steps: fix overlay sizing logic in the simulator to respect radio-map grid extents; add explicit alignment sanity markers in plots and UI.

## Fix applied (pending visual verification)
- Simulator heatmap sizing now honors `heatmap.size/center` (or `cell_centers`) and only falls back to mesh bbox if heatmap metadata is missing.
- Plot outputs now include Tx/Rx markers and use cell-size-aware extents for correct bounds.
- Simulator jobs now expose `progress.json` for UI polling.
- New run: `outputs/20260118_115857` (generated after fixes).

## Follow-up fix (simulator-only misalignment)
- Simulator now derives plane bounds from `cell_centers` before config size (avoids grid rounding mismatch).
- Texture rows are flipped to match the same lower-origin convention used by Matplotlib (`origin="lower"`), preventing vertical inversion.

## Root cause (confirmed via Playwright)
- Radio map `auto_size` produced sizes not aligned to the cell size. Sionna RT rounded the grid to whole cells (e.g., 873.6628 → 876 m), shifting the actual `cell_centers` by ~1–2 m from the config center.
- Simulator rendered the heatmap at the `cell_centers` positions (correct), while the mesh bbox remained centered at (0,0). This caused a visible offset in the 3D overlay even though dashboard plots looked correct.

## Fix applied
- `simulate.py` now snaps `auto_size` to multiples of `cell_size` before calling Sionna RT, so the radio-map grid is centered and aligned.
