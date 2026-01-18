import * as THREE from "./vendor/three.module.js";
import { OrbitControls } from "./vendor/OrbitControls.js";
import { GLTFLoader } from "./vendor/GLTFLoader.js";
import { OBJLoader } from "./vendor/OBJLoader.js";
import { PLYLoader } from "./vendor/PLYLoader.js";

const state = {
  runId: null,
  markers: { tx: [0, 0, 0], rx: [0, 0, 0] },
  paths: [],
  heatmap: null,
  manifest: null,
  selectedPath: null,
  sceneSourceRunId: null,
  sceneOverride: null,
  runInfo: null,
  configs: [],
};

const ui = {
  runSelect: document.getElementById("runSelect"),
  refreshRuns: document.getElementById("refreshRuns"),
  topDown: document.getElementById("topDown"),
  snapshot: document.getElementById("snapshot"),
  baseConfig: document.getElementById("baseConfig"),
  sceneRunSelect: document.getElementById("sceneRunSelect"),
  runStats: document.getElementById("runStats"),
  txX: document.getElementById("txX"),
  txY: document.getElementById("txY"),
  txZ: document.getElementById("txZ"),
  rxX: document.getElementById("rxX"),
  rxY: document.getElementById("rxY"),
  rxZ: document.getElementById("rxZ"),
  applyMarkers: document.getElementById("applyMarkers"),
  dragMarkers: document.getElementById("dragMarkers"),
  qualityPreset: document.getElementById("qualityPreset"),
  jobButtons: document.querySelectorAll(".job-buttons button"),
  jobList: document.getElementById("jobList"),
  radioMapEnabled: document.getElementById("radioMapEnabled"),
  radioMapAuto: document.getElementById("radioMapAuto"),
  radioMapPadding: document.getElementById("radioMapPadding"),
  radioMapCellX: document.getElementById("radioMapCellX"),
  radioMapCellY: document.getElementById("radioMapCellY"),
  radioMapSizeX: document.getElementById("radioMapSizeX"),
  radioMapSizeY: document.getElementById("radioMapSizeY"),
  radioMapCenterX: document.getElementById("radioMapCenterX"),
  radioMapCenterY: document.getElementById("radioMapCenterY"),
  radioMapCenterZ: document.getElementById("radioMapCenterZ"),
  viewerMeta: document.getElementById("viewerMeta"),
  toggleGeometry: document.getElementById("toggleGeometry"),
  toggleMarkers: document.getElementById("toggleMarkers"),
  toggleRays: document.getElementById("toggleRays"),
  toggleHeatmap: document.getElementById("toggleHeatmap"),
  toggleGuides: document.getElementById("toggleGuides"),
  meshRotation: document.getElementById("meshRotation"),
  meshRotationLabel: document.getElementById("meshRotationLabel"),
  heatmapRotation: document.getElementById("heatmapRotation"),
  heatmapRotationLabel: document.getElementById("heatmapRotationLabel"),
  heatmapScale: document.getElementById("heatmapScale"),
  heatmapScaleMin: document.getElementById("heatmapScaleMin"),
  heatmapScaleMax: document.getElementById("heatmapScaleMax"),
  heatmapMin: document.getElementById("heatmapMin"),
  heatmapMax: document.getElementById("heatmapMax"),
  heatmapMinLabel: document.getElementById("heatmapMinLabel"),
  heatmapMaxLabel: document.getElementById("heatmapMaxLabel"),
  heatmapMinInput: document.getElementById("heatmapMinInput"),
  heatmapMaxInput: document.getElementById("heatmapMaxInput"),
  pathTypeFilter: document.getElementById("pathTypeFilter"),
  pathOrderFilter: document.getElementById("pathOrderFilter"),
  pathTableBody: document.getElementById("pathTableBody"),
  pathStats: document.getElementById("pathStats"),
  randomizeMarkers: document.getElementById("randomizeMarkers"),
};

let renderer;
let scene;
let camera;
let controls;
let geometryGroup;
let markerGroup;
let rayGroup;
let heatmapGroup;
let alignmentGroup;
let highlightLine;
let dragging = null;
let debugHeatmapMesh = null;

function refreshHeatmap() {
  heatmapGroup.clear();
  addHeatmap();
}

function initViewer() {
  const container = document.getElementById("viewerCanvas");
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf3f4f6);
  camera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 5000);
  camera.position.set(80, 80, 80);
  camera.up.set(0, 0, 1);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);
  renderer.domElement.addEventListener("contextmenu", (event) => event.preventDefault());

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enablePan = true;
  controls.screenSpacePanning = true;
  controls.panSpeed = 0.9;
  controls.keyPanSpeed = 18.0;
  controls.listenToKeyEvents(window);

  const hemi = new THREE.HemisphereLight(0xffffff, 0x64748b, 0.8);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(50, 120, 60);
  scene.add(dir);

  geometryGroup = new THREE.Group();
  markerGroup = new THREE.Group();
  rayGroup = new THREE.Group();
  heatmapGroup = new THREE.Group();
  alignmentGroup = new THREE.Group();
  alignmentGroup.visible = false;
  scene.add(geometryGroup, markerGroup, rayGroup, heatmapGroup, alignmentGroup);

  window.__simDebug = {
    scene,
    camera,
    controls,
    geometryGroup,
    markerGroup,
    rayGroup,
    heatmapGroup,
    getState() {
      return {
        heatmap: state.heatmap,
        markers: state.markers,
        runId: state.runId,
      };
    },
    get heatmapMesh() {
      return debugHeatmapMesh;
    },
    getBounds() {
      const bboxOf = (obj) => {
        const box = new THREE.Box3().setFromObject(obj);
        if (box.isEmpty()) return null;
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        return {
          min: [box.min.x, box.min.y, box.min.z],
          max: [box.max.x, box.max.y, box.max.z],
          size: [size.x, size.y, size.z],
          center: [center.x, center.y, center.z],
        };
      };
      return {
        geometry: bboxOf(geometryGroup),
        heatmap: debugHeatmapMesh ? bboxOf(debugHeatmapMesh) : null,
      };
    },
  };

  renderer.domElement.addEventListener("mousedown", onMouseDown);
  renderer.domElement.addEventListener("mousemove", onMouseMove);
  renderer.domElement.addEventListener("mouseup", () => (dragging = null));

  window.addEventListener("resize", () => {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  });

  animate();
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

