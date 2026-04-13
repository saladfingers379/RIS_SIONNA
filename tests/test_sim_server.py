import json
import threading
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, build_opener, urlopen

import pytest

from app.sim_server import (
    SimServer,
    _build_run_listing,
    _infer_job_kind,
    _load_run_configs_for_ui,
    _resolve_scene_root_path,
    _scene_file_manifest,
)


def test_load_run_configs_for_ui_prefers_job_config(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "job_config.yaml").write_text(
        "scene:\n  tx:\n    position: [5, 0, 1]\n",
        encoding="utf-8",
    )
    (run_dir / "config.yaml").write_text(
        "scene:\n  tx:\n    position: [10, 0, 1]\n",
        encoding="utf-8",
    )

    configs = _load_run_configs_for_ui(run_dir)

    assert configs["config"]["scene"]["tx"]["position"] == [5, 0, 1]
    assert configs["effective_config"]["scene"]["tx"]["position"] == [10, 0, 1]


def test_load_run_configs_for_ui_falls_back_to_effective_config(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text(
        "scene:\n  tx:\n    position: [7, 0, 1]\n",
        encoding="utf-8",
    )

    configs = _load_run_configs_for_ui(run_dir)

    assert configs["config"]["scene"]["tx"]["position"] == [7, 0, 1]
    assert configs["effective_config"]["scene"]["tx"]["position"] == [7, 0, 1]


def test_infer_job_kind_prefers_job_config(tmp_path: Path) -> None:
    run_dir = tmp_path / "campaign"
    run_dir.mkdir()
    (run_dir / "job_config.yaml").write_text(
        "job:\n  kind: campaign\n",
        encoding="utf-8",
    )

    assert _infer_job_kind(run_dir) == "campaign"


def test_infer_job_kind_supports_link_level_runs(tmp_path: Path) -> None:
    run_dir = tmp_path / "link"
    run_dir.mkdir()
    (run_dir / "job_config.yaml").write_text(
        "job:\n  kind: link_level\n",
        encoding="utf-8",
    )

    assert _infer_job_kind(run_dir) == "link_level"


def test_resolve_scene_root_path_supports_repo_prefixed_paths() -> None:
    resolved = _resolve_scene_root_path("scenes/anechoic_chamber_nofoam/scene.xml")

    assert resolved == Path("scenes/anechoic_chamber_nofoam/scene.xml").resolve()


def test_resolve_scene_root_path_supports_absolute_repo_paths() -> None:
    absolute = str(Path("scenes/anechoic_chamber_nofoam/scene.xml").resolve())

    resolved = _resolve_scene_root_path(absolute)

    assert resolved == Path(absolute)


def test_scene_file_manifest_lists_mesh_files() -> None:
    manifest = _scene_file_manifest(Path("scenes/anechoic_chamber_nofoam/scene.xml"))

    assert manifest["path"] == "scenes/anechoic_chamber_nofoam/scene.xml"
    assert manifest["mesh_files"]
    assert "anechoic_chamber_nofoam/meshes/absorber_back.ply" in manifest["mesh_files"]


def test_scene_file_manifest_normalizes_absolute_scene_path() -> None:
    manifest = _scene_file_manifest(Path("scenes/anechoic_chamber_nofoam/scene.xml").resolve())

    assert manifest["path"] == "scenes/anechoic_chamber_nofoam/scene.xml"


def test_blank_scene_file_manifest_lists_anchor_mesh() -> None:
    manifest = _scene_file_manifest(Path("scenes/blank/scene.xml"))

    assert manifest["path"] == "scenes/blank/scene.xml"
    assert manifest["mesh_files"] == ["blank/meshes/anchor_triangle.ply"]


def test_ashby_scene_file_manifest_includes_mesh_transforms() -> None:
    manifest = _scene_file_manifest(Path("scenes/ashby/scene.xml"))

    assert manifest["path"] == "scenes/ashby/scene.xml"
    assert manifest["mesh_files"]
    city = next(item for item in manifest["mesh_manifest"] if item["shape_id"] == "city_mesh")
    assert city["file"] == "ashby/meshes/ashby_city_clip.ply"
    assert city["transform_ops"] == [
        {"type": "rotate", "axis": [0.0, 1.0, 0.0], "angle_deg": 180.0},
        {"type": "translate", "value": [0.0, 0.0, 23.05]},
    ]


def test_build_run_listing_includes_preview_and_summary_metadata(tmp_path: Path) -> None:
    run_dir = tmp_path / "20260411_103000_123456"
    (run_dir / "plots").mkdir(parents=True)
    (run_dir / "viewer").mkdir()
    (run_dir / "plots" / "scene.png").write_bytes(b"png")
    (run_dir / "viewer" / "thumbnail.png").write_bytes(b"thumb")
    (run_dir / "viewer" / "scene_manifest.json").write_text("{}", encoding="utf-8")
    (run_dir / "config.yaml").write_text("scene:\n  builtin: etoile\n", encoding="utf-8")
    (run_dir / "job_config.yaml").write_text(
        "job:\n  kind: run\nsimulation:\n  frequency_hz: 28.0e9\n  max_depth: 6\nscene:\n  type: builtin\n  builtin: etoile\nquality:\n  preset: high\n",
        encoding="utf-8",
    )
    summary = {
        "metrics": {
            "num_valid_paths": 123,
            "total_path_gain_db": -98.5,
            "rx_power_dbm_estimate": -70.25,
        },
        "runtime": {
            "rt_backend": "cuda/optix",
            "timings_s": {"total_s": 18.4},
        },
    }

    config = {
        "job": {"kind": "run"},
        "simulation": {"frequency_hz": "28.0e9", "max_depth": 6},
        "scene": {"type": "builtin", "builtin": "etoile"},
        "quality": {"preset": "high"},
    }
    listing = _build_run_listing(run_dir, summary, config)

    assert listing["run_id"] == "20260411_103000_123456"
    assert listing["scene_label"] == "etoile"
    assert listing["backend"] == "cuda/optix"
    assert listing["frequency_ghz"] == pytest.approx(28.0)
    assert listing["duration_s"] == pytest.approx(18.4)
    assert listing["path_count"] == 123
    assert listing["thumbnail_path"] == "/runs/20260411_103000_123456/viewer/thumbnail.png"
    assert listing["thumbnail_label"] == "Explorer thumbnail"
    assert listing["quality_preset"] == "high"


def _start_auth_test_server(tmp_path: Path, password: str = "demo-pass") -> tuple[SimServer, str]:
    output_root = tmp_path / "outputs"
    config_root = tmp_path / "configs"
    output_root.mkdir()
    config_root.mkdir()
    (config_root / "demo.yaml").write_text("scene:\n  tx:\n    position: [1, 2, 3]\n", encoding="utf-8")

    server = SimServer(
        "127.0.0.1",
        0,
        static_root=Path("app/sim_web"),
        output_root=output_root,
        config_root=config_root,
        auth_password=password,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def _start_test_server(tmp_path: Path) -> tuple[SimServer, str]:
    output_root = tmp_path / "outputs"
    config_root = tmp_path / "configs"
    output_root.mkdir()
    config_root.mkdir()

    server = SimServer(
        "127.0.0.1",
        0,
        static_root=Path("app/sim_web"),
        output_root=output_root,
        config_root=config_root,
        auth_password=None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def test_sim_server_requires_password_for_api_access(tmp_path: Path) -> None:
    server, base_url = _start_auth_test_server(tmp_path)
    try:
        with pytest.raises(HTTPError) as excinfo:
            urlopen(f"{base_url}/api/configs")
        assert excinfo.value.code == 401
        payload = json.loads(excinfo.value.read().decode("utf-8"))
        assert payload["error"] == "authentication required"
    finally:
        server.shutdown()
        server.server_close()


def test_sim_server_login_unlocks_protected_routes(tmp_path: Path) -> None:
    server, base_url = _start_auth_test_server(tmp_path)
    try:
        with urlopen(base_url) as resp:
            body = resp.read().decode("utf-8")
        assert "Sign In" in body
        assert "viewerCanvas" not in body

        cookies = CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookies))
        login_body = urlencode({"password": "demo-pass", "next": "/"}).encode("utf-8")
        with opener.open(f"{base_url}/auth/login", data=login_body) as resp:
            landing = resp.read().decode("utf-8")
        assert "viewerCanvas" in landing
        assert any(cookie.name == "ris_sim_session" for cookie in cookies)

        with opener.open(f"{base_url}/api/configs") as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["configs"][0]["name"] == "demo.yaml"
    finally:
        server.shutdown()
        server.server_close()


def test_scene_file_asset_response_is_cacheable_for_ply_meshes(tmp_path: Path) -> None:
    server, base_url = _start_test_server(tmp_path)
    try:
        with urlopen(f"{base_url}/api/scene_file_asset?path=blank/meshes/anchor_triangle.ply") as resp:
            cache_control = resp.headers.get("Cache-Control")
            content_type = resp.headers.get("Content-Type")
            body = resp.read()
        assert cache_control == "public, max-age=3600"
        assert content_type == "application/octet-stream"
        assert body
    finally:
        server.shutdown()
        server.server_close()
