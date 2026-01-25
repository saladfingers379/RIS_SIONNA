# REPO_STATUS — audit + repro notes

## How to run current system
- CLI run: `python -m app run --config configs/preview.yaml`
- Simulator UI: `python -m app sim`
- Dashboard (visualization only): `python -m app dashboard`

## What works (verified)
- Preview run completes and writes outputs under `outputs/<run_id>/`.
- Radio map artifacts are generated (`data/radio_map.npz`, `viewer/heatmap.json`).
- Mesh export succeeds (`scene_mesh/*.ply`) for the builtin `etoile` scene.
- GPU runs work with Mitsuba CUDA variants once TF GPU runtime libs are installed.

## Status
- Coverage/heatmap alignment issues are resolved; keep regression checks in place.
- Simulator and dashboard both honor `cell_centers` for heatmap placement.
