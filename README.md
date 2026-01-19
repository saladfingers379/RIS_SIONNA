# RIS_SIONNA — 28 GHz Sionna RT Baseline

A small, beginner-friendly starter kit for Sionna RT ray-tracing at 28 GHz.
It runs a single Tx/Rx link, computes a path-gain proxy, and (optionally) generates a radio map.
The architecture keeps RIS hooks in the config and scene pipeline but **does not implement RIS yet**.

## Highlights
- Single-command CLI run: `python -m app run --config configs/default.yaml`
- Ray tracing via Sionna RT (LOS + reflections by default)
- Optional 2D radio map (batched within Sionna RT solver)
- Rich progress bars + timestamped logs
- Outputs saved per run under `outputs/<timestamp>/`
- Optional Streamlit dashboard (visualization only)
- New Omniverse-lite simulator UI with interactive Tx/Rx placement + jobs

## Quick Start (macOS CPU)
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
python -m app run --config configs/default.yaml
```
Note: Sionna 1.2.1 requires NumPy <2.0, so use Python 3.10–3.12 for smooth installs.

### Quick Start with uv (recommended)
```bash
uv venv -p 3.12 .venv
source .venv/bin/activate
uv pip install -e .
python -m app run --config configs/default.yaml
```

## Dependency Constraints (Sionna 1.2.1)
- Sionna 1.2.1 pins `numpy<2.0` (see Sionna 1.2.1 requirements), which conflicts with Python 3.13 where NumPy <2.0 wheels are not available.
- Result: use Python 3.10–3.12 for this project to keep installs reproducible and avoid slow source builds or resolver failures.

## Dashboard
```bash
pip install -e ".[dashboard]"
python -m app dashboard
```
Dashboard features:
- Latest-run selector (most recent first)
- Coverage map metric picker
- 3D view of RF ray paths (if `ray_paths.csv` is available)
- Scene render + downloads
 - 3D viewer shows live cursor coordinates in the HUD

Notes:
- Dashboard is visualization-only; run simulations from the CLI.
- If the 3D view is blank, click "Regenerate viewer now" in the sidebar.

## Omniverse-lite Simulator (NEW)
The simulator is a lightweight, always-responsive web UI that submits jobs in the background
and visualizes saved outputs (no heavy compute in the UI process).

```bash
python -m app sim
```

What it does:
- Load scene geometry + viewer artifacts from `outputs/<run_id>/viewer/`
- Move Tx/Rx interactively (drag or numeric inputs)
- Run simulations via profiles (CPU only, GPU low/medium/high, custom)
- Custom overrides for key radio-map and solver settings
- Inspect path table and highlight rays
- Toggle geometry / rays / heatmap layers
- Export a snapshot (PNG)

Why not FastAPI/Streamlit?
- The simulator uses only the Python stdlib HTTP server for reliability and zero extra dependencies.

Simulator profiles and radio maps:
- Radio map settings map directly to Sionna RT `RadioMapSolver` parameters (cell size + samples per TX).
  Source: https://nvlabs.github.io/sionna/rt/api/radio_map_solvers

## Quick Start (Ubuntu 24.04 + NVIDIA GPU)
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
python -m app diagnose
python -m app run --config configs/high.yaml
```

## Commands
- `python -m app diagnose`
- `python -m app run --config configs/default.yaml`
- `python -m app plot --latest`
- `python -m app dashboard`
- `python -m app sim`

Makefile shortcuts:
- `make diagnose`, `make run`, `make plot`, `make dashboard`, `make sim`

## GPU Requirements (Ubuntu 24.04)
- NVIDIA driver installed and `nvidia-smi` works.
- Mitsuba 3 CUDA variants (for example `cuda_ad_rgb`) are present and selectable.
  Source: https://github.com/mitsuba-renderer/mitsuba3/blob/master/docs/src/key_topics/variants.rst
- Dr.Jit auto backend uses CUDA when a compatible GPU is detected (otherwise LLVM/CPU).
  Source: https://github.com/mitsuba-renderer/drjit/blob/master/docs/type_ref.rst
- Sionna RT relies on Mitsuba/Dr.Jit types and integration.
  Source: https://github.com/nvlabs/sionna-rt/blob/main/doc/source/developer/dev_compat_frameworks.rst

