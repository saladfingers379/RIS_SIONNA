# AGENTS.md — RIS_SIONNA
**Native Ubuntu 24.04 · GPU-first (CUDA/OptiX) · Sionna RT baseline @ 28 GHz · RIS Lab (validation-first)**

---

## 0. HARD CONTEXT RESET (NON-NEGOTIABLE)

- Primary target: **native Ubuntu 24.04**
- GPU RT target: **CUDA + OptiX (real runtime)**
- WSL may exist as a *CPU-only dev shell*, but **GPU OptiX on WSL is unsupported/unstable** for this repo.
- Any GPU RT failure on native Ubuntu is treated as **misconfiguration**, not “platform limitation”.

This repo must never silently “looks fine” while running CPU/LLVM when a GPU is available.
If we fall back, we must say so loudly and explain why.

---

## 1. SYSTEM ENVIRONMENT (AUTHORITATIVE)

**Baseline assumptions for “GPU-first” work:**
- OS: Ubuntu 24.04 (native install)
- GPU: NVIDIA RTX-class (project dev box is 4070 Ti ~12 GB VRAM)
- NVIDIA driver: proprietary, modern (>= 570 recommended)
- OptiX runtime: present and real (not a stub)
- Python: 3.10–3.12
- Sionna pinned in `pyproject.toml` (currently `sionna==1.2.1`)
- NumPy pinned to stay compatible with Sionna (`numpy<2.0`)

RT stack:
- Sionna RT (via Sionna)
- Mitsuba 3
- Dr.Jit
- CUDA/OptiX backend

**Hard checks (required before claiming “GPU works”):**
- `nvidia-smi` works
- `python -m app diagnose` reports CUDA variant + OptiX symbols OK
- A GPU smoke test completes and logs backend + timing
- No silent backend fallback

---

## 2. REPO CONTEXT

- Repo path: `~/Documents/Github/RIS_SIONNA`
- Git remote: `https://github.com/saladfingers379/RIS_SIONNA.git`
- Core interfaces:
  - CLI: `python -m app …`
  - Config: YAML under `configs/`
  - Outputs: `outputs/<run_id>/` with `config.yaml`, `run.log`, `progress.json`, `summary.json`, `data/`, `plots/`, `viewer/`
  - Simulator UI: `python -m app sim` (stdlib HTTP server + background jobs)

Regression landmines:
- Coverage/heatmap alignment was previously fixed — **DO NOT REGRESS**.

Quality gates:
- **`python -m pytest`** must pass.

---

## 3. PRIMARY OBJECTIVES (ORDERED)

### Track A — Sionna RT baseline (GPU-first, stable)
1. Prove GPU usage for RT (CUDA/OptiX, not CPU/LLVM)
2. Provide repeatable GPU profiles (low/medium/high) without breaking CPU-only mode
3. Preserve correctness + official Sionna RT APIs
4. Maintain UX: progress, logs, responsive UI, clean outputs

### Track B — RIS Lab (validation-first, math-first)
5. Build a **RIS Lab** that lets us design/tune RIS behavior and validate against:
   - MATLAB reference exports (CSV required; NPZ optional; MAT stretch)
   - paper-style methodology (Tx fixed, Rx sweep; normalized patterns; optional link-mode)
6. Produce deterministic artifacts and regression tests so parity doesn’t rot
7. Keep a clean promotion path to later integrate validated RIS into the main pipeline

**Important boundary:** RIS Lab is *not* RT RIS integration.
It is a controlled, math-driven “RIS compositor / lab bench” that runs on CPU.

---

## 4. NON-NEGOTIABLE RULES

- Accuracy > speed
- Use **official Sionna RT APIs** (no undocumented hacks)
- GPU usage must be **explicitly proven** (diagnose + smoke)
- No silent fallback: if CPU/LLVM is used, print a single loud verdict + fixes
- Outputs must be reproducible and saved under `outputs/<run_id>/`
- Keep configuration-driven behavior (no magic constants in code)
- Never regress heatmap alignment

---

## 5. PHASED WORK PLAN

### Phase 0 — Native Linux GPU validation (FIRST, ALWAYS)
Before changing sim logic:
- Verify:
  - `nvidia-smi` OK
  - CUDA visible in Python
  - Mitsuba CUDA variants visible
  - OptiX symbols present
