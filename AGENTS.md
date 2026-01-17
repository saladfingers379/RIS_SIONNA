# AGENTS.md — RIS_SIONNA (28 GHz Sionna baseline)

## Goal of this repo
Build a basic, reproducible Sionna simulation (no RIS yet) with:
- clean CLI UX (progress bars, clear logs)
- outputs saved per run (metrics + plots)
- optional lightweight web dashboard for visualization (must stay responsive)

## My environment
- Today: macOS (M4 Air). Must run CPU-only without pain.
- Main: Windows + WSL2 (Ubuntu) + RTX 4070 Ti + 64 GB RAM.
- Docker is allowed and preferred on WSL2 for reproducibility.
- GPU acceleration is optional; CPU fallback must always work.

## Documentation freshness requirement (non-negotiable)
Before using any Sionna / Sionna RT APIs:
- Look up the latest official docs and installation guides.
- Follow current docs over older examples.
- Cite exact doc pages (URLs) and versions in the README.

## Simulation scope (for now)
- Frequency: 28 GHz baseline.
- Start simple:
  - one Tx + one Rx
  - compute propagation paths / received power proxy
  - optional small radio map
- Do NOT implement RIS yet.
- Architect for future RIS:
  - config placeholder `ris: { enabled: false, ... }`
  - isolate scene objects so RIS can be added later without refactor.

## UX requirements
- Always show progress bars for heavy steps.
- Log milestones with timestamps.
- Save outputs under `outputs/<timestamp>/` including:
  - config snapshot
  - summary.json (metrics + environment + versions)
  - plots (PNG, preferably SVG)

## Responsiveness requirements
- If a dashboard exists, it must visualize saved outputs.
- Heavy compute must run out-of-band (never block UI).
- The dashboard must remain responsive at all times.

## Commands must be kept accurate
- `python -m app diagnose`
- `python -m app run --config configs/default.yaml`
- `python -m app plot --latest`
- `python -m app dashboard` (optional)
- `make run`, `make diagnose`, etc., if a Makefile exists

## Performance rules
- Use batching for radio-map sampling.
- Provide quality presets: preview / standard / high.
- Default to preview on Mac; allow scaling on PC.

