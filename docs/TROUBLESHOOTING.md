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
  In the Simulator UI, this is available as **Run → RIS-only isolation (LOS off, specular off)**.
- For a Sionna tutorial-style diff map, set `radio_map.diff_ris: true` (see `configs/ris_doc_street_canyon.yaml`).
- If Tx/Rx are on opposite sides of the RIS normal, reradiation is disabled and the RIS acts as a blocker.
- The RIS model is passive; total gain improvements can be small unless the RIS is large/close
  or the direct path is weak. For a quick sanity check, disable LOS in the run
  and verify `ris_path_gain_db` is non-zero.
- If the first meters near RIS/Tx appear missing, reduce `radio_map.cell_size`
  and keep `radio_map.align_grid_to_anchor: true` (default). Choose the anchor
  with `radio_map.cell_anchor` (`auto|ris|tx|rx|none`) or set
  `radio_map.cell_anchor_point: [x, y, z]`.

## Directional Tx
If you need a directional transmitter:
- Set `scene.arrays.tx.pattern` to `tr38901`, `dipole`, or `hw_dipole`.
- Aim it with `scene.tx.look_at` or `scene.tx.orientation` (radians).
- In the UI, use **Tx Look-at**, **Tx Pattern**, and **Tx Polarization** before running.

For horn antennas:
- `horn_15dbi` and `horn_22dbi` keep the approximate horn pattern but may still allow rear-hemisphere paths.
- `horn_15dbi_front` and `horn_22dbi_front` are front-only variants for showcase use when you do not want rays launching behind the horn aperture.

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

## Cloudflare Tunnel for Remote Demos
Recommended pattern:
1. Start the simulator locally with a password:
   ```bash
   export SIM_PASSWORD='choose-a-strong-password'
   python -m app sim --host 127.0.0.1 --port 8765 --no-browser
   ```
2. Confirm startup includes:
   - `RIS_SIONNA simulator running at http://127.0.0.1:8765`
   - `Simulator access password is enabled.`
3. Start the tunnel in a second terminal:
   ```bash
   cloudflared tunnel --url http://localhost:8765
   ```
4. Open the printed `https://...trycloudflare.com` URL on the remote device.

Rules:
- Keep the simulator bound to `127.0.0.1`.
- Keep the simulator and `cloudflared` running in separate terminals.
- Do not expose the raw simulator port directly to the internet.

## `cloudflared: command not found`
Install `cloudflared` first.

With `sudo` on Ubuntu:
```bash
curl -L --output /tmp/cloudflared.deb \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$(dpkg --print-architecture).deb"
sudo dpkg -i /tmp/cloudflared.deb
cloudflared --version
```

Without `sudo`, use a user-local binary:
```bash
mkdir -p ~/.local/bin
curl -L --output ~/.local/bin/cloudflared \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
chmod +x ~/.local/bin/cloudflared
export PATH="$HOME/.local/bin:$PATH"
cloudflared --version
```

## Cloudflare Tunnel URL Loads but Shows Origin Error / Connection Refused
If `cloudflared` logs:
`dial tcp 127.0.0.1:8765: connect: connection refused`

Then the simulator is not listening on that port anymore.

Fix:
1. Restart the simulator:
   ```bash
   export SIM_PASSWORD='choose-a-strong-password'
   python -m app sim --host 127.0.0.1 --port 8765 --no-browser
   ```
2. Verify it is listening:
   ```bash
   ss -ltnp | rg 8765
   ```
3. Keep that terminal open.
4. Re-run:
   ```bash
   cloudflared tunnel --url http://localhost:8765
   ```

## Tunnel Works but the Password Page Does Not Appear
If the UI opens directly without a login page, auth was not enabled at simulator startup.

Fix:
1. Stop the simulator.
2. Export the password before starting it:
   ```bash
   export SIM_PASSWORD='choose-a-strong-password'
   python -m app sim --host 127.0.0.1 --port 8765 --no-browser
   ```
3. Confirm startup prints:
   `Simulator access password is enabled.`
4. Open the local URL in a fresh private/incognito window to verify the login page appears before retrying the public tunnel URL.

## Cloudflare Tunnel Logs ICMP or UDP Buffer Warnings
Warnings such as:
- `ICMP proxy feature is disabled`
- `failed to sufficiently increase receive buffer size`

are usually non-fatal for a demo tunnel. If the tunnel also logs a successful registration line and the remote URL loads, these warnings can generally be ignored for simulator access.
