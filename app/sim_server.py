from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .sim_jobs import JobManager
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

    def _list_runs(self) -> Dict[str, Any]:
        output_root: Path = self.server.output_root
        runs = []
        if output_root.exists():
            for run_dir in sorted(output_root.iterdir(), reverse=True):
                if not run_dir.is_dir() or run_dir.name.startswith("_"):
                    continue
                summary_path = run_dir / "summary.json"
                config_path = run_dir / "config.yaml"
                viewer_path = run_dir / "viewer" / "scene_manifest.json"
                summary = None
                if summary_path.exists():
                    try:
                        summary = json.loads(summary_path.read_text())
                    except Exception:
                        summary = None
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

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/configs"):
            return _json_response(self, self._list_configs())
        if parsed.path.startswith("/api/scenes"):
            return _json_response(self, self._list_scenes())
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
        if parsed.path.startswith("/api/runs"):
            return _json_response(self, self._list_runs())
        if parsed.path.startswith("/api/run/"):
            run_id = parsed.path.split("/", 3)[3]
            run_dir = self.server.output_root / run_id
            if not run_dir.exists():
                return _json_response(self, {"error": "run not found"}, status=404)
            summary = None
            config = None
            summary_path = run_dir / "summary.json"
            config_path = run_dir / "config.yaml"
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
            return _json_response(self, {"run_id": run_id, "summary": summary, "config": config})
        if parsed.path.startswith("/api/jobs"):
            jobs = self.server.job_manager.list_jobs()
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
        if parsed.path.startswith("/runs/"):
            parts = parsed.path.split("/", 3)
            if len(parts) < 4:
                self.send_error(404, "Missing run file")
                return
            _, _, run_id, rel = parts
            return self._serve_run_file(run_id, rel)
        if parsed.path.startswith("/api/ping"):
            return _json_response(self, {"ok": True})
        return self._serve_static(parsed.path.lstrip("/"))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/jobs", "/api/ris/jobs"}:
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