function setMeta(text) {
  ui.viewerMeta.textContent = text;
}

function readNumber(input) {
  const val = parseFloat(input.value);
  return Number.isFinite(val) ? val : null;
}

function setInputValue(input, value) {
  if (value === undefined || value === null) {
    input.value = "";
  } else {
    input.value = value;
  }
}

function isTextInput(target) {
  if (!target) return false;
  const tag = target.tagName ? target.tagName.toLowerCase() : "";
  return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
}

function nudgeCamera(direction, boost) {
  const distance = controls.target.distanceTo(camera.position);
  const step = Math.max(1, distance * 0.02) * (boost ? 2 : 1);
  const up = new THREE.Vector3(0, 0, 1);
  const forward = new THREE.Vector3();
  camera.getWorldDirection(forward);
  forward.z = 0;
  if (forward.lengthSq() < 1e-6) {
    forward.set(0, 1, 0);
  }
  forward.normalize();
  const right = new THREE.Vector3().crossVectors(forward, up).normalize();
  const delta = new THREE.Vector3();
  if (direction === "forward") delta.copy(forward).multiplyScalar(step);
  if (direction === "back") delta.copy(forward).multiplyScalar(-step);
  if (direction === "left") delta.copy(right).multiplyScalar(-step);
  if (direction === "right") delta.copy(right).multiplyScalar(step);
  if (direction === "up") delta.copy(up).multiplyScalar(step);
  if (direction === "down") delta.copy(up).multiplyScalar(-step);
  camera.position.add(delta);
  controls.target.add(delta);
}

function bindKeyboardNavigation() {
  window.addEventListener("keydown", (event) => {
    if (event.repeat || isTextInput(event.target)) return;
    const boost = event.shiftKey;
    switch (event.code) {
      case "KeyW":
        nudgeCamera("forward", boost);
        break;
      case "KeyS":
        nudgeCamera("back", boost);
        break;
      case "KeyA":
        nudgeCamera("left", boost);
        break;
      case "KeyD":
        nudgeCamera("right", boost);
        break;
      case "KeyQ":
        nudgeCamera("down", boost);
        break;
      case "KeyE":
        nudgeCamera("up", boost);
        break;
      default:
        return;
    }
    event.preventDefault();
  });
}

function getSelectedConfig() {
  if (!state.configs.length) {
    return null;
  }
  const match = state.configs.find((cfg) => cfg.path === ui.baseConfig.value);
  return match || state.configs[0];
}

function applyRadioMapDefaults(config) {
  const radio = (config && config.data && config.data.radio_map) || {};
  ui.radioMapEnabled.checked = Boolean(radio.enabled);
  ui.radioMapAuto.checked = Boolean(radio.auto_size);
  setInputValue(ui.radioMapPadding, radio.auto_padding);
  if (Array.isArray(radio.cell_size)) {
    setInputValue(ui.radioMapCellX, radio.cell_size[0]);
    setInputValue(ui.radioMapCellY, radio.cell_size[1]);
  } else {
    setInputValue(ui.radioMapCellX, null);
    setInputValue(ui.radioMapCellY, null);
  }
  if (Array.isArray(radio.size)) {
    setInputValue(ui.radioMapSizeX, radio.size[0]);
    setInputValue(ui.radioMapSizeY, radio.size[1]);
  } else {
    setInputValue(ui.radioMapSizeX, null);
    setInputValue(ui.radioMapSizeY, null);
  }
  if (Array.isArray(radio.center)) {
    setInputValue(ui.radioMapCenterX, radio.center[0]);
    setInputValue(ui.radioMapCenterY, radio.center[1]);
    setInputValue(ui.radioMapCenterZ, radio.center[2]);
  } else {
    setInputValue(ui.radioMapCenterX, null);
    setInputValue(ui.radioMapCenterY, null);
    setInputValue(ui.radioMapCenterZ, null);
  }
}

async function fetchConfigs() {
  const res = await fetch("/api/configs");
  if (!res.ok) {
    return;
  }
  const data = await res.json();
  state.configs = data.configs || [];
  ui.baseConfig.innerHTML = "";
  state.configs.forEach((cfg) => {
    const opt = document.createElement("option");
    opt.value = cfg.path;
    opt.textContent = cfg.name;
    ui.baseConfig.appendChild(opt);
  });
  const defaultCfg = state.configs.find((cfg) => cfg.name === "default.yaml");
  if (defaultCfg) {
    ui.baseConfig.value = defaultCfg.path;
  }
  applyRadioMapDefaults(getSelectedConfig());
}

