from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
import logging
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


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

ITU_NAME_MAP = {
    "concrete": "itu_concrete",
    "glass": "itu_glass",
    "metal": "itu_metal",
    "wood": "itu_wood",
    "brick": "itu_brick",
    "marble": "itu_marble",
    "dry_earth": "itu_concrete",
    "very_dry_ground": "itu_concrete",
    "medium_dry_ground": "itu_concrete",
    "wet_ground": "itu_concrete",
}

# Placeholder chamber absorber proxy. For the chamber test scene we model the
# absorber as an ideal matched boundary in Sionna's material parameters.
CUSTOM_RADIO_MATERIAL_LIBRARY = {
    "itu_absorber": {
        "relative_permittivity": 1.0,
        "conductivity": 0.0,
        "scattering_coefficient": 0.0,
        "xpd_coefficient": 0.0,
    },
}

_HORN_PATTERN_LIBRARY = {
    # Approximate standard-gain horn patterns. The 3 dB widths are inferred
    # from the nominal gain using the usual beamwidth/directivity relation and
    # treated as symmetric in azimuth/elevation.
    "horn_15dbi": {
        "gain_dbi": 15.0,
        "theta_3db_deg": 36.0,
        "phi_3db_deg": 36.0,
        "sidelobe_attenuation_db": 30.0,
        "front_only": False,
    },
    "horn_22dbi": {
        "gain_dbi": 22.0,
        "theta_3db_deg": 16.0,
        "phi_3db_deg": 16.0,
        "sidelobe_attenuation_db": 30.0,
        "front_only": False,
    },
    "horn_15dbi_front": {
        "gain_dbi": 15.0,
        "theta_3db_deg": 36.0,
        "phi_3db_deg": 36.0,
        "sidelobe_attenuation_db": 30.0,
        "front_only": True,
    },
    "horn_22dbi_front": {
        "gain_dbi": 22.0,
        "theta_3db_deg": 16.0,
        "phi_3db_deg": 16.0,
        "sidelobe_attenuation_db": 30.0,
        "front_only": True,
    },
}


