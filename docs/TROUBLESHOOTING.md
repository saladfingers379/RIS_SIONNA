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
1) Confirm Sionna RT is installed (`pip install sionna-rt`).
   Source: https://github.com/nvlabs/sionna-rt/blob/main/README.md
2) Ensure Mitsuba has CUDA variants available and selectable.
   Source: https://github.com/mitsuba-renderer/mitsuba3/blob/master/docs/src/key_topics/variants.rst
3) Verify `nvidia-smi` detects the GPU and the driver is installed.
4) Re-run `python -m app diagnose` and check `diagnose.runtime.mitsuba_variants`.

## GPU Visible but No Utilization
- Run the benchmark preset to create a sustained GPU load:
  ```bash
  python -m app run --config configs/benchmark_gpu.yaml
  ```
- Check `summary.json` for `runtime.gpu_monitor.max_utilization_pct`.

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
