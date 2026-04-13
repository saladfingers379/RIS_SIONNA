from __future__ import annotations

import csv
import json
import logging
import math
import shutil
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .scene_file_manifest import load_scene_shape_entries
from .web_assets import ensure_three_vendor

logger = logging.getLogger(__name__)


_RADIO_MAP_PLOT_LABELS = {
    "radio_map_rx_power_dbm.png": "Radio map Rx power [dBm]",
    "radio_map_path_gain_db.png": "Radio map path gain [dB]",
    "radio_map_path_gain.png": "Radio map path gain",
    "radio_map_path_loss_db.png": "Radio map path loss [dB]",
    "radio_map_path_loss.png": "Radio map path loss",
    "radio_map_diff_path_gain_db.png": "RIS delta path gain [dB]",
    "radio_map_ris_on_path_gain_db.png": "Radio map with RIS path gain [dB]",
    "radio_map_ris_on_rx_power_dbm.png": "Radio map with RIS Rx power [dBm]",
    "radio_map_ris_on_path_loss_db.png": "Radio map with RIS path loss [dB]",
    "radio_map_ris_off_path_gain_db.png": "Radio map RIS-off metal baseline path gain [dB]",
    "radio_map_ris_off_rx_power_dbm.png": "Radio map RIS-off metal baseline Rx power [dBm]",
    "radio_map_ris_off_path_loss_db.png": "Radio map RIS-off metal baseline path loss [dB]",
    "radio_map_no_ris_path_gain_db.png": "Radio map without RIS path gain [dB]",
    "radio_map_no_ris_rx_power_dbm.png": "Radio map without RIS Rx power [dBm]",
    "radio_map_no_ris_path_loss_db.png": "Radio map without RIS path loss [dB]",
    "radio_map_tx_ris_incidence_path_gain_db.png": "Tx->RIS incidence path gain [dB]",
    "radio_map_tx_ris_incidence_rx_power_dbm.png": "Tx->RIS incidence Rx power [dBm]",
    "radio_map_tx_ris_incidence_path_loss_db.png": "Tx->RIS incidence path loss [dB]",
}
_RADIO_MAP_Z_RE = re.compile(r"_(?P<ztag>z(?:m)?[0-9]+p[0-9]{2})m\.png$")
_RADIO_MAP_Z_METRIC_LABELS = {
    "path_gain_db": "path gain [dB]",
    "rx_power_dbm": "Rx power [dBm]",
    "path_loss_db": "path loss [dB]",
}


def _radio_map_plot_priority(name: str) -> tuple[int, str]:
    if name == "radio_map_rx_power_dbm.png" or name.startswith("radio_map_rx_power_dbm_z"):
        return (0, name)
    if name in {"radio_map_path_gain_db.png", "radio_map_path_gain.png"} or name.startswith("radio_map_path_gain_db_z"):
        return (1, name)
    if name in {"radio_map_path_loss_db.png", "radio_map_path_loss.png"} or name.startswith("radio_map_path_loss_db_z"):
        return (2, name)
    if name.startswith("radio_map_") and "_diff_" not in name and "_ris_on_" not in name and "_no_ris_" not in name:
        return (3, name)
    if "_no_ris_" in name or "_ris_on_" in name or "_ris_off_" in name:
        return (4, name)
    if "_diff_" in name:
        return (5, name)
    return (6, name)


def _radio_map_plot_label(name: str) -> str:
    label = _RADIO_MAP_PLOT_LABELS.get(name)
    if label:
        return label
    match = _RADIO_MAP_Z_RE.search(name)
    if match:
        ztag = match.group("ztag")
        base_name = f"{name[: match.start()]}.png"
        base_label = _RADIO_MAP_PLOT_LABELS.get(base_name, Path(base_name).stem.replace("_", " "))
        z_value = ztag[2:] if ztag.startswith("zm") else ztag[1:]
        sign = "-" if ztag.startswith("zm") else ""
        return f"{base_label} @ z={sign}{z_value.replace('p', '.')} m"
    return Path(name).stem.replace("_", " ")


def _format_radio_map_plane_z_token(z_m: float) -> str:
    if z_m < 0.0:
        return f"zm{abs(float(z_m)):.2f}".replace(".", "p")
    return f"z{float(z_m):.2f}".replace(".", "p")


