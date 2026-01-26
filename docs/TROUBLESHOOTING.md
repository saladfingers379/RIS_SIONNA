# Troubleshooting

## Diagnose GPU Backend
Run:
```bash
python -m app diagnose
```
Expect:
- `diagnose.runtime.selected_variant` to include `cuda`
- `diagnose.verdict` to show `RT backend is CUDA/OptiX`

If you see `RT backend is CPU/LLVM`:
1) Confirm Sionna v0.19.2 is installed (`pip install sionna==0.19.2`).
   Source: https://github.com/NVlabs/sionna/releases/tag/v0.19.2
2) Ensure Mitsuba has CUDA variants available and selectable.
   Source: https://github.com/mitsuba-renderer/mitsuba3/blob/master/docs/src/key_topics/variants.rst
3) Verify `nvidia-smi` detects the GPU and the driver is installed.
4) Re-run `python -m app diagnose` and check `diagnose.runtime.mitsuba_variants`.

## CUDA Mitsuba Selected but TF GPU Missing
If `diagnose.runtime.selected_variant` is `cuda_*` but TensorFlow reports
`tensorflow_gpus: []`, Sionna RT will crash when transferring CUDA tensors
to TF (DLPack error like `GPU:0 unknown device`).

Fix:
- Install TF GPU runtime libraries matching your TF build.
  TF 2.15 expects CUDA 12.2 + cuDNN 8.
- Re-run `python -m app diagnose --json` and confirm TF sees a GPU.

## GPU Visible but No Utilization
- Run a high compute profile from the sim UI or CLI:
  ```bash
  python -m app run --config configs/high.yaml
  ```
- Check `summary.json` for `runtime.gpu_monitor.max_utilization_pct`.

## RIS Visible but No Radio Map Change
If RIS paths are detected but the radio map looks unchanged:
- Check `run.log` for `RIS paths detected: N` (N should be > 0).
- Check `summary.json` for `metrics.ris_path_gain_db` (should be finite when RIS paths are active).
- Ensure the radio map plane is near the Rx height. The default map is at `z=1.5`.
- Use the Simulator UI “Debug Boost + Center Map” button to:
  - place a large RIS on the same side of the RIS normal as Tx/Rx,
  - auto-aim toward Rx,
  - center the radio map at the Rx height.
- Compare against a baseline run (RIS off) using the diff toggle in the UI.
- For a RIS-only view, set `simulation.los: false` and `simulation.specular_reflection: false` in the config (e.g., `configs/ris_rt_demo.yaml`).
- If Tx/Rx are on opposite sides of the RIS normal, reradiation is disabled and the RIS acts as a blocker.
- The RIS model is passive; total gain improvements can be small unless the RIS is large/close
  or the direct path is weak. For a quick sanity check, disable LOS in the run
  and verify `ris_path_gain_db` is non-zero.

## OptiX Initialization Failed (Driver Version)
If `diagnose` reports `Could not initialize OptiX` or Dr.Jit warns about the driver,
upgrade/downgrade the NVIDIA driver to a supported range. Example warning:
`DrJit ... does not support OptiX with CUDA version 12.7 (driver 565-559).`

Recommended fix:
- Update driver to >= 570, or downgrade to < 565.

## TensorFlow GPU Not Detected
TensorFlow is only imported if enabled in `runtime.tensorflow_import`.
If you need TF visibility, set `tensorflow_import: force` in your config
and re-run `python -m app diagnose`.
