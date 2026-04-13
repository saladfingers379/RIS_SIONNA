# RIS Synthesis Plan

## Project Context

- Repo: `RIS_SIONNA`
- Primary environment: native Ubuntu 24.04, NVIDIA GPU, Sionna RT `0.19.2` baseline, 28 GHz workflows
- Existing architecture already includes:
  - RT simulation pipeline: `app/simulate.py`
  - scene construction and RIS scene integration: `app/scene.py`, `app/ris/ris_sionna.py`
  - analytical RIS Lab: `app/ris/ris_lab.py`
  - simulator UI: `app/sim_web/index.html`, `app/sim_web/app.js`
  - background job system: `app/sim_jobs.py`, `app/sim_server.py`
- Existing non-negotiables:
  - preserve the coverage/heatmap alignment fix
  - keep configuration-driven behavior
  - save reproducible outputs under `outputs/<run_id>/`
  - do not blur analytical RIS Lab and RT-side RIS features into one codepath

## Feature Summary

Add a new top-level simulator workflow called `RIS Synthesis` for gradient-guided synthesis of a realizable 1-bit RIS from a continuous-phase optimized RIS solution using Sionna RT.

The first target workflow is:

- seed scene: `configs/ris_doc_street_canyon.yaml`
- user defines one or more axis-aligned rectangular target boxes
- boxes are defined on the existing coverage-map plane
- the plane is floor-aligned and matches the active coverage-map plane exactly
- the ROI mask is frozen once at run start
- optimize continuous phase first
- project to 1-bit using the repo's quantization logic plus a global phase-offset sweep
- optionally refine later with greedy bit flips
- compare `RIS-off`, continuous, and 1-bit results on the exact same frozen ROI

## Locked Design Decisions

### 1. UI Placement

This feature gets its own main tab:

- `RIS Synthesis`

It should not be added as another action inside the current analytical `RIS Lab` tab.

Reason:

- the current RIS Lab code is an analytical CPU-side bench
- this feature is RT-side, iterative, and tied to Sionna RT scene execution
- a dedicated tab keeps the workflow, artifacts, and job type clean

### 2. Target Region Definition

The target region is defined:

- on the coverage-map plane
- aligned with the floor
- via manually drawn axis-aligned rectangles in plane coordinates

The optimization target is the union of those boxes rasterized to the coverage-map grid.

The target region must not be recomputed during optimization.

Optional future helper:

- auto-suggest shadow region from the `RIS-off` baseline map

But even that helper should produce a fixed mask once, then freeze it.

### 3. Objective

Primary optimization objective for v1:

- maximize `mean(log(path_gain_linear + eps))` over masked cells

Secondary reported metrics:

- mean Rx power over ROI
- median Rx power over ROI
- 5th percentile Rx power over ROI
- coverage fraction above threshold
- delta versus `RIS-off`
- delta versus continuous after 1-bit projection

### 4. 1-Bit Projection

Do not use plain nearest rounding only.

Use:

- global phase-offset sweep over `[0, pi)`
- quantize `phi_cont + delta` to 1-bit
- evaluate the same ROI objective for each candidate
- keep the best 1-bit result

### 5. Refinement

Not required for the first complete implementation.

If added later:

- bounded greedy bit flips
- disabled by default

## High-Level Architecture

Create a new RT-specific backend under `app/ris/`.

Do not extend `app/ris/ris_lab.py` for this feature.

New module family:

- `app/ris/rt_synthesis.py`
- `app/ris/rt_synthesis_config.py`
- `app/ris/rt_synthesis_roi.py`
- `app/ris/rt_synthesis_objective.py`
- `app/ris/rt_synthesis_binarize.py`
- `app/ris/rt_synthesis_artifacts.py`

This backend should reuse:

- scene construction from `app/scene.py`
- existing RIS scene/profile behavior from `app/ris/ris_sionna.py`
- output conventions from `app/simulate.py`
- quantization semantics from `app/ris/ris_core.py`

## Proposed Config Schema

Suggested new config:

- `configs/ris_synthesis_street_canyon.yaml`

Suggested shape:

