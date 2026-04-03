from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np

from app.cc.cc_config import load_channel_charting_config, snapshot_channel_charting_config
from app.cc.csi import compute_csi
from app.cc.eval import evaluate_chart
from app.cc.features import extract_features
from app.cc.model import train_autoencoder
from app.cc.dissimilarity import dissimilarity_charting
from app.cc.plots import plot_chart, plot_feature_summary, plot_losses, plot_trajectory_compare
from app.cc.tracking import smooth_track
from app.cc.trajectory import generate_trajectory
from app.io import create_output_dir, save_json
from app.scene import build_scene
from app.utils.system import (
    configure_tensorflow_for_mitsuba_variant,
    configure_tensorflow_memory_growth,
    select_mitsuba_variant,
    assert_mitsuba_variant,
    collect_environment_info,
    disable_pythreejs_import,
)

logger = logging.getLogger(__name__)


def _write_progress(path: Path, step: int, total: int, status: str, label: str) -> None:
    payload = {
        "status": status,
        "step_index": step,
        "step_name": label,
        "total_steps": total,
        "progress": min(step / total, 1.0) if total else 1.0,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    save_json(path, payload)


def _save_csv(path: Path, data: np.ndarray, header: str) -> None:
    np.savetxt(path, data, delimiter=",", header=header, comments="")


def run_channel_charting(config_path: str) -> Path:
    cfg = load_channel_charting_config(config_path)
    output_dir = create_output_dir(
        cfg.get("output", {}).get("base_dir", "outputs"),
        run_id=cfg.get("output", {}).get("run_id"),
    )
    snapshot_channel_charting_config(output_dir, cfg)
    plots_dir = output_dir / "plots"
    data_dir = output_dir / "data"
    plots_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    progress_path = output_dir / "progress.json"
    steps = [
        "Build scene",
        "Generate trajectory",
        "Compute CSI",
        "Extract features",
        "Train charting model",
        "Track/smooth",
        "Evaluate",
        "Plots",
    ]

    runtime_cfg = cfg.get("runtime", {})
    if runtime_cfg.get("force_cpu"):
        import os
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

    prefer_gpu = bool(runtime_cfg.get("prefer_gpu", True)) and not runtime_cfg.get("force_cpu")
    variant = select_mitsuba_variant(
        prefer_gpu=prefer_gpu,
        forced_variant=str(runtime_cfg.get("mitsuba_variant", "auto")),
        require_cuda=bool(runtime_cfg.get("require_cuda", False)),
    )
    assert_mitsuba_variant(variant, context="channel_charting")
    disable_pythreejs_import("channel_charting")
    tf_device_info = configure_tensorflow_for_mitsuba_variant(variant)
    tf_info = configure_tensorflow_memory_growth(mode=str(runtime_cfg.get("tensorflow_import", "auto")))
    if tf_device_info:
        tf_info.setdefault("device_policy", tf_device_info)

    start_time = time.time()

    try:
        # Step 1: scene
        _write_progress(progress_path, 0, len(steps), "running", steps[0])
        scene = build_scene(cfg, mitsuba_variant=variant)

        # Step 2: trajectory
        _write_progress(progress_path, 1, len(steps), "running", steps[1])
        positions, times = generate_trajectory(cfg.get("channel_charting", {}))
        traj_data = np.column_stack([times, positions])
        _save_csv(data_dir / "trajectory.csv", traj_data, "t_s,x,y,z")

        # Step 3: CSI
        _write_progress(progress_path, 2, len(steps), "running", steps[2])
        csi, _ = compute_csi(scene, cfg, positions, times)
        np.savez_compressed(
            data_dir / "csi.npz",
            csi_type=csi.get("type"),
            frequencies_hz=csi.get("frequencies_hz"),
            center_frequency_hz=csi.get("center_frequency_hz"),
            times_s=csi.get("times_s"),
            data=csi.get("data"),
            tau_s=csi.get("tau_s"),
        )

        # Step 4: features
        _write_progress(progress_path, 3, len(steps), "running", steps[3])
        arrays_cfg = cfg.get("scene", {}).get("arrays", {})
        feat_out = extract_features(csi, cfg, arrays_cfg)
        features = feat_out["features"]
        if features.size == 0 or features.ndim < 2:
            raise ValueError("No features extracted; check CSI configuration and array sizes.")
        np.savez_compressed(
            data_dir / "features.npz",
            features=features,
            feature_type=feat_out.get("feature_type"),
            window=feat_out.get("window"),
        )

        # Step 5: model
        _write_progress(progress_path, 4, len(steps), "running", steps[4])
        model_cfg = cfg.get("channel_charting", {}).get("model", {})
        model_type = str(model_cfg.get("type", "autoencoder"))
        model_out = {}
        if model_type == "dissimilarity_mds":
            cc_cfg_for_dis = cfg.get("channel_charting", {})
            embeddings, dis_meta = dissimilarity_charting(csi, cc_cfg_for_dis)
            model_out["dissimilarity"] = dis_meta
        else:
            model_out = train_autoencoder(features, model_cfg)
            embeddings = model_out["embeddings"]
        np.savez_compressed(
            data_dir / "chart.npz",
            embeddings=embeddings,
            reconstruction=model_out.get("reconstruction"),
        )

        # Step 6: tracking
        _write_progress(progress_path, 5, len(steps), "running", steps[5])
        track_cfg = cfg.get("channel_charting", {}).get("tracking", {})
        track_out = smooth_track(embeddings, track_cfg)
        smoothed = track_out.get("smoothed", embeddings)

        # Step 7: evaluation
        _write_progress(progress_path, 6, len(steps), "running", steps[6])
        eval_cfg = cfg.get("channel_charting", {}).get("evaluation", {})
        eval_out = evaluate_chart(smoothed, positions, eval_cfg)
        aligned = eval_out.get("aligned", smoothed)
        metrics = eval_out.get("metrics", {})

        # Step 8: plots
        _write_progress(progress_path, 7, len(steps), "running", steps[7])
        plot_feature_summary(features, plots_dir, "features.png")
        plot_losses(model_out.get("history", {}), plots_dir, "training_losses.png")
        plot_chart(embeddings, plots_dir, "Chart (raw)", "chart_raw.png", color=times)
        plot_chart(smoothed, plots_dir, "Chart (smoothed)", "chart_smoothed.png", color=times)
        plot_chart(aligned, plots_dir, "Chart (aligned)", "chart_aligned.png", color=times, gt=positions)
        plot_trajectory_compare(positions, aligned, plots_dir, "trajectory_compare.png")
    except Exception as exc:
        payload = {
            "status": "failed",
            "step_name": "failed",
            "error": str(exc),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        save_json(progress_path, payload)
        raise

    runtime = {
        "mitsuba_variant": variant,
        "rt_backend": "cuda/optix" if "cuda" in (variant or "") else "cpu/llvm",
        "tensorflow": tf_info,
        "total_s": time.time() - start_time,
    }

    summary = {
        "metrics": metrics,
        "runtime": runtime,
        "environment": collect_environment_info(),
        "config": {
            "path": str(output_dir / "config.yaml"),
        },
    }
    if model_out.get("dissimilarity"):
        summary["metrics"]["dissimilarity"] = model_out["dissimilarity"]
    save_json(output_dir / "summary.json", summary)

    np.savez_compressed(
        data_dir / "chart_full.npz",
        embeddings=embeddings,
        smoothed=smoothed,
        aligned=aligned,
    )

    # Save trajectory data for 3D viewer overlay
    traj_json = {
        "ground_truth": positions.tolist(),
        "prediction": aligned.tolist(),
    }
    save_json(data_dir / "trajectories.json", traj_json)

    # Measurement antenna info for manifest
    cc_cfg = cfg.get("channel_charting", {})
    meas_antennas = cc_cfg.get("measurement_antennas", [])

    manifest = {
        "run_id": output_dir.name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config_path": "config.yaml",
        "chart_coords": embeddings.tolist(),
        "chart_coords_smoothed": smoothed.tolist(),
        "chart_coords_aligned": aligned.tolist(),
        "ground_truth_coords": positions.tolist(),
        "timestamps_s": times.tolist(),
        "measurement_antennas": meas_antennas,
        "files": {
            "csi": "data/csi.npz",
            "features": "data/features.npz",
            "chart": "data/chart_full.npz",
            "trajectory": "data/trajectory.csv",
            "trajectories_json": "data/trajectories.json",
        },
        "metrics": metrics,
        "plots": {
            "features": "plots/features.png",
            "chart_raw": "plots/chart_raw.png",
            "chart_smoothed": "plots/chart_smoothed.png",
            "chart_aligned": "plots/chart_aligned.png",
            "trajectory_compare": "plots/trajectory_compare.png",
            "training_losses": "plots/training_losses.png",
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    _write_progress(progress_path, len(steps), len(steps), "completed", "Complete")
    logger.info("Channel charting run complete: %s", output_dir)
    return output_dir
