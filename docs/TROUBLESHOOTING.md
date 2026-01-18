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
   Source: https://mitsuba.readthedocs.io/en/stable/src/key_topics/variants.html#choosing-variants
3) Verify `nvidia-smi` detects the GPU and the driver is installed.
4) Re-run `python -m app diagnose` and check `diagnose.runtime.mitsuba_variants`.

## GPU Visible but No Utilization
- Run the benchmark preset to create a sustained GPU load:
  ```bash
  python -m app run --config configs/benchmark_gpu.yaml
  ```
- Check `summary.json` for `runtime.gpu_monitor.max_utilization_pct`.

## WSL: CUDA Driver Library Mismatch
If `nvidia-smi` works but Mitsuba reports `no CUDA-capable device is detected`,
WSL may be loading the Linux libcuda instead of the WSL shim.

Fix by ensuring `/usr/lib/wsl/lib` is first in `LD_LIBRARY_PATH`:
```bash
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH
python -m app diagnose
```
If that resolves the issue, make the change permanent in your shell profile and restart your shell.

## OptiX Initialization Failed (Driver Version)
If `diagnose` reports `Could not initialize OptiX` or Dr.Jit warns about the driver,
upgrade/downgrade the NVIDIA driver to a supported range. Example warning:
`DrJit ... does not support OptiX with CUDA version 12.7 (driver 565-559).`

Recommended fix:
- Update driver to >= 570, or downgrade to < 565.
 - Reboot Windows, then restart WSL (`wsl --shutdown`) before retrying.

## TensorFlow GPU Not Detected
TensorFlow is only imported if enabled in `runtime.tensorflow_import`.
If you need TF visibility, set `tensorflow_import: force` in your config
and re-run `python -m app diagnose`.
