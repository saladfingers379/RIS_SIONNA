# RIS_SIONNA Simulator Summary

## Executive Summary

RIS_SIONNA is a bespoke simulation environment built around Sionna RT for 28 GHz propagation studies and RIS experimentation. It is not just a thin wrapper over an existing ray-tracing library. The project combines GPU-aware radio propagation, configuration-driven experiment control, reproducible artifact generation, a lightweight browser UI for long-running jobs, and a validation-oriented RIS Lab. The central reason for building custom tooling was that the underlying libraries provide the core physics and rendering primitives, but they do not by themselves provide the experiment-management, validation, diagnostics, geometry-handling, usability, reproducibility, and correctness safeguards needed for serious mmWave/RIS research.

At a high level, the simulator supports two major workflows. First, it runs Sionna RT simulations of line-of-sight and reflected paths, optionally computes radio maps, exports path metrics, plots, and viewer assets, and records structured metadata for later analysis. Second, it provides a CPU-based RIS Lab that treats RIS behaviour as a controlled mathematical model, allowing phase synthesis, quantisation, pattern generation, and validation against external references such as CSV exports. Together, these workflows make the repository more accurately described as a research simulator platform than as a single-purpose script.

## Core Purpose

The simulator was built to support repeatable, inspectable mmWave experiments in which scene geometry, transmitter and receiver placement, RIS configuration, sampling parameters, runtime backend, and post-processing artefacts are all explicitly controlled. This matters because mmWave simulation is unusually sensitive to geometry, wavelength-scale sampling effects, backend selection, and configuration drift. A generic notebook or one-off script can produce images, but it is much harder to prove what backend was used, reproduce the exact scene and sampling state, audit intermediate files, compare runs fairly, or integrate new research components without breaking prior behaviour.

The repository therefore treats simulation as an end-to-end pipeline rather than as a single function call. A run begins from a YAML configuration, is resolved into a scene and runtime state, executes path tracing and optional coverage-map computation, writes structured outputs under `outputs/<run_id>/`, generates plots and 3D viewer artefacts, and records summary metadata including timing, environment information, and configuration hashes. This design makes the simulator suitable for thesis work and reportable experiments because it preserves provenance and reduces ambiguity about how a result was produced.

## Main Simulator Architecture

The command-line interface exposes the platform through `python -m app`, with subcommands for propagation runs, plotting, environment diagnosis, the simulator UI, and RIS Lab actions. This means the simulator is organized as a consistent toolchain rather than a collection of disconnected scripts. The main propagation path is implemented in `app/simulate.py`, which loads configuration, applies tuning rules, selects the Mitsuba backend, configures TensorFlow, builds the scene, runs ray tracing, computes metrics, writes artifacts, and generates the viewer bundle. Scene construction is centralized in `app/scene.py`, allowing the project to support built-in scenes, imported file-based scenes, and procedural scenes through one interface. Job orchestration for the browser UI is handled by `app/sim_jobs.py`, while `app/sim_server.py` serves a lightweight HTTP interface and JSON APIs for runs, jobs, scenes, progress, and results.

This layered architecture is one of the main justifications for the bespoke tooling. Sionna RT provides scene objects and propagation operators, but it does not provide a full experiment platform with job submission, persistent run manifests, output browsing, configurable presets, viewer generation, or an integrated validation workflow. Those pieces had to be designed locally so that experiments could move beyond isolated scripting and become reproducible simulation studies.

## Scene Handling and Geometry Ingestion

The simulator supports multiple scene sources: built-in Sionna scenes, procedural scenes generated from configuration, and imported file scenes. Imported scenes are represented as Mitsuba `scene.xml` files that reference triangle meshes, typically `PLY` meshes. This choice allows the scene used by the propagation engine to be explicit and material-aware. The repository also separates the ray-tracing scene from optional viewer-only overlays, where formats such as `glb`, `gltf`, or `obj` can be used for visualization without changing the actual RT geometry. This distinction is important for research integrity because a visually loaded mesh is not necessarily the same as the geometry used in propagation.

This geometry handling is another place where bespoke tooling was necessary. Real environments, such as scanned chambers or imported site models, require cleaning, scaling, material separation, and a path into both the numerical engine and the visualization layer. The simulator therefore provides a controlled import path, mesh export for viewer use, scene caching, and a consistent output structure so that imported geometry can be audited and reused across runs. For report-writing purposes, this is a strong justification for custom infrastructure: without it, geometry ingestion would remain ad hoc, fragile, and difficult to validate.

## GPU-First Runtime Management and Diagnostics

