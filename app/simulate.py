from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .config import load_config
from .sim_tuning import apply_similarity_and_sampling
from .radio_map_grid import (
    align_center_to_anchor,
    assess_ris_plane_visibility,
    derive_tx_ris_incidence_slice,
    diagnose_ris_map_sampling_issue,
    radio_map_z_slice_offsets,
)
from .ris.ris_geometry import apply_ris_geometry_overrides
from .io import create_output_dir, save_json, save_yaml
from .metrics import build_paths_table, compute_path_metrics, extract_path_data
from .plots import plot_radio_map, plot_radio_map_sionna, plot_histogram, plot_rays_3d
from .viewer import generate_viewer
from .scene import (
    build_scene,
    export_scene_meshes,
    scene_sanity_report,
    _apply_default_radio_materials,
    _resolve_horn_pattern,
)
from .utils.progress import progress_steps
from .utils.system import (
    GpuMonitor,
    configure_tensorflow_memory_growth,
    configure_tensorflow_for_mitsuba_variant,
    select_mitsuba_variant,
    assert_mitsuba_variant,
    collect_environment_info,
    disable_pythreejs_import,
)

logger = logging.getLogger(__name__)


def _to_numpy(x):
    try:
        return x.numpy()
    except AttributeError:
        return np.asarray(x)


def _to_vec3(value: Any) -> Optional[np.ndarray]:
    try:
        vec = np.asarray(value, dtype=float).reshape(-1)
    except Exception:
        return None
    if vec.size < 3:
        return None
    return vec[:3].astype(float)


def _unit_vec(value: Any) -> Optional[np.ndarray]:
    vec = _to_vec3(value)
    if vec is None:
        return None
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return None
    return vec / norm


def _rotation_matrix(angles: Any) -> Optional[np.ndarray]:
    vec = _to_vec3(angles)
    if vec is None:
        return None
    a, b, c = vec
    cos_a = math.cos(a)
    cos_b = math.cos(b)
    cos_c = math.cos(c)
    sin_a = math.sin(a)
    sin_b = math.sin(b)
    sin_c = math.sin(c)
    return np.array(
        [
            [cos_a * cos_b, cos_a * sin_b * sin_c - sin_a * cos_c, cos_a * sin_b * cos_c + sin_a * sin_c],
            [sin_a * cos_b, sin_a * sin_b * sin_c + cos_a * cos_c, sin_a * sin_b * cos_c - cos_a * sin_c],
            [-sin_b, cos_b * sin_c, cos_b * cos_c],
        ],
        dtype=float,
    )


def _tx_forward_vector(scene_cfg: Dict[str, Any]) -> Optional[np.ndarray]:
    tx_cfg = scene_cfg.get("tx", {}) if isinstance(scene_cfg, dict) else {}
    tx_pos = _to_vec3(tx_cfg.get("position"))
    look_at = _to_vec3(tx_cfg.get("look_at"))
    if tx_pos is not None and look_at is not None:
        forward = _unit_vec(look_at - tx_pos)
        if forward is not None:
            return forward
    rot = _rotation_matrix(tx_cfg.get("orientation"))
    if rot is None:
        return None
    return _unit_vec(rot @ np.array([1.0, 0.0, 0.0], dtype=float))


def _ray_path_front_filter_enabled(cfg: Dict[str, Any], vis_cfg: Dict[str, Any]) -> bool:
    mode = vis_cfg.get("filter_tx_rear_paths", "auto")
    if isinstance(mode, str):
        mode_norm = mode.strip().lower()
        if mode_norm in {"false", "off", "disabled", "none", "0", "no"}:
            return False
        if mode_norm in {"true", "on", "enabled", "1", "yes"}:
            return True
    elif mode is not None:
        return bool(mode)

    scene_cfg = cfg.get("scene", {}) if isinstance(cfg, dict) else {}
    arrays_cfg = scene_cfg.get("arrays", {}) if isinstance(scene_cfg, dict) else {}
    tx_arr_cfg = arrays_cfg.get("tx", {}) if isinstance(arrays_cfg, dict) else {}
    horn_spec = _resolve_horn_pattern(tx_arr_cfg.get("pattern"))
    return bool(horn_spec and horn_spec.get("front_only"))


def _path_is_valid(valid_mask: np.ndarray, path_index: int) -> bool:
    valid = np.asarray(valid_mask, dtype=bool)
    if valid.size == 0:
        return True
    if valid.ndim == 0:
        return bool(valid.item())
    if valid.shape[-1] <= path_index:
        return False
    return bool(valid.reshape(-1, valid.shape[-1])[:, path_index].any())


def _extract_ray_path_segments(paths: Any, cfg: Dict[str, Any], vis_cfg: Dict[str, Any]) -> Dict[str, Any]:
    verts = _to_numpy(paths.vertices)
    interactions = _to_numpy(getattr(paths, "interactions", np.array([])))
    objects = _to_numpy(getattr(paths, "objects", np.array([])))
    valid = _to_numpy(getattr(paths, "targets_sources_mask", getattr(paths, "mask", np.array([])))).astype(bool)
    sources = _to_numpy(paths.sources)
    targets = _to_numpy(paths.targets)
    src = sources[0].reshape(3)
    tgt = targets[0].reshape(3)
    max_paths = int(vis_cfg.get("max_paths", 200))

    tx_forward = None
    if _ray_path_front_filter_enabled(cfg, vis_cfg):
        tx_forward = _tx_forward_vector(cfg.get("scene", {}))
        if tx_forward is None:
            logger.warning(
                "Ray-path Tx front filter requested but Tx forward direction is unavailable; exporting unfiltered paths."
            )

    segments = []
    num_vertices = verts.shape[0]
    num_paths = verts.shape[3]
    exported_paths = 0
    filtered_rear_paths = 0
    for p in range(num_paths):
        if not _path_is_valid(valid, p):
            continue
        pts = [src]
        if interactions.size:
            inter = interactions[:, 0, 0, p]
            valid_inter = inter != 0
        elif objects.size:
            inter = objects[:, 0, 0, p]
            valid_inter = inter != -1
        else:
            valid_inter = None
        v = verts[:, 0, 0, p, :]
        for i in range(num_vertices):
            if valid_inter is not None and valid_inter[i]:
                pts.append(v[i])
        pts.append(tgt)
        if len(pts) < 2:
            continue
        if tx_forward is not None:
            launch_dir = _unit_vec(np.asarray(pts[1], dtype=float) - np.asarray(pts[0], dtype=float))
            if launch_dir is None or float(np.dot(launch_dir, tx_forward)) <= 0.0:
                filtered_rear_paths += 1
                continue
        for i in range(len(pts) - 1):
            segments.append([p, *pts[i], *pts[i + 1]])
        exported_paths += 1
        if exported_paths >= max_paths:
            break

    return {
        "segments": np.asarray(segments, dtype=float) if segments else np.zeros((0, 7), dtype=float),
        "exported_paths": exported_paths,
        "filtered_rear_paths": filtered_rear_paths,
        "tx_position": src,
        "rx_position": tgt,
    }


def _radio_map_guide_paths(radio_map_cfg: Dict[str, Any]) -> list[Dict[str, Any]]:
    guide_paths = radio_map_cfg.get("guide_paths")
    if guide_paths is None:
        guide_paths = radio_map_cfg.get("specular_paths")
    if not isinstance(guide_paths, list):
        return []
    return [item for item in guide_paths if isinstance(item, dict)]