async function fetchRuns() {
  const res = await fetch("/api/runs");
  const data = await res.json();
  const previous = state.runId;
  ui.runSelect.innerHTML = "";
  ui.sceneRunSelect.innerHTML = "";
  data.runs.forEach((run) => {
    const opt = document.createElement("option");
    opt.value = run.run_id;
    opt.textContent = run.run_id;
    ui.runSelect.appendChild(opt);

    const sceneOpt = document.createElement("option");
    sceneOpt.value = run.run_id;
    sceneOpt.textContent = run.run_id;
    ui.sceneRunSelect.appendChild(sceneOpt);
  });
  if (data.runs.length > 0) {
    state.runId = data.runs.find((r) => r.run_id === previous)?.run_id || data.runs[0].run_id;
    ui.runSelect.value = state.runId;
    state.sceneSourceRunId = state.sceneSourceRunId || state.runId;
    ui.sceneRunSelect.value = state.sceneSourceRunId;
    await loadRun(state.runId);
    const sceneDetails = await fetchRunDetails(state.sceneSourceRunId);
    state.sceneOverride = sceneDetails && sceneDetails.config ? sceneDetails.config.scene : null;
  }
}

async function fetchRunDetails(runId) {
  const res = await fetch(`/api/run/${runId}`);
  if (!res.ok) {
    return null;
  }
  return await res.json();
}

async function fetchProgress(runId) {
  const res = await fetch(`/api/progress/${runId}`);
  if (!res.ok) {
    return null;
  }
  return await res.json();
}

async function loadRun(runId) {
  state.runId = runId;
  setMeta(`Loading ${runId}...`);
  try {
    const [markers, paths, manifest, heatmap, runInfo] = await Promise.all([
      fetch(`/runs/${runId}/viewer/markers.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/runs/${runId}/viewer/paths.json`).then((r) => (r.ok ? r.json() : [])),
      fetch(`/runs/${runId}/viewer/scene_manifest.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/runs/${runId}/viewer/heatmap.json`).then((r) => (r.ok ? r.json() : null)),
      fetchRunDetails(runId),
    ]);
    state.markers = markers || state.markers;
    state.paths = paths || [];
    state.manifest = manifest;
    state.heatmap = heatmap;
    state.runInfo = runInfo;
    updateInputs();
    renderRunStats();
    updateHeatmapControls();
    rebuildScene();
    renderPathTable();
    renderPathStats();
    setMeta(`${runId} · ${state.paths.length} paths`);
  } catch (err) {
    setMeta(`Failed to load ${runId}`);
  }
}

function updateInputs() {
  ui.txX.value = state.markers.tx[0];
  ui.txY.value = state.markers.tx[1];
  ui.txZ.value = state.markers.tx[2];
  ui.rxX.value = state.markers.rx[0];
  ui.rxY.value = state.markers.rx[1];
  ui.rxZ.value = state.markers.rx[2];
}

function renderRunStats() {
  const info = state.runInfo || {};
  const summary = info.summary || {};
  const metrics = summary.metrics || {};
  const sim = (info.config && info.config.simulation) || {};
  const scene = (info.config && info.config.scene) || {};
  const sceneLabel = scene.type === "builtin"
    ? `builtin:${scene.builtin || "unknown"}`
    : scene.type === "file"
      ? `file:${(scene.file || "").split("/").pop() || "unknown"}`
      : scene.type || "unknown";
  const freqHz = sim.frequency_hz || null;
  const freqGHz = freqHz ? (freqHz / 1e9).toFixed(2) : "n/a";
  const numPaths = metrics.num_valid_paths ?? "n/a";
  const maxDepth = sim.max_depth ?? "n/a";
  const rxPower = metrics.rx_power_dbm_estimate !== undefined ? metrics.rx_power_dbm_estimate.toFixed(2) : "n/a";
  const pathGain = metrics.total_path_gain_db !== undefined ? metrics.total_path_gain_db.toFixed(2) : "n/a";
  ui.runStats.innerHTML = `
    <div><strong>Frequency:</strong> ${freqGHz} GHz</div>
    <div><strong>Max depth:</strong> ${maxDepth}</div>
    <div><strong>Valid paths:</strong> ${numPaths}</div>
    <div><strong>Total path gain:</strong> ${pathGain} dB</div>
    <div><strong>Rx power (est.):</strong> ${rxPower} dBm</div>
    <div><strong>Scene:</strong> ${sceneLabel}</div>
  `;
}

function updateHeatmapControls() {
  if (!state.heatmap || !state.heatmap.values) {
    updateHeatmapScaleVisibility(false);
    return;
  }
  const values = state.heatmap.values.flat();
  const min = Math.min(...values);
  const max = Math.max(...values);
  const minVal = Math.floor(min);
  const maxVal = Math.ceil(max);
  ui.heatmapMin.min = String(minVal);
  ui.heatmapMin.max = String(maxVal);
  ui.heatmapMax.min = String(minVal);
  ui.heatmapMax.max = String(maxVal);
  ui.heatmapMin.value = String(minVal);
  ui.heatmapMax.value = String(maxVal);
  ui.heatmapMinLabel.textContent = `${minVal}`;
  ui.heatmapMaxLabel.textContent = `${maxVal}`;
  ui.heatmapMinInput.value = String(minVal);
  ui.heatmapMaxInput.value = String(maxVal);
  updateHeatmapScaleLabels();
  updateHeatmapScaleVisibility();
}

function updateHeatmapScaleLabels() {
  if (!ui.heatmapScaleMin || !ui.heatmapScaleMax) return;
  ui.heatmapScaleMin.textContent = ui.heatmapMin.value || "--";
  ui.heatmapScaleMax.textContent = ui.heatmapMax.value || "--";
}