One of the most important design choices in the project is that backend selection is treated as part of the experiment, not as an invisible implementation detail. The simulator can prefer GPU execution, force CPU execution, or use a selected Mitsuba variant, and it explicitly configures TensorFlow to match the chosen backend. It also includes environment diagnosis logic that inspects `nvidia-smi`, available Mitsuba variants, OptiX runtime symbols, TensorFlow GPU visibility, and a small smoke test before issuing a verdict about whether the RT backend is actually CUDA/OptiX or CPU/LLVM.

This is precisely the kind of functionality that justified bespoke tooling. In GPU-accelerated simulation, silent fallback is a major research risk: a run that appears successful can in fact be using the wrong backend, the wrong device, or a misconfigured dependency chain. If the backend is wrong, runtime measurements, feasibility claims, and even experiment scope become misleading. The custom `diagnose` path and backend-verification logic were therefore necessary to make the simulator defensible in a final report. They provide evidence that the runtime path was explicitly checked rather than assumed.

## Configuration, Tuning, and Experiment Reproducibility

The simulator is configuration-driven. YAML files define scene, runtime, simulation, rendering, radio map, output, and RIS parameters. The run pipeline snapshots configuration into the output directory, writes progress and summary JSON files, and records a configuration hash. This ensures that each result is associated with a concrete experiment definition rather than an implicit state in a notebook or interactive session.

On top of the base configuration layer, the repository implements domain-specific tuning logic for mmWave simulation. Similarity scaling can scale geometry and frequency together to control numerical aliasing while preserving electrical size. Sampling boost can increase radio-map resolution, ray counts, and path depth in a controlled way. VRAM guards can downscale certain workload parameters when GPU memory is limited. These are not generic software features; they are experiment controls created to handle the specific numerical and hardware behaviour of 28 GHz simulations. This is a strong justification for bespoke tooling because the raw ray-tracing engine does not know the experimental intent behind these tradeoffs.

## Radio Maps, Alignment, and Plotting

The simulator can compute coverage maps and radio maps and write the results as structured data files and plots. A particularly important local feature is radio-map grid alignment. The repository includes logic to align the radio-map grid to an anchor such as the RIS or transmitter so that cell placement does not accidentally skip or misrepresent critical near-source regions due to coarse discretization. The project also generates multiple plot styles, supports RIS-difference views, and exports ray-path visualizations.

This is a useful example of why bespoke tooling was needed even when an upstream propagation engine already existed. For research, it is not enough to compute a field; the field must be sampled on a grid that is stable and interpretable across runs. Heatmap alignment issues can look like physical effects when they are actually discretization artefacts. The local alignment logic and plotting conventions therefore address a real methodological problem, not just a convenience issue.

## RIS Support in the Main RT Pipeline

The repository supports RIS objects in the main scene path and exposes them through both configuration and the simulator UI. Users can place panels, control geometry mode, adjust size- or spacing-driven element layouts, and compare RIS-enabled and baseline runs. The simulator also records RIS-specific runtime metadata and can isolate RIS effects in some workflows.

However, the project does not treat RT RIS support as a solved problem supplied entirely by upstream tools. The repository contains explicit local patching for a multi-RIS coverage-map bug in Sionna RT, where per-RIS ray data could become mixed and multiple RIS panels could behave as if they shared a single pattern. The project therefore includes a targeted patch in `app/utils/sionna_patches.py` and integrates that patch during scene construction. This is a particularly strong justification for bespoke tooling in the final report: the research platform had to enforce correctness in the presence of upstream limitations, and it did so in a local, explicit, and reviewable manner.

## RIS Lab: Validation-First, Math-First Research Workflow

The RIS Lab is a separate but central part of the simulator. Rather than relying only on RT-integrated RIS behaviour, the RIS Lab provides a controlled mathematical environment for reflectarray-style RIS modelling. It supports geometry construction, element-center calculation, uniform and steering and focusing phase synthesis, quantisation, pattern-mode execution, link-mode execution, artifact writing, and validation against external references such as CSV, NPZ, and optionally MAT data.

This component exists because research on RIS often requires validation against theory, MATLAB outputs, or paper-style pattern sweeps before any full-scene integration is credible. A pure RT workflow is not enough for that. The RIS Lab therefore functions as a laboratory bench inside the simulator: it isolates the RIS model, makes pattern generation deterministic, records outputs systematically, and provides comparison metrics and overlay plots. In a final report, this is one of the clearest reasons the bespoke platform was necessary. The project needed a bridge between theoretical RIS design and scene-level propagation experiments, and that bridge did not exist in a ready-made form.

## User Interface and Job Management

