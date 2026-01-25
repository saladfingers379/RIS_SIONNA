# RIS Integration Plan (Sionna RT v0.19.2)

This branch targets **Sionna RT v0.19.2** so that RIS objects are available.
The goal is to take the existing RIS Lab phase maps and apply them to a real
`sionna.rt.RIS` inside the scene with reproducible runs and clear validation.

## Current State (Implemented)
- `app/ris/ris_sionna.py` adapts RIS Lab phase maps to Sionna RIS.
- `app/scene.py` can attach RIS when `ris.enabled: true`.
- Demo script: `scripts/demo_ris_in_scene.py`.
- Configs: `configs/ris_lab_example.yaml`, `configs/ris_rt_demo.yaml`.
- CPU + GPU runs complete; GPU requires TF GPU runtime libs.

## Phase 0 — Backend Readiness (Mandatory)
Goal: ensure RT backend is CUDA/OptiX on GPU machines and no silent fallback.

Steps:
1) `python -m app diagnose --json`
2) Confirm:
   - `diagnose.runtime.selected_variant` includes `cuda`
   - `diagnose.verdict` is `RT backend is CUDA/OptiX`
   - `gpu_smoke_test.ok: true`
3) Ensure TensorFlow GPU is available when using CUDA Mitsuba variants.
   - If TF GPU is missing, CUDA RT will fail on DLPack transfer.
   - Fix by installing TF GPU runtime libs (CUDA 12.2 + cuDNN 8 for TF 2.15).

## Phase 1 — Stable RIS Creation (Scene Integration)
Goal: instantiate a `sionna.rt.RIS` with correct geometry and frequency.

Plan:
- Ensure scene frequency is set to 28 GHz before RIS creation.
- RIS config fields (in YAML):
  - `ris.enabled`, `ris.sionna.position`, `ris.sionna.num_rows/num_cols`,
    `ris.sionna.orientation` or `look_at`.
- Use Sionna’s expected RIS plane: **normal +x, grid on y/z**.

## Phase 2 — Phase/Amplitude Map Adapter
Goal: map RIS Lab phase maps onto `ris.phase_profile.values` and
`ris.amplitude_profile.values`.

Adapter rules:
- `phase_profile.values` shape: `[num_modes, num_rows, num_cols]`
- `amplitude_profile.values` shape: `[num_modes, num_rows, num_cols]`
- Ordering must match Sionna:
  - **top-to-bottom, left-to-right** in y-z plane
  - use `mapping.flip_rows/flip_cols` if needed

Artifacts:
- Store applied map snapshot in run logs and output folder.
- Record mapping parameters for reproducibility.

## Phase 3 — Validation Harness
Goal: show measurable effect of RIS ON vs OFF.

Minimal checks:
- Run RIS ON (steered) vs RIS OFF (flat phase).
- Compare total path gain (dB) or received power from paths.
- Record deltas in `summary.json`.

Optional:
- Add a test with a threshold once a stable delta is observed.

## Phase 4 — UI Integration
Goal: allow RIS configuration from simulator UI.

Plan:
- Add RIS controls in UI tab (select config, enable/disable).
- Surface RIS mapping fields and alignment warnings.
- Provide quick run button with RIS ON/OFF comparison.

## Phase 5 — Documentation + Repro
Goal: ensure users can reproduce RIS runs.

Docs to keep current:
- `README.md` (install + demo commands)
- `docs/TROUBLESHOOTING.md` (TF GPU + CUDA mismatch guidance)
- `docs/RT_BACKEND_AUDIT.md` (backend selection + 0.19.2 APIs)

## Key Files
- RIS adapter: `app/ris/ris_sionna.py`
- Scene integration: `app/scene.py`
- Demo: `scripts/demo_ris_in_scene.py`
- Demo config: `configs/ris_rt_demo.yaml`