def _save_ris_profiles(scene, plots_dir: Path) -> None:
    try:
        ris_objects = getattr(scene, "ris", {})
    except Exception:
        ris_objects = {}
    if not ris_objects:
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    for name, ris in ris_objects.items():
        try:
            fig = ris.phase_profile.show(0)
            fig.savefig(plots_dir / f"ris_{name}_phase.png", dpi=160, bbox_inches="tight")
            plt.close(fig)
        except Exception:
            pass
        try:
            fig = ris.amplitude_profile.show(0)
            fig.savefig(plots_dir / f"ris_{name}_amplitude.png", dpi=160, bbox_inches="tight")
            plt.close(fig)
        except Exception:
            pass




def _assign_profile_values(profile: Any, values: Any) -> None:
    try:
        assign = getattr(profile.values, "assign", None)
        if callable(assign):
            assign(values)
            return
    except Exception:
        pass
    profile.values = values


def _snapshot_ris_amplitudes(scene: Any) -> Dict[str, Any]:
    snapshots: Dict[str, Any] = {}
    try:
        ris_objects = getattr(scene, "ris", {}) or {}
    except Exception:
        ris_objects = {}
    for name, ris in ris_objects.items():
        try:
            snapshots[name] = ris.amplitude_profile.values.numpy()
        except Exception:
            snapshots[name] = None
    return snapshots


def _apply_ris_amplitude_mask(scene: Any, enabled: set[str]) -> None:
    import tensorflow as tf

    try:
        ris_objects = getattr(scene, "ris", {}) or {}
    except Exception:
        ris_objects = {}
    for name, ris in ris_objects.items():
        if name in enabled:
            continue
        zeros = tf.zeros_like(ris.amplitude_profile.values)
        _assign_profile_values(ris.amplitude_profile, zeros)


def _restore_ris_amplitudes(scene: Any, snapshots: Dict[str, Any]) -> None:
    import tensorflow as tf

    try:
        ris_objects = getattr(scene, "ris", {}) or {}
    except Exception:
        ris_objects = {}
    for name, ris in ris_objects.items():
        saved = snapshots.get(name)
        if saved is None:
            continue
        _assign_profile_values(ris.amplitude_profile, tf.cast(saved, ris.amplitude_profile.values.dtype))


def _snapshot_ris_profiles(scene: Any) -> Dict[str, Dict[str, Any]]:
    snapshots: Dict[str, Dict[str, Any]] = {}
    try:
        ris_objects = getattr(scene, "ris", {}) or {}
    except Exception:
        ris_objects = {}
    for name, ris in ris_objects.items():
        phase_values = None
        amplitude_values = None
        mode_powers = None
        try:
            phase_values = ris.phase_profile.values.numpy()
        except Exception:
            phase_values = None
        try:
            amplitude_values = ris.amplitude_profile.values.numpy()
        except Exception:
            amplitude_values = None
        try:
            mode_powers = list(getattr(ris.amplitude_profile, "mode_powers", []) or [])
        except Exception:
            mode_powers = None
        snapshots[name] = {
            "phase": phase_values,
            "amplitude": amplitude_values,
            "mode_powers": mode_powers,
        }
    return snapshots


def _apply_ris_metal_baseline(scene: Any, *, amplitude: float = 1.0) -> None:
    import tensorflow as tf

    try:
        ris_objects = getattr(scene, "ris", {}) or {}
    except Exception:
        ris_objects = {}
    for _, ris in ris_objects.items():
        zero_phase = tf.zeros_like(ris.phase_profile.values)
        unit_amplitude = tf.ones_like(ris.amplitude_profile.values) * tf.cast(
            float(amplitude), ris.amplitude_profile.values.dtype
        )
        _assign_profile_values(ris.phase_profile, zero_phase)
        _assign_profile_values(ris.amplitude_profile, unit_amplitude)
        try:
            ris.amplitude_profile.mode_powers = [1.0] * int(getattr(ris, "num_modes", 1))
        except Exception:
            pass


def _restore_ris_profiles(scene: Any, snapshots: Dict[str, Dict[str, Any]]) -> None:
    import tensorflow as tf

    try:
        ris_objects = getattr(scene, "ris", {}) or {}
    except Exception:
        ris_objects = {}
    for name, ris in ris_objects.items():
        saved = snapshots.get(name) or {}
        phase_values = saved.get("phase")
        amplitude_values = saved.get("amplitude")
        if phase_values is not None:
            _assign_profile_values(ris.phase_profile, tf.cast(phase_values, ris.phase_profile.values.dtype))
        if amplitude_values is not None:
            _assign_profile_values(ris.amplitude_profile, tf.cast(amplitude_values, ris.amplitude_profile.values.dtype))
        if "mode_powers" in saved:
            try:
                ris.amplitude_profile.mode_powers = saved.get("mode_powers")
            except Exception:
                pass


def _rt_backend_from_variant(variant: str | None) -> str:
    if not variant:
        return "unknown"
    if "cuda" in variant:
        return "cuda/optix"
    if "llvm" in variant or "scalar" in variant:
        return "cpu/llvm"
    return "unknown"


def _format_radio_map_z_suffix(offset_m: float) -> str:
    sign = "p" if offset_m > 0.0 else "m"
    magnitude = f"{abs(float(offset_m)):.3f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"z{sign}{magnitude}m"


def _radio_map_z_slice_specs(radio_map_cfg: Optional[Dict[str, Any]]) -> list[Dict[str, Any]]:
    specs = []
    for offset_m in radio_map_z_slice_offsets(radio_map_cfg):
        specs.append(
            {
                "offset_m": float(offset_m),
                "suffix": _format_radio_map_z_suffix(offset_m),
                "display_label": f"z={offset_m:+.2f} m",
            }
        )
    return specs


def _format_radio_map_plane_z_token(z_m: float) -> str:
    if z_m < 0.0:
        return f"zm{abs(float(z_m)):.2f}".replace(".", "p")
    return f"z{float(z_m):.2f}".replace(".", "p")


def _radio_map_plot_filename_prefix(
    *,
    write_default: bool,
    suffix: Optional[str],
    metric_name: str,
    kwargs: Dict[str, Any],
) -> str:
    center = kwargs.get("cm_center")
    has_plane_z = isinstance(center, (list, tuple)) and len(center) >= 3
    if suffix and suffix.startswith("ris_off_z") and has_plane_z:
        try:
            return f"radio_map_ris_off_{metric_name}_{_format_radio_map_plane_z_token(float(center[2]))}"
        except Exception:
            pass
    if (write_default or (suffix and suffix.startswith("z") and suffix.endswith("m"))) and has_plane_z:
        try:
            return f"radio_map_{metric_name}_{_format_radio_map_plane_z_token(float(center[2]))}"
        except Exception:
            pass
    if write_default or not suffix:
        return f"radio_map_{metric_name}"
    if suffix.startswith("z") and suffix.endswith("m"):
        return f"radio_map_{metric_name}_{suffix}"
    return f"radio_map_{suffix}_{metric_name}"


def _radio_map_title_suffix(kwargs: Dict[str, Any]) -> str | None:
    center = kwargs.get("cm_center")
    if not isinstance(center, (list, tuple)) or len(center) < 3:
        return None
    try:
        return f"z={float(center[2]):.2f} m"
    except Exception:
        return None