- Confirm:
  - no WSL/Windows shims are in play
- Document known-good setup in:
  - `README.md`
  - `docs/TROUBLESHOOTING.md`

Definition of done:
- `python -m app diagnose` ends with exactly one verdict:
  - ✅ `RT backend is CUDA/OptiX`
  - ⚠️ `RT backend is CPU/LLVM` (with actionable fixes)

---

### Phase A — Repo audit (fast)
Use filesystem tooling to identify:
- CLI entrypoints + command routing
- where Sionna RT is initialized
- where Mitsuba/Dr.Jit variants are selected
- scene build/load path
- radio-map sampling path
- job runner / UI polling path (`sim_jobs.py`, `sim_server.py`, `sim_web/`)

Deliverable:
- short summary of backend selection logic + insertion points for diagnostics + RIS Lab job type

---

### Phase B — Bulletproof GPU diagnostics
Harden `python -m app diagnose`:
Must print:
- OS / kernel, Python version
- NVIDIA driver (from `nvidia-smi` if available)
- Sionna version + key deps
- available Mitsuba variants
- selected variant
- OptiX availability (symbols/runtime)
- backend actually used for a tiny RT call

Must end with a single verdict line (see Phase 0).

No silent fallback.

---

### Phase C — GPU smoke test
Add/keep a minimal RT workload that:
- forces selection of GPU backend when available
- runs a tiny path/radiomap task
- reports backend + timing
- writes to `outputs/<run_id>/summary.json`

Purpose: proof, not benchmarking.

---

### Phase D — High-compute GPU profiles
Maintain or add:
- `configs/high.yaml` (GPU high)
- plus optional `gpu_low.yaml`, `gpu_medium.yaml`

Requirements:
- stress GPU meaningfully (grid size, batching)
- show progress + ETA
- record wall time
- write `summary.json` including backend, driver, variant, config snapshot/hash

CPU-only must still run via preview/default configs.

---

## 6. RIS LAB PLAN (VALIDATION-FIRST)

### Phase R1 — RIS core (math primitives)
Create `app/ris/` modules:
- geometry (element centers + frames)
- control synthesis (uniform / steer / focus / custom phase)
- quantization (none / 1-bit / 2-bit)
- pattern-mode runner (normalized pattern vs Rx sweep)
- artifacts writer (arrays + plots under outputs/<run_id>/)

Definition of done:
- CLI can run pattern-mode and produce required artifacts.

### Phase R2 — Validation harness
Implement reference import:
- CSV required
- NPZ optional
- MAT stretch (scipy optional dependency)

Metrics:
- RMSE (dB), peak angle error (deg), optional peak dB error
- PASS/FAIL summary written into run metrics

Definition of done:
- `python -m app ris validate ...` produces overlay plots + errors + PASS/FAIL.

### Phase R3 — UI integration (simulator tab)
Add a “RIS Lab” tab to simulator UI with sub-tabs:
- Config / Run / Results
- start runs via background jobs
- show progress/logs, render plots from outputs directory
- keep UI responsive

Definition of done:
- UI triggers RIS Lab job without blocking and can browse prior runs.

### Phase R4 — Promotion path (NOT RT integration)
Add a feature-flagged way to reuse validated RIS Lab configs in the main sim **as a compositor**.
(Still no Sionna RT RIS integration.)

---

## 7. EXPLICIT EXCLUSIONS (CURRENT SCOPE)

- No Sionna RT RIS integration yet (no ray-traced RIS scattering)
- No optimization / auto-tuning loops
- No GIS ingestion
- No CUDA hacks or `LD_PRELOAD`
- No pretending CPU fallback is acceptable for GPU profiles (fallback must be explicit + actionable)

---

## 8. START HERE (ORDERED)

1. Confirm Phase 0 on native Ubuntu (diagnose + smoke must be clean)
2. Audit backend selection + job runner insertion points (Phase A)
3. Build RIS Lab Phase R1 (pattern-mode + artifacts + tests)
4. Add validation (Phase R2)
5. Add simulator UI tab (Phase R3)
6. Only then consider compositor promotion (Phase R4)
