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

## Quick Start (WSL2 + Docker + RTX 4070 Ti)
1) Install NVIDIA Container Toolkit and validate `--gpus all` works (see docs below).
2) From the repo root:
```bash
docker run --rm -it --gpus all -v "$PWD":/workspace -w /workspace python:3.10-slim \
  bash -lc "pip install -U pip && pip install -e . && python -m app diagnose"
```
If you see GPUs listed in `diagnose`, run:
```bash
docker run --rm -it --gpus all -v "$PWD":/workspace -w /workspace python:3.10-slim \
  bash -lc "pip install -U pip && pip install -e . && python -m app run --config configs/high.yaml"
```

## Commands
- `python -m app diagnose`
- `python -m app run --config configs/default.yaml`
- `python -m app plot --latest`
- `python -m app dashboard`

Makefile shortcuts:
- `make diagnose`, `make run`, `make plot`, `make dashboard`

## Outputs
Each run saves to `outputs/<timestamp>/`:
- `config.yaml` (snapshot)
- `summary.json` (metrics + environment + versions)
- `data/radio_map.npz` (path gain + derived metrics + cell centers)
- `data/radio_map.csv` (x, y, z, path_gain_db)
- `data/paths.csv` (delay + power + AoA per path)
- `data/ray_paths.csv` and `data/ray_paths.npz` (ray segments for 3D view)
- `plots/radio_map_path_gain_db.png/svg`
- `plots/radio_map_rx_power_dbm.png/svg`
- `plots/radio_map_path_loss_db.png/svg`
- `plots/scene.png` (rendered scene view)
- `plots/path_delay_hist.png/svg`
- `plots/aoa_azimuth_hist.png/svg`
- `plots/aoa_elevation_hist.png/svg`
- `plots/ray_paths_3d.png/svg`

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

Scene sources:
- Built-in: `scene.type: builtin` with `scene.builtin: etoile` (default)
- External: `scene.type: file` with `scene.file: path/to/scene.xml` (Mitsuba 3 format)
 - 3D Viewer mesh: `scene.mesh: path/to/scene.glb|gltf|obj` (optional)
 - Proxy geometry: `scene.proxy` (ground + boxes) for quick 3D previews
 - Dashboard mesh overrides: drop `.glb/.gltf/.obj` into `scenes/` and pick it in the sidebar
 - Built-in mesh export: `scene.export_mesh: true` exports PLY meshes for the 3D viewer

Visualization controls:
- `render.enabled`, `render.samples`, `render.resolution` control the optical scene render.
- `visualization.ray_paths.max_paths` controls how many RF paths are exported for 3D view.
 - Viewer output saved to `outputs/<timestamp>/viewer/index.html`

All configs include a placeholder:
```yaml
ris:
  enabled: false
```

## Project Notes
For operational notes, known quirks, and handoff context, see `PROJECT_CONTEXT.md`.

## Future RIS Extension (Not Implemented)
- Add a SceneObjectSpec implementation for RIS panels.
- Use `ris.enabled: true` to add RIS objects without refactoring the core pipeline.

## Documentation References (URLs + Versions)
Sionna / Sionna RT:
- Sionna Installation (v1.2.1): https://nvlabs.github.io/sionna/installation.html
- Sionna RT Overview (v1.2.1): https://nvlabs.github.io/sionna/rt/index.html
- Sionna RT Scene API (v1.2.1): https://nvlabs.github.io/sionna/rt/api/scene.html
- Sionna RT PathSolver API (v1.2.1): https://nvlabs.github.io/sionna/rt/api/paths_solvers.html
- Sionna RT Paths API (v1.2.1): https://nvlabs.github.io/sionna/rt/api/paths.html
- Sionna RT RadioMapSolver API (v1.2.1): https://nvlabs.github.io/sionna/rt/api/radio_map_solvers.html
- Sionna RT Radio Maps API (v1.2.1): https://nvlabs.github.io/sionna/rt/api/radio_maps.html
- Sionna RT Radio Devices API (v1.2.1): https://nvlabs.github.io/sionna/rt/api/radio_devices.html

Mitsuba / Dr.Jit:
- Mitsuba 3 docs (v3.6.0): https://mitsuba.readthedocs.io/en/latest/
- Mitsuba variants (v3.6.0): https://mitsuba.readthedocs.io/en/latest/src/key_topics/variants.html
- Mitsuba scene format (v3.6.0): https://mitsuba.readthedocs.io/en/latest/src/key_topics/scene_format.html
- Dr.Jit docs (no explicit doc version, used PyPI v1.2.0 for package pinning): https://drjit.readthedocs.io/en/latest/

TensorFlow:
- Install TensorFlow 2 docs (no explicit doc version, used PyPI v2.20.0 for package pinning): https://www.tensorflow.org/install

WSL2 + GPU:
- GPU accelerated ML training in WSL (ms.date 2024-11-19): https://learn.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute

NVIDIA Container Toolkit / Docker GPU:
- Install guide (Last-Modified 2025-12-02): https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
- Sample workload / `--gpus all` (Last-Modified 2025-12-02): https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/sample-workload.html

### Notes on doc-version mismatches
- TensorFlow and Dr.Jit docs do not publish explicit version numbers on the landing pages.
  For reproducibility, this repo records the **current PyPI versions** in `summary.json` and
  uses those versions in these references.