function updateHeatmapScaleVisibility(force) {
  if (!ui.heatmapScale) return;
  const visible = force !== undefined
    ? force
    : Boolean(ui.toggleHeatmap.checked && state.heatmap && state.heatmap.values);
  ui.heatmapScale.classList.toggle("is-hidden", !visible);
}

function rebuildScene() {
  geometryGroup.clear();
  markerGroup.clear();
  rayGroup.clear();
  heatmapGroup.clear();
  alignmentGroup.clear();
  highlightLine = null;

  addProxyGeometry();
  loadMeshes();
  addMarkers();
  addAlignmentMarkers();
  alignmentGroup.visible = ui.toggleGuides.checked;
  addRays();
  addHeatmap();
  fitCamera();
}

function addProxyGeometry() {
  if (!state.manifest || !state.manifest.proxy) {
    return;
  }
  const proxy = state.manifest.proxy;
  if (proxy.ground) {
    const size = proxy.ground.size || [200, 200];
    const elev = proxy.ground.elevation || 0;
    const geo = new THREE.PlaneGeometry(size[0], size[1]);
    const mat = new THREE.MeshStandardMaterial({ color: 0xdbe2e9, side: THREE.DoubleSide });
    const ground = new THREE.Mesh(geo, mat);
    ground.position.set(0, 0, elev);
    geometryGroup.add(ground);
  }
  (proxy.boxes || []).forEach((b, idx) => {
    const size = b.size || [10, 10, 10];
    const center = b.center || [0, 0, size[2] / 2];
    const geo = new THREE.BoxGeometry(size[0], size[1], size[2]);
    const palette = [0xf97316, 0x38bdf8, 0x94a3b8, 0xfacc15];
    const mat = new THREE.MeshStandardMaterial({ color: palette[idx % palette.length], opacity: 0.85, transparent: true });
    const box = new THREE.Mesh(geo, mat);
    box.position.set(center[0], center[1], center[2]);
    geometryGroup.add(box);
  });
}

async function loadMeshes() {
  if (!state.manifest) {
    return;
  }
  if (state.manifest.mesh) {
    const ext = state.manifest.mesh.split(".").pop().toLowerCase();
    if (ext === "glb" || ext === "gltf") {
      const loader = new GLTFLoader();
      loader.load(`/runs/${state.runId}/viewer/${state.manifest.mesh}`, (gltf) => {
        geometryGroup.add(gltf.scene);
        refreshHeatmap();
      });
    } else if (ext === "obj") {
      const loader = new OBJLoader();
      loader.load(`/runs/${state.runId}/viewer/${state.manifest.mesh}`, (obj) => {
        geometryGroup.add(obj);
        refreshHeatmap();
      });
    }
  }
  if (state.manifest.mesh_files && state.manifest.mesh_files.length) {
    const loader = new PLYLoader();
    // Get rotation from UI slider (degrees); default stays 0 to match ray paths.
    const meshRotationDeg = parseFloat(ui.meshRotation?.value || 0);
    state.manifest.mesh_files.forEach((name) => {
      loader.load(`/runs/${state.runId}/viewer/${name}`, (geom) => {
        // Apply Z-axis rotation to align mesh with radio map coordinates
        geom.rotateZ((meshRotationDeg * Math.PI) / 180);
        geom.computeVertexNormals();
        const mat = new THREE.MeshStandardMaterial({ color: 0x9aa8b1, opacity: 0.6, transparent: true });
        const mesh = new THREE.Mesh(geom, mat);
        geometryGroup.add(mesh);
        refreshHeatmap();
      });
    });
  }
}

function addMarkers() {
  const txMat = new THREE.MeshStandardMaterial({ color: 0xdc2626, emissive: 0xdc2626, emissiveIntensity: 0.4 });
  const rxMat = new THREE.MeshStandardMaterial({ color: 0x2563eb, emissive: 0x2563eb, emissiveIntensity: 0.4 });
  const geo = new THREE.SphereGeometry(2.2, 16, 16);
  const tx = new THREE.Mesh(geo, txMat);
  const rx = new THREE.Mesh(geo, rxMat);
  tx.name = "tx";
  rx.name = "rx";
  tx.position.set(...state.markers.tx);
  rx.position.set(...state.markers.rx);
  markerGroup.add(tx, rx);
}

