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
  viewerMeta: document.getElementById("viewerMeta"),
  toggleGeometry: document.getElementById("toggleGeometry"),
  toggleMarkers: document.getElementById("toggleMarkers"),
  toggleRays: document.getElementById("toggleRays"),
  toggleHeatmap: document.getElementById("toggleHeatmap"),
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
};

let renderer;
let scene;
let camera;
let controls;
let geometryGroup;
let markerGroup;
let rayGroup;
let heatmapGroup;
let highlightLine;
let dragging = null;

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

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  const hemi = new THREE.HemisphereLight(0xffffff, 0x64748b, 0.8);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(50, 120, 60);
  scene.add(dir);

  geometryGroup = new THREE.Group();
  markerGroup = new THREE.Group();
  rayGroup = new THREE.Group();
  heatmapGroup = new THREE.Group();
  scene.add(geometryGroup, markerGroup, rayGroup, heatmapGroup);

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
}

function rebuildScene() {
  geometryGroup.clear();
  markerGroup.clear();
  rayGroup.clear();
  heatmapGroup.clear();
  highlightLine = null;

  addProxyGeometry();
  loadMeshes();
  addMarkers();
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
    state.manifest.mesh_files.forEach((name) => {
      loader.load(`/runs/${state.runId}/viewer/${name}`, (geom) => {
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
      const v = values[y][x];
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
    widthM = Math.max(...xs) - Math.min(...xs);
    heightM = Math.max(...ys) - Math.min(...ys);
    center = [
      (Math.max(...xs) + Math.min(...xs)) / 2,
      (Math.max(...ys) + Math.min(...ys)) / 2,
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

  if (!widthM || !heightM || !center) {
    return;
  }
  const plane = new THREE.PlaneGeometry(widthM, heightM);
  const mesh = new THREE.Mesh(plane, mat);
  mesh.position.set(center[0], center[1], z);
  if (state.heatmap.orientation && state.heatmap.orientation.length >= 3) {
    mesh.rotation.set(
      state.heatmap.orientation[0],
      state.heatmap.orientation[1],
      state.heatmap.orientation[2]
    );
  }
  heatmapGroup.add(mesh);
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
  recentJobs.forEach((job) => {
    const item = document.createElement("div");
    const guard = job.vram_guard && job.vram_guard.applied ? " · VRAM guard" : "";
    item.textContent = `${job.run_id} · ${job.kind} · ${job.status}${guard}`;
    ui.jobList.appendChild(item);
    if (job.status === "completed") {
      const inSelect = Array.from(ui.runSelect.options).some((opt) => opt.value === job.run_id);
      if (!inSelect) needsRunRefresh = true;
    }
  });
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
  ui.applyMarkers.addEventListener("click", () => {
    state.markers.tx = [parseFloat(ui.txX.value), parseFloat(ui.txY.value), parseFloat(ui.txZ.value)];
    state.markers.rx = [parseFloat(ui.rxX.value), parseFloat(ui.rxY.value), parseFloat(ui.rxZ.value)];
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
  });
  ui.heatmapMin.addEventListener("input", () => {
    ui.heatmapMinLabel.textContent = `${ui.heatmapMin.value}`;
    ui.heatmapMinInput.value = ui.heatmapMin.value;
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.heatmapMax.addEventListener("input", () => {
    ui.heatmapMaxLabel.textContent = `${ui.heatmapMax.value}`;
    ui.heatmapMaxInput.value = ui.heatmapMax.value;
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.heatmapMinInput.addEventListener("change", () => {
    ui.heatmapMin.value = ui.heatmapMinInput.value;
    ui.heatmapMinLabel.textContent = `${ui.heatmapMin.value}`;
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.heatmapMaxInput.addEventListener("change", () => {
    ui.heatmapMax.value = ui.heatmapMaxInput.value;
    ui.heatmapMaxLabel.textContent = `${ui.heatmapMax.value}`;
    heatmapGroup.clear();
    addHeatmap();
  });
  ui.pathTypeFilter.addEventListener("change", renderPathTable);
  ui.pathOrderFilter.addEventListener("input", renderPathTable);
}

initViewer();
bindUI();
fetchRuns();
setInterval(refreshJobs, 3000);