```yaml
schema_version: 1

seed:
  type: config
  config_path: configs/ris_doc_street_canyon.yaml
  ris_name: ris

target_region:
  plane: coverage_map
  boxes:
    - name: roi_1
      u_min_m: 6.0
      u_max_m: 16.0
      v_min_m: -3.0
      v_max_m: 3.0
  freeze_mask: true

objective:
  kind: mean_log_path_gain
  eps: 1.0e-12
  threshold_dbm: -90.0
  temperature_db: 2.0

optimizer:
  iterations: 150
  learning_rate: 0.03
  algorithm: adam
  log_every: 5

binarization:
  enabled: true
  method: global_offset_sweep
  num_offset_samples: 181

refinement:
  enabled: false
  method: greedy_flip
  candidate_budget: 64
  max_passes: 1

evaluation:
  dense_map:
    enabled: true
    cell_size: [0.1, 0.1]

output:
  base_dir: outputs
```

## Experiment Flow

1. Load the synthesis config.
2. Load the seed RT config from `seed.config_path`.
3. Build the scene through the normal RT path.
4. Identify the named RIS object from `seed.ris_name`.
5. Read the existing coverage-map plane from the seed config.
6. Run a baseline `RIS-off` evaluation on that plane.
7. Convert ROI boxes into a fixed binary mask on the plane grid.
8. Optimize continuous RIS phase against the fixed ROI objective.
9. Save the continuous optimized phase.
10. Project the continuous phase into 1-bit via offset sweep.
11. Optionally refine the 1-bit pattern later.
12. Evaluate `RIS-off`, continuous, and 1-bit variants on the same plane and same mask.
13. Save artifacts, plots, metrics, and replayable manual profile data.

## File-By-File Implementation Checklist

### New Backend Files

#### `app/ris/rt_synthesis_config.py`

Responsibilities:

- define defaults
- validate config structure
- snapshot config and summary metadata
- create output directory like existing RIS Lab config helpers

Functions:

- `resolve_ris_synthesis_config(raw_config: dict) -> dict`
- `load_ris_synthesis_config(path: str | Path) -> dict`
- `compute_ris_synthesis_config_hash(config: dict) -> str`
- `resolve_and_snapshot_ris_synthesis_config(config_path, output_dir=None) -> tuple[dict, Path, dict]`

Implementation notes:

- mirror the style of `app/ris/ris_config.py`
- keep schema separate from RIS Lab schema

#### `app/ris/rt_synthesis_roi.py`

Responsibilities:

- interpret ROI rectangles on the coverage-map plane
- rasterize them into a fixed mask
- generate overlay metadata for plotting

Functions:

- `coverage_plane_metadata_from_seed_cfg(seed_cfg: dict) -> dict`
- `build_target_mask_from_boxes(center, size, cell_size, boxes) -> np.ndarray`
- `boxes_to_overlay_polygons(...) -> list[dict]`

Implementation notes:

- use plane-local coordinates only
- do not introduce free 3D ROI geometry for v1

#### `app/ris/rt_synthesis_objective.py`

Responsibilities:

- objective computation on a masked plane
- reusable metric helpers for summaries and plots

Functions:

- `masked_mean_log_path_gain(path_gain_linear, mask, eps) -> float`
- `masked_soft_coverage(rx_power_dbm, mask, threshold_dbm, temperature_db) -> float`
- `compute_roi_metrics(path_gain_db, rx_power_dbm, mask, threshold_dbm) -> dict`

Implementation notes:

- v1 should implement `mean_log_path_gain` first
- keep `soft_coverage` available as an optional extension point

#### `app/ris/rt_synthesis_binarize.py`

Responsibilities:

- convert optimized continuous phase to 1-bit
- optional local refinement

Functions:

- `project_1bit_offset_sweep(phase_continuous, scorer, num_offset_samples) -> dict`
- `greedy_flip_refine(bits, scorer, candidate_budget, max_passes) -> dict`

Implementation notes:

- use existing 1-bit quantization semantics from `app/ris/ris_core.py`
- do not rely on naive direct rounding only

#### `app/ris/rt_synthesis_artifacts.py`

Responsibilities:

- save arrays, CSVs, plots, summaries
- keep outputs consistent with repo conventions

Functions:

- `write_target_region_artifacts(...)`
- `write_phase_artifacts(...)`
- `write_objective_trace(...)`
- `write_eval_artifacts(...)`
- `write_summary(...)`

Implementation notes:

- save both numeric and visual artifacts
- save replayable manual phase arrays

#### `app/ris/rt_synthesis.py`

Responsibilities:

- orchestrate the full workflow
- update progress
- call RT evaluation routines

Main entrypoint:

- `run_ris_synthesis(config_path: str) -> Path`

Suggested internal helpers:

- `_load_seed_rt_config(...)`
- `_resolve_target_mask(...)`
- `_evaluate_variant(...)`
- `_optimize_continuous_phase(...)`
- `_project_to_1bit(...)`
- `_write_final_outputs(...)`