## GPU Diagnostics
Use `diagnose` to confirm the RT backend and run a small smoke test:
```bash
python -m app diagnose
```
Look for:
- `diagnose.runtime.selected_variant` containing `cuda`
- `diagnose.verdict` showing `RT backend is CUDA/OptiX`
- `diagnose.runtime.gpu_smoke_test` timing + backend
- `diagnose.runtime.optix` showing `libnvoptix.so.1` + `optixQueryFunctionTable`

Each diagnose run also writes `outputs/<run_id>/summary.json`.

## GPU Benchmark (High Compute)
Run the repeatable benchmark preset:
```bash
python -m app run --config configs/benchmark_gpu.yaml
```
This runs two radio maps (256x256 then 512x512) with batching and writes GPU usage samples
into `summary.json` under `runtime.gpu_monitor`.

UI smoke test (requires Playwright):
```bash
python tests/test_ui_smoke.py
```

## Outputs
Each run saves to `outputs/<timestamp>/`:
- `config.yaml` (snapshot)
- `run.log` (timestamped runtime log)
- `progress.json` (live progress for UI polling)
- `summary.json` (metrics + environment + versions)
- `data/radio_map.npz` (path gain + derived metrics + cell centers)
- `data/radio_map.csv` (x, y, z, path_gain_db)
- `data/paths.csv` (order/type/length/delay/power + interactions list)
- `data/ray_paths.csv` and `data/ray_paths.npz` (ray segments for 3D view)
- `viewer/markers.json` (Tx/Rx positions)
- `viewer/paths.json` (path polylines + metadata)
- `viewer/scene_manifest.json` (geometry + proxy manifest)
- `viewer/heatmap.json` and `viewer/heatmap.npz` (coverage overlay)
- `plots/radio_map_path_gain_db.png/svg`
- `plots/radio_map_rx_power_dbm.png/svg`
- `plots/radio_map_path_loss_db.png/svg`
- `plots/scene.png` (rendered scene view)
- `plots/path_delay_hist.png/svg`
- `plots/aoa_azimuth_hist.png/svg`
- `plots/aoa_elevation_hist.png/svg`
- `plots/ray_paths_3d.png/svg`

Viewer artifact format (`outputs/<run_id>/viewer/`):
- `scene_manifest.json`: `{ mesh, mesh_files, proxy }`
- `markers.json`: `{ tx: [x,y,z], rx: [x,y,z] }`
- `paths.json`: list of `{ path_id, points, order, type, path_length_m, delay_s, power_db, interactions }`
- `heatmap.json`: `{ metric, grid_shape, values, cell_centers }`

## Simulation Assumptions
- Carrier frequency: 28 GHz
- Default scene: built-in `etoile` (Sionna RT)
- Tx height: 28 m, Rx height: 1.5 m (see `configs/default.yaml`)
- Camera render: configurable via `scene.camera` in YAML

## Dependencies (Pinned + Justified)
- `sionna==1.2.1`: core simulation + Sionna RT
- `numpy==1.26.4`: numeric arrays + data export (compatible with Sionna 1.2.1)
- `matplotlib==3.10.8`: plotting (PNG/SVG)
- `pyyaml==6.0.3`: config parsing
- `rich==14.2.0`: progress bars + readable logs
- `streamlit==1.53.0` (optional): lightweight dashboard for saved outputs

## Configs & Quality Presets
- `configs/preview.yaml` (CPU-friendly)
- `configs/default.yaml` (preview-safe default)
- `configs/high.yaml` (GPU-friendly)
- `configs/benchmark_gpu.yaml` (GPU stress benchmark: 256/512 radio maps)
- `configs/procedural.yaml` (street-canyon procedural scene)

Scene sources:
- Built-in: `scene.type: builtin` with `scene.builtin: etoile` (default)
- External: `scene.type: file` with `scene.file: path/to/scene.xml` (Mitsuba 3 format)
- Procedural: `scene.type: procedural` with `scene.procedural` (ground + boxes + street canyon preset)
 - 3D Viewer mesh: `scene.mesh: path/to/scene.glb|gltf|obj` (optional)
 - Proxy geometry: `scene.proxy` (ground + boxes) for quick 3D previews
 - Dashboard mesh overrides: drop `.glb/.gltf/.obj` into `scenes/` and pick it in the sidebar
 - Built-in mesh export: `scene.export_mesh: true` exports PLY meshes for the 3D viewer

