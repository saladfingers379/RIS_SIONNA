# AGENTS.md — RIS_SIONNA
**Native Linux · GPU-first · Sionna RT baseline (28 GHz)**

---

## 0. HARD CONTEXT RESET (NON-NEGOTIABLE)

- We are running on **native Ubuntu 24.04**
- **NOT WSL**, **NOT Windows**
- Previous OptiX failures were caused by WSL shipping a stub `libnvoptix.so.1`
- That limitation is now gone

On this system:
- CUDA **must** work
- OptiX **must** work
- Sionna RT **must** be able to run on GPU

If GPU ray tracing fails here, it is a **misconfiguration**, not a platform limitation.

---

## 1. SYSTEM ENVIRONMENT (AUTHORITATIVE)

- OS: Ubuntu 24.04 (native install)
- GPU: NVIDIA RTX 4070 Ti (~12 GB VRAM)
- Driver: NVIDIA proprietary driver (≥ 570 recommended)
- CUDA: Driver-provided (do not install standalone CUDA unless required)
- Python: 3.10–3.12
- TensorFlow: 2.14–2.19
- RT stack:
  - Sionna RT
  - Mitsuba 3
  - Dr.Jit
  - OptiX (CUDA)

Assumptions:
- `/usr/lib/x86_64-linux-gnu/libnvoptix.so.1` is a **real OptiX runtime**
- No WSL shims
- No Windows compatibility layers

---

## 2. REPO CONTEXT

- Repo path: `~/Documents/Github/RIS_SIONNA`
- GitHub: https://github.com/saladfingers379/RIS_SIONNA.git
- Already fixed:
  - coverage / heatmap alignment (**DO NOT REGRESS**)
- Current interfaces:
  - CLI: `python -m app …`
  - Configs: YAML files under `configs/`

---

## 3. PRIMARY OBJECTIVES (ORDERED)

1. **Prove GPU usage** for Sionna RT (CUDA/OptiX, not CPU/LLVM)
2. Add a **repeatable high-compute benchmark mode**
3. Preserve **accuracy and Sionna-correct APIs**
4. Maintain good UX (progress bars, logs, responsive UI)
5. Keep a clean path toward **Omniverse-like digital-twin workflows**
   - RIS later (not now)

---

## 4. NON-NEGOTIABLE RULES

- Accuracy > speed
- Use **official Sionna RT APIs**
- Use Context7 for **current official documentation**
- GPU usage must be **explicitly proven**
- Outputs must be reproducible and saved under:
  - `outputs/<run_id>/`

---

## 5. PHASED WORK PLAN

### Phase 0 — Linux GPU validation (FIRST)

Before modifying simulation logic:

- Verify:
  - `nvidia-smi` works
  - CUDA visible in Python
  - OptiX symbols present
- Confirm:
  - Mitsuba CUDA variants are available
  - No WSL / Windows detection code remains

Document validated setup in:
- `README.md`
- `TROUBLESHOOTING.md`

---

### Phase A — Repo audit (fast)

Using filesystem MCP, identify:
- CLI entrypoints
- Where Sionna RT is initialized
- Where Mitsuba / Dr.Jit variants are selected
- Where scenes are built and loaded
- Where coverage / radio maps are sampled

Produce a short summary of:
- current backend selection logic
- clean insertion points for diagnostics

---

### Phase B — Definitive GPU diagnostics

Implement or harden:

#### `python -m app diagnose`

Must print:
- OS, kernel, Python
- NVIDIA driver version
- CUDA version
- Sionna version
- Sionna RT version
- Available Mitsuba variants
- Selected variant
- OptiX availability

Must end with **exactly one verdict**:
- ✅ `RT backend is CUDA/OptiX`
- ⚠️ `RT backend is CPU/LLVM` (with actionable fixes)

No silent fallback.

---

### Phase C — GPU smoke test

Add a minimal RT task that:
- forces GPU backend if available
- runs a tiny RT workload
- reports backend and timing

Purpose:
- sanity proof, not benchmarking

---

### Phase D — High-compute benchmark mode

Add or confirm:
- `configs/benchmark_gpu.yaml`

Benchmark requirements:
- stress GPU (large grids, batching)
- show progress and ETA
- record wall time
- write `summary.json` including:
  - backend
  - driver
  - CUDA
  - OptiX
  - config snapshot / hash

---

### Phase E — UI responsiveness (if UI exists)

- Heavy compute must run out-of-band
- UI must remain responsive
- Progress visible via logs or polling
- Use Playwright MCP for **basic smoke tests only**

---

### Phase F — Digital-twin roadmap (docs only)

Add a README section:
- current: Sionna RT scenes + configs
- next: structured scenario packs
- future: RIS + optimization

Do **not** implement GIS ingestion yet.

---

## 6. EXPLICIT EXCLUSIONS

- Do NOT implement RIS yet
- Do NOT revisit heatmap alignment unless broken
- Do NOT add CUDA hacks or `LD_PRELOAD`
- Do NOT accept CPU fallback for benchmarks

---

## 7. START HERE

1. Audit backend selection with filesystem MCP
2. Validate CUDA + OptiX on native Linux
3. Implement bulletproof diagnostics
4. Then proceed to benchmarks and UX polish
