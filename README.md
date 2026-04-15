# RIS_SIONNA

GPU-first Sionna RT simulator for 28 GHz propagation and RIS experiments. The repository combines reproducible CLI workflows, a lightweight browser UI, a CPU-based RIS Lab for validation work, and RT-side RIS synthesis tooling.

## Highlights

- Sionna RT simulation runs with saved plots, metrics, and viewer assets
- `python -m app diagnose` for explicit backend/runtime checks
- browser simulator UI via `python -m app sim`
- RIS Lab for pattern and link studies with reference validation
- RT-side RIS synthesis on a frozen coverage-map ROI
- test suite covering CLI, plotting, simulation, RIS, and UI job flows

## Platform Support

- Primary target: native Ubuntu 24.04 with NVIDIA GPU and CUDA/OptiX
- CPU-friendly preview runs: Linux and macOS
- WSL2: treat as CPU-only for this repo; GPU OptiX is not a supported target

The project is designed to make backend choice explicit. Use `python -m app diagnose` before claiming GPU RT is active.

## Installation

### CPU Preview

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
python -m app run --config configs/preview.yaml
```

### Ubuntu 24.04 + NVIDIA GPU

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-0.19.2.txt
pip install -e .
python -m app diagnose
python -m app run --config configs/high.yaml
```

Supported Python range is `>=3.10,<3.12`. The current runtime stack is pinned around `sionna==0.19.2` and `numpy==1.26.4`.

## Common Commands

```bash
python -m app diagnose
python -m app run --config configs/default.yaml
python -m app plot --latest
python -m app sim
python -m app ris run --config configs/ris/steer_1bit.yaml --mode pattern
python -m app ris validate --config configs/ris/validate_vs_csv.yaml --ref tests/fixtures/ris_validation_fixture.csv
python -m app ris-synth run --config configs/ris_synthesis_street_canyon.yaml
python -m pytest
```

Optional dashboard:

```bash
pip install -e ".[dashboard]"
python -m app dashboard
```

## Outputs

Simulation runs write to `outputs/<run_id>/` and typically include:

- `config.yaml`, `run.log`, `progress.json`, `summary.json`
- `data/` for numeric artifacts
- `plots/` for generated figures
- `viewer/` for simulator/browser assets

RIS Lab, RIS synthesis, and campaign workflows follow the same per-run output pattern with workflow-specific artifacts under the same run directory.

## Repository Layout

- `app/`: CLI, simulation pipeline, simulator server, plotting, RIS modules
- `configs/`: YAML presets for simulation, RIS Lab, RIS synthesis, and chamber runs
- `tests/`: regression and workflow coverage
- `scenes/`: Mitsuba/Sionna-compatible scene assets
- `docs/`: focused supporting documentation

## Documentation

- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for backend, CUDA, OptiX, and simulator troubleshooting
- [docs/RIS_SYNTHESIS_OPTIMIZATION.md](docs/RIS_SYNTHESIS_OPTIMIZATION.md) for the RT-side synthesis workflow and optimization method

## License

MIT