Implementation notes:

- reuse existing scene/RT helpers instead of cloning the entire `run_simulation()` body
- keep the codepath explicit about `RIS-off` versus active RIS profiles

### Existing Files To Update

#### `app/cli.py`

Add a new top-level command:

- `python -m app ris-synth run --config <yaml>`

This command should dispatch into `app.ris.rt_synthesis.run_ris_synthesis`.

#### `app/sim_jobs.py`

Add a new job kind:

- `ris_synthesis`

Add:

- `_create_ris_synthesis_job(payload: Dict[str, Any]) -> Dict[str, Any]`

Behavior:

- accept either config path or inline config data
- create `job_config.yaml`
- launch `python -m app ris-synth run --config ...`
- follow existing job conventions

#### `app/sim_server.py`

Add API routes:

- `GET /api/ris-synth/jobs`
- `GET /api/ris-synth/jobs/<job_id>`
- `POST /api/ris-synth/jobs`

Keep behavior parallel to existing `ris_lab` and `link_level` job APIs.

#### `app/sim_web/index.html`

Add a new main tab button:

- `RIS Synthesis`

Add a new panel:

- `data-main-tab="ris-synth"`

Suggested UI sections:

- seed scene/config
- RIS selection
- coverage-plane ROI editor
- optimization controls
- binarization controls
- refinement controls
- job list/status/logs
- run selector/results
- plot tabs

#### `app/sim_web/app.js`

Add:

- UI element bindings for the new tab
- state bucket for `risSynthesis`
- config builder for synthesis jobs
- submit job logic
- polling for `ris_synthesis` jobs
- plot tab handling

Suggested plot tabs:

- ROI Overlay
- RIS-Off
- Continuous
- 1-Bit
- Continuous vs Off
- 1-Bit vs Off
- 1-Bit vs Continuous
- Objective Trace
- Phase Continuous
- Phase 1-Bit

#### `README.md`

Document:

- what RIS Synthesis is
- how to run it from CLI
- where outputs go
- how it differs from RIS Lab

#### `docs/SIMULATOR_SUMMARY.md`

Document:

- new main tab
- new job kind
- new outputs

### New Config File

#### `configs/ris_synthesis_street_canyon.yaml`

Purpose:

- example v1 synthesis config
- references the simple street-canyon seed scene

### New Tests

#### `tests/test_ris_synthesis_config.py`

Cover:

- required fields
- defaults
- config snapshot output

#### `tests/test_ris_synthesis_roi.py`

Cover:

- ROI box rasterization
- union of multiple boxes
- bounds clipping

#### `tests/test_ris_synthesis_binarize.py`

Cover:

- offset sweep chooses the best candidate under a mock scorer
- greedy flip refinement improves or preserves the score

#### `tests/test_ris_synthesis_jobs.py`

Cover:

- job creation writes expected files
- job launcher command is correct

#### Optional `tests/test_ris_synthesis_smoke.py`

Cover:

- minimal RT-side smoke path if `sionna.rt` is available

Pattern:

- use the same `skipif` approach already used in RT smoke tests

## Output Contract

Each run should write:

- `config.yaml`
- `summary.json`
- `metrics.json`
- `progress.json`
- `job.json` when launched via simulator
- `data/target_boxes.json`
- `data/target_mask.npy`
- `data/phase_continuous.npy`
- `data/phase_1bit.npy`
- `data/bits_1bit.npy`
- `data/objective_trace.csv`
- `data/offset_sweep.csv`
- `data/manual_profile_phase.npy`
- `data/eval_ris_off.npz`
- `data/eval_continuous.npz`
- `data/eval_1bit.npz`
- `data/eval_1bit_refined.npz` if refinement is enabled
- `plots/target_region_overlay.png`
- `plots/objective_trace.png`
- `plots/phase_continuous.png`
- `plots/phase_1bit.png`
- `plots/radio_map_ris_off.png`
- `plots/radio_map_continuous.png`
- `plots/radio_map_1bit.png`
- `plots/radio_map_diff_continuous_vs_off.png`
- `plots/radio_map_diff_1bit_vs_off.png`
- `plots/radio_map_diff_1bit_vs_continuous.png`
- `plots/cdf_roi_rx_power.png`

## Minimum Viable Version

V1 should include:

- new `RIS Synthesis` tab
- new CLI command
- new background job kind
- single seed scene: street canyon
- single named RIS
- manual ROI boxes on the coverage-map plane
- fixed ROI mask
- continuous optimization
- 1-bit offset-sweep projection
- outputs and plots
- tests for config, ROI, binarization, jobs

