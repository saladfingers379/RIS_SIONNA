from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


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


def _default_proxy() -> Dict[str, Any]:
    return {
        "ground": {"size": [200.0, 200.0], "elevation": 0.0},
        "boxes": [
            {"center": [35.0, 40.0, 5.0], "size": [20.0, 20.0, 10.0]},
            {"center": [10.0, 20.0, 4.0], "size": [12.0, 16.0, 8.0]},
        ],
    }


def _ensure_vendor(viewer_dir: Path) -> None:
    vendor_dir = viewer_dir / "vendor"
    vendor_dir.mkdir(parents=True, exist_ok=True)
    assets = {
        "three.module.js": "https://unpkg.com/three@0.161.0/build/three.module.js",
        "OrbitControls.js": "https://unpkg.com/three@0.161.0/examples/jsm/controls/OrbitControls.js",
        "GLTFLoader.js": "https://unpkg.com/three@0.161.0/examples/jsm/loaders/GLTFLoader.js",
        "OBJLoader.js": "https://unpkg.com/three@0.161.0/examples/jsm/loaders/OBJLoader.js",
        "BufferGeometryUtils.js": "https://unpkg.com/three@0.161.0/examples/jsm/utils/BufferGeometryUtils.js",
        "PLYLoader.js": "https://unpkg.com/three@0.161.0/examples/jsm/loaders/PLYLoader.js",
    }
    for name, url in assets.items():
        path = vendor_dir / name
        if path.exists():
            continue
        with urllib.request.urlopen(url, timeout=30) as resp:
            content = resp.read()
        # Rewrite module specifiers to local three.module.js for offline use.
        if name != "three.module.js":
            text = content.decode("utf-8")
            text = text.replace("from 'three';", "from './three.module.js';")
            text = text.replace('from \"three\";', 'from \"./three.module.js\";')
            text = text.replace("from 'three'", "from './three.module.js'")
            text = text.replace('from \"three\"', 'from \"./three.module.js\"')
            text = text.replace(
                "three/examples/jsm/utils/BufferGeometryUtils.js",
                "./BufferGeometryUtils.js",
            )
            text = text.replace(
                "three/addons/utils/BufferGeometryUtils.js",
                "./BufferGeometryUtils.js",
            )
            text = text.replace(
                "three/examples/jsm/loaders/PLYLoader.js",
                "./PLYLoader.js",
            )
            content = text.encode("utf-8")
        path.write_bytes(content)


def generate_viewer(output_dir: Path, config: Dict[str, Any]) -> Optional[Path]:
    viewer_dir = output_dir / "viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    _ensure_vendor(viewer_dir)

    ray_csv = output_dir / "data" / "ray_paths.csv"
    segments = _load_ray_segments(ray_csv)

    paths_csv = output_dir / "data" / "paths.csv"
    path_metrics = _load_path_metrics(paths_csv)

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
    if mesh_dir.exists():
        out_mesh_dir = viewer_dir / "meshes"
        out_mesh_dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(mesh_dir.glob("*.ply")):
            dst = out_mesh_dir / src.name
            if src.resolve() != dst.resolve():
                shutil.copyfile(src, dst)
            mesh_files.append(f"meshes/{dst.name}")

    proxy_enabled = scene_cfg.get("proxy_enabled", True)
    proxy = (scene_cfg.get("proxy") or _default_proxy()) if proxy_enabled else None

    plot_dir = output_dir / "plots"
    overlays = []
    for name in [
        "radio_map_path_gain_db.png",
        "radio_map_rx_power_dbm.png",
        "radio_map_path_loss_db.png",
    ]:
        src = plot_dir / name
        if src.exists():
            dst = viewer_dir / name
            if src.resolve() != dst.resolve():
                shutil.copyfile(src, dst)
            overlays.append(name)

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
  <label><input type=\"checkbox\" id=\"showProxy\" checked /> Show proxy geometry</label>
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
  if (!proxyGroup) {{
    const proxyToggle = document.getElementById("showProxy");
    proxyToggle.checked = false;
    proxyToggle.disabled = true;
    proxyToggle.parentElement.style.display = "none";
  }}


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
        scene.add(mesh);
        registerPickable(mesh);
      }});
    }});
  }}

  if (data.mesh) {{
    const ext = data.mesh.split('.').pop().toLowerCase();
    if (ext === 'gltf' || ext === 'glb') {{
      const mod = await import('./vendor/GLTFLoader.js');
      GLTFLoader = mod.GLTFLoader;
      const loader = new GLTFLoader();
      loader.load(data.mesh, (gltf) => {{
        scene.add(gltf.scene);
        gltf.scene.traverse((child) => {{
          if (child.isMesh) registerPickable(child);
        }});
      }});
    }} else if (ext === 'obj') {{
      const mod = await import('./vendor/OBJLoader.js');
      OBJLoader = mod.OBJLoader;
      const loader = new OBJLoader();
      loader.load(data.mesh, (obj) => {{
        scene.add(obj);
        obj.traverse((child) => {{
          if (child.isMesh) registerPickable(child);
        }});
      }});
    }}
  }} else {{
    await loadPlyMeshes();
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