def _resolve_custom_radio_material_library(cfg: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    library = copy.deepcopy(CUSTOM_RADIO_MATERIAL_LIBRARY)

    scene_cfg = cfg.get("scene", {}) if isinstance(cfg, dict) else {}
    overrides = scene_cfg.get("custom_radio_materials", {}) if isinstance(scene_cfg, dict) else {}
    if not isinstance(overrides, dict):
        return library

    for name, params in overrides.items():
        if not isinstance(name, str) or not isinstance(params, dict):
            continue
        merged = dict(library.get(name, {}))
        for key, value in params.items():
            try:
                merged[key] = float(value)
            except Exception:
                continue
        library[name] = merged
    return library


def _make_horn_pattern(
    *,
    gain_dbi: float,
    theta_3db_deg: float,
    phi_3db_deg: float,
    sidelobe_attenuation_db: float,
    front_only: bool = False,
):
    import tensorflow as tf
    from sionna.rt.antenna import PI, polarization_model_1, polarization_model_2

    def pattern(
        theta,
        phi,
        slant_angle=0.0,
        polarization_model=2,
        dtype=tf.complex64,
    ):
        rdtype = dtype.real_dtype
        theta = tf.cast(theta, rdtype)
        phi = tf.cast(phi, rdtype)
        slant_angle = tf.cast(slant_angle, rdtype)
        if theta.shape != phi.shape:
            raise ValueError("theta and phi must have the same shape.")
        if polarization_model not in [1, 2]:
            raise ValueError("polarization_model must be 1 or 2")

        phi_wrapped = tf.math.floormod(phi + PI, 2 * PI) - PI
        theta_3db = tf.cast(np.deg2rad(theta_3db_deg), rdtype)
        phi_3db = tf.cast(np.deg2rad(phi_3db_deg), rdtype)
        a_max = tf.cast(float(sidelobe_attenuation_db), rdtype)
        g_max = tf.cast(float(gain_dbi), rdtype)

        a_v = -tf.minimum(12.0 * ((theta - PI / 2.0) / theta_3db) ** 2, a_max)
        a_h = -tf.minimum(12.0 * (phi_wrapped / phi_3db) ** 2, a_max)
        a_db = -tf.minimum(-(a_v + a_h), a_max) + g_max
        linear_gain = tf.pow(tf.cast(10.0, rdtype), a_db / 10.0)
        if front_only:
            linear_gain = tf.where(
                tf.abs(phi_wrapped) <= (PI / 2.0),
                linear_gain,
                tf.zeros_like(linear_gain),
            )
        c = tf.complex(tf.sqrt(linear_gain), tf.zeros_like(linear_gain))

        if polarization_model == 1:
            return polarization_model_1(c, theta, phi_wrapped, slant_angle)
        return polarization_model_2(c, slant_angle)

    return pattern


def _resolve_horn_pattern(pattern: Any) -> Optional[Dict[str, Any]]:
    pattern_name = str(pattern or "iso").strip().lower()
    horn_spec = _HORN_PATTERN_LIBRARY.get(pattern_name)
    return dict(horn_spec) if horn_spec is not None else None


def _resolve_array_pattern(pattern: Any, polarization: Any) -> tuple[Any, Any]:
    pattern_name = str(pattern or "iso").strip().lower()
    horn_spec = _resolve_horn_pattern(pattern_name)
    if horn_spec is None:
        return pattern, polarization

    from sionna.rt.antenna import PI

    base_pattern = _make_horn_pattern(**horn_spec)
    polarization_name = str(polarization or "V").strip()
    slant_angles = {
        "V": [0.0],
        "H": [float(PI / 2.0)],
        "VH": [0.0, float(PI / 2.0)],
        "cross": [float(-PI / 4.0), float(PI / 4.0)],
    }.get(polarization_name)
    if slant_angles is None:
        raise ValueError(f"Unknown polarization '{polarization_name}' for horn pattern '{pattern_name}'")

    if len(slant_angles) == 1:
        slant_angle = slant_angles[0]
        return (
            lambda theta, phi, sa=slant_angle: base_pattern(theta, phi, sa, 2),
            None,
        )

    patterns = [
        (lambda theta, phi, sa=slant_angle: base_pattern(theta, phi, sa, 2))
        for slant_angle in slant_angles
    ]
    return patterns, None


def _hash_scene_config(cfg: Dict[str, Any]) -> str:
    payload = json.dumps(cfg, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


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


def _itu_material_name(mat_name: str) -> str:
    itu_name = ITU_NAME_MAP.get(mat_name, None)
    if itu_name is None and mat_name.startswith("itu_"):
        itu_name = mat_name
    return itu_name or "itu_concrete"


def _itu_bsdf_def_xml(itu_name: str) -> str:
    return (
        f"  <bsdf type=\"twosided\" id=\"mat-{itu_name}\">\n"
        "    <bsdf type=\"diffuse\">\n"
        "      <rgb name=\"reflectance\" value=\"0.5\"/>\n"
        "    </bsdf>\n"
        "  </bsdf>\n"
    )


def _itu_bsdf_ref_xml(itu_name: str) -> str:
    return f'    <ref id="mat-{itu_name}" name="bsdf"/>\n'


def _write_procedural_scene_xml(path: Path, spec: Dict[str, Any]) -> None:
    ground = spec.get("ground", {})
    ground_size = ground.get("size", [160.0, 160.0])
    ground_elev = ground.get("elevation", 0.0)
    ground_mat = ground.get("material", "concrete")
    itu_names = {_itu_material_name(ground_mat)}
    for box in spec.get("boxes", []):
        itu_names.add(_itu_material_name(box.get("material", "concrete")))
    bsdf_defs = "".join(_itu_bsdf_def_xml(name) for name in sorted(itu_names))
    shapes = []
    shapes.append(
        f"""
  <shape type=\"rectangle\" id=\"ground\">
    <transform name=\"to_world\">
      <scale x=\"{ground_size[0]}\" y=\"{ground_size[1]}\" z=\"1\"/>
      <translate x=\"0\" y=\"0\" z=\"{ground_elev}\"/>
    </transform>
{_itu_bsdf_ref_xml(_itu_material_name(ground_mat))}
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
{_itu_bsdf_ref_xml(_itu_material_name(mat_name))}
  </shape>
"""
        )
    xml = (
        "<scene version=\"3.0.0\">\n"
        "  <integrator type=\"path\"/>\n"
        + bsdf_defs
        + "".join(shapes)
        + "\n</scene>\n"
    )
    path.write_text(xml, encoding="utf-8")

def _apply_floor_elevation_xml(xml_text: str, floor_z: float, target_ids: Optional[List[str]] = None) -> str:
    if floor_z == 0:
        return xml_text
    target_ids = target_ids or ["ground", "ground_mesh", "floor", "floor_mesh", "ground_plane"]
    # Map of id -> updated
    updated = {tid: False for tid in target_ids}

    def _update_shape(match: re.Match) -> str:
        shape = match.group(0)
        shape_id = match.group("id")
        if shape_id not in updated or updated[shape_id]:
            return shape
        updated[shape_id] = True
        # If a translate exists, adjust z.
        def _bump_translate(m: re.Match) -> str:
            attrs = m.group("attrs") or ""
            z_match = re.search(r'\bz\s*=\s*"([^"]+)"', attrs)
            if z_match:
                try:
                    z_val = float(z_match.group(1))
                except ValueError:
                    z_val = 0.0
                new_z = z_val + floor_z
                return re.sub(r'\bz\s*=\s*"[^"]+"', f'z="{new_z}"', m.group(0))
            return m.group(0).replace("/>", f' z="{floor_z}"/>')

        if re.search(r"<translate\b", shape):
            shape = re.sub(r"<translate\b(?P<attrs>[^>]*)/>", _bump_translate, shape, count=1)
            return shape
        # If there's a transform, insert translate as first child.
        if re.search(r"<transform\b", shape):
            return re.sub(
                r"(<transform\b[^>]*>)",
                r"\1\n      <translate x=\"0\" y=\"0\" z=\"{:.6f}\"/>".format(floor_z),
                shape,
                count=1,
            )
        # Otherwise add a new transform block.
        insert = (
            "\n    <transform name=\"to_world\">\n"
            f"      <translate x=\"0\" y=\"0\" z=\"{floor_z:.6f}\"/>\n"
            "    </transform>\n"
        )
        return shape.replace(">", ">" + insert, 1)

    pattern = r"<shape\b[^>]*\bid=\"(?P<id>[^\"]+)\"[^>]*>[\s\S]*?</shape>"
    return re.sub(pattern, _update_shape, xml_text, flags=re.IGNORECASE)


def _apply_materials(scene, spec: Dict[str, Any]) -> None:
    def _get_material_name(name: str) -> str:
        itu_name = ITU_NAME_MAP.get(name, None)
        if itu_name is None and name.startswith("itu_"):
            itu_name = name
        return itu_name or "itu_concrete"

    ground = spec.get("ground", {})
    ground_mat = ground.get("material", "concrete")
    try:
        obj = scene.get("ground")
        obj.radio_material = _get_material_name(ground_mat)
    except Exception:
        pass

    for idx, box in enumerate(spec.get("boxes", [])):
        mat_name = box.get("material", "concrete")
        try:
            obj = scene.get(f"box-{idx}")
            obj.radio_material = _get_material_name(mat_name)
        except Exception:
            continue


def _build_builtin_scene(rt, scene_cfg: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None):
    builtin = scene_cfg.get("builtin", "etoile")
    try:
        scene_ref = getattr(rt.scene, builtin)
    except AttributeError as exc:
        raise ValueError(f"Unknown builtin scene '{builtin}'") from exc
    return rt.load_scene(scene_ref)


def _build_file_scene(rt, scene_cfg: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None):
    filename = scene_cfg.get("file")
    if not filename:
        raise ValueError("scene.file must be set when scene.type is 'file'")
    floor_z = float(scene_cfg.get("floor_elevation", 0.0) or 0.0)
    floor_targets = scene_cfg.get("floor_targets")

    xml_path = Path(filename)
    if not xml_path.exists():
        raise FileNotFoundError(f"Scene file not found: {filename}")

    def _write_cached_scene(xml_text: str):
        cache_root = Path((cfg or {}).get("output", {}).get("base_dir", "outputs")) / "_cache" / "file_scenes"
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_path = cache_root / f"scene_{_hash_text(xml_text)}.xml"
        cache_path.write_text(xml_text, encoding="utf-8")
        return cache_path

    def _normalize_itu_materials(xml_text: str) -> str:
        logger.warning(
            "itu-radio-material plugin not found; normalizing name or falling back to diffuse for '%s'. "
            "Results will not match radio-material propagation.",
            filename,
        )
        # Normalize legacy plugin name if present.
        xml_text = re.sub(r"itu[_-]radio_material", "itu-radio-material", xml_text, flags=re.IGNORECASE)
        # Replace any ITU radio material blocks with a diffuse placeholder.
        def _diffuse_block(match: re.Match) -> str:
            attrs = match.group("attrs") or ""
            id_match = re.search(r'\bid\s*=\s*"([^"]+)"', attrs)
            id_attr = f' id="{id_match.group(1)}"' if id_match else ""
            return f'<bsdf type="diffuse"{id_attr}><rgb name="reflectance" value="0.5"/></bsdf>'

        pattern = r"<bsdf\s+type=\"itu-radio-material\"(?P<attrs>[^>]*)>[\s\S]*?</bsdf>"
        replaced = re.sub(pattern, _diffuse_block, xml_text, flags=re.IGNORECASE)
        if replaced == xml_text:
            # Fallback: handle variants with extra attributes/whitespace.
            alt_pattern = r"<bsdf\s+type=\"itu-radio-material\"(?P<attrs>[^>]*)>[\s\S]*?</bsdf>"
            replaced = re.sub(alt_pattern, _diffuse_block, xml_text, flags=re.IGNORECASE)
        return replaced

    def _absolutize_assets(xml_text: str) -> str:
        base_dir = xml_path.parent
        def _abspath(match: re.Match) -> str:
            path = match.group("path")
            if path.startswith("/") or path.startswith("${"):
                return match.group(0)
            abs_path = (base_dir / path).resolve()
            return f'<string name="filename" value="{abs_path}"/>'
        return re.sub(
            r'<string\s+name=\"filename\"\s+value=\"(?P<path>[^\"]+)\"\s*/?>',
            _abspath,
            xml_text,
            flags=re.IGNORECASE,
        )

    if floor_z == 0.0:
        try:
            return rt.load_scene(filename)
        except RuntimeError as exc:
            msg = str(exc)
            if "itu_radio_material" not in msg and "itu-radio-material" not in msg:
                raise
            xml_text = xml_path.read_text(encoding="utf-8")
            if "itu_radio_material" not in xml_text and "itu-radio-material" not in xml_text:
                raise
            xml_text = _normalize_itu_materials(xml_text)
            xml_text = _absolutize_assets(xml_text)
            cache_path = _write_cached_scene(xml_text)
            scene = rt.load_scene(str(cache_path))
            _apply_default_radio_materials(scene)
            return scene

    # Floor elevation requested: load via cached XML.
    xml_text = xml_path.read_text(encoding="utf-8")
    xml_text = _apply_floor_elevation_xml(xml_text, floor_z, floor_targets)
    xml_text = _absolutize_assets(xml_text)
    cache_path = _write_cached_scene(xml_text)
    try:
        return rt.load_scene(str(cache_path))
    except RuntimeError as exc:
        msg = str(exc)
        if "itu_radio_material" not in msg and "itu-radio-material" not in msg:
            raise
        xml_text = _normalize_itu_materials(xml_text)
        cache_path = _write_cached_scene(xml_text)
        scene = rt.load_scene(str(cache_path))
        _apply_default_radio_materials(scene)
        return scene


def _apply_default_radio_materials(scene, default_name: str = "concrete") -> None:
    """Ensure all objects have a radio material when ITU plugin is missing."""
    try:
        # Ensure every object has a concrete (non-placeholder) material.
        fallback_name = ITU_NAME_MAP.get(default_name, "itu_concrete")
        fallback = scene.get(fallback_name)
        if fallback is None:
            logger.warning("Default ITU material '%s' not found in scene.", fallback_name)
            return
        failed = []
        for obj in scene.objects.values():
            try:
                mat = obj.radio_material
                if mat is None or getattr(mat, "is_placeholder", False):
                    obj.radio_material = fallback.name
            except Exception:
                failed.append(obj.name)
        if failed:
            logger.warning("Failed to assign default radio material to objects: %s", failed)
    except Exception:
        return


def _register_custom_radio_materials(scene, cfg: Optional[Dict[str, Any]] = None) -> None:
    """Replace known placeholder materials with concrete custom RadioMaterial definitions."""
    try:
        import sionna.rt as rt
    except Exception:
        return

    try:
        scene_materials = getattr(scene, "radio_materials", {}) or {}
    except Exception:
        scene_materials = {}

    material_library = _resolve_custom_radio_material_library(cfg or {})

    for name, params in material_library.items():
        existing = scene_materials.get(name)
        if existing is None or not bool(getattr(existing, "is_placeholder", False)):
            continue
        try:
            scene.add(
                rt.RadioMaterial(
                    name,
                    relative_permittivity=float(params.get("relative_permittivity", 1.0)),
                    conductivity=float(params.get("conductivity", 0.0)),
                    scattering_coefficient=float(params.get("scattering_coefficient", 0.0)),
                    xpd_coefficient=float(params.get("xpd_coefficient", 0.0)),
                )
            )
            logger.info(
                "Registered custom radio material '%s' (eps_r=%s, sigma=%s S/m)",
                name,
                params.get("relative_permittivity", 1.0),
                params.get("conductivity", 0.0),
            )
        except Exception as exc:
            logger.warning("Failed to register custom radio material '%s': %s", name, exc)


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
                "mat-itu_" not in xml_text
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
    from .utils.system import apply_mitsuba_variant, assert_mitsuba_variant

    apply_mitsuba_variant(mitsuba_variant)
    assert_mitsuba_variant(mitsuba_variant, context="build_scene")
    import sionna.rt as rt
    from .utils.sionna_patches import apply_sionna_multi_ris_patch

    apply_sionna_multi_ris_patch()

    scene_cfg = cfg.get("scene", {})
    scene_type = scene_cfg.get("type", "builtin")
    builder = SCENE_BUILDERS.get(scene_type)
    if not builder:
        raise ValueError(f"Unsupported scene.type '{scene_type}'")
    if scene_type == "procedural":
        scene = builder(rt, scene_cfg, cfg)
    else:
        scene = builder(rt, scene_cfg, cfg)
    # Ensure file scenes always have radio materials to satisfy Sionna RT checks.
    if scene_type == "file":
        _register_custom_radio_materials(scene, cfg)
        _apply_default_radio_materials(scene)

    # Frequency setup
    sim_cfg = cfg.get("simulation", {})
    if "frequency_hz" in sim_cfg:
        scene.frequency = float(sim_cfg["frequency_hz"])

    # Antenna arrays
    arrays = scene_cfg.get("arrays", {})
    tx_arr = arrays.get("tx", {})
    rx_arr = arrays.get("rx", {})
    tx_pattern, tx_polarization = _resolve_array_pattern(
        tx_arr.get("pattern", "iso"),
        tx_arr.get("polarization", "V"),
    )
    rx_pattern, rx_polarization = _resolve_array_pattern(
        rx_arr.get("pattern", "iso"),
        rx_arr.get("polarization", "V"),
    )
    scene.tx_array = rt.PlanarArray(
        num_rows=int(tx_arr.get("num_rows", 1)),
        num_cols=int(tx_arr.get("num_cols", 1)),
        vertical_spacing=float(tx_arr.get("vertical_spacing", 0.5)),
        horizontal_spacing=float(tx_arr.get("horizontal_spacing", 0.5)),
        pattern=tx_pattern,
        polarization=tx_polarization,
    )
    scene.rx_array = rt.PlanarArray(
        num_rows=int(rx_arr.get("num_rows", 1)),
        num_cols=int(rx_arr.get("num_cols", 1)),
        vertical_spacing=float(rx_arr.get("vertical_spacing", 0.5)),
        horizontal_spacing=float(rx_arr.get("horizontal_spacing", 0.5)),
        pattern=rx_pattern,
        polarization=rx_polarization,
    )

    # Devices
    tx_cfg = scene_cfg.get("tx", {})
    rx_cfg = scene_cfg.get("rx", {})

    tx_look_at = tx_cfg.get("look_at")
    tx_orientation = tx_cfg.get("orientation")
    rx_look_at = rx_cfg.get("look_at")
    rx_orientation = rx_cfg.get("orientation")
    tx = rt.Transmitter(
        name=tx_cfg.get("name", "tx"),
        position=np.array(tx_cfg.get("position", [0.0, 0.0, 10.0])),
        orientation=np.array(tx_orientation) if tx_orientation is not None else (0.0, 0.0, 0.0),
        look_at=np.array(tx_look_at) if tx_look_at is not None else None,
        power_dbm=float(tx_cfg.get("power_dbm", 30.0)),
    )
    rx = rt.Receiver(
        name=rx_cfg.get("name", "rx"),
        position=np.array(rx_cfg.get("position", [10.0, 0.0, 1.5])),
        orientation=np.array(rx_orientation) if rx_orientation is not None else (0.0, 0.0, 0.0),
        look_at=np.array(rx_look_at) if rx_look_at is not None else None,
    )
    scene.add(tx)
    scene.add(rx)

    # RIS integration (optional)
    try:
        from .ris.ris_sionna import add_ris_from_config

        ris_summary = add_ris_from_config(scene, cfg)
        if ris_summary is not None:
            setattr(scene, "_ris_runtime", ris_summary)
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


def _shape_has_nontrivial_transform(shape: ET.Element) -> bool:
    transform = shape.find("transform[@name='to_world']")
    if transform is None:
        return False
    for child in list(transform):
        tag = (child.tag or "").lower()
        if tag in {"translate", "rotate", "scale", "matrix", "lookat"}:
            return True
    return False


def _scene_file_has_nontrivial_mesh_transforms(scene_file: Path) -> bool:
    try:
        root = ET.parse(scene_file).getroot()
    except Exception:
        return False
    for shape in root.findall("shape"):
        string_node = shape.find("string[@name='filename']")
        if string_node is None:
            continue
        if _shape_has_nontrivial_transform(shape):
            return True
    return False


def _cache_manifest_mode(manifest_path: Path) -> Optional[str]:
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(manifest, list) or not manifest:
        return None
    return "raw_copy" if any(isinstance(item, dict) and "source_file" in item for item in manifest) else "baked_export"


def _copy_file_scene_meshes(scene_file: Path, mesh_dir: Path, cache_dir: Path) -> bool:
    """Preserve original file-scene meshes for the viewer when they are plain PLY assets.

    Mitsuba's write_ply() can simplify or flatten some imported file-scene meshes. For
    direct file scenes backed by PLY assets, copying the source meshes preserves the
    geometry that the user authored.
    """
    if _scene_file_has_nontrivial_mesh_transforms(scene_file):
        return False
    try:
        root = ET.parse(scene_file).getroot()
    except Exception:
        return False

    entries = []
    for idx, shape in enumerate(root.findall("shape")):
        string_node = shape.find("string[@name='filename']")
        if string_node is None:
            continue
        rel_path = (string_node.attrib.get("value") or "").strip()
        if not rel_path:
            continue
        asset_path = Path(rel_path)
        if not asset_path.is_absolute():
            asset_path = (scene_file.parent / asset_path).resolve()
        if not asset_path.exists() or asset_path.suffix.lower() != ".ply":
            return False
        entries.append(
            {
                "index": idx,
                "src": asset_path,
                "file": f"mesh_{idx:03d}{asset_path.suffix.lower()}",
                "shape_id": shape.attrib.get("id"),
                "source_file": rel_path,
            }
        )

    if not entries:
        return False

    for stale in cache_dir.glob("mesh_*.*"):
        stale.unlink()

    manifest = []
    for item in entries:
        dst = cache_dir / item["file"]
        shutil.copyfile(item["src"], dst)
        manifest.append(
            {
                "index": item["index"],
                "file": item["file"],
                "shape_id": item["shape_id"],
                "source_file": item["source_file"],
            }
        )

    manifest_path = cache_dir / "mesh_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for src in cache_dir.glob("mesh_*.*"):
        dst = mesh_dir / src.name
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
    dst_manifest = mesh_dir / manifest_path.name
    if manifest_path.resolve() != dst_manifest.resolve():
        shutil.copyfile(manifest_path, dst_manifest)
    return True


def export_scene_meshes(
    scene,
    output_dir: Path,
    scene_id: str,
    cache_root: Optional[Path] = None,
    scene_file: Optional[str | Path] = None,
) -> None:
    """Export Mitsuba meshes to PLY files, with caching for faster re-runs."""
    mesh_dir = output_dir / "scene_mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    cache_root = cache_root or output_dir.parent / "_cache"
    cache_dir = cache_root / _safe_scene_id(scene_id)
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "mesh_manifest.json"

    if scene_file:
        scene_file_path = Path(scene_file)
        if scene_file_path.exists():
            if _copy_file_scene_meshes(scene_file_path, mesh_dir, cache_dir):
                return
            if _scene_file_has_nontrivial_mesh_transforms(scene_file_path) and _cache_manifest_mode(manifest_path) == "raw_copy":
                for stale in cache_dir.glob("mesh_*.*"):
                    stale.unlink()
                if manifest_path.exists():
                    manifest_path.unlink()

    cached_meshes = list(cache_dir.glob("*.ply"))
    if cached_meshes:
        if not manifest_path.exists():
            manifest = []
            mi_scene = scene.mi_scene
            for idx, mesh in enumerate(mi_scene.shapes()):
                shape_id = None
                try:
                    shape_id = mesh.id()
                except Exception:
                    shape_id = None
                manifest.append(
                    {
                        "index": idx,
                        "file": f"mesh_{idx:03d}.ply",
                        "shape_id": shape_id,
                    }
                )
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        for src in cached_meshes:
            dst = mesh_dir / src.name
            if src.resolve() != dst.resolve():
                shutil.copyfile(src, dst)
        if manifest_path.exists():
            dst_manifest = mesh_dir / manifest_path.name
            if manifest_path.resolve() != dst_manifest.resolve():
                shutil.copyfile(manifest_path, dst_manifest)
        return

    mi_scene = scene.mi_scene
    manifest = []
    for idx, mesh in enumerate(mi_scene.shapes()):
        try:
            path = cache_dir / f"mesh_{idx:03d}.ply"
            mesh.write_ply(str(path))
            shape_id = None
            try:
                shape_id = mesh.id()
            except Exception:
                shape_id = None
            manifest.append(
                {
                    "index": idx,
                    "file": path.name,
                    "shape_id": shape_id,
                }
            )
        except Exception:
            continue

    for src in cache_dir.glob("*.ply"):
        dst = mesh_dir / src.name
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
    if manifest:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        dst_manifest = mesh_dir / manifest_path.name
        if manifest_path.resolve() != dst_manifest.resolve():
            shutil.copyfile(manifest_path, dst_manifest)


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