Visualization controls:
- `render.enabled`, `render.samples`, `render.resolution` control the optical scene render.
- `visualization.ray_paths.max_paths` controls how many RF paths are exported for 3D view.
 - Viewer output saved to `outputs/<timestamp>/viewer/index.html`
- `runtime.vram_guard` auto-reduces rays/depth when GPU memory is tight.

All configs include a placeholder:
```yaml
ris:
  enabled: false
```

## Project Notes
For operational notes, known quirks, and handoff context, see `PROJECT_CONTEXT.md`.
Performance trace notes for the simulator viewer: `docs/perf.md`.
GPU troubleshooting and backend checks: `docs/TROUBLESHOOTING.md`.

## Digital Twin Roadmap
Current:
- Sionna RT scenes + configs + per-run outputs for repeatable studies
- Procedural street-canyon scene for realism baselines

Next:
- Structured scene ingestion for repeatable scenario packs (no GIS ingestion yet)
- Consistent asset naming + metadata for multi-run comparisons

Future:
- RIS panel integration behind `ris.enabled`
- Optimization loops and experiment sweeps for RIS placement/control

## Current Status (WIP)
- Heatmap alignment fixed for rotated scenes; validation ongoing on larger meshes.
- Simulator UI is still evolving, but progress is steady.

## Future RIS Extension (Not Implemented)
- Add a SceneObjectSpec implementation for RIS panels.
- Use `ris.enabled: true` to add RIS objects without refactoring the core pipeline.

## Documentation References (URLs + Versions)
Sionna / Sionna RT:
- Sionna RT install guide (Context7, main README): https://github.com/nvlabs/sionna-rt/blob/main/README.md
- Sionna RT Scene API (Context7, main docs): https://github.com/nvlabs/sionna-rt/blob/main/doc/source/api/scene.rst
- Sionna RT PathSolver API (Context7, main docs): https://github.com/nvlabs/sionna-rt/blob/main/doc/source/api/paths_solvers.rst
- Sionna RT Paths API (Context7, main docs): https://github.com/nvlabs/sionna-rt/blob/main/doc/source/api/paths.rst
- Sionna RT RadioMapSolver API (Context7, main docs): https://github.com/nvlabs/sionna-rt/blob/main/doc/source/api/radio_map_solvers.rst
- Sionna RT Radio Maps API (Context7, main docs): https://github.com/nvlabs/sionna-rt/blob/main/doc/source/api/radio_maps.rst
- Sionna RT SceneObject API (Context7, main docs): https://github.com/nvlabs/sionna-rt/blob/main/doc/source/api/scene_object.rst
- Sionna RT compatibility + Mitsuba variants (Context7): https://github.com/nvlabs/sionna-rt/blob/main/doc/source/developer/dev_compat_frameworks.rst

Mitsuba / Dr.Jit:
- Mitsuba 3 scene format (Context7): https://github.com/mitsuba-renderer/mitsuba3/blob/master/docs/src/key_topics/scene_format.rst
- Mitsuba 3 variants (Context7): https://github.com/mitsuba-renderer/mitsuba3/blob/master/docs/src/key_topics/variants.rst
- Dr.Jit auto backend (Context7): https://github.com/mitsuba-renderer/drjit/blob/master/docs/type_ref.rst

TensorFlow:
- TensorFlow pip install (Context7): https://github.com/tensorflow/docs/blob/master/site/en/install/pip.md

Version notes:
- This repo pins `sionna==1.2.1` (see `pyproject.toml`) and follows the Sionna RT APIs linked above. If the Sionna RT API changes upstream, update both the pin and the documentation references together.

Mitsuba / Dr.Jit:
- Mitsuba 3 docs (v3.7.1): https://mitsuba.readthedocs.io/en/latest/
- Mitsuba variants (v3.7.1): https://mitsuba.readthedocs.io/en/latest/src/key_topics/variants.html
- Mitsuba scene format (v3.7.1): https://mitsuba.readthedocs.io/en/latest/src/key_topics/scene_format.html
- Dr.Jit docs (PyPI v1.2.0): https://drjit.readthedocs.io/en/latest/

TensorFlow:
- Install TensorFlow 2 docs (PyPI v2.20.0): https://www.tensorflow.org/install

### Notes on doc-version mismatches
- TensorFlow and Dr.Jit docs do not publish explicit version numbers on the landing pages.
  For reproducibility, this repo records the **current PyPI versions** in `summary.json` and
  uses those versions in these references.
