from pathlib import Path

from app.scene import _copy_file_scene_meshes, export_scene_meshes
from app.sim_server import _parse_ply_bbox


def test_file_scene_export_preserves_anechoic_rightwall_geometry(tmp_path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    cache_root = tmp_path / "cache"
    scene_file = Path("scenes/anechoic_chamber_nofoam/scene.xml")

    export_scene_meshes(
        scene=None,
        output_dir=output_dir,
        scene_id="file-scenes/anechoic_chamber_nofoam/scene.xml",
        cache_root=cache_root,
        scene_file=scene_file,
    )

    exported = output_dir / "scene_mesh" / "mesh_005.ply"
    source = Path("scenes/anechoic_chamber_nofoam/meshes/absorber_rightwall.ply")

    assert exported.exists()
    assert exported.stat().st_size == source.stat().st_size

    exported_bbox = _parse_ply_bbox(exported)
    source_bbox = _parse_ply_bbox(source)

    assert exported_bbox is not None
    assert source_bbox is not None
    assert exported_bbox["bbox_min"] == source_bbox["bbox_min"]
    assert exported_bbox["bbox_max"] == source_bbox["bbox_max"]


def test_file_scene_raw_copy_skips_transformed_mesh_scenes(tmp_path) -> None:
    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    copied = _copy_file_scene_meshes(Path("scenes/ashby/scene.xml"), mesh_dir, cache_dir)

    assert copied is False
    assert list(mesh_dir.glob("*")) == []
    assert list(cache_dir.glob("*")) == []
