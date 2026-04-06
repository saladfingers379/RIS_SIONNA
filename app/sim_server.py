from __future__ import annotations

import json
import mimetypes
import os
import struct
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from .scene_file_manifest import load_scene_shape_entries
from .sim_jobs import JobManager, infer_run_scope_from_config
from .web_assets import ensure_three_vendor


def _json_response(handler: BaseHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    data = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _safe_join(root: Path, path: str) -> Optional[Path]:
    if ".." in path or path.startswith("/"):
        return None
    target = (root / path).resolve()
    if not str(target).startswith(str(root.resolve())):
        return None
    return target


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _scene_repo_path(path: Path) -> str:
    root = Path("scenes").resolve()
    resolved = path.resolve()
    if _path_within_root(resolved, root):
        return Path("scenes", resolved.relative_to(root)).as_posix()
    return path.as_posix()


def _query_value(parsed, name: str) -> Optional[str]:
    values = parse_qs(parsed.query).get(name) or []
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _parse_ply_bbox(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("rb") as f:
            header_lines = []
            while True:
                line = f.readline()
                if not line:
                    return None
                text = line.decode("ascii").rstrip("\n")
                header_lines.append(text)
                if text == "end_header":
                    break

            fmt = None
            nverts = 0
            current_element = None
            vertex_props = []
            for line in header_lines:
                if line.startswith("format "):
                    parts = line.split()
                    if len(parts) >= 2:
                        fmt = parts[1]
                elif line.startswith("element "):
                    parts = line.split()
                    if len(parts) >= 3:
                        current_element = parts[1]
                        if current_element == "vertex":
                            nverts = int(parts[2])
                elif line.startswith("property ") and current_element == "vertex":
                    vertex_props.append(line.split()[-1])

            if nverts <= 0:
                return None

            mins = [float("inf"), float("inf"), float("inf")]
            maxs = [float("-inf"), float("-inf"), float("-inf")]

            if fmt == "ascii":
                for _ in range(nverts):
                    parts = f.readline().decode("ascii").split()
                    if len(parts) < 3:
                        return None
                    coords = [float(parts[0]), float(parts[1]), float(parts[2])]
                    for axis in range(3):
                        mins[axis] = min(mins[axis], coords[axis])
                        maxs[axis] = max(maxs[axis], coords[axis])
            elif fmt == "binary_little_endian":
                row_fmt = "<" + ("f" * len(vertex_props))
                row_size = struct.calcsize(row_fmt)
                if row_size <= 0:
                    return None
                for _ in range(nverts):
                    row = f.read(row_size)
                    if len(row) != row_size:
                        return None
                    vals = struct.unpack(row_fmt, row)
                    coords = vals[:3]
                    for axis in range(3):
                        mins[axis] = min(mins[axis], coords[axis])
                        maxs[axis] = max(maxs[axis], coords[axis])
            else:
                return None

            return {
                "bbox_min": mins,
                "bbox_max": maxs,
                "center": [(mins[i] + maxs[i]) / 2.0 for i in range(3)],
                "size": [maxs[i] - mins[i] for i in range(3)],
            }
    except Exception:
        return None


def _combine_bounds(accum: Optional[Dict[str, Any]], item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if item is None:
        return accum
    if accum is None:
        return {
            "bbox_min": list(item["bbox_min"]),
            "bbox_max": list(item["bbox_max"]),
        }
    for axis in range(3):
        accum["bbox_min"][axis] = min(accum["bbox_min"][axis], item["bbox_min"][axis])
        accum["bbox_max"][axis] = max(accum["bbox_max"][axis], item["bbox_max"][axis])
    return accum


def _inspect_scene_file(scene_xml: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "label": scene_xml.parent.name or scene_xml.as_posix(),
        "path": _scene_repo_path(scene_xml),
        "bounds": None,
    }
    try:
        root = ET.parse(scene_xml).getroot()
    except Exception:
        return result

    bounds = None
    for shape in root.findall("shape"):
        string_node = shape.find("string[@name='filename']")
        if string_node is None:
            continue
        rel_path = (string_node.attrib.get("value") or "").strip()
        if not rel_path:
            continue
        mesh_path = (scene_xml.parent / rel_path).resolve()
        if not mesh_path.exists():
            continue
        bounds = _combine_bounds(bounds, _parse_ply_bbox(mesh_path))

    if bounds is not None:
        mins = bounds["bbox_min"]
        maxs = bounds["bbox_max"]
        result["bounds"] = {
            "bbox_min": mins,
            "bbox_max": maxs,
            "center": [(mins[i] + maxs[i]) / 2.0 for i in range(3)],
            "size": [maxs[i] - mins[i] for i in range(3)],
        }
    return result


def _resolve_scene_root_path(path_value: str) -> Optional[Path]:
    value = unquote(str(path_value or "").strip())
    if not value:
        return None
    root = Path("scenes").resolve()
    candidate = Path(value)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        return resolved if _path_within_root(resolved, root) else None
    if value.startswith("scenes/"):
        value = value[len("scenes/") :]
    return _safe_join(root, value)


def _scene_file_manifest(scene_xml: Path) -> Dict[str, Any]:
    manifest = _inspect_scene_file(scene_xml)
    root = Path("scenes").resolve()
    mesh_files = []
    mesh_manifest = []
    try:
        for entry in load_scene_shape_entries(scene_xml):
            rel_path = str(entry.get("source_file") or "").strip()
            if not rel_path:
                continue
            mesh_path = (scene_xml.parent / rel_path).resolve()
            if not mesh_path.exists():
                continue
            if not str(mesh_path).startswith(str(root)):
                continue
            rel_repo_path = mesh_path.relative_to(root).as_posix()
            mesh_files.append(rel_repo_path)
            mesh_manifest.append(
                {
                    "file": rel_repo_path,
                    "shape_id": entry.get("shape_id"),
                    "source": rel_path,
                    "display": rel_path or entry.get("shape_id") or rel_repo_path,
                    "transform_ops": entry.get("transform_ops") or [],
                }
            )
    except Exception:
        mesh_files = []
        mesh_manifest = []
    manifest["mesh_files"] = mesh_files
    manifest["mesh_manifest"] = mesh_manifest
    return manifest


def _load_yaml_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        import yaml

        data = yaml.safe_load(path.read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _load_run_configs_for_ui(run_dir: Path) -> Dict[str, Optional[Dict[str, Any]]]:
    requested = _load_yaml_file(run_dir / "job_config.yaml")
    effective = _load_yaml_file(run_dir / "config.yaml")
    return {
        "config": requested or effective,
        "effective_config": effective,
    }


def _infer_job_kind(run_dir: Path) -> str:
    configs = _load_run_configs_for_ui(run_dir)
    cfg = configs["config"] or configs["effective_config"] or {}
    if not isinstance(cfg, dict):
        return "run"
    job_cfg = cfg.get("job")
    if isinstance(job_cfg, dict):
        return str(job_cfg.get("kind") or "run")
    return "run"




class SimRequestHandler(BaseHTTPRequestHandler):
    server_version = "RIS_SIONNA_Sim/0.1"

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404, "File not found")
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if path.suffix in {".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".glb"}:
            if "vendor" in path.parts:
                self.send_header("Cache-Control", "public, max-age=86400")
            else:
                self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, rel_path: str) -> None:
        static_root: Path = self.server.static_root
        if rel_path == "":
            rel_path = "index.html"
        if rel_path == "utils/BufferGeometryUtils.js":
            rel_path = "vendor/BufferGeometryUtils.js"
        if rel_path == "utils/three.module.js":
            rel_path = "vendor/three.module.js"
        target = _safe_join(static_root, rel_path)
        if not target:
            self.send_error(400, "Bad path")
            return
        self._serve_file(target)

    def _serve_run_file(self, run_id: str, rel_path: str) -> None:
        output_root: Path = self.server.output_root
        run_dir = output_root / run_id
        target = _safe_join(run_dir, rel_path)
        if not target:
            self.send_error(400, "Bad path")
            return
        self._serve_file(target)

    def _list_scene_caches(self) -> Dict[str, Any]:
        """List cached scene mesh directories available for direct loading."""
        cache_root = self.server.output_root / "_cache"
        caches = []
        if cache_root.exists():
            for cache_dir in sorted(cache_root.iterdir()):
                if not cache_dir.is_dir():
                    continue
                manifest_path = cache_dir / "mesh_manifest.json"
                if manifest_path.exists():
                    try:
                        manifest = json.loads(manifest_path.read_text())
                    except Exception:
                        manifest = []
                    mesh_files = [e["file"] for e in manifest if "file" in e]
                    caches.append({
                        "key": cache_dir.name,
                        "mesh_files": mesh_files,
                    })
        return {"caches": caches}

    def _find_latest_viewer_run(self, scope: Optional[str] = None) -> Dict[str, Any]:
        """Return the run_id of the most recent run that has viewer data."""
        output_root: Path = self.server.output_root
        if output_root.exists():
            for run_dir in sorted(output_root.iterdir(), reverse=True):
                if not run_dir.is_dir() or run_dir.name.startswith("_"):
                    continue
                if scope:
                    config_path = run_dir / "config.yaml"
                    run_scope = "sim"
                    if config_path.exists():
                        try:
                            import yaml

                            run_scope = infer_run_scope_from_config(yaml.safe_load(config_path.read_text()))
                        except Exception:
                            run_scope = "sim"
                    if run_scope != scope:
                        continue
                viewer_manifest = run_dir / "viewer" / "scene_manifest.json"
                if viewer_manifest.exists():
                    return {"run_id": run_dir.name}
        return {"run_id": None}

    def _list_runs(self, scope: Optional[str] = None, kind: Optional[str] = None) -> Dict[str, Any]:
        output_root: Path = self.server.output_root
        runs = []
        if output_root.exists():
            for run_dir in sorted(output_root.iterdir(), reverse=True):
                if not run_dir.is_dir() or run_dir.name.startswith("_"):
                    continue
                if kind and _infer_job_kind(run_dir) != kind:
                    continue
                summary_path = run_dir / "summary.json"
                config_path = run_dir / "config.yaml"
                viewer_path = run_dir / "viewer" / "scene_manifest.json"
                summary = None
                config = None
                if summary_path.exists():
                    try:
                        summary = json.loads(summary_path.read_text())
                    except Exception:
                        summary = None
                if config_path.exists():
                    try:
                        import yaml

                        config = yaml.safe_load(config_path.read_text())
                    except Exception:
                        config = None
                if scope and infer_run_scope_from_config(config) != scope:
                    continue
                runs.append(
                    {
                        "run_id": run_dir.name,
                        "summary": summary,
                        "config_path": str(config_path) if config_path.exists() else None,
                        "has_viewer": viewer_path.exists(),
                    }
                )
        return {"runs": runs}

    def _list_configs(self) -> Dict[str, Any]:
        config_root: Path = self.server.config_root
        configs = []
        if config_root.exists():
            for cfg_path in sorted(config_root.glob("*.yaml")):
                cfg_data = None
                try:
                    import yaml

                    cfg_data = yaml.safe_load(cfg_path.read_text())
                except Exception:
                    cfg_data = None
                configs.append(
                    {
                        "name": cfg_path.name,
                        "path": str(cfg_path.as_posix()),
                        "data": cfg_data,
                    }
                )
        return {"configs": configs}

    def _list_scenes(self) -> Dict[str, Any]:
        scenes = []
        try:
            import sionna.rt.scene as sionna_scene

            for name, value in vars(sionna_scene).items():
                if name.startswith("_"):
                    continue
                if isinstance(value, str):
                    scenes.append(name)
        except Exception:
            scenes = []
        if not scenes:
            scenes = [
                "etoile",
                "simple_street_canyon",
                "simple_street_canyon_with_cars",
                "munich",
                "floor_wall",
                "simple_wedge",
                "simple_reflector",
                "double_reflector",
                "triple_reflector",
                "box",
            ]
        scenes = sorted(set(scenes))
        return {"scenes": scenes}

    def _list_file_scenes(self) -> Dict[str, Any]:
        output = []
        try:
            base = Path("scenes")
            if not base.exists():
                return {"scenes": output}
            for scene_xml in sorted(base.glob("**/scene.xml")):
                output.append(_inspect_scene_file(scene_xml))
        except Exception:
            output = []
        return {"scenes": output}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        scope = _query_value(parsed, "scope")
        if parsed.path.startswith("/api/configs"):
            return _json_response(self, self._list_configs())
        if parsed.path.startswith("/api/scenes"):
            return _json_response(self, self._list_scenes())
        if parsed.path.startswith("/api/scene_files"):
            return _json_response(self, self._list_file_scenes())
        if parsed.path.startswith("/api/scene_file_manifest"):
            scene_path = _query_value(parsed, "path")
            target = _resolve_scene_root_path(scene_path or "")
            if target is None or not target.exists():
                return _json_response(self, {"error": "scene file not found"}, status=404)
            return _json_response(self, _scene_file_manifest(target))
        if parsed.path.startswith("/api/scene_file_asset"):
            asset_path = _query_value(parsed, "path")
            target = _resolve_scene_root_path(asset_path or "")
            if target is None or not target.exists() or not target.is_file():
                self.send_error(404, "Scene asset not found")
                return
            return self._serve_file(target)
        if parsed.path.startswith("/api/progress/"):
            run_id = parsed.path.split("/", 3)[3]
            run_dir = self.server.output_root / run_id
            progress_path = run_dir / "progress.json"
            if not progress_path.exists():
                return _json_response(self, {"error": "progress not found"}, status=404)
            try:
                payload = json.loads(progress_path.read_text())
            except Exception:
                payload = {"error": "progress unreadable"}
            return _json_response(self, payload)
        if parsed.path.startswith("/api/latest-viewer"):
            return _json_response(self, self._find_latest_viewer_run(scope=scope))
        if parsed.path.startswith("/api/runs"):
            return _json_response(self, self._list_runs(scope=scope))
        if parsed.path.startswith("/api/campaign/runs"):
            return _json_response(self, self._list_runs(kind="campaign"))
        if parsed.path.startswith("/api/run/"):
            run_id = parsed.path.split("/", 3)[3]
            run_dir = self.server.output_root / run_id
            if not run_dir.exists():
                return _json_response(self, {"error": "run not found"}, status=404)
            summary = None
            summary_path = run_dir / "summary.json"
            if summary_path.exists():
                try:
                    summary = json.loads(summary_path.read_text())
                except Exception:
                    summary = None
            configs = _load_run_configs_for_ui(run_dir)
            return _json_response(
                self,
                {
                    "run_id": run_id,
                    "summary": summary,
                    "config": configs["config"],
                    "effective_config": configs["effective_config"],
                },
            )
        if parsed.path.startswith("/api/jobs"):
            jobs = self.server.job_manager.list_jobs(scope=scope)
            return _json_response(self, jobs)
        if parsed.path.startswith("/api/ris/jobs/"):
            job_id = parsed.path.split("/", 4)[4]
            job = self.server.job_manager.get_job(job_id)
            if not job or job.get("kind") != "ris_lab":
                return _json_response(self, {"error": "job not found"}, status=404)
            return _json_response(self, job)
        if parsed.path.startswith("/api/ris/jobs"):
            jobs = self.server.job_manager.list_jobs(kind="ris_lab")
            return _json_response(self, jobs)
        if parsed.path.startswith("/api/campaign/jobs/"):
            job_id = parsed.path.split("/", 4)[4]
            job = self.server.job_manager.get_job(job_id)
            if not job or job.get("kind") != "campaign":
                return _json_response(self, {"error": "job not found"}, status=404)
            return _json_response(self, job)
        if parsed.path.startswith("/api/campaign/jobs"):
            jobs = self.server.job_manager.list_jobs(kind="campaign")
            return _json_response(self, jobs)
        if parsed.path.startswith("/runs/"):
            parts = parsed.path.split("/", 3)
            if len(parts) < 4:
                self.send_error(404, "Missing run file")
                return
            _, _, run_id, rel = parts
            return self._serve_run_file(run_id, rel)
        if parsed.path.startswith("/api/scene-cache"):
            return _json_response(self, self._list_scene_caches())
        if parsed.path.startswith("/cache/"):
            # Serve files from outputs/_cache/<cache_key>/<file>
            rel = parsed.path[len("/cache/"):]
            cache_dir = self.server.output_root / "_cache"
            target = (cache_dir / rel).resolve()
            if not str(target).startswith(str(cache_dir.resolve())):
                self.send_error(403, "Forbidden")
                return
            if not target.exists():
                self.send_error(404, "Cache file not found")
                return
            return self._serve_file(target)
        if parsed.path.startswith("/api/ping"):
            return _json_response(self, {"ok": True})
        return self._serve_static(parsed.path.lstrip("/"))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/jobs", "/api/ris/jobs", "/api/campaign/jobs"}:
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}
        if parsed.path == "/api/ris/jobs":
            payload["kind"] = "ris_lab"
        if parsed.path == "/api/campaign/jobs":
            payload["kind"] = "campaign"
        try:
            job = self.server.job_manager.create_job(payload)
        except Exception as exc:
            return _json_response(self, {"error": str(exc)}, status=400)
        return _json_response(self, job)

    def log_message(self, format: str, *args: Any) -> None:
        if os.environ.get("SIM_SERVER_QUIET"):
            return
        super().log_message(format, *args)


class SimServer(ThreadingHTTPServer):
    def __init__(
        self, host: str, port: int, static_root: Path, output_root: Path, config_root: Path
    ) -> None:
        self.static_root = static_root
        self.output_root = output_root
        self.config_root = config_root
        self.job_manager = JobManager(output_root)
        super().__init__((host, port), SimRequestHandler)


def serve_simulator(host: str = "127.0.0.1", port: int = 8765) -> None:
    static_root = Path(__file__).parent / "sim_web"
    ensure_three_vendor(static_root)
    output_root = Path("outputs")
    config_root = Path("configs")
    server = SimServer(
        host,
        port,
        static_root=static_root,
        output_root=output_root,
        config_root=config_root,
    )
    print(f"RIS_SIONNA simulator running at http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
