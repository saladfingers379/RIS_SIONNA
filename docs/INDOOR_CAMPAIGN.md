# Indoor Campaign

## Mission

Build an indoor chamber campaign workflow in the simulator that reproduces the real RIS experiment as closely as possible while preserving the existing single-run indoor workflow.

The target outcome is a separate simulator tab that:

- reuses the indoor scene workflow and controls
- runs repeated chamber simulations across a steering or observation sweep, such as `-90` to `90` degrees in `2` degree steps
- accumulates results across all angles into one campaign dataset
- supports comparison between:
  - ideal model outputs from `/home/josh/Documents/Github/comparison`
  - implemented Sionna indoor simulation results
  - measured real-world chamber results

The campaign runner must be practical on the development machine:

- limited VRAM means jobs must run in chunks
- limited Linux disk space means output storage must be controllable
- experiments must be resumable rather than requiring one monolithic run

## High-Level Intent

This is not a RIS Lab replacement and not just a mathematical comparison tool.
It is an indoor scene driven chamber experiment runner built on top of the main simulator so that:

- the scene geometry matters
- radio maps and ray tracing matter
- RIS placement and steering matter
- experiment geometry matches the real setup as closely as possible

## Scope of the Indoor Campaign Tab

The indoor campaign tab is intended to:

- duplicate the existing Indoor tab baseline
- add batch controls for angular sweeps
- allow chunked execution
- preserve or compact outputs depending on the run mode
- aggregate campaign metrics
- prepare the pipeline for overlay plots against ideal and measured data

Core campaign controls include:

- start angle
- stop angle
- step angle
- sweep device
- pivot point
- radius
- chunk size
- resume behavior
- output preservation mode

## What Has Been Implemented So Far

### 1. Separate indoor-derived campaign workflow

A separate campaign flow was added in the simulator UI and backend so repeated indoor runs can be launched as a campaign instead of a single simulation.

Implemented areas:

- UI tab and campaign controls in `app/sim_web/`
- backend campaign job handling in `app/sim_jobs.py` and `app/sim_server.py`
- campaign execution and aggregation logic in `app/campaign.py`

### 2. Chunked execution for large sweeps

The campaign runner was designed to avoid trying to execute all `91` angles in one go.

Current design supports:

- max angles per job chunk
- incremental accumulation of results
- resumable operation

This is necessary because the target machine does not have unlimited VRAM and only has limited free Linux storage.

### 3. Chamber-specific baseline config

A chamber-specific simulator config was added:

- `configs/indoor_box_ieee_tap_chamber.yaml`

This preset is intended to anchor the campaign to the IEEE TAP paper geometry rather than generic indoor defaults.

Current chamber preset characteristics:

- chamber scene file: `scenes/anechoic_chamber_nofoam/scene.xml`
- paper-backed distances for Tx, RIS, and Rx geometry
- RIS physical size driven from the paper dimensions
- RIS amplitude set to match the intended hardware-style comparison basis
- Sionna configured to use continuous phase rather than `1-bit`

Important comparison intent:

- ideal model
- Sionna continuous-phase indoor scene
- real measured hardware behavior

### 4. Corrected room-side placement assumptions

The initial chamber mapping was placed on the wrong side of the room.

That was corrected by moving the chamber preset onto the correct side of the imported anechoic chamber scene after inspecting mesh bounds and room orientation. The campaign pivot was also aligned with the RIS position so the sweep geometry is anchored to the intended experimental setup.

### 5. Indoor profile wiring

The indoor simulator profile was rewired so the indoor chamber path uses the chamber-specific config instead of the older generic indoor box baseline.

Related UI work includes:

- chamber preset application button
- indoor profile label updated to reflect the chamber use case
- campaign defaults aligned with chamber sweep assumptions

### 6. Output retention changes

The first campaign implementation favored compact output and pruned per-angle artifacts.

That behavior was changed because the goal is not just a lightweight sweep summary. The campaign now defaults toward preserving per-angle outputs so the user can inspect full indoor results rather than only aggregate metrics.

### 7. Scene preview and campaign path preview work

Work has been started to make the setup visually inspectable before launching a run.

Implemented pieces include:

- backend endpoints to expose scene-file mesh manifests and scene assets
- client logic to load the chamber mesh directly from the source scene before a run completes
- a translucent campaign preview overlay showing the planned sweep path
- live updates when campaign geometry controls are changed

This work is meant to let the user verify:

- the chamber scene is the right one
- the RIS is on the correct side of the room
- the Rx sweep path is where it should be
- the experiment geometry looks correct before expensive runs are launched

## Current Known Gaps

The indoor campaign work is not fully complete yet.

Known gaps and open issues:

- the actual pre-run chamber scene is currently reported by the user as not loading in the UI
- the new scene preview likely requires the simulator server to be restarted so the new asset endpoints are available
- ideal-model overlay from `/home/josh/Documents/Github/comparison` is not yet the finished comparison workflow
- measured real-world dataset import and final overlay plots are not yet complete
- horn gain and exact hardware feed modeling are still approximate in the Sionna indoor path
- the full `91` angle campaign has not yet been fully signed off as the final experiment workflow

## Current Working Assumptions

At this stage the implementation assumes:

- the indoor campaign should be built from the Indoor tab, not RIS Lab
- the chamber geometry should be based on the IEEE TAP paper values where possible
- Sionna should remain continuous-phase so hardware quantization stays a real comparison difference
- campaign runs should be chunked by default
- the user needs visual confirmation of geometry before committing to a long run

## Immediate Next Steps

The next work items are:

1. finish and validate pre-run chamber scene loading in the UI
2. verify the translucent Rx campaign path matches the intended physical sweep
3. confirm Tx, Rx, and RIS geometry visually in the chamber scene
4. run a small verified campaign chunk
5. complete the ideal-model and measured-data comparison pipeline

## Relevant Files

- `configs/indoor_box_ieee_tap_chamber.yaml`
- `app/campaign.py`
- `app/sim_jobs.py`
- `app/sim_server.py`
- `app/sim_web/index.html`
- `app/sim_web/app.js`
- `tests/test_sim_scope.py`
- `tests/test_sim_server.py`

## Summary

The indoor campaign effort is aimed at turning the simulator into a chamber experiment runner that can be trusted for repeated comparison against ideal mathematics and measured RIS data.

The main infrastructure now exists:

- chamber-specific config
- campaign execution path
- chunked sweep handling
- output accumulation
- scene preview groundwork

The main short-term blocker is visual validation in the UI so the experiment geometry can be confirmed before launching large campaigns.
