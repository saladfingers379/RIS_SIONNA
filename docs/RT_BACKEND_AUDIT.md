# RT Backend Audit (Linux)

## Entry Points
- CLI entrypoint: `app/__main__.py` -> `app/cli.py` (subcommands: run, diagnose, dashboard, sim).
- Simulation runner: `app/simulate.py::run_simulation()`.

## Backend Selection Points
- Mitsuba variant selection: `app/utils/system.py::select_mitsuba_variant()`.
  - Prefers `cuda_ad_rgb` when `runtime.prefer_gpu` is true and available.
  - Falls back to LLVM/scalar variants for CPU preview.
- CPU fallback switch: `app/simulate.py` uses `runtime.force_cpu` to clear `CUDA_VISIBLE_DEVICES`.
- Diagnose path: `app/utils/system.py::diagnose_environment()` reports variants, selected backend, OptiX checks.

## Scene Build / Load
- Scene construction: `app/scene.py::build_scene()` with `scene.type` (builtin/file/procedural).
- Procedural scene caching: `app/scene.py::_build_procedural_scene()` caches XML under `outputs/_cache/procedural/`.

## Radio Map & Coverage Sampling
- Paths: `app/simulate.py` -> `sionna.rt.PathSolver()`.
- Radio maps: `app/simulate.py::_compute_radio_map()` -> `sionna.rt.RadioMapSolver()`.
- Coverage/heatmap export + plots: `app/simulate.py` and `app/plots.py`.

## Output & Logging
- Output structure: `app/io.py` (run_id, `outputs/<run_id>/` layout).
- Summary written in `app/simulate.py` and `app/utils/system.py` (diagnose).
- Progress tracking: `app/utils/progress.py` + `outputs/<run_id>/progress.json`.

## Clean Insertion Points for Diagnostics
- `app/utils/system.py::diagnose_environment()` for environment checks and OptiX symbol validation.
- `app/simulate.py::run_simulation()` summary payload (`runtime`, `environment`, `config`) for backend proof.

## CPU Preview Preservation
- `configs/preview.yaml` forces CPU (`runtime.force_cpu: true`, `prefer_gpu: false`).
- Streamlit dashboard uses saved outputs only; no GPU dependency in `app/cli.py` dashboard mode.