function addAlignmentMarkers() {
  // Reference height for markers (slightly above ground)
  const markerZ = 3;
  const axisLength = 100;
  const markerSize = 5;

  // Create axis lines from origin
  // X-axis = RED, Y-axis = GREEN
  const xAxisMat = new THREE.LineBasicMaterial({ color: 0xff0000, linewidth: 3 });
  const yAxisMat = new THREE.LineBasicMaterial({ color: 0x00ff00, linewidth: 3 });

  const xAxisGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, markerZ),
    new THREE.Vector3(axisLength, 0, markerZ)
  ]);
  const yAxisGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, markerZ),
    new THREE.Vector3(0, axisLength, markerZ)
  ]);

  const xAxis = new THREE.Line(xAxisGeo, xAxisMat);
  const yAxis = new THREE.Line(yAxisGeo, yAxisMat);
  alignmentGroup.add(xAxis, yAxis);

  // Add spheres at key positions for visual reference
  const sphereGeo = new THREE.SphereGeometry(markerSize, 12, 12);

  // Origin marker (white)
  const originMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.3 });
  const origin = new THREE.Mesh(sphereGeo, originMat);
  origin.position.set(0, 0, markerZ);
  alignmentGroup.add(origin);

  // +X marker (yellow) at (100, 0)
  const xMarkerMat = new THREE.MeshStandardMaterial({ color: 0xffff00, emissive: 0xffff00, emissiveIntensity: 0.3 });
  const xMarker = new THREE.Mesh(sphereGeo, xMarkerMat);
  xMarker.position.set(axisLength, 0, markerZ);
  alignmentGroup.add(xMarker);

  // +Y marker (magenta) at (0, 100)
  const yMarkerMat = new THREE.MeshStandardMaterial({ color: 0xff00ff, emissive: 0xff00ff, emissiveIntensity: 0.3 });
  const yMarker = new THREE.Mesh(sphereGeo, yMarkerMat);
  yMarker.position.set(0, axisLength, markerZ);
  alignmentGroup.add(yMarker);

  // Diagonal marker (cyan) at (100, 100) - helps see rotation
  const diagMat = new THREE.MeshStandardMaterial({ color: 0x00ffff, emissive: 0x00ffff, emissiveIntensity: 0.3 });
  const diagMarker = new THREE.Mesh(sphereGeo, diagMat);
  diagMarker.position.set(axisLength, axisLength, markerZ);
  alignmentGroup.add(diagMarker);

  // Add corner markers for heatmap bounds if available
  if (state.heatmap && state.heatmap.cell_centers) {
    const centers = state.heatmap.cell_centers;
    const cellSize = state.heatmap.cell_size || [0, 0];
    const xs = centers.flatMap((row) => row.map((c) => c[0]));
    const ys = centers.flatMap((row) => row.map((c) => c[1]));
    const xMin = Math.min(...xs) - cellSize[0] * 0.5;
    const xMax = Math.max(...xs) + cellSize[0] * 0.5;
    const yMin = Math.min(...ys) - cellSize[1] * 0.5;
    const yMax = Math.max(...ys) + cellSize[1] * 0.5;
    const hmZ = markerZ + 1;

    // Corner markers (orange = heatmap corners in WORLD SPACE - not rotated)
    const cornerMat = new THREE.MeshStandardMaterial({ color: 0xff8800, emissive: 0xff8800, emissiveIntensity: 0.4 });
    const cornerGeo = new THREE.SphereGeometry(markerSize * 0.7, 8, 8);

    const corners = [
      [xMin, yMin, hmZ], // bottom-left (should match texture bottom-left if aligned)
      [xMax, yMin, hmZ], // bottom-right
      [xMin, yMax, hmZ], // top-left
      [xMax, yMax, hmZ], // top-right
    ];

    corners.forEach(([x, y, z], i) => {
      const marker = new THREE.Mesh(cornerGeo, cornerMat);
      marker.position.set(x, y, z);
      alignmentGroup.add(marker);
    });

    // Add text label hints at corners using small colored spheres
    // Bottom-left gets a distinctive marker (lime green)
    const blMat = new THREE.MeshStandardMaterial({ color: 0x88ff00, emissive: 0x88ff00, emissiveIntensity: 0.5 });
    const blMarker = new THREE.Mesh(new THREE.SphereGeometry(markerSize * 1.2, 12, 12), blMat);
    blMarker.position.set(xMin, yMin, hmZ + 3);
    alignmentGroup.add(blMarker);
  }
}

function pointInsideBox(point, box) {
  const size = box.size || [0, 0, 0];
  const center = box.center || [0, 0, 0];
  const min = [center[0] - size[0] / 2, center[1] - size[1] / 2, center[2] - size[2] / 2];
  const max = [center[0] + size[0] / 2, center[1] + size[1] / 2, center[2] + size[2] / 2];
  return (
    point[0] >= min[0] && point[0] <= max[0] &&
    point[1] >= min[1] && point[1] <= max[1] &&
    point[2] >= min[2] && point[2] <= max[2]
  );
}

function getSceneBounds2D() {
  if (state.heatmap && state.heatmap.cell_centers) {
    const centers = state.heatmap.cell_centers;
    const xs = centers.flatMap((row) => row.map((c) => c[0]));
    const ys = centers.flatMap((row) => row.map((c) => c[1]));
    if (xs.length && ys.length) {
      return {
        xMin: Math.min(...xs),
        xMax: Math.max(...xs),
        yMin: Math.min(...ys),
        yMax: Math.max(...ys),
      };
    }
  }
  const meshBox = new THREE.Box3().setFromObject(geometryGroup);
  if (!meshBox.isEmpty()) {
    return {
      xMin: meshBox.min.x,
      xMax: meshBox.max.x,
      yMin: meshBox.min.y,
      yMax: meshBox.max.y,
    };
  }
  return { xMin: -80, xMax: 80, yMin: -80, yMax: 80 };
}

function findRandomPoint(bounds, z) {
  const proxyBoxes = (state.manifest && state.manifest.proxy && state.manifest.proxy.boxes) || [];
  const tries = 250;
  for (let i = 0; i < tries; i++) {
    const x = bounds.xMin + Math.random() * (bounds.xMax - bounds.xMin);
    const y = bounds.yMin + Math.random() * (bounds.yMax - bounds.yMin);
    const candidate = [x, y, z];
    if (!proxyBoxes.some((box) => pointInsideBox(candidate, box))) {
      return candidate;
    }
  }
  return [
    (bounds.xMin + bounds.xMax) / 2,
    (bounds.yMin + bounds.yMax) / 2,
    z,
  ];
}

