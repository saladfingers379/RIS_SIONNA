#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXACT MATCH to Machado/Tang near-field experiment-style sweep (MATLAB -> Python)
Extended: N-bit phase quantization OR continuous phase.

Set PHASE_BITS:
  - PHASE_BITS = 1,2,3,...  -> uniform B-bit quantization over [0, 2π)
  - PHASE_BITS = None       -> continuous phase (ideal)

Critical MATLAB-matching details:
- MATLAB uses column-major ordering for (:), reshape(). We replicate with order="F".
- Degrees-based trig (sind/cosd) is used everywhere.
- For PHASE_BITS=1, quantization matches MATLAB rule: {0, π} with threshold at π.
- Tang cosine^((G/2)-1) pattern factor with LINEAR gains.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


# -----------------------------
# Helpers (degree trig like MATLAB)
# -----------------------------
def sind(x_deg):
    return np.sin(np.deg2rad(x_deg))


def cosd(x_deg):
    return np.cos(np.deg2rad(x_deg))


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def matlab_lines(n):
    # MATLAB default "lines" palette (first 7), repeats if n > 7
    base = np.array([
        [0.0000, 0.4470, 0.7410],
        [0.8500, 0.3250, 0.0980],
        [0.9290, 0.6940, 0.1250],
        [0.4940, 0.1840, 0.5560],
        [0.4660, 0.6740, 0.1880],
        [0.3010, 0.7450, 0.9330],
        [0.6350, 0.0780, 0.1840],
    ])
    if n <= base.shape[0]:
        return base[:n]
    reps = int(np.ceil(n / base.shape[0]))
    return np.vstack([base] * reps)[:n]


def quantize_phase(phi_cont, bits=None):
    """
    Quantize continuous phase to:
      - continuous (bits=None): returns phi mod 2π
      - B-bit uniform quantization on [0,2π), with B>=1

    For bits=1, matches MATLAB:
      phi_mod = mod(phi_cont, 2*pi);
      phi_bin = double(phi_mod >= pi) * pi;
    """
    phi_mod = np.mod(phi_cont, 2.0 * np.pi)

    if bits is None:
        return phi_mod

    if bits < 1:
        raise ValueError("bits must be >= 1 or None for continuous phase")

    L = 2 ** bits
    delta = 2.0 * np.pi / L

    q = np.floor(phi_mod / delta)          # 0..L-1
    phi_q = q * delta
    return phi_q


def polar_db_plot(ax, theta_deg, r_db, rmin=-40.0, rmax=5.0, **kwargs):
    """
    Matplotlib polar axes don't like negative radii.
    Shift radii so rmin -> 0, and relabel ticks back to dB.
    """
    theta = np.deg2rad(theta_deg)
    r_shift = r_db - rmin
    ax.plot(theta, r_shift, **kwargs)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)  # clockwise
    ax.set_thetamin(-90)
    ax.set_thetamax(90)
    ax.set_rlim(0.0, rmax - rmin)

    rticks_db = np.array([-40, -30, -20, -10, 0, 5], dtype=float)
    rticks_db = rticks_db[(rticks_db >= rmin) & (rticks_db <= rmax)]
    ax.set_yticks(rticks_db - rmin)
    ax.set_yticklabels([f"{t:g}" for t in rticks_db])


