# RIS Target Region Illumination Optimization

## Purpose

The Target Region Illumination routine optimizes the RIS phase profile so that a user-defined region on a 2D coverage-map plane receives as much energy as possible. In the current simulator UI, the user draws one or more rectangular ROI boxes on the seed run heatmap, and the optimizer searches for a RIS phase profile that improves radio-map performance inside those boxes.

The implementation lives mainly in:

- `app/ris/rt_synthesis.py`
- `app/ris/rt_synthesis_objective.py`
- `app/ris/rt_synthesis_binarize.py`
- `app/ris/rt_synthesis_phase_manifold.py`
- `app/ris/rt_synthesis_roi.py`

## High-Level Pipeline

The optimization pipeline is:

1. Load a seed RT configuration and build the scene.
2. Freeze a coverage-map plane from the realized seed run radio-map grid.
3. Convert the user ROI boxes into a binary mask on that frozen grid.
4. Evaluate the seed scene with RIS disabled (`RIS Off`).
5. Evaluate the seed scene with the original RIS profile (`Seed`).
6. Optimize a continuous RIS phase profile over the masked region.
7. Optionally project the continuous solution to a 1-bit profile.
8. Re-evaluate all variants on the same frozen grid.
9. Write plots, arrays, metrics, and promoted config snippets.

The key design choice is that the ROI mask is frozen on a single coverage-map grid and reused for every variant. This makes all comparisons directly comparable.

## Frozen ROI Grid

The optimizer does not define the ROI on arbitrary world coordinates and then resample later. Instead, it freezes a discrete set of coverage-map cells and keeps that set fixed throughout optimization.

Let the frozen radio-map grid have cell centers

$$
\mathbf{c}_{ij} = [u_{ij}, v_{ij}, z_{ij}],
$$

with indices $(i,j)$ over the 2D coverage map.

Each ROI box is defined by

$$
[u_{\min}, u_{\max}] \times [v_{\min}, v_{\max}].
$$

The binary ROI mask is then

$$
M_{ij} =
\begin{cases}
1, & \text{if } (u_{ij}, v_{ij}) \text{ lies inside at least one ROI box}, \\
0, & \text{otherwise.}
\end{cases}
$$

As of the current implementation, RIS synthesis first tries to freeze the plane from the realized seed run radio-map cell centers, not merely from the literal `radio_map.center` and `radio_map.size` stored in the config. This matters because the main simulator can auto-size the coverage map to the scene, so the realized grid can be larger than the raw config fallback.

If a realized seed radio map is unavailable, RIS synthesis falls back to the seed config and applies the same scene-bbox auto-size logic used by the main simulator.

## Optimization Objective

The objective used by the optimizer is the masked mean log path gain over the ROI:

$$
J(\phi) = \frac{1}{|M|} \sum_{(i,j) \in M} \log\left(g_{ij}(\phi) + \epsilon\right),
$$

where:

- $\phi$ is the RIS phase profile,
- $g_{ij}(\phi)$ is the linear path gain at coverage-map cell $(i,j)$,
- $|M|$ is the number of masked cells,
- $\epsilon$ is a small stabilizer to avoid $\log(0)$.

In the code this is implemented as `masked_mean_log_path_gain(...)`.

Two points are important:

- The optimization target is path gain, not the threshold-based coverage fraction.
- The ROI threshold in dBm is used only for reporting metrics, not as the optimization objective.

Since Tx power is fixed during a run, maximizing path gain is equivalent to maximizing received power up to a constant offset.

## Baseline Evaluations

Before optimizing the RIS, the pipeline computes:

### RIS Off

The scene is evaluated with RIS participation disabled in the coverage map. This gives a baseline radio map:

$$
g_{ij}^{\text{off}}.
$$

This map is also used to build the frozen ROI mask.

### Seed

The original RIS profile from the seed scene is evaluated next:

$$
g_{ij}^{\text{seed}}.
$$

This is the reference RIS-enabled solution before optimization.

## Default Continuous Optimization in the UI: Steering Search

The current Target Region Illumination UI submits

```yaml
parameterization:
  kind: steering_search
```

