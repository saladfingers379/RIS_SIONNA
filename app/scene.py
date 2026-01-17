from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SceneObjectSpec:
    """Placeholder for future scene objects (e.g., RIS panels)."""

    name: str
    kind: str
    position: List[float]
    orientation: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None


def build_scene(cfg: Dict[str, Any]):
    import numpy as np
    from .utils.system import disable_pythreejs_import

    disable_pythreejs_import("build_scene")
    import sionna.rt as rt

    scene_cfg = cfg.get("scene", {})
    scene_type = scene_cfg.get("type", "builtin")

    if scene_type == "builtin":
        builtin = scene_cfg.get("builtin", "etoile")
        try:
            scene_ref = getattr(rt.scene, builtin)
        except AttributeError as exc:
            raise ValueError(f"Unknown builtin scene '{builtin}'") from exc
        scene = rt.load_scene(scene_ref)
    elif scene_type == "file":
        filename = scene_cfg.get("file")
        if not filename:
            raise ValueError("scene.file must be set when scene.type is 'file'")
        scene = rt.load_scene(filename)
    else:
        raise ValueError(f"Unsupported scene.type '{scene_type}'")

    # Frequency setup
    sim_cfg = cfg.get("simulation", {})
    if "frequency_hz" in sim_cfg:
        scene.frequency = float(sim_cfg["frequency_hz"])

    # Antenna arrays
    arrays = scene_cfg.get("arrays", {})
    tx_arr = arrays.get("tx", {})
    rx_arr = arrays.get("rx", {})
    scene.tx_array = rt.PlanarArray(
        num_rows=int(tx_arr.get("num_rows", 1)),
        num_cols=int(tx_arr.get("num_cols", 1)),
        vertical_spacing=float(tx_arr.get("vertical_spacing", 0.5)),
        horizontal_spacing=float(tx_arr.get("horizontal_spacing", 0.5)),
        pattern=tx_arr.get("pattern", "iso"),
        polarization=tx_arr.get("polarization", "V"),
    )
    scene.rx_array = rt.PlanarArray(
        num_rows=int(rx_arr.get("num_rows", 1)),
        num_cols=int(rx_arr.get("num_cols", 1)),
        vertical_spacing=float(rx_arr.get("vertical_spacing", 0.5)),
        horizontal_spacing=float(rx_arr.get("horizontal_spacing", 0.5)),
        pattern=rx_arr.get("pattern", "iso"),
        polarization=rx_arr.get("polarization", "V"),
    )

    # Devices
    tx_cfg = scene_cfg.get("tx", {})
    rx_cfg = scene_cfg.get("rx", {})

    tx_look_at = tx_cfg.get("look_at")
    tx = rt.Transmitter(
        name=tx_cfg.get("name", "tx"),
        position=np.array(tx_cfg.get("position", [0.0, 0.0, 10.0])),
        look_at=np.array(tx_look_at) if tx_look_at is not None else None,
        power_dbm=float(tx_cfg.get("power_dbm", 30.0)),
    )
    rx = rt.Receiver(
        name=rx_cfg.get("name", "rx"),
        position=np.array(rx_cfg.get("position", [10.0, 0.0, 1.5])),
    )
    scene.add(tx)
    scene.add(rx)

    # Placeholder for future scene objects (including RIS)
    _objects = scene_cfg.get("objects", [])
    if _objects:
        # No-op placeholder: objects are defined for future extensions.
        pass

    return scene


def _safe_scene_id(scene_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", scene_id).strip("_") or "scene"


def export_scene_meshes(scene, output_dir: Path, scene_id: str, cache_root: Optional[Path] = None) -> None:
    """Export Mitsuba meshes to PLY files, with caching for faster re-runs."""
    mesh_dir = output_dir / "scene_mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    cache_root = cache_root or output_dir.parent / "_cache"
    cache_dir = cache_root / _safe_scene_id(scene_id)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cached_meshes = list(cache_dir.glob("*.ply"))
    if cached_meshes:
        for src in cached_meshes:
            dst = mesh_dir / src.name
            if src.resolve() != dst.resolve():
                shutil.copyfile(src, dst)
        return

    mi_scene = scene.mi_scene
    for idx, mesh in enumerate(mi_scene.shapes()):
        try:
            path = cache_dir / f"mesh_{idx:03d}.ply"
            mesh.write_ply(str(path))
        except Exception:
            continue

    for src in cache_dir.glob("*.ply"):
        dst = mesh_dir / src.name
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