# -----------------------------
# Main
# -----------------------------
def main():
    # ============================================================
    # USER KNOBS
    # ============================================================
    PHASE_BITS = 10     # 1,2,3,... or None for continuous phase
    # ============================================================

    # %% Physical constants
    c = 299792458.0
    f = 28e9
    lam = c / f
    k0 = 2.0 * np.pi / lam

    # %% RIS grid (20x20) on yz-plane
    N = 20
    M = 20
    lu = 4.9e-3
    dy = lu
    dz = lu

    RIS_center = np.array([0.0, 0.0, 0.0], dtype=float)

    y_vec = (np.arange(-(M - 1) / 2, (M - 1) / 2 + 1) * dy) + RIS_center[1]
    z_vec = (np.arange(-(N - 1) / 2, (N - 1) / 2 + 1) * dz) + RIS_center[2]

    # MATLAB: [YY, ZZ] = meshgrid(y_vec, z_vec); sizes N x M
    YY, ZZ = np.meshgrid(y_vec, z_vec, indexing="xy")

    # MATLAB: YY(:), ZZ(:) are column-major; replicate with order="F"
    x_nm = np.zeros(YY.size, dtype=float) + RIS_center[0]   # x=0 plane
    y_nm = YY.reshape(-1, order="F")
    z_nm = ZZ.reshape(-1, order="F")
    numEls = x_nm.size

    # distance from element to RIS center in the panel plane
    d_nm = np.sqrt((y_nm - RIS_center[1]) ** 2 + (z_nm - RIS_center[2]) ** 2)

    print(f"RIS grid: {numEls} elements ({N}×{M})")
    if PHASE_BITS is None:
        print("Phase mode: continuous")
    else:
        print(f"Phase mode: {PHASE_BITS}-bit ({2**PHASE_BITS} states)")

    # %% Experiment geometry
    theta_t = -30.0
    d1 = 0.4
    d2 = 2.0
    theta_r_sweep = np.arange(-90.0, 90.0 + 1e-9, 2.0)

    Tx = np.array([d1 * cosd(theta_t), d1 * sind(theta_t), 0.0], dtype=float)
    d1_center = np.linalg.norm(Tx - RIS_center)

    # %% Gains and reflection coefficient
    Gt_dBi = 15.0
    Gr_dBi = 22.0
    Gt = 10.0 ** (Gt_dBi / 10.0)
    Gr = 10.0 ** (Gr_dBi / 10.0)

    rho = 0.84

    Pt_dBm = 28.0
    Pt_W = 10.0 ** ((Pt_dBm - 30.0) / 10.0)

    # %% Distances Tx->elements
    rt = np.sqrt((Tx[0] - x_nm) ** 2 + (Tx[1] - y_nm) ** 2 + (Tx[2] - z_nm) ** 2)

    # Panel normal is +x (since yz-plane). So cos(theta) uses x-component.
    cos_theta_nm_t = np.abs(Tx[0] - x_nm) / rt
    cos_theta_nm_t = clamp01(cos_theta_nm_t)

    # Tx boresight assumed pointed at RIS center
    cos_theta_nm_tx = (d1_center ** 2 + rt ** 2 - d_nm ** 2) / (2.0 * d1_center * rt)
    cos_theta_nm_tx = clamp01(cos_theta_nm_tx)

    # %% RIS steering configs
    steering_angles = np.array([0.0, 15.0, 45.0, 60.0], dtype=float)
    num_configs = steering_angles.size
    phase_configs = np.zeros((N, M, num_configs), dtype=float)

    phi0 = 0.0

    # element position vectors
    r_i = np.column_stack([x_nm, y_nm, z_nm])  # (numEls, 3)

    # %% Phase maps: reflectarray steering + N-bit quantization
    for config_idx, theta0 in enumerate(steering_angles):
        # desired outgoing unit direction in azimuth plane
        k_hat = np.array([cosd(theta0), sind(theta0), 0.0], dtype=float)

        proj = r_i @ k_hat   # dot(k_hat, r_i)
        R_i = rt             # feed-to-element distance

        # steering phase (continuous)
        phi_cont = k0 * (R_i - proj) + phi0

        # quantize: N-bit or continuous
        phi_q = quantize_phase(phi_cont, bits=PHASE_BITS)

        # MATLAB reshape column-major
        phase_configs[:, :, config_idx] = phi_q.reshape((N, M), order="F")

        print(f"Configured RIS for steering to {int(theta0)}°")

    # %% Pattern computation
    alpha_t = (Gt / 2.0) - 1.0
    alpha_r = (Gr / 2.0) - 1.0

    num_angles = theta_r_sweep.size
    Pr_dB_configs = np.zeros((num_angles, num_configs), dtype=float)
    Pr_dB_off = np.zeros(num_angles, dtype=float)

    eps = np.finfo(float).eps

    for config_idx, theta0 in enumerate(steering_angles):
        print(f"Calculating pattern for steering to {int(theta0)}°...")

        Gamma_on = rho * np.exp(1j * phase_configs[:, :, config_idx])
        Gamma_on = Gamma_on.reshape(-1, order="F")  # MATLAB (:)
        Gamma_off = rho * np.ones_like(Gamma_on)

        for sweep_idx, theta_r in enumerate(theta_r_sweep):
            Rx = np.array([d2 * cosd(theta_r), d2 * sind(theta_r), 0.0], dtype=float)
            d2_center = np.linalg.norm(Rx - RIS_center)

            rr = np.sqrt((Rx[0] - x_nm) ** 2 + (Rx[1] - y_nm) ** 2 + (Rx[2] - z_nm) ** 2)

            cos_theta_nm_r = np.abs(Rx[0] - x_nm) / rr
            cos_theta_nm_r = clamp01(cos_theta_nm_r)

            cos_theta_nm_rx = (d2_center ** 2 + rr ** 2 - d_nm ** 2) / (2.0 * d2_center * rr)
            cos_theta_nm_rx = clamp01(cos_theta_nm_rx)

            # Tang-style combined factor
            F_combine = (cos_theta_nm_tx ** alpha_t) * (cos_theta_nm_t) * (cos_theta_nm_r) * (cos_theta_nm_rx ** alpha_r)
            F_combine = np.maximum(F_combine, 0.0)

            phase_term = np.exp(-1j * k0 * (rt + rr))
            denom = (rt * rr)

            sum_on = np.sum(np.sqrt(F_combine) * Gamma_on  / denom * phase_term)
            sum_off = np.sum(np.sqrt(F_combine) * Gamma_off / denom * phase_term)

            Pr_on = Pt_W * Gt * Gr * (lu ** 4) / (16.0 * np.pi ** 2) * (np.abs(sum_on) ** 2)
            Pr_off = Pt_W * Gt * Gr * (lu ** 4) / (16.0 * np.pi ** 2) * (np.abs(sum_off) ** 2)

            Pr_dB_configs[sweep_idx, config_idx] = 10.0 * np.log10(Pr_on + eps)
            if config_idx == 0:
                Pr_dB_off[sweep_idx] = 10.0 * np.log10(Pr_off + eps)

    # %% Normalize (like the paper's normalized patterns)
    Pr_norm_configs = Pr_dB_configs - np.max(Pr_dB_configs, axis=0, keepdims=True)
    Pr_norm_off = Pr_dB_off - np.max(Pr_dB_off)

    # ============================================================
    # VISUALIZATION 1: Combined Normalized Patterns
    # ============================================================
    colors = matlab_lines(num_configs)

    plt.figure(figsize=(14, 9), num="RIS Radiation Patterns")
    ax = plt.subplot2grid((2, 2), (0, 0), colspan=2)

    for i in range(num_configs):
        ax.plot(theta_r_sweep, Pr_norm_configs[:, i], linewidth=2.5, color=colors[i],
                label=f"Steer to {int(steering_angles[i])}°")
    ax.plot(theta_r_sweep, Pr_norm_off, "k--", linewidth=2.5, label="RIS OFF")

    ax.grid(True)
    ax.set_xlabel("Azimuth angle (deg)")
    ax.set_ylabel("Normalized received level (dB)")
    ax.set_title("Normalized 2D Radiation Pattern (Tx fixed @ -30°, Rx swept)", fontweight="bold")
    ax.set_xlim([-90, 90])
    ax.set_ylim([-40, 5])

    specular_angle = -theta_t
    ax.axvline(specular_angle, color="g", linestyle=":", linewidth=2)

    ax.legend(loc="best", ncols=2, fontsize=10)

    # Peak gains (normalized => zeros, but kept to mirror MATLAB figure)
    ax2 = plt.subplot2grid((2, 2), (1, 0))
    peak_gains = np.max(Pr_norm_configs, axis=0)
    ax2.bar(steering_angles, peak_gains)
    ax2.grid(True)
    ax2.set_xlabel("Steering Angle (deg)")
    ax2.set_ylabel("Peak Normalized Gain (dB)")
    ax2.set_title("Peak Gain vs Steering Angle", fontweight="bold")

    # Beamwidth analysis
    ax3 = plt.subplot2grid((2, 2), (1, 1))
    beamwidths = np.zeros(num_configs, dtype=float)
    for i in range(num_configs):
        pattern = Pr_norm_configs[:, i]
        peak_val = np.max(pattern)
        half_power = peak_val - 3.0
        idx = np.where(pattern >= half_power)[0]
        if idx.size > 0:
            beamwidths[i] = theta_r_sweep[idx[-1]] - theta_r_sweep[idx[0]]
    ax3.bar(steering_angles, beamwidths)
    ax3.grid(True)
    ax3.set_xlabel("Steering Angle (deg)")
    ax3.set_ylabel("3-dB Beamwidth (deg)")
    ax3.set_title("Beamwidth vs Steering Angle", fontweight="bold")

    # ============================================================
    # VISUALIZATION 2: Phase Maps with Detailed Analysis
    #   - If PHASE_BITS==1 -> binary colormap like MATLAB
    #   - Else -> HSV phase colormap
    # ============================================================
    plt.figure(figsize=(15, 9), num="Phase Configuration Analysis")

    if PHASE_BITS == 1:
        cmap_phase = ListedColormap([[1, 0, 0], [0, 0, 1]])  # red=0, blue=pi
        vmin, vmax = 0.0, np.pi
        cb_ticks = [0.0, np.pi]
        cb_labels = ["0", "π"]
    else:
        cmap_phase = "hsv"
        vmin, vmax = 0.0, 2.0 * np.pi
        cb_ticks = [0.0, np.pi, 2.0 * np.pi]
        cb_labels = ["0", "π", "2π"]

    for i in range(num_configs):
        axp = plt.subplot(2, 4, i + 1)
        im = axp.imshow(phase_configs[:, :, i],
                        extent=[y_vec[0] * 1000, y_vec[-1] * 1000, z_vec[0] * 1000, z_vec[-1] * 1000],
                        origin="lower", aspect="equal", cmap=cmap_phase, vmin=vmin, vmax=vmax)
        axp.set_xlabel("y (mm)")
        axp.set_ylabel("z (mm)")
        axp.set_title(f"Phase Map: Steer {int(steering_angles[i])}°", fontweight="bold", fontsize=10)
        cb = plt.colorbar(im, ax=axp, fraction=0.046, pad=0.04)
        cb.set_ticks(cb_ticks)
        cb.set_ticklabels(cb_labels)

        axd = plt.subplot(2, 4, i + 5)
        phase_vals = phase_configs[:, :, i].reshape(-1, order="F")

        if PHASE_BITS is None:
            # Continuous: show histogram
            axd.hist(phase_vals, bins=24)
            axd.set_xlabel("Phase (rad)")
            axd.set_ylabel("Count")
            axd.set_title("Phase Histogram", fontsize=10)
        else:
            # Quantized: count states
            L = 2 ** PHASE_BITS
            delta = 2.0 * np.pi / L
            # state indices derived from phase (robust against float issues)
            q = np.round(phase_vals / delta).astype(int) % L
            counts = np.bincount(q, minlength=L)

            axd.bar(np.arange(L), counts)
            axd.set_xlabel("State index")
            axd.set_ylabel("Number of Elements")
            axd.set_title(f"Phase Distribution ({L} states)", fontsize=10)

        axd.grid(True)

    # ============================================================
    # VISUALIZATION 3: Polar Radiation Patterns (ON + OFF standalone)
    # ============================================================
    fig3 = plt.figure(figsize=(15, 8.5), num="Polar Radiation Patterns (ON + OFF standalone)")

    positions = [
        [0.06, 0.55, 0.27, 0.38],
        [0.37, 0.55, 0.27, 0.38],
        [0.68, 0.55, 0.27, 0.38],
        [0.06, 0.08, 0.27, 0.38],
        [0.37, 0.08, 0.27, 0.38],
        [0.68, 0.08, 0.27, 0.38],
    ]

    for i in range(num_configs):
        pax = fig3.add_axes(positions[i], projection="polar")
        polar_db_plot(pax, theta_r_sweep, Pr_norm_configs[:, i], rmin=-40, rmax=5,
                      linewidth=2.2, color=colors[i])

        r_line_db = np.array([-40.0, 5.0])
        theta_spec = np.deg2rad(specular_angle)
        theta_tx = np.deg2rad(theta_t)
        pax.plot([theta_spec, theta_spec], r_line_db - (-40.0), linestyle=":", linewidth=2.2, color="g")
        pax.plot([theta_tx, theta_tx],     r_line_db - (-40.0), linestyle="--", linewidth=2.2, color="m")

        pax.set_title(f"Steer {int(steering_angles[i])}°", fontweight="bold", fontsize=11)

    pax_off = fig3.add_axes(positions[4], projection="polar")
    polar_db_plot(pax_off, theta_r_sweep, Pr_norm_off, rmin=-40, rmax=5,
                  linewidth=2.2, color="k")
    r_line_db = np.array([-40.0, 5.0])
    theta_spec = np.deg2rad(specular_angle)
    theta_tx = np.deg2rad(theta_t)
    pax_off.plot([theta_spec, theta_spec], r_line_db - (-40.0), linestyle=":", linewidth=2.2, color="g")
    pax_off.plot([theta_tx, theta_tx],     r_line_db - (-40.0), linestyle="--", linewidth=2.2, color="m")
    pax_off.set_title("RIS OFF", fontweight="bold", fontsize=11)

    ax_key = fig3.add_axes(positions[5])
    ax_key.axis("off")
    ax_key.set_xlim(0, 1)
    ax_key.set_ylim(0, 1)
    title_phase = "continuous" if PHASE_BITS is None else f"{PHASE_BITS}-bit"
    ax_key.set_title(f"Key ({title_phase} phase)", fontweight="bold", fontsize=12)

    y0 = 0.85
    dy_key = 0.12
    for i in range(num_configs):
        ax_key.plot([0.08, 0.28], [y0 - i * dy_key, y0 - i * dy_key], linewidth=3, color=colors[i])
        ax_key.text(0.33, y0 - i * dy_key, f"Steer {int(steering_angles[i])}° (ON)",
                    fontsize=11, va="center")

    y_off = y0 - num_configs * dy_key - 0.05
    ax_key.plot([0.08, 0.28], [y_off, y_off], linewidth=2.5, color="k")
    ax_key.text(0.33, y_off, "RIS OFF (standalone)", fontsize=11, va="center")

    y_spec = y_off - 0.14
    ax_key.plot([0.08, 0.28], [y_spec, y_spec], linewidth=2.5, color="g", linestyle=":")
    ax_key.text(0.33, y_spec, f"Specular ({int(specular_angle)}°)", fontsize=11, va="center")

    y_tx = y_spec - 0.14
    ax_key.plot([0.08, 0.28], [y_tx, y_tx], linewidth=2.5, color="m", linestyle="--")
    ax_key.text(0.33, y_tx, f"Tx angle ({int(theta_t)}°)", fontsize=11, va="center")

    # ============================================================
    # VISUALIZATION 6: Steering Efficiency Analysis (kept from prior)
    # ============================================================
    plt.figure(figsize=(14, 6), num="Steering Performance Analysis")

    actual_peaks = np.zeros(num_configs, dtype=float)
    for i in range(num_configs):
        peak_idx = int(np.argmax(Pr_norm_configs[:, i]))
        actual_peaks[i] = theta_r_sweep[peak_idx]

    ax8 = plt.subplot(1, 3, 1)
    ax8.plot(steering_angles, actual_peaks, "ro-", linewidth=2, markersize=8)
    ax8.plot(steering_angles, steering_angles, "b--", linewidth=2)
    ax8.grid(True)
    ax8.set_xlabel("Commanded Steering Angle (deg)")
    ax8.set_ylabel("Actual Peak Angle (deg)")
    ax8.set_title("Steering Accuracy", fontweight="bold")
    ax8.legend(["Measured", "Ideal"], loc="best")
    ax8.set_aspect("equal", adjustable="box")

    steering_error = np.abs(actual_peaks - steering_angles)

    ax9 = plt.subplot(1, 3, 2)
    ax9.bar(steering_angles, steering_error)
    ax9.grid(True)
    ax9.set_xlabel("Steering Angle (deg)")
    ax9.set_ylabel("Pointing Error (deg)")
    ax9.set_title("Steering Error", fontweight="bold")

    improvement = np.zeros(num_configs, dtype=float)
    for i in range(num_configs):
        peak_idx = int(np.argmax(Pr_norm_configs[:, i]))
        peak_on = Pr_norm_configs[peak_idx, i]   # normalized peak -> 0
        peak_off = Pr_norm_off[peak_idx]
        improvement[i] = peak_on - peak_off

    ax10 = plt.subplot(1, 3, 3)
    ax10.bar(steering_angles, improvement)
    ax10.grid(True)
    ax10.set_xlabel("Steering Angle (deg)")
    ax10.set_ylabel("Gain Improvement (dB)")
    ax10.set_title("RIS ON vs OFF Gain", fontweight="bold")

    print("\n=== Steering Performance Summary ===")
    for i in range(num_configs):
        print(f"Steering {int(steering_angles[i])}°: Peak @ {actual_peaks[i]:.1f}° "
              f"(Error: {steering_error[i]:.2f}°, Gain: +{improvement[i]:.2f} dB)")
    print("===================================\n")

    plt.show()


if __name__ == "__main__":
    main()