function randomizeMarkers() {
  const bounds = getSceneBounds2D();
  const txZ = state.markers.tx[2] ?? 1.5;
  const rxZ = state.markers.rx[2] ?? 1.5;
  state.markers.tx = findRandomPoint(bounds, txZ);
  state.markers.rx = findRandomPoint(bounds, rxZ);
  updateInputs();
  rebuildScene();
}

function addRays() {
  if (!state.paths.length) {
    return;
  }
  const positions = [];
  const color = new THREE.Color(0xf97316);
  const colors = [];
  state.paths.forEach((p) => {
    const pts = p.points || [];
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i];
      const b = pts[i + 1];
      positions.push(...a, ...b);
      colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
    }
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  const mat = new THREE.LineBasicMaterial({ vertexColors: true, opacity: 0.8, transparent: true });
  const lines = new THREE.LineSegments(geo, mat);
  rayGroup.add(lines);
}

function addHeatmap() {
  if (!state.heatmap) {
    return;
  }
  const values = state.heatmap.values || [];
  if (!values.length) {
    return;
  }
  const height = values.length;
  const width = values[0].length || 0;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(width, height);
  let min = Infinity;
  let max = -Infinity;
  values.forEach((row) => row.forEach((v) => { min = Math.min(min, v); max = Math.max(max, v); }));
  const rangeMin = parseFloat(ui.heatmapMin.value || min);
  const rangeMax = parseFloat(ui.heatmapMax.value || max);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const v = values[y][x];  // No vertical flip - flips heatmap like turning over paper
      const t = rangeMax > rangeMin ? (v - rangeMin) / (rangeMax - rangeMin) : 0.0;
      const c = heatmapColor(t);
      const idx = (y * width + x) * 4;
      img.data[idx] = c[0];
      img.data[idx + 1] = c[1];
      img.data[idx + 2] = c[2];
      img.data[idx + 3] = 200;
    }
  }
  ctx.putImageData(img, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.flipY = false;
  const mat = new THREE.MeshBasicMaterial({ map: texture, transparent: true, opacity: 0.7, side: THREE.DoubleSide });

  let widthM = null;
  let heightM = null;
  let center = null;
  let z = 0;

  const centers = state.heatmap.cell_centers || [];
  if (centers.length) {
    const xs = centers.flatMap((row) => row.map((c) => c[0]));
    const ys = centers.flatMap((row) => row.map((c) => c[1]));
    const zs = centers.flatMap((row) => row.map((c) => c[2]));
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);
    const cellSize = state.heatmap.cell_size || [0, 0];
    widthM = xMax - xMin + (cellSize[0] || 0);
    heightM = yMax - yMin + (cellSize[1] || 0);
    center = [
      (xMax + xMin) / 2,
      (yMax + yMin) / 2,
      zs.length ? zs.reduce((a, b) => a + b, 0) / zs.length : 0,
    ];
    z = center[2];
  } else if (state.heatmap.size && state.heatmap.center) {
    widthM = state.heatmap.size[0];
    heightM = state.heatmap.size[1];
    center = state.heatmap.center;
    z = Array.isArray(state.heatmap.center) ? state.heatmap.center[2] || 0 : 0;
  } else if (state.heatmap.grid_shape && state.heatmap.cell_size && state.heatmap.center) {
    widthM = state.heatmap.grid_shape[1] * state.heatmap.cell_size[0];
    heightM = state.heatmap.grid_shape[0] * state.heatmap.cell_size[1];
    center = state.heatmap.center;
    z = Array.isArray(state.heatmap.center) ? state.heatmap.center[2] || 0 : 0;
  }
  if (!widthM || !heightM || !center) {
    const meshBox = new THREE.Box3().setFromObject(geometryGroup);
    if (!meshBox.isEmpty()) {
      const size = meshBox.getSize(new THREE.Vector3());
      const meshCenter = meshBox.getCenter(new THREE.Vector3());
      if (size.x > 0 && size.y > 0) {
        widthM = size.x;
        heightM = size.y;
        center = [meshCenter.x, meshCenter.y, z];
      }
    }
  }

  if (!widthM || !heightM || !center) {
    return;
  }
  const plane = new THREE.PlaneGeometry(widthM, heightM);
  const mesh = new THREE.Mesh(plane, mat);
  mesh.position.set(center[0], center[1], z);

  // Apply rotation from UI slider (degrees to radians, around Z-axis)
  const uiRotationDeg = parseFloat(ui.heatmapRotation?.value || 0);
  const uiRotationRad = (uiRotationDeg * Math.PI) / 180;

  if (state.heatmap.orientation && state.heatmap.orientation.length >= 3) {
    mesh.rotation.set(
      state.heatmap.orientation[0],
      state.heatmap.orientation[1],
      state.heatmap.orientation[2] + uiRotationRad
    );
  } else {
    mesh.rotation.set(0, 0, uiRotationRad);
  }
  heatmapGroup.add(mesh);
  debugHeatmapMesh = mesh;
  heatmapGroup.visible = ui.toggleHeatmap.checked;
}

function heatmapColor(t) {
  const c1 = [34, 197, 94];
  const c2 = [249, 115, 22];
  return [
    Math.round(c1[0] + (c2[0] - c1[0]) * t),
    Math.round(c1[1] + (c2[1] - c1[1]) * t),
    Math.round(c1[2] + (c2[2] - c1[2]) * t),
  ];
}

function fitCamera() {
  const box = new THREE.Box3().setFromObject(scene);
  if (box.isEmpty()) {
    camera.position.set(80, 80, 80);
    controls.target.set(0, 0, 0);
    return;
  }
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z) * 0.9 + 10;
  camera.position.set(center.x + radius, center.y + radius, center.z + radius);
  controls.target.copy(center);
}