def _resolve_primary_radio_map_plot(
    plot_dir: Path,
    metric_base_name: str,
    *,
    preferred_z_m: float | None = None,
) -> Optional[str]:
    direct = plot_dir / metric_base_name
    if direct.exists():
        return metric_base_name

    stem = Path(metric_base_name).stem
    if preferred_z_m is not None:
        preferred_name = f"{stem}_{_format_radio_map_plane_z_token(preferred_z_m)}.png"
        preferred_path = plot_dir / preferred_name
        if preferred_path.exists():
            return preferred_name
    matches = sorted(plot_dir.glob(f"{stem}_z*m.png"))
    if not matches:
        return None
    return matches[len(matches) // 2].name


def _load_ray_segments(ray_csv: Path) -> List[List[float]]:
    if not ray_csv.exists():
        return []
    data = np.loadtxt(ray_csv, delimiter=",", skiprows=1)
    if data.size == 0:
        return []
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return data.tolist()


def _load_path_metrics(paths_csv: Path) -> Dict[str, Any]:
    if not paths_csv.exists():
        return {}
    with paths_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return {}

    # Support both legacy and extended formats.
    if "power_linear" in rows[0] and "delay_s" in rows[0]:
        return {
            "path_id": [int(r.get("path_id", 0)) for r in rows],
            "delay_s": [float(r.get("delay_s", 0.0)) for r in rows],
            "power_linear": [float(r.get("power_linear", 0.0)) for r in rows],
        }

    data = np.loadtxt(paths_csv, delimiter=",", skiprows=1)
    if data.size == 0:
        return {}
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return {
        "path_id": data[:, 0].tolist(),
        "delay_s": data[:, 1].tolist(),
        "power_linear": data[:, 2].tolist(),
        "aoa_azimuth_deg": data[:, 3].tolist(),
        "aoa_elevation_deg": data[:, 4].tolist(),
    }


def _load_path_table(paths_csv: Path) -> List[Dict[str, Any]]:
    if not paths_csv.exists():
        return []
    with paths_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return []
    if "order" not in rows[0]:
        return []
    table = []
    for row in rows:
        interactions = row.get("interactions", "")
        table.append(
            {
                "path_id": int(row.get("path_id", 0)),
                "order": int(row.get("order", 0)),
                "type": row.get("type", "unknown"),
                "path_length_m": float(row.get("path_length_m", 0.0)),
                "delay_s": float(row.get("delay_s", 0.0)),
                "power_linear": float(row.get("power_linear", 0.0)),
                "power_db": float(row.get("power_db", 0.0)),
                "interactions": [s for s in interactions.split(";") if s],
            }
        )
    return table


def _segments_to_polylines(segments: List[List[float]]) -> Dict[int, List[List[float]]]:
    polylines: Dict[int, List[List[float]]] = {}
    for row in segments:
        path_id = int(row[0])
        x0, y0, z0, x1, y1, z1 = row[1:]
        if path_id not in polylines:
            polylines[path_id] = [[x0, y0, z0]]
        polylines[path_id].append([x1, y1, z1])
    return polylines


def _scene_ris_interaction_names(scene: Any) -> set[str]:
    if scene is None or not hasattr(scene, "ris"):
        return set()
    names: set[str] = set()
    try:
        for ris in scene.ris.values():
            object_id = getattr(ris, "object_id", None)
            if object_id is None:
                continue
            names.add(f"object_{int(object_id)}")
    except Exception:
        return set()
    return names


def _ensure_vendor(viewer_dir: Path) -> None:
    ensure_three_vendor(viewer_dir)


def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    arr = np.asarray(vec, dtype=float).reshape(-1)
    norm = float(np.linalg.norm(arr))
    if norm <= 0.0:
        return np.array([1.0, 0.0, 0.0], dtype=float)
    return arr / norm


def _build_thumbnail_camera(scene: Any, aspect: float = 16.0 / 9.0, fov_deg: float = 35.0) -> Any:
    from sionna.rt import Camera

    bbox = scene.mi_scene.bbox()
    bbox_min = np.array([float(bbox.min.x), float(bbox.min.y), float(bbox.min.z)], dtype=float)
    bbox_max = np.array([float(bbox.max.x), float(bbox.max.y), float(bbox.max.z)], dtype=float)
    center = (bbox_min + bbox_max) * 0.5
    size = np.maximum(bbox_max - bbox_min, 1e-6)
    max_dim = float(max(np.max(size), 1.0))

    view_dir = _normalize_vector(np.array([1.0, 1.0, 0.8], dtype=float))
    world_up = np.array([0.0, 0.0, 1.0], dtype=float)
    if abs(float(np.dot(view_dir, world_up))) > 0.95:
        world_up = np.array([0.0, 1.0, 0.0], dtype=float)
    right = _normalize_vector(np.cross(world_up, view_dir))
    up = _normalize_vector(np.cross(view_dir, right))

    corners = np.array(
        [
            [bbox_min[0], bbox_min[1], bbox_min[2]],
            [bbox_min[0], bbox_min[1], bbox_max[2]],
            [bbox_min[0], bbox_max[1], bbox_min[2]],
            [bbox_min[0], bbox_max[1], bbox_max[2]],
            [bbox_max[0], bbox_min[1], bbox_min[2]],
            [bbox_max[0], bbox_min[1], bbox_max[2]],
            [bbox_max[0], bbox_max[1], bbox_min[2]],
            [bbox_max[0], bbox_max[1], bbox_max[2]],
        ],
        dtype=float,
    )
    rel = corners - center[None, :]
    half_width = float(np.max(np.abs(rel @ right)))
    half_height = float(np.max(np.abs(rel @ up)))
    half_depth = float(np.max(np.abs(rel @ view_dir)))

    fit_half_height = max(half_height, half_width / max(aspect, 1e-6), max_dim * 0.15) * 1.16
    fit_half_width = fit_half_height * aspect
    v_fov = math.radians(fov_deg)
    h_fov = 2.0 * math.atan(math.tan(v_fov * 0.5) * aspect)
    distance_y = fit_half_height / max(math.tan(v_fov * 0.5), 1e-6)
    distance_x = fit_half_width / max(math.tan(h_fov * 0.5), 1e-6)
    distance = max(distance_x, distance_y) + half_depth + max_dim * 0.35
    position = center + view_dir * distance

    return Camera(
        name="thumbnail_export",
        position=position,
        look_at=center,
    )


def _write_run_thumbnail(output_dir: Path, viewer_dir: Path, scene: Any = None) -> Optional[Path]:
    target = viewer_dir / "thumbnail.png"
    if target.exists():
        return target
    if scene is not None:
        try:
            cam = _build_thumbnail_camera(scene)
            scene.render_to_file(
                camera=cam,
                filename=str(target),
                num_samples=64,
                resolution=(1600, 900),
            )
            if target.exists():
                return target
        except Exception as exc:  # pragma: no cover - rendering path depends on runtime stack
            logger.warning("Explorer thumbnail render failed: %s", exc)
    return None


def generate_viewer(output_dir: Path, config: Dict[str, Any], scene=None) -> Optional[Path]:
    viewer_dir = output_dir / "viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    _ensure_vendor(viewer_dir)

    ray_csv = output_dir / "data" / "ray_paths.csv"
    segments = _load_ray_segments(ray_csv)

    paths_csv = output_dir / "data" / "paths.csv"
    path_metrics = _load_path_metrics(paths_csv)
    path_table = _load_path_table(paths_csv)

    scene_cfg = config.get("scene", {})
    tx = scene_cfg.get("tx", {}).get("position", [0.0, 0.0, 0.0])
    rx = scene_cfg.get("rx", {}).get("position", [0.0, 0.0, 0.0])

    mesh_src = scene_cfg.get("mesh")
    mesh_dst = None
    if mesh_src:
        mesh_src = Path(mesh_src)
        if mesh_src.exists():
            mesh_dst = viewer_dir / mesh_src.name
            if mesh_src.resolve() != mesh_dst.resolve():
                shutil.copyfile(mesh_src, mesh_dst)

    mesh_dir = output_dir / "scene_mesh"
    mesh_files = []
    mesh_manifest = []
    if mesh_dir.exists():
        out_mesh_dir = viewer_dir / "meshes"
        out_mesh_dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(mesh_dir.glob("*.ply")):
            dst = out_mesh_dir / src.name
            if src.resolve() != dst.resolve():
                shutil.copyfile(src, dst)
            mesh_files.append(f"meshes/{dst.name}")
        manifest_src = mesh_dir / "mesh_manifest.json"
        if manifest_src.exists():
            try:
                mesh_manifest = json.loads(manifest_src.read_text(encoding="utf-8"))
            except Exception:
                mesh_manifest = []

    proxy_enabled = scene_cfg.get("proxy_enabled", False)
    proxy = scene_cfg.get("proxy") if proxy_enabled else None

    plot_dir = output_dir / "plots"
    radio_cfg = config.get("radio_map", {})
    preferred_plane_z = None
    try:
        if radio_cfg.get("center_z_only") is not None:
            preferred_plane_z = float(radio_cfg.get("center_z_only"))
        elif isinstance(radio_cfg.get("center"), list) and len(radio_cfg.get("center", [])) >= 3:
            preferred_plane_z = float(radio_cfg["center"][2])
    except Exception:
        preferred_plane_z = None
    overlays = []
    for base_name in [
        "radio_map_path_gain_db.png",
        "radio_map_rx_power_dbm.png",
        "radio_map_path_loss_db.png",
    ]:
        resolved_name = _resolve_primary_radio_map_plot(plot_dir, base_name, preferred_z_m=preferred_plane_z)
        if resolved_name is None:
            continue
        src = plot_dir / resolved_name
        if src.exists():
            dst = viewer_dir / resolved_name
            if src.resolve() != dst.resolve():
                shutil.copyfile(src, dst)
            overlays.append(resolved_name)

    data = {
        "segments": segments,
        "path_metrics": path_metrics,
        "tx": tx,
        "rx": rx,
        "mesh": mesh_dst.name if mesh_dst else None,
        "mesh_files": mesh_files,
        "proxy": proxy,
        "overlays": overlays,
    }

    polylines = _segments_to_polylines(segments)
    path_rows = []
    by_id = {row["path_id"]: row for row in path_table}
    ris_interaction_names = _scene_ris_interaction_names(scene)
    for path_id, points in polylines.items():
        meta = by_id.get(path_id, {})
        interactions = meta.get("interactions", [])
        path_rows.append(
            {
                "path_id": path_id,
                "points": points,
                "order": meta.get("order", 0),
                "type": meta.get("type", "unknown"),
                "path_length_m": meta.get("path_length_m"),
                "delay_s": meta.get("delay_s"),
                "power_db": meta.get("power_db"),
                "power_linear": meta.get("power_linear"),
                "interactions": interactions,
                "has_ris": bool(ris_interaction_names and any(name in ris_interaction_names for name in interactions)),
            }
        )

    ris_positions = []
    try:
        ris_positions = [np.asarray(r.position).reshape(-1).tolist() for r in scene.ris.values()]
    except Exception:
        ris_positions = []
    markers = {"tx": tx, "rx": rx, "ris": ris_positions}
    (viewer_dir / "markers.json").write_text(json.dumps(markers, indent=2), encoding="utf-8")
    (viewer_dir / "paths.json").write_text(json.dumps(path_rows, indent=2), encoding="utf-8")

    scene_manifest = {
        "mesh": mesh_dst.name if mesh_dst else None,
        "mesh_files": mesh_files,
        "mesh_rotation_deg": scene_cfg.get("mesh_rotation_deg"),
        "proxy": proxy,
    }
    if mesh_manifest:
        source_map = {}
        transform_map = {}
        scene_file = scene_cfg.get("file")
        if scene_cfg.get("type") == "file" and scene_file:
            try:
                for entry in load_scene_shape_entries(Path(scene_file)):
                    sid = entry.get("shape_id")
                    src = entry.get("source_file")
                    if sid and src:
                        source_map[sid] = src
                    if sid:
                        transform_map[sid] = entry.get("transform_ops") or []
            except Exception:
                source_map = {}
                transform_map = {}
        enriched = []
        for item in mesh_manifest:
            shape_id = item.get("shape_id")
            src_name = source_map.get(shape_id) if shape_id else None
            display = src_name or shape_id or item.get("file")
            payload = {
                "file": f"meshes/{item.get('file')}",
                "shape_id": shape_id,
                "source": src_name,
                "display": display,
            }
            # Raw-copied file-scene meshes still need the source XML transform in the browser.
            if item.get("source_file") and shape_id in transform_map:
                payload["transform_ops"] = transform_map.get(shape_id) or []
            enriched.append(payload)
        scene_manifest["mesh_manifest"] = enriched
    materials = []
    objects = []
    if scene is not None:
        try:
            objects = list(getattr(scene, "objects", {}).values())
        except Exception:
            objects = []

    def _material_row(name, rm):
        radio_material = None
        is_placeholder = False
        if isinstance(rm, str):
            radio_material = rm
        elif rm is not None:
            radio_material = getattr(rm, "name", str(rm))
            is_placeholder = bool(getattr(rm, "is_placeholder", False))
        return {
            "object": name,
            "radio_material": radio_material,
            "is_placeholder": is_placeholder,
        }

    if objects:
        for obj in objects:
            name = getattr(obj, "name", None)
            if name is None:
                continue
            try:
                rm = obj.radio_material
            except Exception:
                rm = None
            materials.append(_material_row(name, rm))
    elif scene is not None:
        # Fallback: use Mitsuba shape ids and resolve via scene.get(name).
        try:
            shape_ids = []
            for shape in scene.mi_scene.shapes():
                try:
                    sid = shape.id()
                except Exception:
                    sid = None
                if sid:
                    shape_ids.append(str(sid))
            for sid in shape_ids:
                rm = None
                try:
                    obj = scene.get(sid)
                    rm = obj.radio_material
                except Exception:
                    rm = None
                materials.append(_material_row(sid, rm))
        except Exception:
            materials = []
    else:
        # Last resort: parse file scene XML to extract bsdf references.
        scene_file = scene_cfg.get("file")
        if scene_cfg.get("type") == "file" and scene_file:
            try:
                xml_text = Path(scene_file).read_text(encoding="utf-8")
                shape_pattern = r"<shape\\b[^>]*\\bid=\"(?P<id>[^\"]+)\"[^>]*>(?P<body>[\\s\\S]*?)</shape>"
                for match in re.finditer(shape_pattern, xml_text, flags=re.IGNORECASE):
                    sid = match.group("id")
                    body = match.group("body") or ""
                    bsdf_id = None
                    ref_match = re.search(r"<ref\\b[^>]*\\bname=\"bsdf\"[^>]*\\bid=\"([^\"]+)\"", body)
                    if not ref_match:
                        ref_match = re.search(r"<ref\\b[^>]*\\bid=\"([^\"]+)\"[^>]*\\bname=\"bsdf\"", body)
                    if ref_match:
                        bsdf_id = ref_match.group(1)
                    else:
                        bsdf_match = re.search(r"<bsdf\\b[^>]*\\bid=\"([^\"]+)\"", body)
                        if bsdf_match:
                            bsdf_id = bsdf_match.group(1)
                    materials.append(_material_row(sid, bsdf_id))
            except Exception:
                materials = []
    scene_manifest["materials"] = materials
    (viewer_dir / "scene_manifest.json").write_text(
        json.dumps(scene_manifest, indent=2), encoding="utf-8"
    )

    heatmap_src = output_dir / "data" / "radio_map.npz"
    if heatmap_src.exists():
        try:
            with np.load(heatmap_src) as hm:
                rx_power_dbm = hm.get("rx_power_dbm")
                path_gain_db = hm.get("path_gain_db")
                cell_centers = hm.get("cell_centers")
            metric_name = "rx_power_dbm" if rx_power_dbm is not None else "path_gain_db"
            values = rx_power_dbm if rx_power_dbm is not None else path_gain_db
            if values is not None and cell_centers is not None:
                if values.ndim == 3:
                    values_out = values[0]
                    grid_shape = list(values.shape[1:])
                else:
                    values_out = values
                    grid_shape = list(values.shape)
                heatmap = {
                    "metric": metric_name,
                    "grid_shape": grid_shape,
                    "values": values_out.tolist(),
                    "cell_centers": cell_centers.tolist(),
                    "center": radio_cfg.get("center"),
                    "size": radio_cfg.get("size"),
                    "cell_size": radio_cfg.get("cell_size"),
                    "orientation": radio_cfg.get("orientation"),
                }
                (viewer_dir / "heatmap.json").write_text(
                    json.dumps(heatmap, indent=2), encoding="utf-8"
                )
                heatmap_dst = viewer_dir / "heatmap.npz"
                if heatmap_dst.resolve() != heatmap_src.resolve():
                    shutil.copyfile(heatmap_src, heatmap_dst)
        except Exception:
            pass

    heatmap_diff_src = output_dir / "data" / "radio_map_diff.npz"
    if heatmap_diff_src.exists():
        try:
            with np.load(heatmap_diff_src) as hm:
                path_gain_diff_db = hm.get("path_gain_db")
                cell_centers = hm.get("cell_centers")
            if path_gain_diff_db is not None and cell_centers is not None:
                if path_gain_diff_db.ndim == 3:
                    values_out = path_gain_diff_db[0]
                    grid_shape = list(path_gain_diff_db.shape[1:])
                else:
                    values_out = path_gain_diff_db
                    grid_shape = list(path_gain_diff_db.shape)
                radio_cfg = config.get("radio_map", {})
                heatmap_diff = {
                    "metric": "diff_path_gain_db",
                    "grid_shape": grid_shape,
                    "values": values_out.tolist(),
                    "cell_centers": cell_centers.tolist(),
                    "center": radio_cfg.get("center"),
                    "size": radio_cfg.get("size"),
                    "cell_size": radio_cfg.get("cell_size"),
                    "orientation": radio_cfg.get("orientation"),
                }
                (viewer_dir / "heatmap_diff.json").write_text(
                    json.dumps(heatmap_diff, indent=2), encoding="utf-8"
                )
                heatmap_diff_dst = viewer_dir / "heatmap_diff.npz"
                if heatmap_diff_dst.resolve() != heatmap_diff_src.resolve():
                    shutil.copyfile(heatmap_diff_src, heatmap_diff_dst)
        except Exception:
            pass

    # Collect radio map plot images for UI preview (heatmap or Sionna plots)
    radio_plots = []
    plots_dir = output_dir / "plots"
    if plots_dir.exists():
        for img in sorted(plots_dir.glob("radio_map_*.png"), key=lambda path: _radio_map_plot_priority(path.name)):
            dst = viewer_dir / img.name
            if dst.resolve() != img.resolve():
                shutil.copyfile(img, dst)
            radio_plots.append({"file": img.name, "label": _radio_map_plot_label(img.name)})
        for img in sorted(plots_dir.glob("ris_*_phase.png")):
            dst = viewer_dir / img.name
            if dst.resolve() != img.resolve():
                shutil.copyfile(img, dst)
            radio_plots.append({"file": img.name, "label": img.stem})
        for img in sorted(plots_dir.glob("ris_*_amplitude.png")):
            dst = viewer_dir / img.name
            if dst.resolve() != img.resolve():
                shutil.copyfile(img, dst)
            radio_plots.append({"file": img.name, "label": img.stem})
    (viewer_dir / "radio_map_plots.json").write_text(
        json.dumps({"plots": radio_plots}, indent=2), encoding="utf-8"
    )
    _write_run_thumbnail(output_dir, viewer_dir, scene=scene)

    html = build_viewer_html(data)
    html_path = viewer_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def build_viewer_html(data: Dict[str, Any]) -> str:
    payload = json.dumps(data)
    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self' data: blob:; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:;\" />
  <title>RIS_SIONNA 3D Viewer</title>
  <style>
    html, body, #c {{ margin: 0; width: 100%; height: 100%; overflow: hidden; background: #f7f7f2; }}
    #hud {{ position: absolute; top: 12px; left: 12px; background: rgba(255,255,255,0.9); padding: 8px 10px; font: 12px/1.4 Arial; border-radius: 6px; }}
    #controls {{ position: absolute; top: 12px; right: 12px; background: rgba(255,255,255,0.9); padding: 8px 10px; font: 12px/1.4 Arial; border-radius: 6px; }}
  </style>
</head>
<body>
<div id=\"c\"></div>
<div id=\"hud\">Tx: red · Rx: blue · Rays: orange · <span id=\"coords\">x: -- y: -- z: --</span></div>
<div id=\"controls\">
  <label>Ray color:
    <select id=\"colorMode\">
      <option value=\"uniform\">Uniform</option>
      <option value=\"power\">By power</option>
      <option value=\"delay\">By delay</option>
    </select>
  </label>
  <br/>
  <label><input type=\"checkbox\" id=\"showProxy\" /> Show proxy geometry</label>
  <br/>
  <label><input type=\"checkbox\" id=\"showMesh\" checked /> Show scene mesh</label>
  <br/>
</div>
<script type=\"module\">
  import * as THREE from "./vendor/three.module.js";
  import {{ OrbitControls }} from "./vendor/OrbitControls.js";
  let GLTFLoader = null;
  let OBJLoader = null;
  let PLYLoader = null;

  const data = {payload};
  const container = document.getElementById("c");
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf3f6f9);

  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 5000);
  camera.up.set(0, 0, 1);

  const renderer = new THREE.WebGLRenderer({{ antialias: true }});
  renderer.setSize(window.innerWidth, window.innerHeight);
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  const hemi = new THREE.HemisphereLight(0xffffff, 0x6b7a89, 0.9);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 0.6);
  dir.position.set(50, 100, 20);
  scene.add(dir);
  const fill = new THREE.PointLight(0xffffff, 0.35);
  fill.position.set(-60, -40, 60);
  scene.add(fill);

  // Keep the scene clean; rely on actual geometry only.
  const pickables = [];
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  const groundPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const coordsEl = document.getElementById("coords");
  const meshGroup = new THREE.Group();
  scene.add(meshGroup);

  function registerPickable(obj) {{
    if (obj) pickables.push(obj);
  }}

  function addProxy(proxy) {{
    if (!proxy) return null;
    const proxyGroup = new THREE.Group();
    if (proxy.ground) {{
      const size = proxy.ground.size || [200, 200];
      const elev = proxy.ground.elevation || 0;
      const geo = new THREE.PlaneGeometry(size[0], size[1]);
      const mat = new THREE.MeshStandardMaterial({{ color: 0xdfe7ef, side: THREE.DoubleSide, roughness: 0.9, metalness: 0.0 }});
      const ground = new THREE.Mesh(geo, mat);
      ground.position.z = elev;
      proxyGroup.add(ground);
    }}
    (proxy.boxes || []).forEach((b, idx) => {{
      const size = b.size || [10, 10, 10];
      const center = b.center || [0, 0, size[2] / 2];
      const geo = new THREE.BoxGeometry(size[0], size[1], size[2]);
      const palette = [0x7aa2f7, 0x2ac3de, 0xf6c177, 0xbb9af7];
      const mat = new THREE.MeshStandardMaterial({{ color: palette[idx % palette.length], transparent: true, opacity: 0.85, roughness: 0.7, metalness: 0.05 }});
      const box = new THREE.Mesh(geo, mat);
      box.position.set(center[0], center[1], center[2]);
      proxyGroup.add(box);
      const edges = new THREE.EdgesGeometry(geo);
      const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({{ color: 0x2c3e50, opacity: 0.6, transparent: true }}));
      line.position.copy(box.position);
      proxyGroup.add(line);
    }});
    scene.add(proxyGroup);
    proxyGroup.traverse((child) => {{
      if (child.isMesh) registerPickable(child);
    }});
    return proxyGroup;
  }}

  function lerpColor(t) {{
    const c1 = new THREE.Color(0x2a9d8f);
    const c2 = new THREE.Color(0xe76f51);
    return c1.lerp(c2, t);
  }}

  function buildPathMetricMap(metric) {{
    const m = data.path_metrics || {{}};
    if (!m.path_id) return {{}};
    const map = {{}};
    for (let i = 0; i < m.path_id.length; i++) {{
      map[m.path_id[i]] = metric === "delay" ? m.delay_s[i] : m.power_linear[i];
    }}
    return map;
  }}

  function normalizeValues(values) {{
    const vals = Object.values(values);
    if (vals.length === 0) return {{ min: 0, max: 1 }};
    return {{ min: Math.min(...vals), max: Math.max(...vals) }};
  }}

  function addRays(segments) {{
    if (!segments || segments.length === 0) return null;
    const positions = [];
    const colors = [];
    const pathIds = [];
    const defaultColor = new THREE.Color(0xff9750);
    for (const s of segments) {{
      const [pathId, x0, y0, z0, x1, y1, z1] = s;
      positions.push(x0, y0, z0, x1, y1, z1);
      colors.push(defaultColor.r, defaultColor.g, defaultColor.b);
      colors.push(defaultColor.r, defaultColor.g, defaultColor.b);
      pathIds.push(pathId);
    }}
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.LineBasicMaterial({{ vertexColors: true, transparent: true, opacity: 0.85 }});
    const line = new THREE.LineSegments(geo, mat);
    scene.add(line);
    return {{ line, pathIds }};
  }}

  function addMarker(pos, color) {{
    const geo = new THREE.SphereGeometry(2.2, 20, 20);
    const mat = new THREE.MeshStandardMaterial({{ color, emissive: color, emissiveIntensity: 0.35 }});
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(pos[0], pos[1], pos[2]);
    scene.add(mesh);
  }}

  function addLabel(pos, text, color) {{
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.font = '16px Arial';
    const pad = 6;
    const textWidth = ctx.measureText(text).width;
    canvas.width = textWidth + pad * 2;
    canvas.height = 28;
    ctx.font = '16px Arial';
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#111827';
    ctx.fillText(text, pad, 19);
    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({{ map: texture, depthTest: false }});
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(canvas.width / 6, canvas.height / 6, 1);
    sprite.position.set(pos[0], pos[1], pos[2] + 4);
    scene.add(sprite);
  }}

  const proxyGroup = addProxy(data.proxy);
  const rayBundle = addRays(data.segments);
  addMarker(data.tx, 0xdc322f);
  addMarker(data.rx, 0x268bd2);
  addLabel(data.tx, "Tx", 0xdc322f);
  addLabel(data.rx, "Rx", 0x268bd2);
  const proxyToggle = document.getElementById("showProxy");
  const meshToggle = document.getElementById("showMesh");
  proxyToggle.checked = false;
  if (!proxyGroup) {{
    proxyToggle.disabled = true;
    proxyToggle.parentElement.style.display = "none";
  }}


  let meshLoaded = false;
  async function loadPlyMeshes() {{
    if (!data.mesh_files || data.mesh_files.length === 0) return;
    const mod = await import('./vendor/PLYLoader.js');
    PLYLoader = mod.PLYLoader;
    const loader = new PLYLoader();
    data.mesh_files.forEach((fname) => {{
      loader.load(fname, (geom) => {{
        geom.computeVertexNormals();
        const mat = new THREE.MeshStandardMaterial({{ color: 0x9aa8b1, transparent: true, opacity: 0.55 }});
        const mesh = new THREE.Mesh(geom, mat);
        meshGroup.add(mesh);
        registerPickable(mesh);
      }});
    }});
  }}

  async function ensureMeshesLoaded() {{
    if (meshLoaded) return;
    meshLoaded = true;
    if (data.mesh) {{
      const ext = data.mesh.split('.').pop().toLowerCase();
      if (ext === 'gltf' || ext === 'glb') {{
        const mod = await import('./vendor/GLTFLoader.js');
        GLTFLoader = mod.GLTFLoader;
        const loader = new GLTFLoader();
        loader.load(data.mesh, (gltf) => {{
          meshGroup.add(gltf.scene);
          gltf.scene.traverse((child) => {{
            if (child.isMesh) registerPickable(child);
          }});
        }});
      }} else if (ext === 'obj') {{
        const mod = await import('./vendor/OBJLoader.js');
        OBJLoader = mod.OBJLoader;
        const loader = new OBJLoader();
        loader.load(data.mesh, (obj) => {{
          meshGroup.add(obj);
          obj.traverse((child) => {{
            if (child.isMesh) registerPickable(child);
          }});
        }});
      }}
    }} else {{
      await loadPlyMeshes();
    }}
  }}

  function setCameraToBounds() {{
    const points = [];
    for (const s of data.segments || []) {{
      points.push(new THREE.Vector3(s[1], s[2], s[3]));
      points.push(new THREE.Vector3(s[4], s[5], s[6]));
    }}
    points.push(new THREE.Vector3(data.tx[0], data.tx[1], data.tx[2]));
    points.push(new THREE.Vector3(data.rx[0], data.rx[1], data.rx[2]));
    if (points.length === 0) {{
      camera.position.set(60, 80, 100);
      controls.target.set(0, 0, 0);
      return;
    }}
    const box = new THREE.Box3().setFromPoints(points);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z) * 0.9 + 10;
    camera.position.set(center.x + radius, center.y + radius, center.z + radius);
    controls.target.copy(center);
    camera.lookAt(center);
  }}

  function applyRayColors(mode) {{
    if (!rayBundle || !rayBundle.line) return;
    const colors = rayBundle.line.geometry.getAttribute("color");
    if (mode === "uniform") {{
      const c = new THREE.Color(0xff9750);
      for (let i = 0; i < colors.count; i++) {{
        colors.setXYZ(i, c.r, c.g, c.b);
      }}
      colors.needsUpdate = true;
      return;
    }}
    const map = buildPathMetricMap(mode);
    const bounds = normalizeValues(map);
    for (let i = 0; i < rayBundle.pathIds.length; i++) {{
      const pathId = rayBundle.pathIds[i];
      const val = map[pathId] ?? bounds.min;
      const t = bounds.max > bounds.min ? (val - bounds.min) / (bounds.max - bounds.min) : 0.0;
      const c = lerpColor(t);
      colors.setXYZ(i * 2, c.r, c.g, c.b);
      colors.setXYZ(i * 2 + 1, c.r, c.g, c.b);
    }}
    colors.needsUpdate = true;
  }}

  document.getElementById("colorMode").addEventListener("change", (e) => {{
    applyRayColors(e.target.value);
  }});
  document.getElementById("showProxy").addEventListener("change", (e) => {{
    if (proxyGroup) proxyGroup.visible = e.target.checked;
  }});
  document.getElementById("showMesh").addEventListener("change", async (e) => {{
    meshGroup.visible = e.target.checked;
    if (e.target.checked) {{
      await ensureMeshesLoaded();
    }}
  }});
  meshGroup.visible = meshToggle.checked;
  if (meshToggle.checked) {{
    await ensureMeshesLoaded();
  }}
  if (!data.mesh && (!data.mesh_files || data.mesh_files.length === 0)) {{
    meshToggle.checked = false;
    meshToggle.disabled = true;
    meshToggle.parentElement.style.display = "none";
  }}
  setCameraToBounds();
  controls.update();
  applyRayColors("uniform");

  function animate() {{
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }}
  animate();

  function updateCoords(event) {{
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    let point = null;
    if (pickables.length) {{
      const hits = raycaster.intersectObjects(pickables, true);
      if (hits.length > 0) point = hits[0].point;
    }}
    if (!point) {{
      point = new THREE.Vector3();
      raycaster.ray.intersectPlane(groundPlane, point);
    }}
    if (point) {{
      coordsEl.textContent = `x: ${{point.x.toFixed(2)}} y: ${{point.y.toFixed(2)}} z: ${{point.z.toFixed(2)}}`;
    }}
  }}

  renderer.domElement.addEventListener('mousemove', updateCoords);

  window.addEventListener('resize', () => {{
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }});
</script>
</body>
</html>"""
