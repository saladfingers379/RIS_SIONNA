# Channel Charting / UE Tracking (Sionna RT)

This document explains the Channel Charting (CC) pipeline added to RIS_SIONNA.

## Overview
The CC pipeline simulates a moving UE (Rx) or moving AP (Tx) in a Sionna RT scene, generates CSI over time, extracts channel-charting features, learns a low-dimensional embedding, smooths/filters the track, and evaluates alignment to the known ground truth trajectory.

### Key capabilities
- UE trajectories (straight, waypoints, smooth random walk, spiral)
- CSI generation (CFR via Paths.cfr when available, or CFR from a/tau fallback; CIR; Taps)
- Feature extraction (R2M/covariance-like, beamspace magnitude)
- Self-supervised charting model (autoencoder + temporal adjacency loss)
- Tracking/smoothing (EMA)
- Evaluation metrics (RMSE/MAE with Procrustes or affine alignment)
- Outputs with a manifest for UI rendering

## How it runs
The CC runner is implemented in `app/cc/runner.py` and can be invoked via CLI or the simulator UI.

### CLI
```bash
python -m app cc run --config configs/cc_indoor_quick.yaml
```

### Simulator UI
- Launch `python -m app sim`
- Open the **Channel Charting** tab
- Choose a preset or config file
- Adjust trajectory/CSI/features/model settings
- Run and view results
Note: if you want the YAML model params to apply, leave “Override model/training params” unchecked.

## Configuration
Channel charting config lives under `channel_charting:` in YAML configs. See presets:
- `configs/cc_indoor_quick.yaml`
- `configs/cc_wideband_mimo.yaml`
- `configs/cc_high_fidelity.yaml`

### Example
```yaml
channel_charting:
  enabled: true
  role: downlink
  trajectory:
    type: spiral
    num_steps: 100
    dt_s: 0.1
    spiral:
      center: [0.0, 0.0, 1.5]
      radius_start: 1.0
      radius_end: 10.0
      turns: 2.0
  csi:
    type: cfr
    ofdm:
      num_subcarriers: 64
      subcarrier_spacing_hz: 150e3
  features:
    type: r2m
    window: 3
    r2m:
      beamspace: true
      mode: diag
  model:
    type: autoencoder
    embedding_dim: 2
    hidden_dims: [128, 64]
    epochs: 200
    learning_rate: 1e-3
    adjacency_weight: 0.2
  tracking:
    enabled: true
    method: ema
    alpha: 0.2
  evaluation:
    align: affine
    dims: 2
```

### Role
- `downlink` (default): Tx fixed, Rx moves along trajectory
- `uplink`: Rx fixed, Tx moves along trajectory

## Trajectories
Implemented in `app/cc/trajectory.py`.

Types:
- `straight`: linear interpolation between `start` and `end`
- `waypoints`: polyline through `waypoints`
- `random_walk`: smoothed random walk
- `spiral`: expanding/contracting spiral

Example (random walk):
```yaml
trajectory:
  type: random_walk
  start: [0, 0, 1.5]
  num_steps: 200
  random_walk:
    step_std: 0.6
    smooth_alpha: 0.2
    drift: [0.0, 0.0, 0.0]
```

Example (spiral):
```yaml
trajectory:
  type: spiral
  num_steps: 120
  spiral:
    center: [0, 0, 1.5]
    radius_start: 1.0
    radius_end: 10.0
    turns: 2.5
```

## CSI generation
Implemented in `app/cc/csi.py`.

Modes:
- `cfr` (default): Frequency response at OFDM subcarriers
- `cir`: Channel impulse response
- `taps`: Discrete taps

Notes:
- For `sionna==0.19.2`, `Paths.cfr` is not available, so CFR is computed from `paths.a` and `paths.tau`.
- Shapes are normalized across time steps to prevent mismatched arrays when paths are missing.

## Feature extraction
Implemented in `app/cc/features.py`.

Options:
- `r2m`: covariance-like power features (diag or full)
- `beamspace_mag`: beamspace magnitude (FFT across antennas)

Common defaults:
```yaml
features:
  type: r2m
  window: 3
  r2m:
    beamspace: true
    mode: diag
```

## Model
Implemented in `app/cc/model.py`.

Currently supported:
- `autoencoder`: MLP encoder/decoder
- `dissimilarity_mds`: dissimilarity-metric charting (ADP cosine + MDS)

Loss:
- reconstruction + adjacency loss (temporal smoothness)

Key parameters:
```yaml
model:
  embedding_dim: 2
  hidden_dims: [128, 64]
  epochs: 200
  learning_rate: 1e-3
  adjacency_weight: 0.2
```

### Dissimilarity-metric charting
This option follows a dissimilarity-metric CC workflow and is useful when the autoencoder
does not produce stable 3D embeddings. It computes an Angular-Delay Profile (ADP) from
CSI, builds a cosine dissimilarity matrix, optionally fuses time, applies geodesic
shortest paths (kNN graph), then runs classical MDS to obtain chart coordinates.

```yaml
model:
  type: dissimilarity_mds
dissimilarity:
  metric: adp_cosine
  fuse_time: true
  time_window_s: 2.0
  time_weight: 0.35
  use_geodesic: true
  knn: 10
  max_taps: null
  dims: 3
```

3D plotting: when the embedding has 3 dimensions, charts render as 3D plots.

## Tracking / smoothing
Implemented in `app/cc/tracking.py`.

Currently supported:
- `ema`: exponential moving average

```yaml
tracking:
  enabled: true
  method: ema
  alpha: 0.2
```

## Evaluation
Implemented in `app/cc/eval.py`.

Alignments:
- `affine` (default): least-squares affine transform
- `procrustes`: similarity transform

Metrics:
- RMSE (meters)
- MAE (meters)

```yaml
evaluation:
  align: affine
  dims: 2
```

## Outputs
Each run writes to `outputs/<run_id>/`:

- `config.yaml` (snapshot)
- `summary.json`
- `manifest.json` (UI-friendly paths + arrays)
- `data/`:
  - `trajectory.csv`
  - `csi.npz`
  - `features.npz`
  - `chart.npz` and `chart_full.npz`
- `plots/`:
  - `chart_raw.png`
  - `chart_smoothed.png`
  - `chart_aligned.png`
  - `trajectory_compare.png`
  - `features.png`
  - `training_losses.png`

### Manifest fields (UI)
`manifest.json` includes inline arrays for `chart_coords`, `chart_coords_smoothed`, `chart_coords_aligned`, `ground_truth_coords`, timestamps, metrics, and plot paths.

## Troubleshooting
- **CFR errors on sionna 0.19.2**: CFR is computed from `paths.a` and `paths.tau` fallback; ensure `paths.compute_paths` returns valid paths.
- **No paths**: Increase `samples_per_src`, reduce `max_depth`, check scene scale/positions.
- **Chart looks rotated/offset**: use `evaluation.align: affine` for best visual alignment.
- **GPU vs CPU**: the runtime uses the same GPU-first logic as the main sim (`runtime.prefer_gpu` and `mitsuba_variant`).

## Files & Modules
- `app/cc/runner.py` — pipeline runner
- `app/cc/trajectory.py` — UE/Tx trajectory generator
- `app/cc/csi.py` — CSI computation
- `app/cc/features.py` — feature extraction
- `app/cc/model.py` — charting model
- `app/cc/tracking.py` — smoothing
- `app/cc/eval.py` — alignment + metrics
- `app/cc/plots.py` — chart/trajectory plots
