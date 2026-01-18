# AGENTS.md — RIS_SIONNA (Sionna RT digital-twin baseline @ 28 GHz)

## Goal of this repo
Build a trustworthy, reproducible Sionna / Sionna RT simulation tool (RIS later) with:
- accurate, documented use of Sionna RT APIs
- configurable experiments (YAML) runnable from CLI and UI
- report-ready outputs per run (metrics + plots + artifacts)
- a responsive UI/dashboard (visualization-first; compute runs out-of-band)
- a clear path toward “Omniverse-like” digital-twin workflows (scene realism, repeatable scenario packs)

## Current context / priorities
- We have fixed the coverage/heatmap alignment issues already (do not regress).
- We are continuing the Omniverse replication and development direction.
- Immediate focus:
  1) verify GPU acceleration is actually being used for heavy workloads
  2) test higher-compute-cost modes (bigger maps / more complex scenes) with good progress + logs
  3) keep accuracy and Sionna correctness as the highest priority

## Environment
Primary dev:
- Windows + WSL2 (Ubuntu) + RTX 4070 Ti (~12 GB VRAM) + 64 GB RAM.
- Docker allowed and preferred on WSL2 when it improves reproducibility (but do not force if repo is native-first).

Secondary dev:
- macOS (M4 Air) CPU-only: must remain able to run “preview” mode, but not the focus right now.

## Documentation freshness requirement (non-negotiable)
- Use Context7 MCP for up-to-date docs when touching Sionna/Sionna RT/Mitsuba/Dr.Jit/TensorFlow/WSL GPU setup.
- Follow current official docs over older examples.
- Cite exact doc pages (URLs) + versions in README or NOTES.md whenever changing simulation logic or backend selection.

## Accuracy & correctness rules (highest priority)
- Prefer Sionna RT built-in/idiomatic APIs for paths, coverage maps, and metrics.
- No “hand-rolled” RF physics unless validated against Sionna outputs or a reference.
- Maintain consistent coordinate frames and units end-to-end (scene → sampling grid → plotting → UI).
- Preserve the coverage/heatmap alignment fix and add a regression check (visual overlay and/or small validation test).

## Simulation scope (now)
Baseline:
- 28 GHz carrier frequency.
- Tx/Rx placement in a simple, documented scene.
- Compute: paths + received power/pathloss proxy.
- Coverage/radio map supported with batching.

High-compute testing (now required):
- Provide a benchmark/high-quality preset for GPU stress tests (larger grid + controlled complexity).
- Measure and record runtime + backend + key settings and write them into summary.json.

## GPU requirement (must be proven, not assumed)
- Implement/maintain `diagnose` to clearly show:
  - Sionna/Sionna RT version
  - Mitsuba/Dr.Jit variants available
  - selected backend variant (CUDA/OptiX vs CPU/LLVM)
  - a final verdict line:
    - ✅ RT backend is CUDA/OptiX
    - ⚠️ RT backend is CPU/LLVM (with actionable fix hints)
- During benchmarks, provide observable evidence of GPU usage (backend selection + utilization sampling best-effort).

## Experiments must be configurable
- No hard-coded “tests” as the primary interface.
- Experiments are defined via YAML configs in `configs/` with presets:
  - `preview.yaml` (CPU-friendly)
  - `default.yaml` (standard)
  - `high.yaml` (heavier)
  - `benchmark_gpu.yaml` (stress test)
- UI must allow selecting a config and adjusting safe parameters (quality preset, map bounds/resolution, batching).

## UX requirements
- Always show progress bars for heavy steps (scene build, tracing, map sampling, plotting).
- Log milestones with timestamps.
- Save outputs under `outputs/<run_id>/` including:
  - config snapshot (exact YAML used)
  - summary.json (metrics + environment + versions + backend)
  - plots (PNG and preferably SVG)
  - numeric artifacts (CSV/NPZ/Parquet as appropriate)

## Responsiveness requirements (UI)
- UI/dashboard must remain responsive at all times.
- Heavy compute must run out-of-band (separate process/background job).
- UI should visualize completed outputs and show live progress via log tail / progress.json / polling or SSE.
- Use Playwright MCP for basic UI smoke tests (launch UI, start run, ensure no freeze, plots load).

## Commands must be kept accurate
- `python -m app diagnose`
- `python -m app run --config configs/default.yaml`
- `python -m app run --config configs/benchmark_gpu.yaml` (or equivalent benchmark flag)
- `python -m app plot --latest`
- `python -m app dashboard` (if present)
- `make run`, `make diagnose`, etc., if a Makefile exists (keep aligned)

## Performance rules
- Use batching for radio-map sampling to avoid VRAM/RAM spikes.
- Cache expensive steps where sensible; avoid recomputation when only replotting.
- Keep preview defaults light; allow scaling up on GPU configs.

## Change discipline
- Prefer minimal diffs over rewrites unless correctness demands it.
- If changing core simulation logic, add/adjust a regression check and document how correctness was verified.
- Avoid adding dependencies unless necessary; pin versions and document why.