function renderPathTable() {
  const maxOrder = parseInt(ui.pathOrderFilter.value || "99", 10);
  const typeFilter = ui.pathTypeFilter.value;
  const types = new Set();
  ui.pathTableBody.innerHTML = "";
  ui.pathTypeFilter.innerHTML = "<option value=\"all\">all</option>";
  state.paths.forEach((p) => {
    types.add(p.type || "unknown");
    if (p.order > maxOrder) return;
    if (typeFilter !== "all" && p.type !== typeFilter) return;
    const row = document.createElement("tr");
    row.innerHTML = `<td>${p.path_id}</td><td>${p.type}</td><td>${p.order}</td><td>${(p.path_length_m || 0).toFixed(1)}</td><td>${(p.power_db || 0).toFixed(1)}</td>`;
    row.addEventListener("click", () => highlightPath(p));
    ui.pathTableBody.appendChild(row);
  });
  types.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    ui.pathTypeFilter.appendChild(opt);
  });
}

function renderPathStats() {
  const stats = {
    los: 0,
    reflection: 0,
    diffraction: 0,
    refraction: 0,
    scattering: 0,
  };
  state.paths.forEach((p) => {
    if (p.order === 0) stats.los += 1;
    (p.interactions || []).forEach((name) => {
      const n = String(name).toLowerCase();
      if (n.includes("diffraction")) stats.diffraction += 1;
      else if (n.includes("refraction")) stats.refraction += 1;
      else if (n.includes("scattering")) stats.scattering += 1;
      else if (n.includes("reflection") || n.includes("specular")) stats.reflection += 1;
    });
  });
  ui.pathStats.innerHTML = `
    <div><strong>LOS paths:</strong> ${stats.los}</div>
    <div><strong>Reflections:</strong> ${stats.reflection}</div>
    <div><strong>Diffractions:</strong> ${stats.diffraction}</div>
    <div><strong>Refractions:</strong> ${stats.refraction}</div>
    <div><strong>Scattering:</strong> ${stats.scattering}</div>
  `;
}

function highlightPath(path) {
  if (highlightLine) {
    rayGroup.remove(highlightLine);
  }
  const pts = path.points || [];
  if (pts.length < 2) {
    return;
  }
  const positions = [];
  for (let i = 0; i < pts.length - 1; i++) {
    positions.push(...pts[i], ...pts[i + 1]);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  const mat = new THREE.LineBasicMaterial({ color: 0xef4444 });
  highlightLine = new THREE.LineSegments(geo, mat);
  rayGroup.add(highlightLine);
  state.selectedPath = path.path_id;
}

function onMouseDown(event) {
  if (!ui.dragMarkers.checked) return;
  const mouse = getMouse(event);
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(markerGroup.children, true);
  if (hits.length) {
    dragging = hits[0].object;
  }
}

function onMouseMove(event) {
  if (!dragging) return;
  const mouse = getMouse(event);
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const point = new THREE.Vector3();
  raycaster.ray.intersectPlane(plane, point);
  dragging.position.copy(point);
  if (dragging.name === "tx") {
    state.markers.tx = [point.x, point.y, point.z];
  } else {
    state.markers.rx = [point.x, point.y, point.z];
  }
  updateInputs();
}

function getMouse(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * 2 - 1,
    y: -((event.clientY - rect.top) / rect.height) * 2 + 1,
  };
}

async function refreshJobs() {
  const res = await fetch("/api/jobs");
  const data = await res.json();
  ui.jobList.innerHTML = "";
  let needsRunRefresh = false;
  let newestCompleted = null;
  const sorted = [...data.jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const recentJobs = sorted.slice(-3).reverse();
  newestCompleted = sorted.slice().reverse().find((job) => job.status === "completed")?.run_id || null;
  const jobItems = [];
  recentJobs.forEach((job) => {
    const item = document.createElement("div");
    const guard = job.vram_guard && job.vram_guard.applied ? " · VRAM guard" : "";
    item.textContent = `${job.run_id} · ${job.kind} · ${job.status}${guard}`;
    ui.jobList.appendChild(item);
    jobItems.push({ job, item });
    if (job.status === "completed") {
      const inSelect = Array.from(ui.runSelect.options).some((opt) => opt.value === job.run_id);
      if (!inSelect) needsRunRefresh = true;
    }
  });
  await Promise.all(
    jobItems.map(async ({ job, item }) => {
      if (job.status !== "running") return;
      const progress = await fetchProgress(job.run_id);
      if (!progress || progress.error) return;
      const step = progress.step_name || "Running";
      const total = progress.total_steps || 0;
      const idx = progress.step_index != null ? progress.step_index + 1 : null;
      const pct = progress.progress != null ? Math.round(progress.progress * 100) : null;
      const pctLabel = pct !== null ? ` · ${pct}%` : "";
      const stepLabel = total && idx ? ` · ${step} (${idx}/${total})` : ` · ${step}`;
      item.textContent = `${job.run_id} · ${job.kind} · ${job.status}${stepLabel}${pctLabel}`;
    })
  );
  if (needsRunRefresh) {
    await fetchRuns();
  }
  if (newestCompleted && ui.runSelect.value !== newestCompleted) {
    ui.runSelect.value = newestCompleted;
    await loadRun(newestCompleted);
  }
}

async function submitJob(kind) {
  const payload = {
    kind,
    preset: ui.qualityPreset.value,
    base_config: ui.baseConfig.value,
  };
  const radio = {};
  radio.enabled = ui.radioMapEnabled.checked;
  radio.auto_size = ui.radioMapAuto.checked;
  const padding = readNumber(ui.radioMapPadding);
  if (padding !== null) {
    radio.auto_padding = padding;
  }
  const cellX = readNumber(ui.radioMapCellX);
  const cellY = readNumber(ui.radioMapCellY);
  if (cellX !== null && cellY !== null) {
    radio.cell_size = [cellX, cellY];
  }
  const sizeX = readNumber(ui.radioMapSizeX);
  const sizeY = readNumber(ui.radioMapSizeY);
  if (sizeX !== null && sizeY !== null) {
    radio.size = [sizeX, sizeY];
  }
  const centerX = readNumber(ui.radioMapCenterX);
  const centerY = readNumber(ui.radioMapCenterY);
  const centerZ = readNumber(ui.radioMapCenterZ);
  if (centerX !== null && centerY !== null && centerZ !== null) {
    radio.center = [centerX, centerY, centerZ];
  }
  if (Object.keys(radio).length) {
    payload.radio_map = radio;
  }
  const scenePayload = JSON.parse(JSON.stringify(state.sceneOverride || {}));
  scenePayload.tx = { position: state.markers.tx };
  scenePayload.rx = { position: state.markers.rx };
  payload.scene = scenePayload;
  setMeta(`Submitting ${kind}...`);
  try {
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      setMeta(`Job error: ${data.error || res.status}`);
    } else {
      setMeta(`Job submitted: ${data.run_id}`);
    }
    await refreshJobs();
  } catch (err) {
    setMeta("Job error: network failure");
  }
}

