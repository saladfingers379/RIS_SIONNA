## Project Context and Idiosyncrasies

This document captures operational notes, known quirks, and handoff context so the project can be picked up later without surprises.

### Current Behavior
- The dashboard is visualization-only; run simulations from the CLI.
- 3D viewer is generated per run under `outputs/<timestamp>/viewer/index.html`.
- The 3D viewer uses a lightweight local HTTP server (spawned in the dashboard) to serve static assets.

### Performance Notes
- Built-in `etoile` scene is heavy on CPU. Preview runs can be slow unless you disable `scene.export_mesh` and `render.enabled`.
- Mesh export (`scene.export_mesh: true`) can be expensive on the first run. Meshes are cached under `outputs/_cache/`.
- Rays are drawn as `LineSegments` in the viewer for performance (no thickness slider).

### Known Quirks
- Sionna RT imports `pythreejs` even for CLI usage; this project stubs `pythreejs` on CLI runs to avoid long import hangs.
- TensorFlow import can hang on macOS; CLI skips TF import on macOS by default.
- Streamlit can appear to “hang” if port 8501 is already in use; CLI auto-picks a free port and prints it.

### Common Errors and Fixes
- `PlanarRadioMap` error about `center/orientation/size`:
  Ensure all three fields are set in the config when radio maps are enabled.
- Viewer errors (blank 3D view):
  Click "Regenerate viewer now" in the dashboard sidebar.
  Ensure `outputs/<run>/data/ray_paths.csv` exists.
- Missing ray path plots:
  Ensure `visualization.ray_paths.enabled: true` in the config.

### Where Things Live
- Outputs: `outputs/<timestamp>/`
- Mesh cache: `outputs/_cache/`
- Viewer assets: `outputs/<timestamp>/viewer/`
- Plots: `outputs/<timestamp>/plots/`
- Data: `outputs/<timestamp>/data/`

### Recommended Workflow
1. Run a simulation:
   `python -m app run --config configs/default.yaml`
2. Open dashboard:
   `python -m app dashboard`
3. If viewer is blank:
   Click "Regenerate viewer now" in the sidebar.

### Constraints to Remember
- Sionna 1.2.1 requires `numpy<2.0`; use Python 3.10–3.12.
- GPU acceleration is optional; CPU runs must always work.
- RIS is not implemented yet; keep `ris.enabled: false`.