So the default optimization is not a generic gradient descent over every RIS element. It is a structured search over steering directions.

### Step 1: Estimate the ROI centroid

From the frozen ROI mask, the algorithm computes the centroid of all masked cells:

$$
\mathbf{c}_{\text{ROI}} = \frac{1}{|M|} \sum_{(i,j) \in M} \mathbf{c}_{ij}.
$$

This gives a representative target point for the region.

### Step 2: Build a baseline steering direction

If the RIS position is $\mathbf{p}_{\text{RIS}}$, then the baseline steering direction is

$$
\mathbf{d}_0 =
\frac{\mathbf{c}_{\text{ROI}} - \mathbf{p}_{\text{RIS}}}
{\left\lVert \mathbf{c}_{\text{ROI}} - \mathbf{p}_{\text{RIS}} \right\rVert}.
$$

The algorithm converts this direction into a baseline azimuth/elevation pair.

It also defines a steering radius

$$
r = \left\lVert \mathbf{c}_{\text{ROI}} - \mathbf{p}_{\text{RIS}} \right\rVert,
$$

so any candidate direction $(\alpha, \beta)$ corresponds to a target point

$$
\mathbf{p}_{\text{target}}(\alpha,\beta)
= \mathbf{p}_{\text{RIS}} + r \, \mathbf{d}(\alpha,\beta).
$$

### Step 3: Coarse search

The algorithm evaluates a grid of azimuth/elevation candidates around the baseline direction.

For each candidate:

1. The RIS is configured with Sionna's `phase_gradient_reflector(...)`.
2. A coverage map is generated.
3. The ROI objective $J(\phi)$ is evaluated.

The coarse search is intentionally cheaper than the final evaluation:

- The cell size is scaled up.
- The Monte Carlo sample count is scaled down.

This is controlled by:

- `coarse_cell_scale`
- `coarse_sample_scale`

### Step 4: Refine around the best coarse directions

The top-$K$ coarse candidates are selected, where $K = \texttt{refine_top_k}$.

Around each top candidate, a finer local azimuth/elevation grid is sampled and evaluated. This again uses a reduced-cost coverage map, but it is more precise than the coarse stage.

### Step 5: Final full-resolution evaluation

The best refined candidates are then re-evaluated on the full frozen coverage-map settings. The algorithm keeps whichever solution gives the highest ROI objective.

The seed solution is also kept as a valid candidate, so optimization never has to beat the seed by assumption; it only keeps the seed if the search does not find something better.

### Search Cost

If

- $N_a^{(c)}$ = coarse azimuth count,
- $N_e^{(c)}$ = coarse elevation count,
- $K$ = refine top-$K$,
- $N_a^{(r)}$ = refine azimuth count,
- $N_e^{(r)}$ = refine elevation count,

then the total number of steering evaluations is

$$
1 + N_a^{(c)} N_e^{(c)} + K N_a^{(r)} N_e^{(r)} + K.
$$

The leading `1` is the seed steering baseline.

## Alternative Continuous Optimization Modes in the Code

Although the UI currently uses `steering_search`, the backend also supports two more general continuous optimization modes.

### 1. `raw_phase`

This mode directly optimizes every RIS phase entry as a trainable TensorFlow variable and wraps the phase back into $[0,2\pi)$ after each update.

### 2. `smooth_residual`

This mode optimizes a smooth residual added to the unwrapped seed phase. The unwrapped continuous phase is modeled as

$$
\phi_{\text{unwrap}}(x,y)
= \phi_{\text{seed,unwrap}}(x,y)
  + \sum_{m=1}^{6} a_m b_m(x,y),
$$

where the quadratic basis functions are

$$
\{b_m\} = \{1, x, y, x^2, xy, y^2\}.
$$

The coordinates $(x,y)$ are normalized panel coordinates derived from RIS cell positions.

This parameterization dramatically reduces the number of free variables and biases the optimizer toward smooth phase fields.

### Gradient-Based Optimization

For `raw_phase` and `smooth_residual`, the optimizer uses Adam on the objective

$$
\max_{\theta} J(\phi(\theta)).
$$

In implementation, the code minimizes