The project includes a lightweight browser-based simulator UI served through the Python standard library, plus an optional Streamlit dashboard for visualization. The main browser UI supports scene selection, run submission, profile selection, RIS object editing, radio-map controls, job status, logs, and browsing of saved runs. It also contains a dedicated RIS Lab workflow. Long-running jobs are launched asynchronously, recorded by a local job manager, monitored in the background, and linked to output directories and logs.

This part of the system is important to justify because large RT runs are slow, parameter-heavy, and difficult to manage through repeated manual command execution. The bespoke UI and job system reduce operational friction while preserving reproducibility: users can inspect progress, logs, configuration state, and results without losing the discipline of run-based output directories. This is not cosmetic tooling; it is infrastructure that makes a research workflow manageable over many experiments.

## Output Discipline and Traceability

Each simulation run writes into `outputs/<run_id>/` and typically includes `config.yaml`, `run.log`, `progress.json`, `summary.json`, data files, plot files, and viewer artifacts. The diagnose path also writes a summary under the outputs tree. RIS Lab runs follow a similar discipline, writing structured outputs that can be re-opened by the UI or consumed by external analysis tools.

This output discipline is one of the biggest practical advantages of the bespoke toolchain. In research, figures and conclusions often outlive the interactive session that produced them. Without structured outputs and consistent manifests, it becomes hard to answer simple but essential questions such as which config produced a plot, whether a run used GPU or CPU, what scene geometry was active, or whether a result corresponded to a baseline or RIS-enabled condition. The local output conventions solve that problem.

## Why Off-the-Shelf Tooling Was Not Enough

The project needed bespoke tooling because the research problem sits at the intersection of several domains: GPU-accelerated ray tracing, mmWave experiment management, RIS modelling and validation, scene import and visualization, interactive parameter editing, and reproducible artifact generation. Sionna RT is powerful, but it is a lower-level simulation engine, not a complete experimental platform. It does not by itself give a thesis-ready workflow with backend-proof diagnostics, run manifests, output discipline, radio-map alignment safeguards, job orchestration, reference validation, geometry import conventions, browser-based experiment control, or local correctness patches for edge cases such as multi-RIS coverage-map behaviour.

In other words, the bespoke tooling was not built because an existing library was inadequate in principle; it was built because a serious research workflow requires many layers of infrastructure around the core solver. The custom code in this repository adds those layers and turns the underlying libraries into a usable and defensible simulator environment.

## Key Contributions of the Bespoke Tooling

The custom engineering contributions of the simulator can be summarized as follows. It provides a unified CLI and UI across propagation and RIS Lab. It turns simulation runs into structured, reproducible experiments with persistent outputs and metadata. It treats GPU backend verification as a first-class concern. It adds domain-specific controls for mmWave tuning, including similarity scaling and sampling boosts. It manages imported scenes and visualization assets in a consistent way. It implements radio-map alignment safeguards to avoid misleading discretization artefacts. It provides a validation-first RIS laboratory for theory-to-simulation comparison. It patches identified upstream correctness issues in a local and auditable way. It supports asynchronous job execution and progress tracking for long experiments.

## Limitations and Scope Boundaries

The simulator is still a research platform with explicit boundaries. Imported geometry must be cleaned and scaled correctly before use. Viewer overlays are distinct from RT geometry and must not be confused with the actual propagation scene. RIS Lab is a mathematical validation tool and should not be treated as identical to full RT RIS behaviour. Some functionality depends on specific backend and dependency compatibility, especially for GPU execution. Local patches improve correctness for known cases but also reflect the fact that some upstream solver paths require careful scrutiny. These limitations do not weaken the case for bespoke tooling; they reinforce it, because they show the need for explicit controls, validation, and documentation.

## Suggested Report Framing

For a final report, the simulator can be framed as a research-enabling software platform developed to bridge the gap between raw RT capability and a rigorous experimental workflow. A concise justification would be that existing libraries supplied the underlying propagation and rendering mechanisms, but bespoke tooling was required to make those mechanisms reliable, reproducible, inspectable, validation-friendly, and practical for iterative RIS experiments. That justification is supported by the project’s architecture, which couples solver access with diagnostics, scene management, output traceability, validation infrastructure, and UI orchestration in a single coherent environment.

## Checked Repository Context

This summary is based on the current repository implementation, including `README.md`, the CLI and runtime modules under `app/`, the simulator server and job manager, the RIS Lab modules under `app/ris/`, and supporting documentation under `docs/`. At the time of writing, the checked `pyproject.toml` pins `sionna==0.19.2`; if the dependency stack is upgraded later, the architectural and methodological arguments in this summary remain valid even if some implementation details change.
