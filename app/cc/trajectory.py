from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np


def _linspace_points(start: np.ndarray, end: np.ndarray, num: int) -> np.ndarray:
    if num <= 1:
        return start.reshape(1, 3)
    t = np.linspace(0.0, 1.0, num)
    return start[None, :] * (1.0 - t[:, None]) + end[None, :] * t[:, None]


def _waypoints_points(waypoints: np.ndarray, num: int) -> np.ndarray:
    if waypoints.shape[0] == 1:
        return waypoints
    # Distribute samples proportional to segment length.
    segs = waypoints[1:] - waypoints[:-1]
    seg_lengths = np.linalg.norm(segs, axis=1)
    total = float(np.sum(seg_lengths))
    if total <= 0.0:
        return np.repeat(waypoints[:1], num, axis=0)
    alloc = np.maximum(1, np.round((seg_lengths / total) * (num - 1)).astype(int))
    # Adjust allocations to match num-1 exactly.
    diff = (num - 1) - int(np.sum(alloc))
    if diff != 0:
        alloc[-1] = max(1, alloc[-1] + diff)
    points = [waypoints[0]]
    for i, n in enumerate(alloc):
        seg = _linspace_points(waypoints[i], waypoints[i + 1], n + 1)
        points.extend(seg[1:])
    return np.vstack(points)[:num]


def generate_trajectory(cfg: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    traj_cfg = cfg.get("trajectory", {}) if isinstance(cfg, dict) else {}
    traj_type = str(traj_cfg.get("type", "straight"))
    num_steps = int(traj_cfg.get("num_steps", 100))
    dt_s = float(traj_cfg.get("dt_s", 0.1))
    if num_steps < 1:
        num_steps = 1

    if traj_type == "waypoints":
        waypoints = np.array(traj_cfg.get("waypoints", []), dtype=float)
        if waypoints.size == 0:
            waypoints = np.array([[0.0, 0.0, 1.5]], dtype=float)
        if waypoints.ndim == 1:
            waypoints = waypoints.reshape(1, 3)
        points = _waypoints_points(waypoints, num_steps)
    elif traj_type == "random_walk":
        start = np.array(traj_cfg.get("start", [0.0, 0.0, 1.5]), dtype=float)
        rw_cfg = traj_cfg.get("random_walk", {}) if isinstance(traj_cfg, dict) else {}
        step_std = float(rw_cfg.get("step_std", traj_cfg.get("step_std", 0.6)))
        smooth_alpha = float(rw_cfg.get("smooth_alpha", traj_cfg.get("smooth_alpha", 0.2)))
        drift = np.array(rw_cfg.get("drift", traj_cfg.get("drift", [0.0, 0.0, 0.0])), dtype=float)
        positions = [start]
        velocity = np.zeros(3, dtype=float)
        for _ in range(1, num_steps):
            noise = np.random.normal(scale=step_std, size=3)
            velocity = smooth_alpha * noise + (1.0 - smooth_alpha) * velocity + drift
            positions.append(positions[-1] + velocity)
        points = np.vstack(positions)
    elif traj_type == "spiral":
        sp_cfg = traj_cfg.get("spiral", {}) if isinstance(traj_cfg, dict) else {}
        center = np.array(sp_cfg.get("center", traj_cfg.get("center", [0.0, 0.0, 1.5])), dtype=float)
        radius_start = float(sp_cfg.get("radius_start", traj_cfg.get("radius_start", 1.0)))
        radius_end = float(sp_cfg.get("radius_end", traj_cfg.get("radius_end", 10.0)))
        turns = float(sp_cfg.get("turns", traj_cfg.get("turns", 2.0)))
        theta = np.linspace(0.0, 2.0 * np.pi * turns, num_steps)
        radius = np.linspace(radius_start, radius_end, num_steps)
        x = center[0] + radius * np.cos(theta)
        y = center[1] + radius * np.sin(theta)
        z = np.full_like(x, center[2])
        points = np.column_stack([x, y, z])
    else:
        start = np.array(traj_cfg.get("start", [0.0, 0.0, 1.5]), dtype=float)
        end = np.array(traj_cfg.get("end", [20.0, 10.0, 1.5]), dtype=float)
        points = _linspace_points(start, end, num_steps)

    times = np.arange(points.shape[0], dtype=float) * dt_s
    return points, times