def _format_tuning_summary(tuning: Dict[str, Any]) -> str:
    scale = tuning.get("scale_similarity", {})
    sampling = tuning.get("sampling_boost", {})

    scale_enabled = bool(scale.get("effective_enabled", False))
    factor = scale.get("factor", 1.0)
    original_f = scale.get("original_frequency_hz")
    scaled_f = scale.get("scaled_frequency_hz")
    scale_part = "Similarity scaling: OFF"
    if scale_enabled:
        try:
            original_ghz = float(original_f) / 1e9 if original_f is not None else None
            scaled_ghz = float(scaled_f) / 1e9 if scaled_f is not None else None
        except (TypeError, ValueError):
            original_ghz = None
            scaled_ghz = None
        if original_ghz is not None and scaled_ghz is not None:
            scale_part = (
                f"Similarity scaling: ON (s={factor:g}), f: {original_ghz:.3g} GHz -> {scaled_ghz:.3g} GHz"
            )
        else:
            scale_part = f"Similarity scaling: ON (s={factor:g})"

    sampling_enabled = bool(sampling.get("effective_enabled", False))
    sampling_part = "Sampling boost: OFF"
    if sampling_enabled:
        map_mult = sampling.get("map_resolution_multiplier", 1.0)
        ray_mult = sampling.get("ray_samples_multiplier", 1.0)
        depth_add = sampling.get("max_depth_add", 0)
        sampling_part = (
            f"Sampling boost: ON (map x{map_mult:g}, rays x{ray_mult:g}, depth +{depth_add})"
        )

    return f"{scale_part}; {sampling_part}"


def _compute_paths_with_current_flags(scene: Any, sim_cfg: Dict[str, Any], *, use_ris: bool) -> Any:
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


def _compute_ris_link_probe(
    scene: Any,
    sim_cfg: Dict[str, Any],
    tx_device: Any,
    metrics_on: Dict[str, Any],
    *,
    has_ris: bool,
    use_ris_paths: bool,
) -> Optional[Dict[str, Any]]:
    if not has_ris or not use_ris_paths:
        return None
    probe_mode = "metal_plate"
    snapshots = None
    try:
        snapshots = _snapshot_ris_profiles(scene)
        if snapshots:
            _apply_ris_metal_baseline(scene, amplitude=float(sim_cfg.get("ris_off_amplitude", 1.0)))
            paths_off = _compute_paths_with_current_flags(scene, sim_cfg, use_ris=True)
        else:
            probe_mode = "disabled_fallback"
            paths_off = _compute_paths_with_current_flags(scene, sim_cfg, use_ris=False)
        metrics_off = compute_path_metrics(paths_off, tx_power_dbm=tx_device.power_dbm, scene=scene)
    except Exception as exc:
        logger.warning("RIS link probe failed: %s", exc)
        return {"error": str(exc)}
    finally:
        if snapshots:
            _restore_ris_profiles(scene, snapshots)

    on_gain = metrics_on.get("total_path_gain_db")
    off_gain = metrics_off.get("total_path_gain_db")
    on_rx = metrics_on.get("rx_power_dbm_estimate")
    off_rx = metrics_off.get("rx_power_dbm_estimate")
    probe = {
        "on_total_path_gain_db": float(on_gain) if on_gain is not None else None,
        "off_total_path_gain_db": float(off_gain) if off_gain is not None else None,
        "on_rx_power_dbm_estimate": float(on_rx) if on_rx is not None else None,
        "off_rx_power_dbm_estimate": float(off_rx) if off_rx is not None else None,
        "off_mode": probe_mode,
    }
    if on_gain is not None and off_gain is not None:
        probe["delta_total_path_gain_db"] = float(on_gain - off_gain)
    if on_rx is not None and off_rx is not None:
        probe["delta_rx_power_dbm_estimate"] = float(on_rx - off_rx)
    return probe


