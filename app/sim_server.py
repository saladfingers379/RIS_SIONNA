from __future__ import annotations

import html
import hmac
import json
import mimetypes
import os
import secrets
import struct
import threading
import time
import xml.etree.ElementTree as ET
from http import cookies
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
    try:
        handler.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError):
        return


def _html_response(handler: BaseHTTPRequestHandler, body: str, status: int = 200) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    try:
        handler.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError):
        return


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


def _normalize_redirect_target(target: Optional[str]) -> str:
    value = str(target or "").strip()
    if not value.startswith("/"):
        return "/"
    if value.startswith("//"):
        return "/"
    return value or "/"


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




def _coerce_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not (number == number):
        return None
    return number


def _humanize_name(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    text = Path(text).stem.replace("_", " ").replace("-", " ")
    return " ".join(part for part in text.split() if part)


def _extract_scene_label(config: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(config, dict):
        return None
    scene = config.get("scene")
    if not isinstance(scene, dict):
        return None
    for key in ("label", "name", "title"):
        label = _humanize_name(scene.get(key))
        if label:
            return label
    if str(scene.get("type") or "").strip() == "builtin":
        return _humanize_name(scene.get("builtin"))
    return _humanize_name(scene.get("file"))


def _pick_run_thumbnail(run_dir: Path) -> tuple[Optional[str], Optional[str]]:
    explorer_thumb = run_dir / "viewer" / "thumbnail.png"
    if explorer_thumb.exists():
        return f"/runs/{run_dir.name}/viewer/thumbnail.png", "Explorer thumbnail"
    return None, None


def _build_run_listing(
    run_dir: Path,
    summary: Optional[Dict[str, Any]],
    config: Optional[Dict[str, Any]],
    *,
    has_viewer: Optional[bool] = None,
) -> Dict[str, Any]:
    cfg = config if isinstance(config, dict) else {}
    summary_data = summary if isinstance(summary, dict) else None
    simulation = cfg.get("simulation") if isinstance(cfg.get("simulation"), dict) else {}
    runtime = summary_data.get("runtime") if summary_data else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    metrics = summary_data.get("metrics") if summary_data else {}
    metrics = metrics if isinstance(metrics, dict) else {}
    timings = runtime.get("timings_s")

    viewer_manifest = run_dir / "viewer" / "scene_manifest.json"
    thumbnail_path, thumbnail_label = _pick_run_thumbnail(run_dir)
    frequency_hz = _coerce_float(simulation.get("frequency_hz"))
    total_seconds = _coerce_float(timings.get("total_s")) if isinstance(timings, dict) else None
    config_path = run_dir / "config.yaml"

    return {
        "run_id": run_dir.name,
        "summary": summary_data,
        "config_path": str(config_path) if config_path.exists() else None,
        "has_viewer": viewer_manifest.exists() if has_viewer is None else bool(has_viewer),
        "kind": _infer_job_kind(run_dir),
        "scope": infer_run_scope_from_config(cfg) if cfg else "sim",
        "scene_label": _extract_scene_label(cfg),
        "backend": str(runtime.get("rt_backend") or runtime.get("mitsuba_variant") or "").strip() or None,
        "frequency_ghz": (frequency_hz / 1e9) if frequency_hz is not None else None,
        "max_depth": simulation.get("max_depth"),
        "path_count": metrics.get("num_valid_paths"),
        "total_path_gain_db": metrics.get("total_path_gain_db"),
        "rx_power_dbm": metrics.get("rx_power_dbm_estimate"),
        "duration_s": total_seconds,
        "thumbnail_path": thumbnail_path,
        "thumbnail_label": thumbnail_label,
        "quality_preset": cfg.get("quality", {}).get("preset") if isinstance(cfg.get("quality"), dict) else None,
    }


class SimRequestHandler(BaseHTTPRequestHandler):
    server_version = "RIS_SIONNA_Sim/0.1"

    def _is_api_request(self, path: str) -> bool:
        return path.startswith("/api/")

    def _request_target(self) -> str:
        parsed = urlparse(self.path)
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        return _normalize_redirect_target(target)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        return self.rfile.read(length) if length else b""

    def _session_cookie_name(self) -> str:
        return self.server.auth_cookie_name

    def _current_session_token(self) -> Optional[str]:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return None
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw)
        except cookies.CookieError:
            return None
        morsel = jar.get(self._session_cookie_name())
        if morsel is None:
            return None
        token = morsel.value.strip()
        return token or None

    def _is_authenticated(self) -> bool:
        if not self.server.auth_enabled:
            return True
        token = self._current_session_token()
        if not token:
            return False
        return self.server.validate_session(token)

    def _set_session_cookie(self, token: str) -> None:
        cookie = cookies.SimpleCookie()
        cookie[self._session_cookie_name()] = token
        cookie[self._session_cookie_name()]["path"] = "/"
        cookie[self._session_cookie_name()]["httponly"] = True
        cookie[self._session_cookie_name()]["samesite"] = "Lax"
        self.send_header("Set-Cookie", cookie.output(header="").strip())

    def _clear_session_cookie(self) -> None:
        cookie = cookies.SimpleCookie()
        cookie[self._session_cookie_name()] = ""
        cookie[self._session_cookie_name()]["path"] = "/"
        cookie[self._session_cookie_name()]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        cookie[self._session_cookie_name()]["max-age"] = "0"
        cookie[self._session_cookie_name()]["httponly"] = True
        cookie[self._session_cookie_name()]["samesite"] = "Lax"
        self.send_header("Set-Cookie", cookie.output(header="").strip())

    def _redirect(self, location: str, set_cookie_token: Optional[str] = None, clear_cookie: bool = False) -> None:
        self.send_response(303)
        self.send_header("Location", _normalize_redirect_target(location))
        self.send_header("Cache-Control", "no-store")
        if set_cookie_token:
            self._set_session_cookie(set_cookie_token)
        if clear_cookie:
            self._clear_session_cookie()
        self.end_headers()

    def _render_login_page(self, error: Optional[str] = None, next_target: Optional[str] = None) -> str:
        message = ""
        if error:
            message = f'<p class="error">{html.escape(error)}</p>'
        target = html.escape(_normalize_redirect_target(next_target), quote=True)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RIS_SIONNA Login</title>
  <style>
    :root {{
      color-scheme: light;
      --bg-a: #eef6ff;
      --bg-b: #d8f0df;
      --panel: rgba(255, 255, 255, 0.92);
      --text: #122033;
      --muted: #576579;
      --accent: #0d6a87;
      --accent-strong: #084c61;
      --danger: #9f1d35;
      --border: rgba(18, 32, 51, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(13, 106, 135, 0.18), transparent 35%),
        radial-gradient(circle at bottom right, rgba(16, 125, 87, 0.16), transparent 30%),
        linear-gradient(135deg, var(--bg-a), var(--bg-b));
    }}
    .panel {{
      width: min(420px, 100%);
      padding: 32px 28px;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--panel);
      backdrop-filter: blur(8px);
      box-shadow: 0 28px 60px rgba(18, 32, 51, 0.16);
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 1.9rem;
      line-height: 1.1;
    }}
    p {{
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.5;
    }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-size: 0.95rem;
      font-weight: 600;
    }}
    input {{
      width: 100%;
      padding: 14px 16px;
      border: 1px solid var(--border);
      border-radius: 12px;
      font: inherit;
      background: #fff;
    }}
    button {{
      width: 100%;
      margin-top: 16px;
      padding: 14px 16px;
      border: 0;
      border-radius: 12px;
      font: inherit;
      font-weight: 700;
      color: #fff;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      cursor: pointer;
    }}
    .error {{
      margin-bottom: 14px;
      color: var(--danger);
      font-weight: 600;
    }}
    .hint {{
      margin-top: 14px;
      font-size: 0.88rem;
    }}
  </style>