function bindUI() {
  ui.refreshRuns.addEventListener("click", fetchRuns);
  ui.runSelect.addEventListener("change", () => loadRun(ui.runSelect.value));
  ui.sceneRunSelect.addEventListener("change", async () => {
    state.sceneSourceRunId = ui.sceneRunSelect.value;
    const details = await fetchRunDetails(state.sceneSourceRunId);
    state.sceneOverride = details && details.config ? details.config.scene : null;
  });
  ui.baseConfig.addEventListener("change", () => {
    applyRadioMapDefaults(getSelectedConfig());
  });
  ui.applyMarkers.addEventListener("click", () => {
    state.markers.tx = [parseFloat(ui.txX.value), parseFloat(ui.txY.value), parseFloat(ui.txZ.value)];
    state.markers.rx = [parseFloat(ui.rxX.value), parseFloat(ui.rxY.value), parseFloat(ui.rxZ.value)];
    rebuildScene();
  });
  ui.meshRotation.addEventListener("input", () => {
    ui.meshRotationLabel.textContent = `${ui.meshRotation.value}`;
    rebuildScene();
  });
  ui.jobButtons.forEach((btn) =>
    btn.addEventListener("click", () => submitJob(btn.dataset.kind))
  );
  ui.topDown.addEventListener("click", () => {
    camera.position.set(0, 0, 200);
    controls.target.set(0, 0, 0);
  });
  ui.snapshot.addEventListener("click", () => {
    const link = document.createElement("a");
    link.download = `snapshot-${state.runId || "run"}.png`;
    link.href = renderer.domElement.toDataURL("image/png");
    link.click();
  });
  ui.toggleGeometry.addEventListener("change", () => {
    geometryGroup.visible = ui.toggleGeometry.checked;
  });
  ui.toggleMarkers.addEventListener("change", () => {
    markerGroup.visible = ui.toggleMarkers.checked;
  });
  ui.toggleRays.addEventListener("change", () => {
    rayGroup.visible = ui.toggleRays.checked;
  });
  ui.toggleHeatmap.addEventListener("change", () => {
    heatmapGroup.visible = ui.toggleHeatmap.checked;
    updateHeatmapScaleVisibility();
  });
  ui.toggleGuides.addEventListener("change", () => {
    alignmentGroup.visible = ui.toggleGuides.checked;
  });
  ui.heatmapRotation.addEventListener("input", () => {
    ui.heatmapRotationLabel.textContent = `${ui.heatmapRotation.value}`;
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.heatmapMin.addEventListener("input", () => {
    ui.heatmapMinLabel.textContent = `${ui.heatmapMin.value}`;
    ui.heatmapMinInput.value = ui.heatmapMin.value;
    updateHeatmapScaleLabels();
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.heatmapMax.addEventListener("input", () => {
    ui.heatmapMaxLabel.textContent = `${ui.heatmapMax.value}`;
    ui.heatmapMaxInput.value = ui.heatmapMax.value;
    updateHeatmapScaleLabels();
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.heatmapMinInput.addEventListener("change", () => {
    ui.heatmapMin.value = ui.heatmapMinInput.value;
    ui.heatmapMinLabel.textContent = `${ui.heatmapMin.value}`;
    updateHeatmapScaleLabels();
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.heatmapMaxInput.addEventListener("change", () => {
    ui.heatmapMax.value = ui.heatmapMaxInput.value;
    ui.heatmapMaxLabel.textContent = `${ui.heatmapMax.value}`;
    updateHeatmapScaleLabels();
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.randomizeMarkers.addEventListener("click", randomizeMarkers);
  ui.pathTypeFilter.addEventListener("change", renderPathTable);
  ui.pathOrderFilter.addEventListener("input", renderPathTable);
}

initViewer();
bindKeyboardNavigation();
bindUI();
fetchConfigs().then(fetchRuns);
setInterval(refreshJobs, 3000);