def run_simulation(config_path: str, overrides: Optional[Dict[str, Any]] = None) -> Path:
    cfg = load_config(config_path)
    tuned_cfg, tuning_summary = apply_similarity_and_sampling(cfg.data, overrides=overrides)
    cfg.data = tuned_cfg
    if overrides and overrides.get("ris"):
        cfg.data = apply_ris_geometry_overrides(cfg.data, overrides.get("ris", {}))
    output_dir = create_output_dir(
        cfg.output.get("base_dir", "outputs"),
        run_id=cfg.output.get("run_id"),
    )
    save_yaml(output_dir / "config.yaml", cfg.data)
    config_hash = hashlib.sha256(json.dumps(cfg.data, sort_keys=True).encode("utf-8")).hexdigest()
    log_path = output_dir / "run.log"
    log_stream = log_path.open("a", encoding="utf-8")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    progress_path = output_dir / "progress.json"

    logger.info(_format_tuning_summary(tuning_summary))
    if tuning_summary.get("scale_similarity", {}).get("effective_enabled"):
        logger.info("Similarity scaling metadata: %s", tuning_summary.get("scale_similarity"))
        warning = tuning_summary.get("scale_similarity", {}).get("interpretation_warning")
        if warning:
            logger.info("Similarity scaling note: %s", warning)
    if tuning_summary.get("sampling_boost", {}).get("effective_enabled"):
        logger.info("Sampling boost applied: %s", tuning_summary.get("sampling_boost", {}).get("applied"))

    runtime_cfg = cfg.runtime
    if runtime_cfg.get("force_cpu"):
        # Ensure CPU fallback for both TF and Mitsuba.
        import os

        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    prefer_gpu = bool(runtime_cfg.get("prefer_gpu", True)) and not runtime_cfg.get("force_cpu")
    variant = select_mitsuba_variant(
        prefer_gpu=prefer_gpu,
        forced_variant=str(runtime_cfg.get("mitsuba_variant", "auto")),
        require_cuda=bool(runtime_cfg.get("require_cuda", False)),
    )
    assert_mitsuba_variant(variant, context="run_simulation")
    logger.info("Mitsuba variant selected: %s", variant)
    if prefer_gpu and "cuda" not in (variant or ""):
        logger.warning("GPU mode requested but CUDA variant not selected. Using %s", variant)
    if runtime_cfg.get("disable_pythreejs", True):
        disable_pythreejs_import("simulate")
    tf_device_info = configure_tensorflow_for_mitsuba_variant(variant)
    tf_info = configure_tensorflow_memory_growth(
        mode=str(runtime_cfg.get("tensorflow_import", "auto"))
    )
    if tf_device_info:
        tf_info.setdefault("device_policy", tf_device_info)
    tf_gpus = tf_info.get("tf_gpus") or []
    if "cuda" in (variant or "") and not tf_gpus:
        raise RuntimeError(
            "CUDA Mitsuba variant selected but TensorFlow GPU is unavailable. "
            "Install CUDA/CuDNN runtime libraries compatible with your TensorFlow build "
            "(TF 2.15 expects CUDA 12.2 + cuDNN 8) or install a TF build that matches "
            "your system CUDA. Otherwise use CPU (llvm) variants."
        )

    timings: Dict[str, float] = {}
    gpu_monitor = None
    monitor_cfg = runtime_cfg.get("gpu_monitor", {})
    if isinstance(monitor_cfg, dict) and monitor_cfg.get("enabled"):
        gpu_monitor = GpuMonitor(interval_s=float(monitor_cfg.get("interval_s", 0.5)))
        gpu_monitor.start()

    need_export = bool(cfg.scene.get("export_mesh", True))
    sim_cfg = dict(cfg.simulation)
    ris_isolation = bool(sim_cfg.get("ris_isolation", False))
    if ris_isolation:
        if sim_cfg.get("los", True) or sim_cfg.get("specular_reflection", True):
            logger.info(
                "RIS-only isolation active: forcing simulation.los=false and simulation.specular_reflection=false"
            )
        sim_cfg["los"] = False
        sim_cfg["specular_reflection"] = False
    compute_paths_enabled = bool(sim_cfg.get("compute_paths", True))
    steps = ["Build scene"]
    if need_export:
        steps.append("Export meshes")
    steps.append("Render scene")
    if compute_paths_enabled:
        steps.append("Ray trace paths")
    steps.append("Radio map")
    steps.append("Plots")

    plots_dir = output_dir / "plots"
    data_dir = output_dir / "data"
    plots_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    def write_progress(step_index: int, status: str) -> None:
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
        save_json(progress_path, payload)

    run_start = time.time()
    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            try:
                with progress_steps("Simulation", len(steps)) as (progress, task_id):
                    step_idx = 0
                    write_progress(step_idx, "running")
                    t0 = time.time()
                    progress.update(task_id, description=steps[0])
                    scene = build_scene(cfg.data, mitsuba_variant=variant)
                    timings["scene_build_s"] = time.time() - t0
                    scene_cfg = cfg.scene
                    if scene_cfg.get("type") == "file":
                        _apply_default_radio_materials(scene)
                    progress.advance(task_id)
                    step_idx += 1

                    _save_ris_profiles(scene, plots_dir)

                    if need_export:
                        progress.update(task_id, description="Export meshes")
                        write_progress(step_idx, "running")
                        scene_id = (
                            f"builtin-{scene_cfg.get('builtin', 'unknown')}"
                            if scene_cfg.get("type") == "builtin"
                            else f"file-{scene_cfg.get('file', 'scene')}"
                        )
                        try:
                            export_scene_meshes(
                                scene,
                                output_dir,
                                scene_id=scene_id,
                                cache_root=Path(cfg.output.get("base_dir", "outputs")) / "_cache",
                                scene_file=scene_cfg.get("file"),
                            )
                        except Exception as exc:  # pragma: no cover
                            logger.warning("Mesh export failed: %s", exc)
                        progress.advance(task_id)
                        step_idx += 1

                    # Render a static scene view (optical)
                    progress.update(task_id, description="Render scene")
                    write_progress(step_idx, "running")
                    render_cfg = cfg.data.get("render", {})
                    if render_cfg.get("enabled", True):
                        try:
                            from sionna.rt import Camera

                            cam_cfg = cfg.scene.get("camera", {})
                            cam = Camera(
                                name=cam_cfg.get("name", "camera"),
                                position=np.array(cam_cfg.get("position", [0.0, 80.0, 500.0])),
                                orientation=np.array(cam_cfg.get("orientation", [0.0, 1.5708, -1.5708])),
                            )
                            scene.render_to_file(
                                camera=cam,
                                filename=str(output_dir / "plots" / "scene.png"),
                                num_samples=int(render_cfg.get("samples", 64)),
                                resolution=tuple(render_cfg.get("resolution", [800, 600])),
                            )
                        except Exception as exc:  # pragma: no cover - optional rendering path
                            logger.warning("Scene render failed: %s", exc)
                    progress.advance(task_id)
                    step_idx += 1

                    ris_runtime = getattr(scene, "_ris_runtime", None)
                    ris_objects = {}
                    try:
                        ris_objects = getattr(scene, "ris", {}) or {}
                    except Exception:
                        ris_objects = {}
                    has_ris = bool(ris_runtime) or bool(ris_objects)
                    use_ris_paths = bool(sim_cfg.get("ris", False) or ris_runtime)
                    if use_ris_paths and not has_ris:
                        logger.warning("RIS enabled in config but no RIS objects are present; disabling RIS paths.")
                        use_ris_paths = False
                    paths = None
                    metrics = {}
                    path_data = {
                        "delays_s": np.array([]),
                        "weights": np.array([]),
                        "aoa_azimuth_rad": np.array([]),
                        "aoa_elevation_rad": np.array([]),
                    }
                    tx_device = next(iter(scene.transmitters.values()))
                    rx_device = next(iter(scene.receivers.values()), None)
                    tx_pos = _to_numpy(tx_device.position).reshape(-1)
                    rx_pos = _to_numpy(rx_device.position).reshape(-1) if rx_device is not None else None
                    if compute_paths_enabled:
                        t0 = time.time()
                        progress.update(task_id, description="Ray trace paths")
                        write_progress(step_idx, "running")
                        if ris_runtime:
                            logger.info("RIS enabled in scene (%d objects). compute_paths.ris=%s", len(ris_runtime), use_ris_paths)
                        paths = _compute_paths_with_current_flags(scene, sim_cfg, use_ris=use_ris_paths)
                        timings["path_tracing_s"] = time.time() - t0
                        progress.advance(task_id)
                        step_idx += 1

                        metrics = compute_path_metrics(paths, tx_power_dbm=tx_device.power_dbm, scene=scene)
                        if metrics.get("num_ris_paths") is not None:
                            logger.info("RIS paths detected: %s", metrics["num_ris_paths"])
                            if ris_runtime and metrics.get("num_ris_paths") == 0:
                                logger.warning(
                                    "RIS active but no RIS paths detected. "
                                    "Increase RIS size or move it between Tx and Rx to intersect rays."
                                )
                        path_data = extract_path_data(paths)
                        metrics.update(path_data.get("metrics", {}))
                        probe_t0 = time.time()
                        ris_link_probe = _compute_ris_link_probe(
                            scene,
                            sim_cfg,
                            tx_device,
                            metrics,
                            has_ris=has_ris,
                            use_ris_paths=use_ris_paths,
                        )
                        if ris_link_probe is not None:
                            timings["ris_link_probe_s"] = time.time() - probe_t0
                        if ris_link_probe is not None:
                            metrics["ris_link_probe"] = ris_link_probe
                            delta_gain = ris_link_probe.get("delta_total_path_gain_db")
                            if delta_gain is not None:
                                logger.info("RIS link probe: on-off total path gain delta = %.2f dB", float(delta_gain))
                        path_table = build_paths_table(paths, tx_power_dbm=tx_device.power_dbm)
                        if path_table["rows"]:
                            import csv

                            with (output_dir / "data" / "paths.csv").open("w", encoding="utf-8", newline="") as f:
                                writer = csv.writer(f)
                                writer.writerow(
                                    [
                                        "path_id",
                                        "order",
                                        "type",
                                        "path_length_m",
                                        "delay_s",
                                        "power_linear",
                                        "power_db",
                                        "interactions",
                                    ]
                                )
                                for row in path_table["rows"]:
                                    writer.writerow(
                                        [
                                            row["path_id"],
                                            row["order"],
                                            row["type"],
                                            f"{row['path_length_m']:.6f}",
                                            f"{row['delay_s']:.9e}",
                                            f"{row['power_linear']:.6e}",
                                        f"{row['power_db']:.3f}",
                                        ";".join(row["interactions"]),
                                    ]
                                )

                    radio_map_cfg = dict(cfg.radio_map)
                    if ris_isolation:
                        if radio_map_cfg.get("los", True) or radio_map_cfg.get("specular_reflection", True):
                            logger.info(
                                "RIS-only isolation active: forcing radio_map.los=false and radio_map.specular_reflection=false"
                            )
                        if radio_map_cfg.get("diff_ris", False):
                            logger.info("RIS-only isolation active: forcing radio_map.diff_ris=false")
                        radio_map_cfg["los"] = False
                        radio_map_cfg["specular_reflection"] = False
                        radio_map_cfg["diff_ris"] = False
                    radio_map = None
                    radio_map_summaries = []
                    radio_map_default_data = None
                    radio_map_visibility = None

                    def _maybe_autosize(target_cfg: Dict[str, Any]) -> Dict[str, Any]:
                        if not target_cfg.get("auto_size"):
                            return target_cfg
                        try:
                            bbox = scene.mi_scene.bbox()
                            padding = float(target_cfg.get("auto_padding", 0.0))
                            size_x = float(bbox.max.x - bbox.min.x) + padding * 2
                            size_y = float(bbox.max.y - bbox.min.y) + padding * 2
                            cell_size = target_cfg.get("cell_size", [2.0, 2.0])
                            if isinstance(cell_size, (list, tuple)) and len(cell_size) >= 2:
                                cell_x = float(cell_size[0]) if cell_size[0] else 0.0
                                cell_y = float(cell_size[1]) if cell_size[1] else 0.0
                                if cell_x > 0:
                                    size_x = math.ceil(size_x / cell_x) * cell_x
                                if cell_y > 0:
                                    size_y = math.ceil(size_y / cell_y) * cell_y
                            center = target_cfg.get("center") or [0.0, 0.0, 0.0]
                            center_z = center[2] if isinstance(center, list) and len(center) > 2 else 0.0
                            center = [
                                float(bbox.min.x + bbox.max.x) * 0.5,
                                float(bbox.min.y + bbox.max.y) * 0.5,
                                center_z,
                            ]
                            target_cfg = dict(target_cfg)
                            target_cfg["size"] = [size_x, size_y]
                            target_cfg["center"] = center
                        except Exception:
                            pass
                        return target_cfg

                    def _resolve_map_anchor(cfg_local: Dict[str, Any], use_ris_map: bool) -> Optional[list[float]]:
                        anchor_mode = str(cfg_local.get("cell_anchor", "auto")).strip().lower()
                        if anchor_mode in {"none", "off", "disabled", "false"}:
                            return None

                        anchor_xyz = cfg_local.get("cell_anchor_point")
                        if isinstance(anchor_xyz, (list, tuple)) and len(anchor_xyz) >= 3:
                            try:
                                return [float(anchor_xyz[0]), float(anchor_xyz[1]), float(anchor_xyz[2])]
                            except Exception:
                                return None

                        if anchor_mode in {"auto", "ris"} and use_ris_map:
                            try:
                                ris_values = list((getattr(scene, "ris", {}) or {}).values())
                            except Exception:
                                ris_values = []
                            if ris_values:
                                try:
                                    pos = _to_numpy(ris_values[0].position).reshape(-1)
                                    return [float(pos[0]), float(pos[1]), float(pos[2])]
                                except Exception:
                                    pass
                            if anchor_mode == "ris":
                                return None

                        if anchor_mode in {"auto", "tx"} and tx_pos is not None:
                            try:
                                return [float(tx_pos[0]), float(tx_pos[1]), float(tx_pos[2])]
                            except Exception:
                                return None

                        if anchor_mode in {"auto", "rx"} and rx_pos is not None:
                            try:
                                return [float(rx_pos[0]), float(rx_pos[1]), float(rx_pos[2])]
                            except Exception:
                                return None

                        return None

                    def _radio_map_kwargs(
                        target_cfg: Dict[str, Any], overrides: Dict[str, Any]
                    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
                        cfg_local = dict(target_cfg)
                        cfg_local.update(overrides)
                        cfg_local = _maybe_autosize(cfg_local)
                        # Apply Z-only override after autosize/center calculation.
                        if "center_z_only" in cfg_local:
                            try:
                                z_override = float(cfg_local.get("center_z_only"))
                            except Exception:
                                z_override = None
                            if z_override is not None:
                                center = cfg_local.get("center") or [0.0, 0.0, 0.0]
                                if isinstance(center, (list, tuple)) and len(center) >= 2:
                                    cfg_local = dict(cfg_local)
                                    cfg_local["center"] = [float(center[0]), float(center[1]), z_override]
                        if "ris" in overrides:
                            use_ris_map = bool(overrides.get("ris"))
                        else:
                            use_ris_map = bool(cfg_local.get("ris", False) or ris_runtime)
                        if use_ris_map and not has_ris:
                            logger.warning("RIS enabled for radio map but no RIS objects are present; disabling RIS.")
                            use_ris_map = False

                        alignment_info = None
                        visibility_info = None
                        if bool(cfg_local.get("align_grid_to_anchor", True)):
                            anchor = _resolve_map_anchor(cfg_local, use_ris_map=use_ris_map)
                            if anchor is not None:
                                aligned_center, alignment_info = align_center_to_anchor(
                                    cfg_local.get("center"),
                                    cfg_local.get("size"),
                                    cfg_local.get("cell_size", [2.0, 2.0]),
                                    anchor,
                                    inside_only=True,
                                )
                                if aligned_center is not None:
                                    cfg_local = dict(cfg_local)
                                    cfg_local["center"] = aligned_center
                                    if alignment_info and alignment_info.get("applied"):
                                        shift_xy = alignment_info.get("shift_xy_m", [0.0, 0.0])
                                        logger.info(
                                            "Aligned radio-map grid to anchor at [%.3f, %.3f, %.3f] with center shift [%.3f, %.3f] m",
                                            anchor[0],
                                            anchor[1],
                                            anchor[2],
                                            float(shift_xy[0]),
                                            float(shift_xy[1]),
                                        )
                        if use_ris_map:
                            try:
                                center_cfg = cfg_local.get("center") or [0.0, 0.0, 0.0]
                                plane_z = float(center_cfg[2]) if len(center_cfg) > 2 else 0.0
                            except Exception:
                                plane_z = None
                            ris_pos = None
                            ris_z = None
                            try:
                                ris_values = list((getattr(scene, "ris", {}) or {}).values())
                                if ris_values:
                                    ris_pos = _to_numpy(ris_values[0].position).reshape(-1)
                                    ris_z = float(ris_pos[2])
                            except Exception:
                                ris_z = None
                            if plane_z is not None and ris_z is not None:
                                dz = abs(plane_z - ris_z)
                                if dz > 0.75:
                                    logger.warning(
                                        "Radio-map plane z=%.3f differs from RIS z=%.3f by %.3fm. "
                                        "RIS reradiation may appear to start meters away because the 2D slice "
                                        "intersects the beam later. Consider setting center_z_only near Rx/RIS height.",
                                        plane_z,
                                        ris_z,
                                        dz,
                                    )
                            if rx_pos is not None and ris_pos is not None:
                                visibility_info = assess_ris_plane_visibility(
                                    ris_pos,
                                    rx_pos,
                                    cfg_local.get("orientation", [0.0, 0.0, 0.0]),
                                )
                                if visibility_info and visibility_info.get("beam_parallel_to_plane"):
                                    logger.warning(
                                        "Radio-map plane is %.2f deg from the RIS->Rx beam. "
                                        "coverage_map() samples intersections with the 2D slice, so a nearly in-plane "
                                        "RIS beam can miss the actual Tx/Rx boost. Use the RIS link probe or a vertical slice.",
                                        float(visibility_info.get("ris_to_rx_angle_from_plane_deg", 0.0)),
                                    )
                        kwargs = dict(
                            cm_center=cfg_local.get("center"),
                            cm_orientation=cfg_local.get("orientation", [0.0, 0.0, 0.0]),
                            cm_size=cfg_local.get("size"),
                            cm_cell_size=cfg_local.get("cell_size", [2.0, 2.0]),
                            num_samples=int(cfg_local.get("samples_per_tx", 200000)),
                            max_depth=int(cfg_local.get("max_depth", 3)),
                            los=bool(cfg_local.get("los", True)),
                            reflection=bool(cfg_local.get("specular_reflection", True)),
                            diffraction=bool(cfg_local.get("diffraction", False)),
                            scattering=bool(cfg_local.get("diffuse_reflection", False)),
                            ris=bool(use_ris_map),
                        )
                        if cfg_local.get("num_runs"):
                            kwargs["num_runs"] = int(cfg_local.get("num_runs"))
                        return kwargs, alignment_info, visibility_info

                    def _compute_radio_map(
                        label: str,
                        overrides: Dict[str, Any],
                        suffix: Optional[str],
                        write_default: bool,
                        enabled_ris: Optional[set[str]] = None,
                        baseline_mode: Optional[str] = None,
                        cfg_source: Optional[Dict[str, Any]] = None,
                        axis_labels: tuple[str, str] = ("x [m]", "y [m]"),
                    ) -> tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]]:
                        nonlocal radio_map
                        t0 = time.time()
                        progress.update(task_id, description=f"Radio map ({label})")
                        write_progress(step_idx, "running")
                        # Allow a Z-only override that doesn't affect X/Y center.
                        cfg_base = dict(cfg_source if cfg_source is not None else radio_map_cfg)
                        z_override = None
                        if "center_z_only" in cfg_base:
                            try:
                                z_override = float(cfg_base.get("center_z_only"))
                            except Exception:
                                z_override = None
                        if "center_z_only" in overrides:
                            try:
                                z_override = float(overrides.get("center_z_only"))
                            except Exception:
                                z_override = z_override
                        if z_override is not None:
                            cfg_base = dict(cfg_base)
                            cfg_base["center_z_only"] = z_override
                        kwargs, alignment_info, visibility_info = _radio_map_kwargs(cfg_base, overrides)
                        amplitude_snapshots = None
                        profile_snapshots = None
                        if baseline_mode == "metal_plate":
                            profile_snapshots = _snapshot_ris_profiles(scene)
                            if profile_snapshots:
                                _apply_ris_metal_baseline(
                                    scene,
                                    amplitude=float(cfg_source.get("ris_off_amplitude", radio_map_cfg.get("ris_off_amplitude", 1.0)))
                                    if isinstance(cfg_source, dict)
                                    else float(radio_map_cfg.get("ris_off_amplitude", 1.0)),
                                )
                        elif enabled_ris is not None:
                            amplitude_snapshots = _snapshot_ris_amplitudes(scene)
                            _apply_ris_amplitude_mask(scene, enabled_ris)
                        try:
                            result = scene.coverage_map(**kwargs)
                        finally:
                            if amplitude_snapshots is not None:
                                _restore_ris_amplitudes(scene, amplitude_snapshots)
                            if profile_snapshots is not None:
                                _restore_ris_profiles(scene, profile_snapshots)
                        timings_key = f"radio_map_{label}_s" if label else "radio_map_s"
                        timings[timings_key] = time.time() - t0
                        radio_map = result

                        path_gain = _to_numpy(result.path_gain)
                        cell_centers = _to_numpy(result.cell_centers)
                        path_gain_tx = path_gain[0] if path_gain.ndim == 3 else path_gain
                        path_gain_db = 10.0 * np.log10(path_gain_tx + 1e-12)
                        tx_power_dbm = _to_numpy(tx_device.power_dbm).item()
                        rx_power_dbm = tx_power_dbm + path_gain_db
                        path_loss_db = -path_gain_db

                        npz_name = "radio_map.npz" if write_default else f"radio_map_{suffix}.npz"
                        np.savez_compressed(
                            data_dir / npz_name,
                            path_gain_linear=path_gain_tx,
                            path_gain_db=path_gain_db,
                            rx_power_dbm=rx_power_dbm,
                            path_loss_db=path_loss_db,
                            cell_centers=cell_centers,
                        )

                        if write_default:
                            flat_gain = path_gain_db.reshape(-1)
                            flat_centers = cell_centers.reshape(-1, 3)
                            csv_data = np.column_stack([flat_centers, flat_gain])
                            np.savetxt(
                                data_dir / "radio_map.csv",
                                csv_data,
                                delimiter=",",
                                header="x,y,z,path_gain_db",
                                comments="",
                            )

                        plot_style = str(cfg_base.get("plot_style", "heatmap")).lower()
                        title_suffix = _radio_map_title_suffix(kwargs)
                        if plot_style == "sionna":
                            plot_metrics = cfg_base.get("plot_metrics", "path_gain")
                            if isinstance(plot_metrics, str):
                                plot_metrics = [plot_metrics]
                            show_tx = bool(cfg_base.get("plot_show_tx", True))
                            show_rx = bool(cfg_base.get("plot_show_rx", False))
                            show_ris = bool(cfg_base.get("plot_show_ris", False))
                            vmin = cfg_base.get("plot_vmin")
                            vmax = cfg_base.get("plot_vmax")
                            for metric in plot_metrics:
                                metric_name = str(metric)
                                plot_radio_map_sionna(
                                    radio_map,
                                    plots_dir,
                                    metric=metric_name,
                                    filename_prefix=_radio_map_plot_filename_prefix(
                                        write_default=write_default,
                                        suffix=suffix,
                                        metric_name=metric_name,
                                        kwargs=kwargs,
                                    ),
                                    tx=cfg_base.get("plot_tx"),
                                    vmin=vmin,
                                    vmax=vmax,
                                    show_tx=show_tx,
                                    show_rx=show_rx,
                                    show_ris=show_ris,
                                    title_suffix=title_suffix,
                                )
                        else:
                            ris_positions = []
                            try:
                                ris_positions = [np.asarray(r.position).reshape(-1) for r in scene.ris.values()]
                            except Exception:
                                ris_positions = []
                            guide_paths = _radio_map_guide_paths(cfg_base)
                            plot_radio_map(
                                path_gain_db,
                                cell_centers,
                                plots_dir,
                                metric_label="Path gain [dB]",
                                filename_prefix=_radio_map_plot_filename_prefix(
                                    write_default=write_default,
                                    suffix=suffix,
                                    metric_name="path_gain_db",
                                    kwargs=kwargs,
                                ),
                                tx_pos=tx_pos,
                                rx_pos=rx_pos,
                                ris_positions=ris_positions,
                                guide_paths=guide_paths,
                                axis_labels=axis_labels,
                                title_suffix=title_suffix,
                            )
                            plot_radio_map(
                                rx_power_dbm,
                                cell_centers,
                                plots_dir,
                                metric_label="Rx power [dBm]",
                                filename_prefix=_radio_map_plot_filename_prefix(
                                    write_default=write_default,
                                    suffix=suffix,
                                    metric_name="rx_power_dbm",
                                    kwargs=kwargs,
                                ),
                                tx_pos=tx_pos,
                                rx_pos=rx_pos,
                                ris_positions=ris_positions,
                                guide_paths=guide_paths,
                                axis_labels=axis_labels,
                                title_suffix=title_suffix,
                            )
                            plot_radio_map(
                                path_loss_db,
                                cell_centers,
                                plots_dir,
                                metric_label="Path loss [dB]",
                                filename_prefix=_radio_map_plot_filename_prefix(
                                    write_default=write_default,
                                    suffix=suffix,
                                    metric_name="path_loss_db",
                                    kwargs=kwargs,
                                ),
                                tx_pos=tx_pos,
                                rx_pos=rx_pos,
                                ris_positions=ris_positions,
                                guide_paths=guide_paths,
                                axis_labels=axis_labels,
                                title_suffix=title_suffix,
                            )

                        stats = {
                            "path_gain_db_min": float(np.min(path_gain_db)),
                            "path_gain_db_mean": float(np.mean(path_gain_db)),
                            "path_gain_db_max": float(np.max(path_gain_db)),
                            "rx_power_dbm_min": float(np.min(rx_power_dbm)),
                            "rx_power_dbm_mean": float(np.mean(rx_power_dbm)),
                            "rx_power_dbm_max": float(np.max(rx_power_dbm)),
                            "path_loss_db_min": float(np.min(path_loss_db)),
                            "path_loss_db_mean": float(np.mean(path_loss_db)),
                            "path_loss_db_max": float(np.max(path_loss_db)),
                            "grid_shape": list(path_gain_db.shape[-2:]),
                        }
                        summary = {
                            "label": label,
                            "suffix": suffix,
                            "stats": stats,
                            "parameters": kwargs,
                        }
                        if baseline_mode:
                            summary["baseline_mode"] = baseline_mode
                        center_cfg = kwargs.get("cm_center")
                        if isinstance(center_cfg, (list, tuple)) and len(center_cfg) >= 3:
                            try:
                                summary["plane_center_z_m"] = float(center_cfg[2])
                            except Exception:
                                pass
                        if alignment_info is not None:
                            summary["grid_alignment"] = alignment_info
                        if visibility_info is not None:
                            summary["visibility"] = visibility_info
                        data = {
                            "path_gain_db": path_gain_db,
                            "rx_power_dbm": rx_power_dbm,
                            "path_loss_db": path_loss_db,
                            "cell_centers": cell_centers,
                        }
                        return summary, data, visibility_info

                    write_progress(step_idx, "running")
                    if radio_map_cfg.get("enabled", False):
                        summary, radio_map_default_data, radio_map_visibility = _compute_radio_map(
                            label="default",
                            overrides={},
                            suffix=None,
                            write_default=True,
                        )
                        radio_map_issue = diagnose_ris_map_sampling_issue(
                            summary.get("stats"),
                            radio_map_visibility,
                            metrics.get("ris_link_probe"),
                        )
                        if radio_map_issue is not None:
                            metrics["radio_map_issue"] = radio_map_issue
                            logger.warning("%s %s", radio_map_issue["message"], radio_map_issue["recommended_action"])
                        radio_map_summaries.append(summary)
                        progress.advance(task_id)
                        step_idx += 1

                        base_plane_z_m = 0.0
                        try:
                            if "center_z_only" in radio_map_cfg:
                                base_plane_z_m = float(radio_map_cfg.get("center_z_only"))
                            else:
                                center_cfg = radio_map_cfg.get("center") or [0.0, 0.0, 0.0]
                                if isinstance(center_cfg, (list, tuple)) and len(center_cfg) >= 3:
                                    base_plane_z_m = float(center_cfg[2])
                        except Exception:
                            base_plane_z_m = 0.0
                        z_slice_specs = _radio_map_z_slice_specs(radio_map_cfg)
                        for slice_spec in z_slice_specs:
                            offset_m = float(slice_spec["offset_m"])
                            summary_slice, _, _ = _compute_radio_map(
                                label=str(slice_spec["suffix"]),
                                overrides={"center_z_only": float(base_plane_z_m + offset_m)},
                                suffix=str(slice_spec["suffix"]),
                                write_default=False,
                            )
                            summary_slice["z_offset_m"] = offset_m
                            summary_slice["display_label"] = str(slice_spec["display_label"])
                            radio_map_summaries.append(summary_slice)

                        tx_ris_slice_cfg = radio_map_cfg.get("tx_ris_incidence", {})
                        if isinstance(tx_ris_slice_cfg, dict) and tx_ris_slice_cfg.get("enabled", False):
                            ris_positions = []
                            try:
                                ris_positions = [np.asarray(r.position).reshape(-1) for r in scene.ris.values()]
                            except Exception:
                                ris_positions = []
                            if tx_pos is None or not ris_positions:
                                logger.warning(
                                    "Tx->RIS incidence radio map requested but Tx or RIS positions are unavailable; skipping."
                                )
                            else:
                                derived_slice = derive_tx_ris_incidence_slice(
                                    tx_pos,
                                    ris_positions[0],
                                    radio_map_cfg=radio_map_cfg,
                                    slice_cfg=tx_ris_slice_cfg,
                                )
                                if derived_slice is None:
                                    logger.warning("Tx->RIS incidence radio map could not derive a valid slice; skipping.")
                                else:
                                    incidence_cfg = dict(radio_map_cfg)
                                    incidence_cfg.pop("center_z_only", None)
                                    for key, value in derived_slice.items():
                                        if key == "plot_axis_labels":
                                            continue
                                        incidence_cfg[key] = value
                                    for key, value in tx_ris_slice_cfg.items():
                                        if key != "enabled":
                                            incidence_cfg[key] = value
                                    axis_labels_local = tuple(derived_slice.get("plot_axis_labels", ["x [m]", "y [m]"]))
                                    summary_incidence, _, _ = _compute_radio_map(
                                        label="tx_ris_incidence",
                                        overrides={},
                                        suffix="tx_ris_incidence",
                                        write_default=False,
                                        cfg_source=incidence_cfg,
                                        axis_labels=(
                                            str(axis_labels_local[0]),
                                            str(axis_labels_local[1]),
                                        ),
                                    )
                                    radio_map_summaries.append(summary_incidence)

                        if has_ris and bool(radio_map_cfg.get("ris_off_map", False)):
                            summary_ris_off, _, _ = _compute_radio_map(
                                label="ris_off",
                                overrides={"ris": True},
                                suffix="ris_off",
                                write_default=False,
                                baseline_mode="metal_plate",
                            )
                            radio_map_summaries.append(summary_ris_off)
                            for slice_spec in z_slice_specs:
                                offset_m = float(slice_spec["offset_m"])
                                summary_ris_off_slice, _, _ = _compute_radio_map(
                                    label=f"ris_off_{slice_spec['suffix']}",
                                    overrides={
                                        "ris": True,
                                        "center_z_only": float(base_plane_z_m + offset_m),
                                    },
                                    suffix=f"ris_off_{slice_spec['suffix']}",
                                    write_default=False,
                                    baseline_mode="metal_plate",
                                )
                                summary_ris_off_slice["z_offset_m"] = offset_m
                                summary_ris_off_slice["display_label"] = f"RIS off {slice_spec['display_label']}"
                                radio_map_summaries.append(summary_ris_off_slice)

                    else:
                        progress.update(task_id, description="Radio map (skipped)")
                        progress.advance(task_id)
                        step_idx += 1

                    if radio_map_cfg.get("diff_ris", False) and radio_map_default_data is not None:
                        default_ris = bool(radio_map_cfg.get("ris", False) or ris_runtime)
                        alt_ris = not default_ris
                        alt_label = "ris_on" if alt_ris else "no_ris"
                        diff_overrides: Dict[str, Any] = {"ris": alt_ris}
                        default_anchor = None
                        try:
                            default_anchor = summary.get("grid_alignment", {}).get("anchor")
                        except Exception:
                            default_anchor = None
                        if isinstance(default_anchor, (list, tuple)) and len(default_anchor) >= 3:
                            diff_overrides["cell_anchor_point"] = [
                                float(default_anchor[0]),
                                float(default_anchor[1]),
                                float(default_anchor[2]),
                            ]
                        summary_alt, radio_map_alt_data, _ = _compute_radio_map(
                            label=alt_label,
                            overrides=diff_overrides,
                            suffix=alt_label,
                            write_default=False,
                        )
                        radio_map_summaries.append(summary_alt)

                        base_data = radio_map_alt_data if default_ris else radio_map_default_data
                        ris_data = radio_map_default_data if default_ris else radio_map_alt_data
                        try:
                            base_centers = base_data["cell_centers"]
                            ris_centers = ris_data["cell_centers"]
                            if base_centers.shape != ris_centers.shape or not np.allclose(base_centers, ris_centers):
                                logger.warning("Radio map diff skipped: grid mismatch between RIS and baseline.")
                            else:
                                diff_db = ris_data["path_gain_db"] - base_data["path_gain_db"]
                                np.savez_compressed(
                                    data_dir / "radio_map_diff.npz",
                                    path_gain_db=diff_db,
                                    cell_centers=ris_centers,
                                )
                                plot_radio_map(
                                    diff_db,
                                    ris_centers,
                                    plots_dir,
                                    metric_label="RIS ΔPath gain [dB]",
                                    filename_prefix="radio_map_diff_path_gain_db",
                                    tx_pos=tx_pos,
                                    rx_pos=rx_pos,
                                    ris_positions=[np.asarray(r.position).reshape(-1) for r in scene.ris.values()] if hasattr(scene, "ris") else [],
                                    guide_paths=_radio_map_guide_paths(radio_map_cfg),
                                )
                                metrics["radio_map_diff"] = {
                                    "path_gain_db_min": float(np.min(diff_db)),
                                    "path_gain_db_mean": float(np.mean(diff_db)),
                                    "path_gain_db_max": float(np.max(diff_db)),
                                }
                        except Exception as exc:
                            logger.warning("Radio map diff failed: %s", exc)


                    write_progress(step_idx, "running")
                    if radio_map is not None:
                        progress.update(task_id, description="Plots")
                    else:
                        progress.update(task_id, description="Plots (skipped)")
                    plot_t0 = time.time()
                    if path_data["delays_s"].size > 0:
                        plot_histogram(
                            path_data["delays_s"],
                            path_data["weights"],
                            plots_dir,
                            title="Path Delay Distribution",
                            xlabel="Delay [s]",
                            filename_prefix="path_delay_hist",
                        )
                        plot_histogram(
                            np.degrees(path_data["aoa_azimuth_rad"]),
                            path_data["weights"],
                            plots_dir,
                            title="AoA Azimuth Distribution",
                            xlabel="Azimuth [deg]",
                            filename_prefix="aoa_azimuth_hist",
                        )
                        plot_histogram(
                            np.degrees(path_data["aoa_elevation_rad"]),
                            path_data["weights"],
                            plots_dir,
                            title="AoA Elevation Distribution",
                            xlabel="Elevation [deg]",
                            filename_prefix="aoa_elevation_hist",
                        )
                    if radio_map_summaries:
                        metrics["radio_map"] = radio_map_summaries
                    if radio_map_visibility is not None:
                        metrics["radio_map_visibility"] = radio_map_visibility
                    timings["plots_s"] = time.time() - plot_t0
                    progress.advance(task_id)
                    write_progress(len(steps), "completed")

                # Export ray-path segments for 3D visualization
                vis_cfg = cfg.data.get("visualization", {}).get("ray_paths", {})
                if vis_cfg.get("enabled", True) and paths is not None:
                    try:
                        export = _extract_ray_path_segments(paths, cfg.data, vis_cfg)
                        segments_arr = export["segments"]
                        if segments_arr.size:
                            np.savetxt(
                                data_dir / "ray_paths.csv",
                                segments_arr,
                                delimiter=",",
                                header="path_id,x0,y0,z0,x1,y1,z1",
                                comments="",
                            )
                            np.savez_compressed(data_dir / "ray_paths.npz", segments=segments_arr)
                            plot_rays_3d(
                                segments_arr,
                                tx_pos=export["tx_position"],
                                rx_pos=export["rx_position"],
                                output_dir=output_dir / "plots",
                            )
                            metrics["ray_paths_exported"] = int(export["exported_paths"])
                            metrics["ray_segments_exported"] = int(len(segments_arr))
                            if export["filtered_rear_paths"] > 0:
                                metrics["ray_paths_filtered_tx_rear"] = int(export["filtered_rear_paths"])
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Ray path export failed: %s", exc)

                timings["total_s"] = time.time() - run_start
                summary = {
                    "metrics": metrics,
                    "scene_sanity": scene_sanity_report(scene, cfg.data),
                    "simulation_tuning": tuning_summary,
                    "runtime": {
                        "mitsuba_variant": variant,
                        "rt_backend": _rt_backend_from_variant(variant),
                        "tensorflow": tf_info,
                        "timings_s": timings,
                    },
                    "environment": collect_environment_info(),
                    "config": {
                        "hash_sha256": config_hash,
                        "path": str(output_dir / "config.yaml"),
                    },
                }
                ris_summary = getattr(scene, "_ris_runtime", None)
                if ris_summary is not None:
                    summary["runtime"]["ris_enabled"] = True
                    summary["runtime"]["ris_objects"] = ris_summary
                else:
                    summary["runtime"]["ris_enabled"] = False
                if gpu_monitor is not None:
                    summary["runtime"]["gpu_monitor"] = gpu_monitor.summary()

                save_json(output_dir / "summary.json", summary)
                viewer_cfg = cfg.data.get("viewer", {}) if isinstance(cfg.data.get("viewer"), dict) else {}
                if viewer_cfg.get("enabled", True):
                    try:
                        generate_viewer(output_dir, cfg.data, scene=scene)
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Viewer generation failed: %s", exc)
                logger.info("Run complete: %s", output_dir)

                return output_dir
            except Exception:
                logger.exception("Simulation failed")
                raise
    finally:
        if gpu_monitor is not None:
            gpu_monitor.stop()
        root_logger.removeHandler(file_handler)
        file_handler.close()
        log_stream.close()
