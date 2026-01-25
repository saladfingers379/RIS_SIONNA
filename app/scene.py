from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
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


MATERIAL_LIBRARY = {
    "concrete": {"itu_type": "concrete", "thickness": 0.2},
    "glass": {"itu_type": "glass", "thickness": 0.01},
    "metal": {"itu_type": "metal", "thickness": 0.005},
    "wood": {"itu_type": "wood", "thickness": 0.05},
}


def _hash_scene_config(cfg: Dict[str, Any]) -> str:
    payload = json.dumps(cfg, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _procedural_defaults() -> Dict[str, Any]:
    return {
        "ground": {"size": [160.0, 160.0], "elevation": 0.0, "material": "concrete"},
        "boxes": [
            {"center": [25.0, 40.0, 6.0], "size": [18.0, 18.0, 12.0], "material": "concrete"},
            {"center": [-20.0, 15.0, 4.5], "size": [10.0, 14.0, 9.0], "material": "glass"},
        ],
    }


def _street_canyon_spec(cfg: Dict[str, Any]) -> Dict[str, Any]:
    width = float(cfg.get("width", 20.0))
    length = float(cfg.get("length", 120.0))
    height = float(cfg.get("height", 20.0))
    step = float(cfg.get("step", 20.0))
    material = cfg.get("material", "concrete")

    boxes = []
    offset = width / 2.0 + 5.0
    z = height / 2.0
    x_positions = list(range(int(-length / 2), int(length / 2 + 1), int(step)))
    for x in x_positions:
        boxes.append({"center": [x, offset, z], "size": [step * 0.8, 12.0, height], "material": material})
        boxes.append({"center": [x, -offset, z], "size": [step * 0.8, 12.0, height], "material": material})
    return {
        "ground": {"size": [length + 40.0, width + 40.0], "elevation": 0.0, "material": "concrete"},
        "boxes": boxes,
    }


def _build_procedural_spec(scene_cfg: Dict[str, Any]) -> Dict[str, Any]:
    proc_cfg = scene_cfg.get("procedural", {}) if isinstance(scene_cfg, dict) else {}
    preset = proc_cfg.get("preset")
    if preset == "street_canyon":
        spec = _street_canyon_spec(proc_cfg.get("street_canyon", {}))
    else:
        spec = _procedural_defaults()
    if "ground" in proc_cfg:
        spec["ground"].update(proc_cfg.get("ground", {}))
    if "boxes" in proc_cfg:
        spec["boxes"] = proc_cfg.get("boxes", [])
    return spec


def _material_props(name: str) -> Dict[str, Any]:
    props = MATERIAL_LIBRARY.get(name, MATERIAL_LIBRARY["concrete"])
    return {"itu_type": props["itu_type"], "thickness": props["thickness"]}


def _itu_bsdf_xml(mat_name: str, bsdf_id: str) -> str:
    props = _material_props(mat_name)
    return (
        f"  <bsdf type=\"itu-radio-material\" id=\"{bsdf_id}\">\n"
        f"    <string name=\"type\" value=\"{props['itu_type']}\"/>\n"
        f"    <float name=\"thickness\" value=\"{props['thickness']}\"/>\n"
        "  </bsdf>\n"
    )


def _write_procedural_scene_xml(path: Path, spec: Dict[str, Any]) -> None:
    ground = spec.get("ground", {})
    ground_size = ground.get("size", [160.0, 160.0])
    ground_elev = ground.get("elevation", 0.0)
    ground_mat = ground.get("material", "concrete")
    shapes = []
    shapes.append(
        f"""
  <shape type=\"rectangle\" id=\"ground\">
    <transform name=\"to_world\">
      <scale x=\"{ground_size[0]}\" y=\"{ground_size[1]}\" z=\"1\"/>
      <translate x=\"0\" y=\"0\" z=\"{ground_elev}\"/>
    </transform>
{_itu_bsdf_xml(ground_mat, "rm-ground")}
  </shape>
"""
    )
    for idx, box in enumerate(spec.get("boxes", [])):
        size = box.get("size", [10.0, 10.0, 10.0])
        center = box.get("center", [0.0, 0.0, size[2] / 2.0])
        mat_name = box.get("material", "concrete")
        shapes.append(
            f"""
  <shape type=\"cube\" id=\"box-{idx}\">
    <transform name=\"to_world\">
      <scale x=\"{size[0]}\" y=\"{size[1]}\" z=\"{size[2]}\"/>
      <translate x=\"{center[0]}\" y=\"{center[1]}\" z=\"{center[2]}\"/>
    </transform>
{_itu_bsdf_xml(mat_name, f"rm-box-{idx}")}
  </shape>
"""
        )
    xml = (
        "<scene version=\"3.0.0\">\n"
        "  <integrator type=\"path\"/>\n"
        + "".join(shapes)
        + "\n</scene>\n"
    )
    path.write_text(xml, encoding="utf-8")


def _apply_materials(scene, spec: Dict[str, Any]) -> None:
    try:
        from sionna.rt.radio_materials import ITURadioMaterial  # pylint: disable=import-error
    except Exception:
        return

    material_cache = {}

    def _get_material(name: str):
        if name in material_cache:
            return material_cache[name]
        props = MATERIAL_LIBRARY.get(name, MATERIAL_LIBRARY["concrete"])
        mat = ITURadioMaterial(name=f"itu-{name}", itu_type=props["itu_type"], thickness=props["thickness"])
        material_cache[name] = mat
        return mat

    ground = spec.get("ground", {})
    ground_mat = ground.get("material", "concrete")
    try:
        obj = scene.get("ground")
        obj.radio_material = _get_material(ground_mat)
    except Exception:
        pass

    for idx, box in enumerate(spec.get("boxes", [])):
        mat_name = box.get("material", "concrete")
        try:
            obj = scene.get(f"box-{idx}")
            obj.radio_material = _get_material(mat_name)
        except Exception:
            continue


def _build_builtin_scene(rt, scene_cfg: Dict[str, Any]):
    builtin = scene_cfg.get("builtin", "etoile")
    try:
        scene_ref = getattr(rt.scene, builtin)
    except AttributeError as exc:
        raise ValueError(f"Unknown builtin scene '{builtin}'") from exc
    return rt.load_scene(scene_ref)


def _build_file_scene(rt, scene_cfg: Dict[str, Any]):
    filename = scene_cfg.get("file")
    if not filename:
        raise ValueError("scene.file must be set when scene.type is 'file'")
    return rt.load_scene(filename)


def _build_procedural_scene(rt, scene_cfg: Dict[str, Any], cfg: Dict[str, Any]):
    spec = _build_procedural_spec(scene_cfg)
    cache_root = Path(cfg.get("output", {}).get("base_dir", "outputs")) / "_cache" / "procedural"
    cache_root.mkdir(parents=True, exist_ok=True)
    scene_id = _hash_scene_config(spec)
    xml_path = cache_root / f"scene_{scene_id}.xml"
    rewrite = not xml_path.exists()
    if not rewrite:
        try:
            xml_text = xml_path.read_text(encoding="utf-8")
            if (
                "itu-radio-material" not in xml_text
                or "rm-" not in xml_text
                or "rotate x=\"1\" angle=\"-90\"" in xml_text
            ):
                rewrite = True
        except Exception:
            rewrite = True
    if rewrite:
        _write_procedural_scene_xml(xml_path, spec)
    scene = rt.load_scene(str(xml_path))
    _apply_materials(scene, spec)
    return scene


SCENE_BUILDERS = {
    "builtin": _build_builtin_scene,
    "file": _build_file_scene,
    "procedural": _build_procedural_scene,
}


def build_scene(cfg: Dict[str, Any], mitsuba_variant: Optional[str] = None):
    import numpy as np
    from .utils.system import disable_pythreejs_import

    disable_pythreejs_import("build_scene")
    import sionna.rt as rt
    from .utils.system import apply_mitsuba_variant

    apply_mitsuba_variant(mitsuba_variant)

    scene_cfg = cfg.get("scene", {})
    scene_type = scene_cfg.get("type", "builtin")
    builder = SCENE_BUILDERS.get(scene_type)
    if not builder:
        raise ValueError(f"Unsupported scene.type '{scene_type}'")
    if scene_type == "procedural":
        scene = builder(rt, scene_cfg, cfg)
    else:
        scene = builder(rt, scene_cfg)

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

    # RIS integration (optional)
    try:
        from .ris.ris_sionna import add_ris_from_config

        add_ris_from_config(scene, cfg)
    except Exception:
        # RIS is optional; ignore failures unless explicitly enabled elsewhere.
        if cfg.get("ris", {}).get("enabled"):
            raise

    # Placeholder for future scene objects (including custom objects)
    _objects = scene_cfg.get("objects", [])
    if _objects:
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


def scene_sanity_report(scene, cfg: Dict[str, Any]) -> Dict[str, Any]:
    report: Dict[str, Any] = {"units": "meters", "axis": "x,y horizontal; z up"}
    scene_cfg = cfg.get("scene", {})
    report["tx_height_m"] = float(scene_cfg.get("tx", {}).get("position", [0, 0, 0])[2])
    report["rx_height_m"] = float(scene_cfg.get("rx", {}).get("position", [0, 0, 0])[2])
    try:
        bbox = scene.mi_scene.bbox()
        report["bbox_min"] = [float(bbox.min.x), float(bbox.min.y), float(bbox.min.z)]
        report["bbox_max"] = [float(bbox.max.x), float(bbox.max.y), float(bbox.max.z)]
    except Exception:
        report["bbox_error"] = "bbox unavailable"
    return report
