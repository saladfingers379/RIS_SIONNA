from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict

import numpy as np

from .config import load_config
from .io import create_output_dir, save_json, save_yaml
from .metrics import compute_path_metrics
from .plots import plot_radio_map
from .scene import build_scene
from .utils.progress import progress_steps
from .utils.system import configure_tensorflow_memory_growth, select_mitsuba_variant, collect_environment_info

logger = logging.getLogger(__name__)


def _to_numpy(x):
    try:
        return x.numpy()
    except AttributeError:
        return np.asarray(x)


def run_simulation(config_path: str) -> Path:
    cfg = load_config(config_path)
    output_dir = create_output_dir(cfg.output.get("base_dir", "outputs"))
    save_yaml(output_dir / "config.yaml", cfg.data)

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
    tf_info = configure_tensorflow_memory_growth()

    timings: Dict[str, float] = {}

    steps = ["Build scene", "Render scene", "Ray trace paths", "Radio map", "Plots"]
    with progress_steps("Simulation", len(steps)) as (progress, task_id):
        t0 = time.time()
        progress.update(task_id, description=steps[0])
        scene = build_scene(cfg.data)
        timings["scene_build_s"] = time.time() - t0
        progress.advance(task_id)

        # Render a static scene view
        progress.update(task_id, description=steps[1])
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
                num_samples=64,
                resolution=(800, 600),
            )
        except Exception as exc:  # pragma: no cover - optional rendering path
            logger.warning("Scene render failed: %s", exc)
        progress.advance(task_id)

        from sionna.rt import PathSolver, RadioMapSolver

        sim_cfg = cfg.simulation
        t0 = time.time()
        progress.update(task_id, description=steps[2])
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

        tx_device = next(iter(scene.transmitters.values()))
        metrics = compute_path_metrics(paths, tx_power_dbm=tx_device.power_dbm)

        radio_map_cfg = cfg.radio_map
        radio_map = None
        if radio_map_cfg.get("enabled", False):
            t0 = time.time()
            progress.update(task_id, description=steps[3])
            rm_solver = RadioMapSolver()
            radio_map = rm_solver(
                scene,
                center=radio_map_cfg.get("center"),
                orientation=radio_map_cfg.get("orientation", [0.0, 0.0, 0.0]),
                size=radio_map_cfg.get("size"),
                cell_size=radio_map_cfg.get("cell_size", [2.0, 2.0]),
                samples_per_tx=int(radio_map_cfg.get("samples_per_tx", 200000)),
                max_depth=int(radio_map_cfg.get("max_depth", 3)),
                los=bool(radio_map_cfg.get("los", True)),
                specular_reflection=bool(radio_map_cfg.get("specular_reflection", True)),
                diffuse_reflection=bool(radio_map_cfg.get("diffuse_reflection", False)),
                refraction=bool(radio_map_cfg.get("refraction", True)),
                diffraction=bool(radio_map_cfg.get("diffraction", False)),
            )
            timings["radio_map_s"] = time.time() - t0
        else:
            progress.update(task_id, description=f"{steps[3]} (skipped)")
        progress.advance(task_id)

        plots_dir = output_dir / "plots"
        data_dir = output_dir / "data"
        if radio_map is not None:
            progress.update(task_id, description=steps[4])
            path_gain = _to_numpy(radio_map.path_gain)
            cell_centers = _to_numpy(radio_map.cell_centers)
            path_gain_db = 10.0 * np.log10(path_gain + 1e-12)
            tx_power_dbm = _to_numpy(tx_device.power_dbm).item()
            rx_power_dbm = tx_power_dbm + path_gain_db
            path_loss_db = -path_gain_db

            np.savez_compressed(
                data_dir / "radio_map.npz",
                path_gain_linear=path_gain,
                path_gain_db=path_gain_db,
                rx_power_dbm=rx_power_dbm,
                path_loss_db=path_loss_db,
                cell_centers=cell_centers,
            )

            # CSV export for external tools
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

            plot_radio_map(
                path_gain_db,
                cell_centers,
                plots_dir,
                metric_label="Path gain [dB]",
                filename_prefix="radio_map_path_gain_db",
            )
            plot_radio_map(
                rx_power_dbm,
                cell_centers,
                plots_dir,
                metric_label="Rx power [dBm]",
                filename_prefix="radio_map_rx_power_dbm",
            )
            plot_radio_map(
                path_loss_db,
                cell_centers,
                plots_dir,
                metric_label="Path loss [dB]",
                filename_prefix="radio_map_path_loss_db",
            )
        else:
            progress.update(task_id, description=f"{steps[4]} (skipped)")
        progress.advance(task_id)

    summary = {
        "metrics": metrics,
        "runtime": {
            "mitsuba_variant": variant,
            "tensorflow": tf_info,
            "timings_s": timings,
        },
        "environment": collect_environment_info(),
    }

    save_json(output_dir / "summary.json", summary)
    logger.info("Run complete: %s", output_dir)

    return output_dir
