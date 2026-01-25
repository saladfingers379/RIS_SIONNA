# RIS_SIONNA — 28 GHz Sionna RT Baseline

Starter kit for Sionna RT ray tracing at 28 GHz with a lightweight simulator UI and a math-first RIS Lab. This branch targets Sionna RT v0.19.2 and supports RIS integration.

## Highlights
- CLI runs: `python -m app run --config configs/default.yaml`
- Sionna RT LOS + reflections + optional radio map
- Omniverse-lite simulator UI (stdlib HTTP server)
- RIS Lab (CPU-only): near-field reflectarray model + validation
- Optional Streamlit dashboard (visualization only)

## Quick Start (macOS CPU)
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
python -m app run --config configs/preview.yaml
```
Note: Sionna 0.19.2 requires TensorFlow 2.13–2.15 and NumPy <2.0, so use Python 3.10–3.11.

## Quick Start (Ubuntu 24.04 + NVIDIA GPU)
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
python -m app diagnose
python -m app run --config configs/high.yaml
```
If you want a clean install that matches Sionna v0.19.2, use:
```bash
pip install -r requirements-0.19.2.txt
pip install -e .
```

## Commands
- `python -m app diagnose`
- `python -m app run --config configs/default.yaml`
- `python -m app plot --latest`
- `python -m app dashboard`
- `python -m app sim`
- `python -m app ris run --config configs/ris/steer_1bit.yaml --mode pattern`
- `python -m app ris validate --config configs/ris/validate_vs_csv.yaml --ref refs/pattern.csv`

## Dashboard (Streamlit)
```bash
pip install -e ".[dashboard]"
python -m app dashboard
```
Notes:
- Visualization only; run simulations from CLI/UI.
- If 3D view is blank, click “Regenerate viewer now”.

## Omniverse-lite Simulator UI
```bash
python -m app sim
```
Features:
- Load saved outputs from `outputs/<run_id>/viewer/`
- Interactive Tx/Rx placement
- Profiles: CPU, GPU low/medium/high, custom
- Job status, logs, and snapshots

## RIS Lab (CPU-only)
RIS Lab is a math-first validation tool for RIS patterns and link metrics. It uses a near-field reflectarray model (Machado/Tang-style sweep).

CLI examples:
```bash
python -m app ris run --config configs/ris/steer_1bit.yaml --mode pattern
python -m app ris run --config configs/ris/focus_point.yaml --mode pattern
python -m app ris validate --config configs/ris/validate_vs_csv.yaml --ref refs/pattern.csv
```

UI workflow:
1) Run `python -m app sim`
2) Switch to the “RIS Lab” tab
3) Use the builder (or a config file) and run
4) Results auto-load; plots are tabbed (Phase/Pattern/Polar/Validation)

Artifacts (written under `outputs/<run_id>/`):
- Common: `config.yaml`, `config.json`, `summary.json`, `progress.json`, `metrics.json`
- Pattern: `plots/phase_map.png`, `plots/pattern_cartesian.png`, `plots/pattern_polar.png`,
  `data/phase_map.npy`, `data/theta_deg.npy`, `data/pattern_linear.npy`, `data/pattern_db.npy`
- Validation: `plots/phase_map.png`, `plots/validation_overlay.png`

## RIS in Sionna RT (v0.19.2)
Enable RIS with a workbench phase map by editing `configs/default.yaml`:
- Set `ris.enabled: true`
- Update `ris.workbench.config_path` to point at a RIS Lab YAML (example: `configs/ris_lab_example.yaml`)

Minimal demo script:
```bash
python scripts/demo_ris_in_scene.py --ris-config configs/ris_lab_example.yaml
```
The demo prints total path-gain with RIS ON vs RIS OFF.

## GPU Diagnostics
Run:
```bash
python -m app diagnose
```
Look for:
- `diagnose.runtime.selected_variant` includes `cuda`
- `diagnose.verdict` shows `RT backend is CUDA/OptiX`
- `diagnose.runtime.optix` finds `libnvoptix.so.1` + `optixQueryFunctionTable`

Each diagnose run writes `outputs/<run_id>/summary.json`.
Tip: `python -m app diagnose --json` prints JSON only.

## CUDA + TensorFlow GPU Requirement
Sionna RT v0.19.2 transfers CUDA tensors to TensorFlow via DLPack. If
Mitsuba selects a CUDA variant but TensorFlow cannot see a GPU, runs will
fail with `GPU:0 unknown device`.

Fix:
- Install TF GPU runtime libraries matching your TensorFlow build.
  TF 2.15 expects CUDA 12.2 + cuDNN 8.

## Outputs (Simulation)
Each run saves to `outputs/<run_id>/`:
- `config.yaml`, `run.log`, `progress.json`, `summary.json`
- `data/` (radio map + paths)
- `plots/` (radio map + path stats)
- `viewer/` (3D viewer artifacts)

## Platform Support
Supported & tested:
- Native Ubuntu 24.04 + NVIDIA GPU (CUDA/OptiX)
- CPU-only runs: Linux/macOS/WSL

WSL2 note:
- OptiX is not officially supported on WSL2; GPU RT is considered unsupported/experimental there.

## Docs
- `docs/TROUBLESHOOTING.md` GPU backend checks
- `docs/perf.md` simulator performance trace notes
- `PROJECT_CONTEXT.md` handoff/notes
