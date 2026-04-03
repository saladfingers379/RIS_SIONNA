from pathlib import Path

from app.sim_server import _infer_job_kind, _load_run_configs_for_ui, _resolve_scene_root_path, _scene_file_manifest


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
