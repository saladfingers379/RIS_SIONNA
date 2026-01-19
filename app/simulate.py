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
from .io import create_output_dir, save_json, save_yaml
from .metrics import build_paths_table, compute_path_metrics, extract_path_data
from .plots import plot_radio_map, plot_histogram, plot_rays_3d
from .viewer import generate_viewer
from .scene import build_scene, export_scene_meshes, scene_sanity_report
from .utils.progress import progress_steps
from .utils.system import (
    GpuMonitor,
    configure_tensorflow_memory_growth,
    select_mitsuba_variant,
    collect_environment_info,
    disable_pythreejs_import,
)

logger = logging.getLogger(__name__)


def _to_numpy(x):
    try:
        return x.numpy()
    except AttributeError:
        return np.asarray(x)


def _rt_backend_from_variant(variant: str | None) -> str:
    if not variant:
        return "unknown"
    if "cuda" in variant:
        return "cuda/optix"
    if "llvm" in variant or "scalar" in variant:
        return "cpu/llvm"
    return "unknown"


def run_simulation(config_path: str) -> Path:
    cfg = load_config(config_path)
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

    runtime_cfg = cfg.runtime
    if runtime_cfg.get("force_cpu"):
        # Ensure CPU fallback for both TF and Mitsuba.
        import os

        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    prefer_gpu = bool(runtime_cfg.get("prefer_gpu", True)) and not runtime_cfg.get("force_cpu")
    variant = select_mitsuba_variant(
        prefer_gpu=prefer_gpu,
        forced_variant=str(runtime_cfg.get("mitsuba_variant", "auto")),
    )
    if runtime_cfg.get("disable_pythreejs", True):
        disable_pythreejs_import("simulate")
    tf_info = configure_tensorflow_memory_growth(
        mode=str(runtime_cfg.get("tensorflow_import", "auto"))
    )

    timings: Dict[str, float] = {}
    gpu_monitor = None
    monitor_cfg = runtime_cfg.get("gpu_monitor", {})
    if isinstance(monitor_cfg, dict) and monitor_cfg.get("enabled"):
        gpu_monitor = GpuMonitor(interval_s=float(monitor_cfg.get("interval_s", 0.5)))
        gpu_monitor.start()

    need_export = bool(cfg.scene.get("export_mesh", True))
    benchmark_cfg = cfg.data.get("benchmark", {})
    benchmark_levels = benchmark_cfg.get("radio_map_levels", []) if isinstance(benchmark_cfg, dict) else []
    benchmark_enabled = bool(benchmark_cfg.get("enabled")) and bool(benchmark_levels)
    steps = ["Build scene"]
    if need_export:
        steps.append("Export meshes")
    steps.append("Render scene")
    steps.append("Ray trace paths")
    if benchmark_enabled:
        for level in benchmark_levels:
            label = level.get("name") or f"{level.get('grid_shape', ['?', '?'])[0]}x{level.get('grid_shape', ['?', '?'])[1]}"
            steps.append(f"Radio map ({label})")
    else:
        steps.append("Radio map")
    steps.append("Plots")

    plots_dir = output_dir / "plots"
    data_dir = output_dir / "data"

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
                    scene = build_scene(cfg.data)
                    timings["scene_build_s"] = time.time() - t0
                    scene_cfg = cfg.scene
                    progress.advance(task_id)
                    step_idx += 1

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

                    from sionna.rt import PathSolver, RadioMapSolver

                    sim_cfg = cfg.simulation
                    t0 = time.time()
                    progress.update(task_id, description="Ray trace paths")
                    write_progress(step_idx, "running")
                    path_solver = PathSolver()
                    paths = path_solver(
                        scene,
                        max_depth=int(sim_cfg.get("max_depth", 3)),
                        max_num_paths_per_src=int(sim_cfg.get("max_num_paths_per_src", 200000)),
                        samples_per_src=int(sim_cfg.get("samples_per_src", 200000)),
                        los=bool(sim_cfg.get("los", True)),
                        specular_reflection=bool(sim_cfg.get("specular_reflection", True)),
                        diffuse_reflection=bool(sim_cfg.get("diffuse_reflection", False)),
                        refraction=bool(sim_cfg.get("refraction", True)),
                        diffraction=bool(sim_cfg.get("diffraction", False)),
                    )
                    timings["path_tracing_s"] = time.time() - t0
                    progress.advance(task_id)
                    step_idx += 1

                    tx_device = next(iter(scene.transmitters.values()))
                    rx_device = next(iter(scene.receivers.values()), None)
                    tx_pos = _to_numpy(tx_device.position).reshape(-1)
                    rx_pos = _to_numpy(rx_device.position).reshape(-1) if rx_device is not None else None
                    metrics = compute_path_metrics(paths, tx_power_dbm=tx_device.power_dbm)
                    path_data = extract_path_data(paths)
                    metrics.update(path_data.get("metrics", {}))
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

                    radio_map_cfg = cfg.radio_map
                    radio_map = None
                    radio_map_summaries = []

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

                    def _radio_map_kwargs(target_cfg: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
                        cfg_local = dict(target_cfg)
                        cfg_local.update(overrides)
                        cfg_local = _maybe_autosize(cfg_local)
                        kwargs = dict(
                            center=cfg_local.get("center"),
                            orientation=cfg_local.get("orientation", [0.0, 0.0, 0.0]),
                            size=cfg_local.get("size"),
                            cell_size=cfg_local.get("cell_size", [2.0, 2.0]),
                            samples_per_tx=int(cfg_local.get("samples_per_tx", 200000)),
                            max_depth=int(cfg_local.get("max_depth", 3)),
                            los=bool(cfg_local.get("los", True)),
                            specular_reflection=bool(cfg_local.get("specular_reflection", True)),
                            diffuse_reflection=bool(cfg_local.get("diffuse_reflection", False)),
                            refraction=bool(cfg_local.get("refraction", True)),
                            diffraction=bool(cfg_local.get("diffraction", False)),
                        )
                        if cfg_local.get("batch_size"):
                            kwargs["batch_size"] = int(cfg_local.get("batch_size"))
                        return kwargs

                    def _compute_radio_map(
                        rm_solver: RadioMapSolver,
                        label: str,
                        overrides: Dict[str, Any],
                        suffix: Optional[str],
                        write_default: bool,
                    ) -> Dict[str, Any]:
                        nonlocal radio_map
                        t0 = time.time()
                        progress.update(task_id, description=f"Radio map ({label})")
                        write_progress(step_idx, "running")
                        kwargs = _radio_map_kwargs(radio_map_cfg, overrides)
                        try:
                            result = rm_solver(scene, **kwargs)
                        except TypeError:
                            kwargs.pop("batch_size", None)
                            result = rm_solver(scene, **kwargs)
                        timings_key = f"radio_map_{label}_s" if label else "radio_map_s"
                        timings[timings_key] = time.time() - t0
                        radio_map = result

                        path_gain = _to_numpy(result.path_gain)
                        cell_centers = _to_numpy(result.cell_centers)
                        path_gain_db = 10.0 * np.log10(path_gain + 1e-12)
                        tx_power_dbm = _to_numpy(tx_device.power_dbm).item()
                        rx_power_dbm = tx_power_dbm + path_gain_db
                        path_loss_db = -path_gain_db

                        npz_name = "radio_map.npz" if write_default else f"radio_map_{suffix}.npz"
                        np.savez_compressed(
                            data_dir / npz_name,
                            path_gain_linear=path_gain,
                            path_gain_db=path_gain_db,
                            rx_power_dbm=rx_power_dbm,
                            path_loss_db=path_loss_db,
                            cell_centers=cell_centers,
                        )

                        if write_default:
                            flat_gain = path_gain_db[0].reshape(-1)
                            flat_centers = cell_centers.reshape(-1, 3)
                            csv_data = np.column_stack([flat_centers, flat_gain])
                            np.savetxt(
                                data_dir / "radio_map.csv",
                                csv_data,
                                delimiter=",",
                                header="x,y,z,path_gain_db",
                                comments="",
                            )

                        prefix = "radio_map" if write_default else f"radio_map_{suffix}"
                        plot_radio_map(
                            path_gain_db,
                            cell_centers,
                            plots_dir,
                            metric_label="Path gain [dB]",
                            filename_prefix=f"{prefix}_path_gain_db",
                            tx_pos=tx_pos,
                            rx_pos=rx_pos,
                        )
                        plot_radio_map(
                            rx_power_dbm,
                            cell_centers,
                            plots_dir,
                            metric_label="Rx power [dBm]",
                            filename_prefix=f"{prefix}_rx_power_dbm",
                            tx_pos=tx_pos,
                            rx_pos=rx_pos,
                        )
                        plot_radio_map(
                            path_loss_db,
                            cell_centers,
                            plots_dir,
                            metric_label="Path loss [dB]",
                            filename_prefix=f"{prefix}_path_loss_db",
                            tx_pos=tx_pos,
                            rx_pos=rx_pos,
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
                        return {
                            "label": label,
                            "suffix": suffix,
                            "stats": stats,
                            "parameters": kwargs,
                        }

                    write_progress(step_idx, "running")
                    if benchmark_enabled:
                        rm_solver = RadioMapSolver()
                        benchmark_overrides = benchmark_cfg.get("radio_map", {}) if isinstance(benchmark_cfg, dict) else {}
                        for idx, level in enumerate(benchmark_levels):
                            level_name = level.get("name") or f"level_{idx+1}"
                            grid_shape = level.get("grid_shape")
                            cell_size = level.get("cell_size", radio_map_cfg.get("cell_size", [2.0, 2.0]))
                            overrides = dict(benchmark_overrides)
                            if grid_shape and isinstance(grid_shape, (list, tuple)) and len(grid_shape) >= 2:
                                overrides["size"] = [
                                    float(grid_shape[1]) * float(cell_size[0]),
                                    float(grid_shape[0]) * float(cell_size[1]),
                                ]
                                overrides["cell_size"] = list(cell_size)
                            elif level.get("size"):
                                overrides["size"] = level.get("size")
                                overrides["cell_size"] = list(cell_size)
                            if level.get("center"):
                                overrides["center"] = level.get("center")
                            if level.get("orientation"):
                                overrides["orientation"] = level.get("orientation")
                            suffix = level.get("name", f"level_{idx+1}")
                            summary = _compute_radio_map(
                                rm_solver,
                                label=level_name,
                                overrides=overrides,
                                suffix=suffix,
                                write_default=(idx == len(benchmark_levels) - 1),
                            )
                            radio_map_summaries.append(summary)
                            progress.advance(task_id)
                            step_idx += 1
                    elif radio_map_cfg.get("enabled", False):
                        rm_solver = RadioMapSolver()
                        summary = _compute_radio_map(
                            rm_solver,
                            label="default",
                            overrides={},
                            suffix=None,
                            write_default=True,
                        )
                        radio_map_summaries.append(summary)
                        progress.advance(task_id)
                        step_idx += 1
                    else:
                        progress.update(task_id, description="Radio map (skipped)")
                        progress.advance(task_id)
                        step_idx += 1

                    write_progress(step_idx, "running")
                    if radio_map is not None:
                        progress.update(task_id, description="Plots")
                    else:
                        progress.update(task_id, description="Plots (skipped)")
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
                    progress.advance(task_id)
                    write_progress(len(steps), "completed")

                # Export ray-path segments for 3D visualization
                vis_cfg = cfg.data.get("visualization", {}).get("ray_paths", {})
                if vis_cfg.get("enabled", True):
                    try:
                        verts = _to_numpy(paths.vertices)
                        interactions = _to_numpy(paths.interactions)
                        valid = _to_numpy(paths.valid).astype(bool)
                        src = _to_numpy(paths.sources).reshape(3)
                        tgt = _to_numpy(paths.targets).reshape(3)
                        max_paths = int(vis_cfg.get("max_paths", 200))

                        segments = []
                        path_id = 0
                        num_vertices = verts.shape[0]
                        num_paths = verts.shape[3]
                        for p in range(num_paths):
                            if not valid[0, 0, p]:
                                continue
                            pts = [src]
                            inter = interactions[:, 0, 0, p]
                            v = verts[:, 0, 0, p, :]
                            for i in range(num_vertices):
                                if inter[i] != 0:
                                    pts.append(v[i])
                            pts.append(tgt)
                            if len(pts) < 2:
                                continue
                            for i in range(len(pts) - 1):
                                segments.append([path_id, *pts[i], *pts[i + 1]])
                            path_id += 1
                            if path_id >= max_paths:
                                break

                        if segments:
                            segments_arr = np.array(segments)
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
                                tx_pos=src,
                                rx_pos=tgt,
                                output_dir=output_dir / "plots",
                            )
                            metrics["ray_paths_exported"] = int(path_id)
                            metrics["ray_segments_exported"] = int(len(segments))
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Ray path export failed: %s", exc)

                timings["total_s"] = time.time() - run_start
                summary = {
                    "metrics": metrics,
                    "scene_sanity": scene_sanity_report(scene, cfg.data),
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
                if gpu_monitor is not None:
                    summary["runtime"]["gpu_monitor"] = gpu_monitor.summary()

                save_json(output_dir / "summary.json", summary)
                try:
                    generate_viewer(output_dir, cfg.data)
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
