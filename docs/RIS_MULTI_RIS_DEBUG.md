# Multi-RIS Duplication Bug – Investigation Log

Date: 2026-02-04
Repo: RIS_SIONNA
Branch: legacy/sionna-0.19.2 (local)

## Summary
When multiple RIS objects are enabled simultaneously, they **behave as if they share a single RIS pattern**. Each RIS behaves correctly when run individually. With multiple RIS enabled, their patterns/behavior appear duplicated (one RIS dominates/gets applied to others). This occurs in coverage-map/heatmap and possibly compute_paths. Multiple attempts to isolate shared state in our adapter and to fix RIS ID mapping inside Sionna have **not resolved the duplication**.

## Expected Behavior
- Each RIS should compute its own phase profile based on its own position and its own incident/outgoing directions.
- Multiple RIS should **coexist** without sharing phase/amplitude data.
- When RIS1/2/3 are enabled together, each should contribute independently to the field and heatmap.

## Observed Behavior
- Individually, RIS1/2/3 behave correctly.
- Together, **all RIS seem to apply the same pattern** (duplication/crosstalk).
- The issue persists despite logging that per-RIS phase/amplitude profiles differ in memory.

## Diagnostic Evidence
From logs (example):
- RIS v_in/v_out vectors differ per RIS.
- Per-RIS phase stats differ.
- Per-RIS amplitude stats differ.
- Yet combined behavior still duplicates.

This suggests the **mixing occurs downstream** during solver application (likely in Sionna RT solver pipeline), not in RIS setup.

## Changes Made in RIS Adapter (app/ris/ris_sionna.py)
1. **Auto-aim logic**
   - Modified auto-aim to **only override sources/targets if not provided**.
2. **Deep copy per-RIS profile config**
   - Added `copy.deepcopy` for `profile` to avoid shared dict references.
3. **Per-RIS logging**
   - v_in / v_out / optional Tx gain
   - phase/amplitude signatures
   - phase/amplitude stats (min/mean/max)
   - per-RIS diff vs first RIS
4. **Per-RIS enable flag in UI**
   - Added `enabled` checkbox and backend skip of disabled RIS.

## Attempts to Fix in Sionna RT (local .venv patches)
> These are **local patches to the venv**, not upstream Sionna.

### 1) `solver_paths._ris_transition_matrices`
- Problem suspicion: `sc = concat(ris)` then `coef *= sc` might broadcast/mix.
- Patch: apply per-RIS coefficients **per slice** of cell indices.
- Result: **No fix** (duplication persists).

### 2) `solver_cm` RIS ID mapping (coverage map)
- Suspicion: RIS IDs from Mitsuba are mis-mapped → wrong RIS profile applied.
- Multiple iterations:
  - Mapping Mitsuba shape IDs → RIS object IDs
  - Remapping `primitives`
  - Fixing shape/broadcast errors
- Result: either crashes (shape mismatch) or **no change in duplication**.

### 3) `_ris_intersect` in `solver_base`
- Changed `_ris_intersect` to return an **explicit RIS index (0..N-1)**
  instead of Mitsuba shape IDs, to eliminate offsets and ambiguity.
- In `solver_cm`, mapped RIS index to `ris.object_id` directly.
- Result: **duplication persists**.

## Current Local Patch Diff Summary (by file)
### app/ris/ris_sionna.py
- Auto-aim conditional
- Deep copy profile
- Extensive per-RIS logging (v_in/v_out, signatures, diffs)
- Skip RIS when `enabled: false`

### app/sim_web/index.html + app/sim_web/app.js
- Per-RIS “Enabled” checkbox and payload support

### .venv/lib/python3.11/site-packages/sionna/rt/solver_paths.py
- `_ris_transition_matrices` per-RIS coefficient slicing

### .venv/lib/python3.11/site-packages/sionna/rt/solver_cm.py
- Reworked RIS ID mapping
- Fixes for TensorFlow shape errors

### .venv/lib/python3.11/site-packages/sionna/rt/solver_base.py
- `_ris_intersect` returns RIS index instead of Mitsuba shape ID

## Status
- **Bug persists**: Multi-RIS behavior still collapses to a single pattern.
- Individual RIS runs are correct.
- Evidence suggests the **mixing occurs inside Sionna’s solver** when combining RIS contributions, not in our adapter.

## Next Steps (Suggested)
1. Instrument inside Sionna RT solver with per-RIS `gamma` statistics at the exact point of application.
2. Compare the per-RIS `gamma` tensors used during path evaluation.
3. If confirmed, implement a **per-RIS path evaluation loop** (slow but correct) to isolate contribution and validate.
4. Consider reporting upstream to Sionna with a minimal reproducible case.

## Repro Notes
- Sionna version: **0.19.2**
- GPU: RTX 4070 Ti, `cuda_ad_rgb`
- Multiple RIS configured with `phase_gradient_reflector`, `auto_aim: true`.
- Issue occurs only when more than one RIS is enabled.