</head>
<body>
  <main class="panel">
    <h1>RIS_SIONNA</h1>
    <p>Enter the local showcase password to access the simulator and run controls.</p>
    {message}
    <form method="post" action="/auth/login">
      <input type="hidden" name="next" value="{target}">
      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" autofocus required>
      <button type="submit">Sign In</button>
    </form>
    <p class="hint">Authentication is enabled on this simulator instance.</p>
  </main>
</body>
</html>
"""

    def _serve_login_page(self, status: int = 200, error: Optional[str] = None) -> None:
        _html_response(self, self._render_login_page(error=error, next_target=self._request_target()), status=status)

    def _auth_gate(self) -> bool:
        parsed = urlparse(self.path)
        path = parsed.path
        if not self.server.auth_enabled:
            return True
        if path in {"/auth/login", "/auth/logout"}:
            return True
        if path == "/api/ping":
            return True
        if self._is_authenticated():
            return True
        if self._is_api_request(path):
            _json_response(self, {"error": "authentication required"}, status=401)
            return False
        self._serve_login_page()
        return False

    def _handle_login(self) -> None:
        body = self._read_body()
        form = parse_qs(body.decode("utf-8", errors="ignore"))
        password = str((form.get("password") or [""])[0] or "")
        next_target = _normalize_redirect_target((form.get("next") or ["/"])[0])
        if not self.server.auth_enabled:
            return self._redirect(next_target)
        if not password or not hmac.compare_digest(password, self.server.auth_password):
            _html_response(
                self,
                self._render_login_page(error="Incorrect password.", next_target=next_target),
                status=401,
            )
            return
        token = self.server.create_session()
        self._redirect(next_target, set_cookie_token=token)

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404, "File not found")
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if path.suffix in {".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".glb", ".ply"}:
            if "vendor" in path.parts:
                self.send_header("Cache-Control", "public, max-age=86400")
            else:
                self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

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
                runs.append(_build_run_listing(run_dir, summary, config, has_viewer=viewer_path.exists()))
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
        if parsed.path == "/auth/logout":
            token = self._current_session_token()
            if token:
                self.server.drop_session(token)
            self._redirect("/", clear_cookie=True)
            return
        if parsed.path == "/auth/login":
            if self._is_authenticated():
                self._redirect("/")
                return
            self._serve_login_page()
            return
        if not self._auth_gate():
            return
        scope = _query_value(parsed, "scope")
        kind = _query_value(parsed, "kind")
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
            return _json_response(self, self._list_runs(scope=scope, kind=kind))
        if parsed.path.startswith("/api/campaign/runs"):
            return _json_response(self, self._list_runs(kind="campaign"))
        if parsed.path.startswith("/api/link/runs"):
            return _json_response(self, self._list_runs(kind="link_level"))
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
        if parsed.path.startswith("/api/ris-synth/jobs/"):
            job_id = parsed.path.split("/", 4)[4]
            job = self.server.job_manager.get_job(job_id)
            if not job or job.get("kind") != "ris_synthesis":
                return _json_response(self, {"error": "job not found"}, status=404)
            return _json_response(self, job)
        if parsed.path.startswith("/api/ris-synth/jobs"):
            jobs = self.server.job_manager.list_jobs(kind="ris_synthesis")
            return _json_response(self, jobs)
        if parsed.path.startswith("/api/link/jobs/"):
            job_id = parsed.path.split("/", 4)[4]
            job = self.server.job_manager.get_job(job_id)
            if not job or job.get("kind") != "link_level":
                return _json_response(self, {"error": "job not found"}, status=404)
            return _json_response(self, job)
        if parsed.path.startswith("/api/link/jobs"):
            jobs = self.server.job_manager.list_jobs(kind="link_level")
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
        if parsed.path == "/auth/login":
            self._handle_login()
            return
        if not self._auth_gate():
            return
        if parsed.path not in {"/api/jobs", "/api/ris/jobs", "/api/ris-synth/jobs", "/api/campaign/jobs", "/api/link/jobs"}:
            self.send_error(404, "Not found")
            return
        body = self._read_body() or b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}
        if parsed.path == "/api/ris/jobs":
            payload["kind"] = "ris_lab"
        if parsed.path == "/api/ris-synth/jobs":
            payload["kind"] = "ris_synthesis"
        if parsed.path == "/api/link/jobs":
            payload["kind"] = "link_level"
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
        self,
        host: str,
        port: int,
        static_root: Path,
        output_root: Path,
        config_root: Path,
        auth_password: Optional[str] = None,
    ) -> None:
        self.static_root = static_root
        self.output_root = output_root
        self.config_root = config_root
        self.job_manager = JobManager(output_root)
        self.auth_password = str(auth_password or "")
        self.auth_enabled = bool(self.auth_password)
        self.auth_cookie_name = "ris_sim_session"
        self.auth_session_ttl_s = 12 * 60 * 60
        self._auth_sessions: Dict[str, float] = {}
        self._auth_lock = threading.Lock()
        super().__init__((host, port), SimRequestHandler)

    def _prune_sessions_locked(self, now: Optional[float] = None) -> None:
        timestamp = now if now is not None else time.time()
        expired = [
            token
            for token, created_at in self._auth_sessions.items()
            if (timestamp - created_at) > self.auth_session_ttl_s
        ]
        for token in expired:
            self._auth_sessions.pop(token, None)

    def create_session(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._auth_lock:
            self._prune_sessions_locked()
            self._auth_sessions[token] = time.time()
        return token

    def validate_session(self, token: str) -> bool:
        with self._auth_lock:
            self._prune_sessions_locked()
            created_at = self._auth_sessions.get(token)
            if created_at is None:
                return False
            self._auth_sessions[token] = time.time()
            return True

    def drop_session(self, token: str) -> None:
        with self._auth_lock:
            self._auth_sessions.pop(token, None)


def serve_simulator(
    host: str = "127.0.0.1", port: int = 8765, auth_password: Optional[str] = None
) -> None:
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
        auth_password=auth_password,
    )
    print(f"RIS_SIONNA simulator running at http://{host}:{port}")
    if auth_password:
        print("Simulator access password is enabled.")
    try:
        server.serve_forever()
    finally:
        server.server_close()
