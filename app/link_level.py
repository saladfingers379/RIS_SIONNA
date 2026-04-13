from __future__ import annotations

import copy
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from .config import apply_quality_preset
from .io import create_output_dir, save_json, save_yaml
from .metrics import compute_path_metrics, extract_path_data
from .scene import build_scene
from .simulate import _save_ris_profiles, run_simulation
from .utils.system import (
    assert_mitsuba_variant,
    collect_environment_info,
    configure_tensorflow_for_mitsuba_variant,
    configure_tensorflow_memory_growth,
    select_mitsuba_variant,
)

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_RECEIVER_LABELS = {
    "perfect_csi": "Perfect CSI",
    "ls_lin": "LS Linear",
    "ls_nn": "LS Nearest",
}


def _write_progress(
    progress_path: Path,
    steps: list[str],
    step_index: int,
    status: str,
    error: str | None = None,
) -> None:
    total = len(steps)
    step_name = steps[step_index] if step_index < total else "Complete"
    payload = {
        "status": status,
        "step_index": step_index,
        "step_name": step_name,
        "total_steps": total,
        "progress": min(step_index / total, 1.0) if total else 1.0,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if error:
        payload["error"] = error
    save_json(progress_path, payload)


def _load_yaml_mapping(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return data


def _assign_profile_values(profile: Any, values: Any) -> None:
    try:
        assign = getattr(profile.values, "assign", None)
        if callable(assign):
            assign(values)
            return
    except Exception:
        pass
    profile.values = values


def _apply_flat_ris_profile(scene: Any) -> None:
    import tensorflow as tf

    try:
        ris_objects = getattr(scene, "ris", {}) or {}
    except Exception:
        ris_objects = {}
    for _, ris in ris_objects.items():
        zero_phase = tf.zeros_like(ris.phase_profile.values)
        unit_amplitude = tf.ones_like(ris.amplitude_profile.values)
        _assign_profile_values(ris.phase_profile, zero_phase)
        _assign_profile_values(ris.amplitude_profile, unit_amplitude)
        try:
            ris.amplitude_profile.mode_powers = [1.0] * int(getattr(ris, "num_modes", 1))
        except Exception:
            pass


def _compute_paths(scene: Any, sim_cfg: Dict[str, Any], *, use_ris: bool) -> Any:
    if sim_cfg.get("refraction"):
        logger.warning("Sionna 0.19.2 RT does not support refraction; ignoring refraction=True.")
    return scene.compute_paths(
        max_depth=int(sim_cfg.get("max_depth", 3)),
        method=str(sim_cfg.get("method", "fibonacci")),
        num_samples=int(sim_cfg.get("samples_per_src", 200000)),
        los=bool(sim_cfg.get("los", True)),
        reflection=bool(sim_cfg.get("specular_reflection", True)),
        diffraction=bool(sim_cfg.get("diffraction", False)),
        scattering=bool(sim_cfg.get("diffuse_reflection", False)),
        ris=bool(use_ris),
    )


def _parse_ebno_list(values: Any) -> list[float]:
    if isinstance(values, str):
        tokens = [token.strip() for token in values.split(",") if token.strip()]
        parsed = [float(token) for token in tokens]
    elif isinstance(values, Iterable):
        parsed = [float(value) for value in values]
    else:
        raise ValueError("ebno_db_list must be a list or comma-separated string")
    if not parsed:
        raise ValueError("ebno_db_list must not be empty")
    return parsed


def _normalize_estimator_modes(values: Any) -> list[str]:
    if not isinstance(values, list):
        values = ["perfect_csi", "ls_lin"]
    normalized: list[str] = []
    for value in values:
        key = str(value or "").strip().lower()
        if key in _RECEIVER_LABELS and key not in normalized:
            normalized.append(key)
    if not normalized:
        normalized = ["perfect_csi", "ls_lin"]
    return normalized


def _requested_ris_variant_keys(eval_cfg: Dict[str, Any]) -> list[str]:
    requested = eval_cfg.get("ris_variants")
    if not isinstance(requested, list) or not requested:
        requested = ["ris_off", "ris_configured", "ris_flat"]
    normalized: list[str] = []
    for value in requested:
        key = str(value or "").strip().lower()
        if key in {"ris_off", "ris_configured", "ris_flat"} and key not in normalized:
            normalized.append(key)
    return normalized or ["ris_off", "ris_configured", "ris_flat"]


def _variant_definition(key: str) -> Dict[str, Any]:
    if key == "ris_off":
        return {"key": "ris_off", "label": "RIS Off", "ris_enabled": False, "flat": False}
    if key == "ris_flat":
        return {"key": "ris_flat", "label": "RIS Flat", "ris_enabled": True, "flat": True}
    if key == "ris_configured":
        return {"key": "ris_configured", "label": "RIS Configured", "ris_enabled": True, "flat": False}
    raise ValueError(f"Unknown link-level RIS variant: {key}")


def resolve_link_variants(seed_cfg: Dict[str, Any], eval_cfg: Dict[str, Any]) -> list[Dict[str, Any]]:
    requested = _requested_ris_variant_keys(eval_cfg)
    ris_enabled = bool((seed_cfg.get("ris") or {}).get("enabled"))
    variants: list[Dict[str, Any]] = []
    for key in requested:
        key_s = str(key or "").strip().lower()
        if key_s not in {"ris_off", "ris_flat", "ris_configured"}:
            continue
        if key_s in {"ris_flat", "ris_configured"} and not ris_enabled:
            continue
        variant = _variant_definition(key_s)
        if variant["key"] not in {item["key"] for item in variants}:
            variants.append(variant)
    if not variants:
        variants.append(_variant_definition("ris_off"))
    return variants


def validate_link_seed_variants(seed_cfg: Dict[str, Any], eval_cfg: Dict[str, Any]) -> None:
    requested = _requested_ris_variant_keys(eval_cfg)
    ris_enabled = bool((seed_cfg.get("ris") or {}).get("enabled"))
    requested_ris = [key for key in requested if key in {"ris_configured", "ris_flat"}]
    if requested_ris and not ris_enabled:
        requested_text = ", ".join(requested_ris)
        raise ValueError(
            "Link-level RIS comparison requested "
            f"({requested_text}) but the seed scene has ris.enabled=false. "
            "Use a RIS-enabled outdoor config/run or select only RIS Off."
        )


def coerce_link_eval_for_seed(seed_cfg: Dict[str, Any], eval_cfg: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    coerced = copy.deepcopy(eval_cfg)
    warnings: list[str] = []
    requested = _requested_ris_variant_keys(coerced)
    ris_enabled = bool((seed_cfg.get("ris") or {}).get("enabled"))
    requested_ris = [key for key in requested if key in {"ris_configured", "ris_flat"}]
    if requested_ris and not ris_enabled:
        kept = [key for key in requested if key == "ris_off"] or ["ris_off"]
        coerced["ris_variants"] = kept
        requested_text = ", ".join(requested_ris)
        warnings.append(
            "Requested RIS variants "
            f"({requested_text}) but the seed scene has ris.enabled=false; "
            "evaluation was reduced to RIS Off only."
        )
    return coerced, warnings


def prepare_link_seed_config(seed_cfg: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    cfg = apply_quality_preset(copy.deepcopy(seed_cfg))
    warnings: list[str] = []
    cfg.setdefault("render", {})["enabled"] = False
    cfg.setdefault("radio_map", {})["enabled"] = False
    scene_cfg = cfg.setdefault("scene", {})
    arrays = scene_cfg.setdefault("arrays", {})
    for side in ("tx", "rx"):
        arr = arrays.setdefault(side, {})
        rows = int(arr.get("num_rows", 1))
        cols = int(arr.get("num_cols", 1))
        if rows != 1 or cols != 1:
            warnings.append(
                f"Link-level evaluation coerced {side} array from {rows}x{cols} to 1x1 for single-stream OFDM."
            )
        arr["num_rows"] = 1
        arr["num_cols"] = 1
    return cfg, warnings


def _resolve_link_trace_config(seed_cfg: Dict[str, Any], eval_cfg: Dict[str, Any]) -> tuple[Dict[str, Any], list[str], Dict[str, Any]]:
    sim_cfg = copy.deepcopy(seed_cfg.get("simulation", {}) or {})
    warnings: list[str] = []
    trace_meta = {
        "seed_rt_max_depth": int(sim_cfg.get("max_depth", 3)),
        "seed_rt_samples_per_src": int(sim_cfg.get("samples_per_src", 200000)),
    }

    requested_max_depth = eval_cfg.get("max_depth")
    if requested_max_depth is not None:
        requested_max_depth = int(requested_max_depth)
        sim_cfg["max_depth"] = requested_max_depth
        if requested_max_depth < trace_meta["seed_rt_max_depth"]:
            warnings.append(
                "Link-level RT max_depth override "
                f"({requested_max_depth}) is below the seed outdoor run setting "
                f"({trace_meta['seed_rt_max_depth']}); this can undercount RIS-assisted paths."
            )

    requested_samples_per_src = eval_cfg.get("samples_per_src")
    if requested_samples_per_src is not None:
        requested_samples_per_src = int(requested_samples_per_src)
        sim_cfg["samples_per_src"] = requested_samples_per_src
        if requested_samples_per_src < trace_meta["seed_rt_samples_per_src"]:
            warnings.append(
                "Link-level RT samples_per_src override "
                f"({requested_samples_per_src}) is below the seed outdoor run setting "
                f"({trace_meta['seed_rt_samples_per_src']}); this can miss RIS energy."
            )

    trace_meta["rt_max_depth"] = int(sim_cfg.get("max_depth", 3))
    trace_meta["rt_samples_per_src"] = int(sim_cfg.get("samples_per_src", 200000))
    return sim_cfg, warnings, trace_meta


def _build_variant_config(seed_cfg: Dict[str, Any], variant: Dict[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(seed_cfg)
    ris_cfg = cfg.setdefault("ris", {})
    ris_cfg["enabled"] = bool(variant["ris_enabled"])
    return cfg


def _to_numpy(x: Any) -> np.ndarray:
    try:
        return x.numpy()
    except AttributeError:
        return np.asarray(x)


def _extract_cir_for_dataset(
    paths: Any,
    *,
    num_paths: int,
    num_time_steps: int,
    subcarrier_spacing_hz: float,
) -> tuple[np.ndarray, np.ndarray]:
    paths.apply_doppler(
        sampling_frequency=float(subcarrier_spacing_hz),
        num_time_steps=int(num_time_steps),
        tx_velocities=[0.0, 0.0, 0.0],
        rx_velocities=[0.0, 0.0, 0.0],
    )
    a, tau = paths.cir(num_paths=int(num_paths))
    a_np = np.asarray(_to_numpy(a))
    tau_np = np.asarray(_to_numpy(tau))
    if a_np.ndim != 7 or tau_np.ndim != 4:
        raise ValueError(f"Unexpected CIR shapes: a={a_np.shape}, tau={tau_np.shape}")
    return a_np, tau_np


def _delay_profile_from_cir(a: np.ndarray, tau: np.ndarray) -> Dict[str, Any]:
    if a.ndim != 7 or tau.ndim != 4:
        return {"delays_s": np.array([], dtype=float), "weights": np.array([], dtype=float), "rms_delay_spread_ns": None}

    num_paths = int(a.shape[-2])
    if num_paths <= 0:
        return {"delays_s": np.array([], dtype=float), "weights": np.array([], dtype=float), "rms_delay_spread_ns": None}

    power = np.abs(a) ** 2
    per_path_power = np.asarray(power.sum(axis=(0, 1, 2, 3, 4, 6)), dtype=float).reshape(-1)
    tau_per_path = np.asarray(tau.reshape(-1, num_paths)[0], dtype=float).reshape(-1)
    valid = np.isfinite(tau_per_path) & np.isfinite(per_path_power) & (per_path_power > 0.0)
    delays_s = tau_per_path[valid]
    weights = per_path_power[valid]
    if delays_s.size == 0 or not np.any(weights > 0.0):
        return {"delays_s": delays_s, "weights": weights, "rms_delay_spread_ns": None}

    weight_sum = float(np.sum(weights))
    mean_delay = float(np.sum(weights * delays_s) / weight_sum)
    rms_delay_s = float(np.sqrt(np.sum(weights * (delays_s - mean_delay) ** 2) / weight_sum))
    return {
        "delays_s": delays_s,
        "weights": weights,
        "rms_delay_spread_ns": rms_delay_s * 1e9,
    }


def _scale_cir_to_reference_gain(
    a: np.ndarray,
    *,
    path_gain_linear: float | None,
    reference_gain_linear: float | None,
) -> np.ndarray:
    gain = float(path_gain_linear or 0.0)
    ref = float(reference_gain_linear or 0.0)
    if gain <= 0.0 or ref <= 0.0:
        return a
    return a / np.sqrt(ref)


class _FixedCIRGenerator:
    def __init__(self, a: np.ndarray, tau: np.ndarray) -> None:
        if a.ndim == 7:
            a = a[0]
        if tau.ndim == 4:
            tau = tau[0]
        self._a = a.astype(np.complex64, copy=False)
        self._tau = tau.astype(np.float32, copy=False)

    def __call__(self):
        import tensorflow as tf

        a_tf = tf.constant(self._a, dtype=tf.complex64)
        tau_tf = tf.constant(self._tau, dtype=tf.float32)
        while True:
            yield a_tf, tau_tf


def _bit_error_count(bits: Any, bits_hat: Any) -> int:
    import tensorflow as tf

    return int(
        tf.reduce_sum(
            tf.cast(
                tf.not_equal(tf.cast(bits_hat, bits.dtype), bits),
                tf.int64,
            )
        ).numpy()
    )


def _simulate_receiver_curves(
    a: np.ndarray,
    tau: np.ndarray,
    eval_cfg: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    import tensorflow as tf
    from sionna.channel import CIRDataset, OFDMChannel
    from sionna.mapping import Mapper
    from sionna.mimo import StreamManagement
    from sionna.ofdm import LSChannelEstimator, LinearDetector, ResourceGrid, ResourceGridMapper
    from sionna.utils import BinarySource, ebnodb2no

    batch_size = int(eval_cfg.get("batch_size", 32))
    iterations = int(eval_cfg.get("iterations_per_ebno", 8))
    num_bits_per_symbol = int(eval_cfg.get("num_bits_per_symbol", 2))
    num_ofdm_symbols = int(eval_cfg.get("num_ofdm_symbols", 14))
    fft_size = int(eval_cfg.get("fft_size", 64))
    subcarrier_spacing_hz = float(eval_cfg.get("subcarrier_spacing_hz", 30e3))
    pilot_symbols = eval_cfg.get("pilot_ofdm_symbol_indices", [2, 11])
    ebno_db_list = _parse_ebno_list(eval_cfg.get("ebno_db_list", [0.0, 5.0, 10.0, 15.0, 20.0]))
    estimator_modes = _normalize_estimator_modes(eval_cfg.get("estimators"))

    num_paths = int(a.shape[-2])
    num_time_steps = int(a.shape[-1])
    rg = ResourceGrid(
        num_ofdm_symbols=num_ofdm_symbols,
        fft_size=fft_size,
        subcarrier_spacing=subcarrier_spacing_hz,
        num_tx=1,
        pilot_pattern="kronecker",
        pilot_ofdm_symbol_indices=pilot_symbols,
    )
    sm = StreamManagement(np.ones([1, 1], int), 1)
    mapper = Mapper(constellation_type="qam", num_bits_per_symbol=num_bits_per_symbol)
    binary_source = BinarySource()
    rg_mapper = ResourceGridMapper(rg)
    channel_model = CIRDataset(
        _FixedCIRGenerator(a, tau),
        batch_size,
        1,
        1,
        1,
        1,
        num_paths,
        num_time_steps,
    )
    channel = OFDMChannel(channel_model, rg, return_channel=True)
    detector = LinearDetector(
        "lmmse",
        "bit",
        "app",
        rg,
        sm,
        constellation_type="qam",
        num_bits_per_symbol=num_bits_per_symbol,
        hard_out=True,
    )
    estimators: Dict[str, Any] = {}
    if "ls_lin" in estimator_modes:
        estimators["ls_lin"] = LSChannelEstimator(rg, interpolation_type="lin")
    if "ls_nn" in estimator_modes:
        estimators["ls_nn"] = LSChannelEstimator(rg, interpolation_type="nn")

    n = int(rg.num_data_symbols * num_bits_per_symbol)
    total_bits_per_iteration = batch_size * n
    out: Dict[str, Dict[str, Any]] = {}

    for mode in estimator_modes:
        ber_values: list[float] = []
        for ebno_db in ebno_db_list:
            errors = 0
            for _ in range(iterations):
                bits = binary_source([batch_size, 1, 1, n])
                symbols = mapper(bits)
                x_rg = rg_mapper(symbols)
                no = ebnodb2no(ebno_db, num_bits_per_symbol, 1.0, resource_grid=rg)
                y_rg, h_freq = channel((x_rg, no))
                if mode == "perfect_csi":
                    h_hat = h_freq
                    err_var = 0.0
                else:
                    h_hat, err_var = estimators[mode]((y_rg, no))
                bits_hat = detector((y_rg, h_hat, err_var, no))
                errors += _bit_error_count(bits, bits_hat)
            ber_values.append(float(errors) / float(iterations * total_bits_per_iteration))
        out[mode] = {
            "label": _RECEIVER_LABELS[mode],
            "ebno_db": list(ebno_db_list),
            "ber": ber_values,
        }
    return out


def _plot_ber_curves(curves: Dict[str, Dict[str, Any]], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for series in curves.values():
        ebno = series.get("ebno_db") or []
        ber = np.asarray(series.get("ber") or [], dtype=float)
        if not ebno or ber.size == 0:
            continue
        safe = np.maximum(ber, 1e-5)
        ax.semilogy(ebno, safe, marker="o", linewidth=2.0, label=series.get("label", "Series"))
    ax.set_title("BER vs Eb/N0")
    ax.set_xlabel("Eb/N0 [dB]")
    ax.set_ylabel("BER")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _plot_variant_metric(
    variants: Dict[str, Dict[str, Any]],
    metric_key: str,
    title: str,
    ylabel: str,
    output_path: Path,
) -> None:
    labels = []
    values = []
    for variant in variants.values():
        value = variant.get(metric_key)
        if value is None or not np.isfinite(value):
            continue
        labels.append(variant.get("label", variant.get("key", metric_key)))
        values.append(float(value))
    if not values:
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = ["#005f73", "#0a9396", "#ee9b00", "#ca6702"]
    ax.bar(labels, values, color=colors[: len(values)])
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _plot_variant_delay_histograms(
    delay_profiles: Dict[str, Dict[str, Any]],
    output_path: Path,
) -> None:
    all_delays: list[np.ndarray] = []
    for profile in delay_profiles.values():
        delays_raw = profile.get("delays_s")
        delays_s = np.asarray(delays_raw if delays_raw is not None else [], dtype=float)
        delays_s = delays_s[np.isfinite(delays_s)]
        if delays_s.size:
            all_delays.append(delays_s)
    if not all_delays:
        return

    all_delays_ns = np.concatenate(all_delays) * 1e9
    if all_delays_ns.size == 0:
        return
    finite = all_delays_ns[np.isfinite(all_delays_ns)]
    if finite.size == 0:
        return

    lo = float(np.min(finite))
    hi = float(np.max(finite))
    if not np.isfinite(lo) or not np.isfinite(hi):
        return
    if np.isclose(lo, hi):
        hi = lo + 1.0
    bins = np.linspace(lo, hi, 50)

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#005f73", "#0a9396", "#ee9b00", "#ca6702", "#9b2226"]
    for idx, profile in enumerate(delay_profiles.values()):
        delays_raw = profile.get("delays_s")
        delays_s = np.asarray(delays_raw if delays_raw is not None else [], dtype=float)
        weights = profile.get("weights")
        delays_s = delays_s[np.isfinite(delays_s)]
        if delays_s.size == 0:
            continue
        delays_ns = delays_s * 1e9
        weights_arr = None
        if weights is not None:
            weights_arr = np.asarray(weights, dtype=float)
            if weights_arr.shape != delays_s.shape:
                weights_arr = None
        ax.hist(
            delays_ns,
            bins=bins,
            weights=weights_arr,
            histtype="step",
            linewidth=2.0,
            color=colors[idx % len(colors)],
            label=profile.get("label", f"Variant {idx + 1}"),
        )

    ax.set_title("Path Delay Distribution")
    ax.set_xlabel("Delay [ns]")
    ax.set_ylabel("Weighted count")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _save_ris_profiles_for_variant(scene: Any, plots_dir: Path, variant_key: str) -> Dict[str, str]:
    before = {path.name for path in plots_dir.glob("ris_*_phase.png")} | {path.name for path in plots_dir.glob("ris_*_amplitude.png")}
    _save_ris_profiles(scene, plots_dir)
    after = {path.name for path in plots_dir.glob("ris_*_phase.png")} | {path.name for path in plots_dir.glob("ris_*_amplitude.png")}
    created = sorted(after - before)
    renamed: Dict[str, str] = {}
    for filename in created:
        src = plots_dir / filename
        dst_name = f"{variant_key}_{filename}"
        dst = plots_dir / dst_name
        src.replace(dst)
        renamed[filename] = dst_name
    return renamed


def _load_link_job(path: str | Path) -> Dict[str, Any]:
    cfg = _load_yaml_mapping(Path(path))
    if not isinstance(cfg.get("seed"), dict) or not isinstance(cfg["seed"].get("config"), dict):
        raise ValueError("Link-level job config requires seed.config")
    return cfg


def _prepare_seed_run_config(
    *,
    seed_cfg: Dict[str, Any],
    link_output_dir: Path,
    link_run_id: str,
    base_dir: str,
) -> tuple[Path, str]:
    run_cfg = copy.deepcopy(seed_cfg)
    seed_run_id = f"{link_run_id}__seed"
    run_cfg.setdefault("radio_map", {})["enabled"] = False
    run_cfg.setdefault("output", {})
    run_cfg["output"]["base_dir"] = base_dir
    run_cfg["output"]["run_id"] = seed_run_id
    run_cfg["output"]["scope"] = "sim"
    run_cfg.setdefault("job", {})
    run_cfg["job"]["kind"] = "run"
    run_cfg["job"]["scope"] = "sim"
    run_cfg["job"]["id"] = f"job-{seed_run_id}"
    config_path = link_output_dir / "seed_run_config.yaml"
    save_yaml(config_path, run_cfg)
    return config_path, seed_run_id


def run_link_level_eval(config_path: str) -> Path:
    cfg = _load_link_job(config_path)
    output_cfg = cfg.setdefault("output", {})
    run_id = output_cfg.get("run_id")
    output_dir = create_output_dir(output_cfg.get("base_dir", "outputs"), run_id=run_id)
    save_yaml(output_dir / "config.yaml", cfg)
    progress_path = output_dir / "progress.json"
    metrics_path = output_dir / "metrics.json"
    plots_dir = output_dir / "plots"
    data_dir = output_dir / "data"
    plots_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    seed_meta = cfg.setdefault("seed", {})
    auto_seed_run = bool(seed_meta.get("prepare_seed_run")) and str(seed_meta.get("type") or "").strip().lower() == "config"
    steps = ["Initialize"]
    if auto_seed_run:
        steps.append("Run seed outdoor sim")
    steps.extend(
        [
            "Select backend",
            "Build scene variants",
            "Generate CIRs",
            "Run link-level BER",
            "Write artifacts",
        ]
    )
    _write_progress(progress_path, steps, 0, "running")

    eval_cfg = copy.deepcopy(cfg.get("evaluation", {}) or {})
    runtime_cfg = cfg.get("runtime", {}) or {}

    try:
        seed_cfg_raw = copy.deepcopy(seed_meta["config"])
        eval_cfg, variant_warnings = coerce_link_eval_for_seed(seed_cfg_raw, eval_cfg)

        active_seed_run_id = str(seed_meta.get("run_id") or "").strip() or None
        active_seed_config_path = str(seed_meta.get("config_path") or "").strip() or None
        if auto_seed_run:
            _write_progress(progress_path, steps, 1, "running")
            seed_run_config_path, generated_seed_run_id = _prepare_seed_run_config(
                seed_cfg=seed_cfg_raw,
                link_output_dir=output_dir,
                link_run_id=str(run_id),
                base_dir=str(output_cfg.get("base_dir", "outputs")),
            )
            run_simulation(str(seed_run_config_path))
            active_seed_run_id = generated_seed_run_id
            seed_meta["prepared_run_id"] = generated_seed_run_id
            seed_cfg_raw = _load_yaml_mapping(
                Path(output_cfg.get("base_dir", "outputs")) / generated_seed_run_id / "config.yaml"
            )

        seed_cfg, seed_warnings = prepare_link_seed_config(seed_cfg_raw)
        variants = resolve_link_variants(seed_cfg, eval_cfg)
        sim_cfg, trace_warnings, trace_meta = _resolve_link_trace_config(seed_cfg, eval_cfg)

        backend_step = 2 if auto_seed_run else 1
        build_step = 3 if auto_seed_run else 2
        cir_step = 4 if auto_seed_run else 3
        ber_step = 5 if auto_seed_run else 4
        write_step = 6 if auto_seed_run else 5

        _write_progress(progress_path, steps, backend_step, "running")
        prefer_gpu = bool(runtime_cfg.get("prefer_gpu", True))
        forced_variant = str(runtime_cfg.get("mitsuba_variant", "auto"))
        variant_name = select_mitsuba_variant(prefer_gpu=prefer_gpu, forced_variant=forced_variant)
        assert_mitsuba_variant(variant_name, context="link_level")
        tf_policy = configure_tensorflow_for_mitsuba_variant(variant_name)
        tf_growth = configure_tensorflow_memory_growth(mode=str(runtime_cfg.get("tensorflow_import", "auto")))

        _write_progress(progress_path, steps, build_step, "running")
        variant_results: Dict[str, Dict[str, Any]] = {}
        variant_cirs: Dict[str, Dict[str, Any]] = {}
        variant_delay_profiles: Dict[str, Dict[str, Any]] = {}
        variant_ris_plot_files: Dict[str, Dict[str, str]] = {}
        for link_variant in variants:
            link_cfg = _build_variant_config(seed_cfg, link_variant)
            scene = build_scene(link_cfg, mitsuba_variant=variant_name)
            if link_variant.get("flat"):
                _apply_flat_ris_profile(scene)
            variant_ris_plot_files[link_variant["key"]] = _save_ris_profiles_for_variant(
                scene,
                plots_dir,
                link_variant["key"],
            )

            _write_progress(progress_path, steps, cir_step, "running")
            paths = _compute_paths(
                scene,
                sim_cfg,
                use_ris=bool(link_variant.get("ris_enabled")),
            )
            num_time_steps = int(eval_cfg.get("num_ofdm_symbols", 14))
            subcarrier_spacing_hz = float(eval_cfg.get("subcarrier_spacing_hz", 30e3))
            num_paths = int(eval_cfg.get("num_paths", 32))
            a, tau = _extract_cir_for_dataset(
                paths,
                num_paths=num_paths,
                num_time_steps=num_time_steps,
                subcarrier_spacing_hz=subcarrier_spacing_hz,
            )

            _write_progress(progress_path, steps, ber_step, "running")
            cir_delay_profile = _delay_profile_from_cir(a, tau)
            path_metrics = compute_path_metrics(paths, tx_power_dbm=next(iter(scene.transmitters.values())).power_dbm, scene=scene)
            path_data = extract_path_data(paths)
            extra_metrics = path_data.get("metrics", {})
            variant_results[link_variant["key"]] = {
                "key": link_variant["key"],
                "label": link_variant["label"],
                "path_gain_linear": path_metrics.get("total_path_gain_linear"),
                "path_gain_db": path_metrics.get("total_path_gain_db"),
                "rx_power_dbm_estimate": path_metrics.get("rx_power_dbm_estimate"),
                "num_valid_paths": path_metrics.get("num_valid_paths"),
                "num_ris_paths": path_metrics.get("num_ris_paths"),
                "rms_delay_spread_ns": (
                    float(extra_metrics["rms_delay_spread_s"]) * 1e9
                    if extra_metrics.get("rms_delay_spread_s") is not None
                    else cir_delay_profile.get("rms_delay_spread_ns")
                ),
            }
            variant_delay_profiles[link_variant["key"]] = {
                "label": link_variant["label"],
                "delays_s": np.asarray(cir_delay_profile.get("delays_s") if cir_delay_profile.get("delays_s") is not None else [], dtype=float),
                "weights": np.asarray(cir_delay_profile.get("weights") if cir_delay_profile.get("weights") is not None else [], dtype=float),
            }
            variant_cirs[link_variant["key"]] = {"a": a, "tau": tau}
            save_json(data_dir / f"{link_variant['key']}_cir_summary.json", {
                "a_shape": list(a.shape),
                "tau_shape": list(tau.shape),
                "path_gain_db": variant_results[link_variant["key"]]["path_gain_db"],
                "rms_delay_spread_ns": variant_results[link_variant["key"]]["rms_delay_spread_ns"],
                "num_delay_samples": int(variant_delay_profiles[link_variant["key"]]["delays_s"].size),
                "ris_plot_files": variant_ris_plot_files[link_variant["key"]],
            })

        _write_progress(progress_path, steps, write_step, "running")
        reference_gain_linear = max(
            (
                float(variant.get("path_gain_linear") or 0.0)
                for variant in variant_results.values()
            ),
            default=0.0,
        )
        if reference_gain_linear > 0.0:
            reference_gain_db = 10.0 * np.log10(reference_gain_linear + 1e-12)
            variant_warnings.append(
                "BER sweep uses a shared channel-power reference anchored to the strongest variant "
                f"({reference_gain_db:.2f} dB path gain) so relative RIS differences remain visible."
            )
        else:
            reference_gain_db = None

        for key, payload in variant_cirs.items():
            scaled_a = _scale_cir_to_reference_gain(
                payload["a"],
                path_gain_linear=variant_results[key].get("path_gain_linear"),
                reference_gain_linear=reference_gain_linear,
            )
            receiver_curves = _simulate_receiver_curves(scaled_a, payload["tau"], eval_cfg)
            variant_results[key]["receivers"] = receiver_curves

        ber_series: Dict[str, Dict[str, Any]] = {}
        for variant in variant_results.values():
            for receiver_key, receiver in (variant.get("receivers") or {}).items():
                series_key = f"{variant['key']}::{receiver_key}"
                ber_series[series_key] = {
                    "label": f"{variant['label']} · {receiver['label']}",
                    "ebno_db": receiver.get("ebno_db") or [],
                    "ber": receiver.get("ber") or [],
                }

        _plot_ber_curves(ber_series, plots_dir / "ber_vs_ebno.png")
        _plot_variant_metric(
            variant_results,
            "path_gain_db",
            "Path Gain by RIS Variant",
            "Path gain [dB]",
            plots_dir / "variant_path_gain_db.png",
        )
        _plot_variant_metric(
            variant_results,
            "rms_delay_spread_ns",
            "Delay Spread by RIS Variant",
            "RMS delay spread [ns]",
            plots_dir / "variant_delay_spread_ns.png",
        )
        _plot_variant_delay_histograms(
            variant_delay_profiles,
            plots_dir / "variant_path_delay_hist_ns.png",
        )

        preferred_ris_variant = None
        for key in ("ris_configured", "ris_flat", "ris_off"):
            files = variant_ris_plot_files.get(key) or {}
            if files:
                preferred_ris_variant = key
                break
        if preferred_ris_variant is not None:
            preferred_files = variant_ris_plot_files.get(preferred_ris_variant, {})
            phase_file = next((name for original, name in preferred_files.items() if original.endswith("_phase.png")), None)
            amplitude_file = next((name for original, name in preferred_files.items() if original.endswith("_amplitude.png")), None)
            if phase_file and (plots_dir / phase_file).exists():
                shutil.copyfile(plots_dir / phase_file, plots_dir / "variant_ris_phase.png")
            if amplitude_file and (plots_dir / amplitude_file).exists():
                shutil.copyfile(plots_dir / amplitude_file, plots_dir / "variant_ris_amplitude.png")

        available_plots = []
        for filename in [
            "ber_vs_ebno.png",
            "variant_path_gain_db.png",
            "variant_delay_spread_ns.png",
            "variant_path_delay_hist_ns.png",
            "variant_ris_phase.png",
            "variant_ris_amplitude.png",
        ]:
            if (plots_dir / filename).exists():
                available_plots.append(filename)

        summary = {
            "schema_version": _SCHEMA_VERSION,
            "kind": "link_level",
            "seed": {
                "type": cfg.get("seed", {}).get("type"),
                "run_id": active_seed_run_id,
                "config_path": active_seed_config_path,
                "prepared_run_id": cfg.get("seed", {}).get("prepared_run_id"),
            },
            "runtime": {
                "mitsuba_variant": variant_name,
                "rt_backend": "cuda/optix" if "cuda" in variant_name else "cpu/llvm",
                "tensorflow_policy": tf_policy,
                "tensorflow_runtime": tf_growth,
            },
            "evaluation": {
                "estimators": _normalize_estimator_modes(eval_cfg.get("estimators")),
                "ebno_db_list": _parse_ebno_list(eval_cfg.get("ebno_db_list", [0.0, 5.0, 10.0, 15.0, 20.0])),
                "batch_size": int(eval_cfg.get("batch_size", 32)),
                "iterations_per_ebno": int(eval_cfg.get("iterations_per_ebno", 8)),
                "num_ofdm_symbols": int(eval_cfg.get("num_ofdm_symbols", 14)),
                "fft_size": int(eval_cfg.get("fft_size", 64)),
                "rt_max_depth": trace_meta["rt_max_depth"],
                "rt_samples_per_src": trace_meta["rt_samples_per_src"],
                "seed_rt_max_depth": trace_meta["seed_rt_max_depth"],
                "seed_rt_samples_per_src": trace_meta["seed_rt_samples_per_src"],
                "ber_reference_mode": "shared_strongest_variant",
                "ber_reference_path_gain_db": reference_gain_db,
            },
            "warnings": seed_warnings + trace_warnings + variant_warnings,
            "results": variant_results,
            "plots": available_plots,
            "plot_sources": {
                "variant_ris_phase.png": preferred_ris_variant,
                "variant_ris_amplitude.png": preferred_ris_variant,
            },
            "environment": collect_environment_info(),
        }
        if auto_seed_run:
            summary["warnings"].insert(
                0,
                "Auto-prepared seed runs disable radio_map generation. "
                "This avoids a Sionna 0.19.2 GPU coverage_map SVD failure with small steered RIS panels "
                "while preserving the rendered scene/viewer and the link-level path tracing.",
            )
        save_json(metrics_path, summary)
        save_json(output_dir / "summary.json", summary)
        _write_progress(progress_path, steps, len(steps), "completed")
        return output_dir
    except Exception as exc:
        _write_progress(progress_path, steps, min(steps.index("Write artifacts"), len(steps) - 1), "failed", error=str(exc))
        raise