V1 should not require:

- multi-RIS optimization
- automatic shadow-region detection
- GA-based refinement
- arbitrary 3D ROI volumes

## Recommended Implementation Order

1. Add synthesis config module and example config.
2. Add ROI plane-mask utilities.
3. Add objective and binarization modules.
4. Add top-level RT synthesis runner.
5. Wire CLI command.
6. Add job manager and server support.
7. Add new `RIS Synthesis` UI tab.
8. Add plots/artifacts polish.
9. Add tests.
10. Update docs.

## Risks and Guardrails

### Coverage-Map Alignment Risk

- The repo already fixed heatmap/coverage alignment.
- Do not introduce a second coordinate convention for ROI boxes.
- The mask must be built from the exact coverage-plane metadata used for evaluation.

### RT/Analytical Boundary Risk

- Do not mix this implementation into `app/ris/ris_lab.py`.
- Do not use analytical RIS Lab geometry as the truth source for the synthesis workflow.

### Replayability Risk

- Save explicit manual phase arrays for the final continuous and 1-bit results.
- Do not depend on recreating them only from high-level steering parameters.

### Scope Risk

- Keep v1 on one scene, one plane, one ROI type, one main objective.
- Add refinement only after the baseline pipeline is stable.

## Fresh Codex Handoff Prompt

```text
Implement the RIS Synthesis feature described in docs/RIS_SYNTHESIS_PLAN.md.

Repo: /home/josh/Documents/Github/RIS_SIONNA

You must read and follow:
- AGENTS.md
- PROJECT_CONTEXT.md
- docs/RIS_SYNTHESIS_PLAN.md

Feature summary:
- Add a new top-level simulator tab: RIS Synthesis
- Add a new RT-specific backend for gradient-guided synthesis of a 1-bit RIS from a continuous optimized RIS
- Use the simple street-canyon seed scene:
  - configs/ris_doc_street_canyon.yaml
- The target region is defined by user-drawn axis-aligned boxes on the existing coverage-map plane
- The plane is floor-aligned and exactly the coverage-map plane
- The ROI mask is frozen once per run
- Optimize continuous phase first
- Project to 1-bit via global phase-offset sweep
- Compare RIS-off, continuous, and 1-bit on the same frozen ROI

Hard constraints:
- Do not implement this inside app/ris/ris_lab.py
- Preserve the coverage-map alignment fix
- Reuse existing scene/RIS/RT architecture where possible
- Save reproducible outputs under outputs/<run_id>/
- Keep changes focused and coherent

Required new files:
- app/ris/rt_synthesis.py
- app/ris/rt_synthesis_config.py
- app/ris/rt_synthesis_roi.py
- app/ris/rt_synthesis_objective.py
- app/ris/rt_synthesis_binarize.py
- app/ris/rt_synthesis_artifacts.py
- configs/ris_synthesis_street_canyon.yaml
- tests/test_ris_synthesis_config.py
- tests/test_ris_synthesis_roi.py
- tests/test_ris_synthesis_binarize.py
- tests/test_ris_synthesis_jobs.py

Required updates:
- app/cli.py
- app/sim_jobs.py
- app/sim_server.py
- app/sim_web/index.html
- app/sim_web/app.js
- README.md
- docs/SIMULATOR_SUMMARY.md

Implementation priorities:
1. backend config + ROI + objective + binarization
2. RT synthesis runner
3. CLI wiring
4. job/server wiring
5. UI tab
6. tests/docs

Primary optimization objective:
- mean(log(path_gain_linear + eps)) over the ROI mask

1-bit projection:
- do not use naive nearest rounding only
- use offset sweep over [0, pi)
- quantize each candidate using existing 1-bit semantics
- keep the best scoring candidate

Outputs must include:
- config.yaml
- summary.json
- metrics.json
- progress.json
- data/target_boxes.json
- data/target_mask.npy
- data/phase_continuous.npy
- data/phase_1bit.npy
- data/bits_1bit.npy
- data/objective_trace.csv
- data/offset_sweep.csv
- data/eval_ris_off.npz
- data/eval_continuous.npz
- data/eval_1bit.npz
- plots for ROI overlay, phase maps, eval maps, diffs, and objective trace

Testing:
- python -m pytest must pass
- if Sionna RT is not available, guard smoke tests the same way existing RT tests are guarded

Do the implementation end-to-end. Do not stop after planning.
```
