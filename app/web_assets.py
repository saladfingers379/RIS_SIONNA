from __future__ import annotations

import urllib.request
from pathlib import Path


def ensure_three_vendor(root_dir: Path) -> None:
    vendor_dir = root_dir / "vendor"
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