$$
\mathcal{L}(\theta) = -J(\phi(\theta)).
$$

### Coordinate-Search Fallback

If the gradient becomes non-finite, the code falls back to a derivative-free coordinate search over the active parameter vector. This fallback perturbs one coefficient at a time, accepts improvements, and adapts the step size.

This makes the pipeline more robust when the differentiable path becomes numerically unstable.

## Optional 1-Bit Projection

After continuous optimization, the code can project the continuous phase to a binary RIS phase profile.

For 1-bit RIS control, the projected phases are in $\{0, \pi\}$.

The projection is not a naive pointwise threshold. Instead, it performs a global offset sweep:

$$
\phi_{1\text{-bit}}(\phi_0) = Q_1\left(\phi_{\text{cont}} + \phi_0\right),
$$

where:

- $\phi_{\text{cont}}$ is the continuous optimized phase,
- $\phi_0$ is a constant offset,
- $Q_1(\cdot)$ is 1-bit quantization.

The algorithm evaluates a set of candidate offsets and keeps the one with the largest ROI objective:

$$
\phi_0^\star = \arg\max_{\phi_0} J\left(\phi_{1\text{-bit}}(\phi_0)\right).
$$

This matters because a global phase offset can move many elements across the binary threshold together and substantially change the final binary pattern.

## Optional Greedy Bit-Flip Refinement

If enabled, the 1-bit result can be refined by a greedy local search:

1. Start from the best offset-sweep binary pattern.
2. Flip one candidate bit at a time.
3. Keep the best improving flip.
4. Repeat for a limited number of passes.

This is a small local combinatorial refinement around the best binary projection found by the offset sweep.

## Quantization to More Than 1 Bit

There is also a separate quantization path that starts from a saved continuous solution and projects it to $n$ bits:

$$
\phi_{n\text{-bit}}(\phi_0) = Q_n\left(\phi_{\text{cont}} + \phi_0\right).
$$

For $L = 2^n$ levels, the offset search only needs to scan one quantization period:

$$
\phi_0 \in \left[0, \frac{2\pi}{L}\right).
$$

The best offset is again chosen by maximizing the same ROI objective.

## Metrics Reported After Optimization

For each evaluated variant, the code reports ROI metrics such as:

- number of masked cells,
- mean path gain,
- mean received power,
- median received power,
- 5th percentile received power,
- 95th percentile received power,
- coverage fraction above the reporting threshold.

The main compared variants are:

- `ris_off`
- `seed`
- `continuous`
- `1bit` when enabled
- `quantized` in the separate quantization path

The code also reports deltas such as:

- continuous vs off,
- continuous vs seed,
- 1-bit vs continuous,
- quantized vs continuous.

## What the Optimizer Is Actually Doing

In plain terms, the optimizer is doing three things:

1. It freezes a specific set of coverage-map cells that define the target region.
2. It searches for a RIS phase profile that increases average log path gain over exactly those cells.
3. It then compares the optimized solution against the RIS-off and seed baselines on the same frozen grid.

So the method is not "maximize the best single point" and it is not "maximize whole-scene coverage." It is explicitly a region-based optimization over a user-selected subset of the radio map.

## Concise Pseudocode

```text
load seed scene
freeze realized coverage-map grid from seed run
build ROI mask from user boxes on that grid

evaluate RIS Off map
evaluate Seed RIS map

if parameterization.kind == steering_search:
    estimate ROI centroid
    coarse search over steering directions
    refine around top candidates
    re-evaluate finalists on full grid
    keep best continuous solution
else:
    build trainable phase parameterization
    optimize masked mean log path gain with Adam
    if gradients break:
        fall back to coordinate search

if 1-bit projection enabled:
    sweep global phase offset
    quantize to 1-bit
    optionally run greedy bit-flip refinement

re-evaluate final variants
write plots, arrays, metrics, and promoted configs
```

## Practical Interpretation

The current default UI path is best understood as a structured beam-steering search for the RIS, scored by the average log path gain inside the selected ROI. The more general gradient-based machinery also exists in the codebase, but the normal Target Region Illumination workflow currently uses the steering-search formulation because it is robust and interpretable.
