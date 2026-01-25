import * as THREE from "./vendor/three.module.js";
import { OrbitControls } from "./vendor/OrbitControls.js";
import { GLTFLoader } from "./vendor/GLTFLoader.js";
import { OBJLoader } from "./vendor/OBJLoader.js";
import { PLYLoader } from "./vendor/PLYLoader.js";

window.onerror = function (msg, url, line) {
  const div = document.createElement("div");
  div.style.cssText = "position:fixed;top:0;left:0;right:0;background:red;color:white;z-index:9999;padding:10px;font-family:monospace;font-size:12px;white-space:pre-wrap;";
  div.textContent = `JS Error: ${msg}\nLine: ${line}\nURL: ${url}`;
  document.body.appendChild(div);
  console.error("Global error:", msg, url, line);
};

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
  ris: {
    jobs: [],
    runs: [],
    activeRunId: null,
    activeJobId: null,
  },
};

const ui = {
  runSelect: document.getElementById("runSelect"),
  refreshRuns: document.getElementById("refreshRuns"),
  topDown: document.getElementById("topDown"),
  snapshot: document.getElementById("snapshot"),
  mainTabStrip: document.getElementById("mainTabStrip"),
  runProfile: document.getElementById("runProfile"),
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
  runSim: document.getElementById("runSim"),
  jobList: document.getElementById("jobList"),
  risConfigSource: document.getElementById("risConfigSource"),
  risConfigPath: document.getElementById("risConfigPath"),
  risConfigPreview: document.getElementById("risConfigPreview"),
  risFreqHz: document.getElementById("risFreqHz"),
  risTxAngle: document.getElementById("risTxAngle"),
  risTxDistance: document.getElementById("risTxDistance"),
  risRxDistance: document.getElementById("risRxDistance"),
  risTxGain: document.getElementById("risTxGain"),
  risRxGain: document.getElementById("risRxGain"),
  risTxPower: document.getElementById("risTxPower"),
  risReflectionCoeff: document.getElementById("risReflectionCoeff"),
  risGeomNx: document.getElementById("risGeomNx"),
  risGeomNy: document.getElementById("risGeomNy"),
  risGeomDx: document.getElementById("risGeomDx"),
  risGeomDy: document.getElementById("risGeomDy"),
  risOriginX: document.getElementById("risOriginX"),
  risOriginY: document.getElementById("risOriginY"),
  risOriginZ: document.getElementById("risOriginZ"),
  risNormalX: document.getElementById("risNormalX"),
  risNormalY: document.getElementById("risNormalY"),
  risNormalZ: document.getElementById("risNormalZ"),
  risAxisX: document.getElementById("risAxisX"),
  risAxisY: document.getElementById("risAxisY"),
  risAxisZ: document.getElementById("risAxisZ"),
  risElementSize: document.getElementById("risElementSize"),
  risControlMode: document.getElementById("risControlMode"),
  risSteerAz: document.getElementById("risSteerAz"),
  risSteerEl: document.getElementById("risSteerEl"),
  risPhaseOffsetDeg: document.getElementById("risPhaseOffsetDeg"),
  risUniformPhaseDeg: document.getElementById("risUniformPhaseDeg"),
  risFocusX: document.getElementById("risFocusX"),
  risFocusY: document.getElementById("risFocusY"),
  risFocusZ: document.getElementById("risFocusZ"),
  risQuantBits: document.getElementById("risQuantBits"),
  risSweepStart: document.getElementById("risSweepStart"),
  risSweepStop: document.getElementById("risSweepStop"),
  risSweepStep: document.getElementById("risSweepStep"),
  risNormalization: document.getElementById("risNormalization"),
  risAction: document.getElementById("risAction"),
  risMode: document.getElementById("risMode"),
  risReferenceField: document.getElementById("risReferenceField"),
  risReferencePath: document.getElementById("risReferencePath"),
  risStart: document.getElementById("risStart"),
  risRefresh: document.getElementById("risRefresh"),
  risJobStatus: document.getElementById("risJobStatus"),
  risProgress: document.getElementById("risProgress"),
  risLog: document.getElementById("risLog"),
  risJobList: document.getElementById("risJobList"),
  risRunSelect: document.getElementById("risRunSelect"),
  risLoadResults: document.getElementById("risLoadResults"),
  risResultStatus: document.getElementById("risResultStatus"),
  risMetrics: document.getElementById("risMetrics"),
  risPlots: document.getElementById("risPlots"),
  risPlotTabs: document.getElementById("risPlotTabs"),
  risPlotImage: document.getElementById("risPlotImage"),
  risPlotCaption: document.getElementById("risPlotCaption"),
  risPreviewSvg: document.getElementById("risPreviewSvg"),
  risPreviewTx: document.getElementById("risPreviewTx"),
  risPreviewRx: document.getElementById("risPreviewRx"),
  risPreviewPanel: document.getElementById("risPreviewPanel"),
  risPreviewTxRay: document.getElementById("risPreviewTxRay"),
  risPreviewRxRay: document.getElementById("risPreviewRxRay"),
  risPreviewMeta: document.getElementById("risPreviewMeta"),
  radioMapAuto: document.getElementById("radioMapAuto"),
  radioMapPadding: document.getElementById("radioMapPadding"),
  radioMapCellX: document.getElementById("radioMapCellX"),
  radioMapCellY: document.getElementById("radioMapCellY"),
  radioMapSizeX: document.getElementById("radioMapSizeX"),
  radioMapSizeY: document.getElementById("radioMapSizeY"),
  radioMapCenterX: document.getElementById("radioMapCenterX"),
  radioMapCenterY: document.getElementById("radioMapCenterY"),
  radioMapCenterZ: document.getElementById("radioMapCenterZ"),
  customOverridesSection: document.getElementById("customOverridesSection"),
  customBackend: document.getElementById("customBackend"),
  customMaxDepth: document.getElementById("customMaxDepth"),
  customSamplesPerSrc: document.getElementById("customSamplesPerSrc"),
  customMaxPathsPerSrc: document.getElementById("customMaxPathsPerSrc"),
  customSamplesPerTx: document.getElementById("customSamplesPerTx"),
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

const RUN_PROFILES = {
  cpu_only: {
    label: "CPU Only",
    configName: "preview.yaml",
    runtime: { force_cpu: true, prefer_gpu: false },
    qualityPreset: "preview",
  },
  gpu_low: {
    label: "GPU Low",
    configName: "default.yaml",
    runtime: { force_cpu: false, prefer_gpu: true },
    qualityPreset: "preview",
  },
  gpu_medium: {
    label: "GPU Medium",
    configName: "default.yaml",
    runtime: { force_cpu: false, prefer_gpu: true },
    qualityPreset: "standard",
  },
  gpu_high: {
    label: "GPU High",
    configName: "high.yaml",
    runtime: { force_cpu: false, prefer_gpu: true },
    qualityPreset: "high",
  },
  custom: {
    label: "Custom",
    configName: "default.yaml",
  },
};

const RIS_PLOT_FILES = [
  { file: "phase_map.png", label: "Phase map" },
  { file: "pattern_cartesian.png", label: "Pattern (cartesian)" },
  { file: "pattern_polar.png", label: "Pattern (polar)" },
  { file: "validation_overlay.png", label: "Validation overlay" },
];
const RIS_PLOT_LABELS = Object.fromEntries(RIS_PLOT_FILES.map((p) => [p.file, p.label]));

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

  ui.toggleGeometry.checked = true;
  ui.toggleGuides.checked = false;

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
  renderer.domElement.addEventListener("mouseup", endDrag);
  renderer.domElement.addEventListener("mouseleave", endDrag);

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

function setMainTab(tabName) {
  if (!ui.mainTabStrip) return;
  const buttons = ui.mainTabStrip.querySelectorAll(".main-tab-button");
  const panels = document.querySelectorAll(".main-tab-panel");
  buttons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.mainTab === tabName);
  });
  panels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.mainTab === tabName);
  });
}

function updateRisActionVisibility() {
  const action = ui.risAction.value;
  const isValidate = action === "validate";
  ui.risReferenceField.style.display = isValidate ? "" : "none";
  ui.risMode.disabled = isValidate;
}

function updateRisConfigSourceVisibility() {
  const source = ui.risConfigSource ? ui.risConfigSource.value : "builder";
  const fileFields = document.querySelectorAll(".ris-config-file");
  fileFields.forEach((el) => {
    el.style.display = source === "file" ? "" : "none";
  });
}

function updateRisControlVisibility() {
  const mode = ui.risControlMode ? ui.risControlMode.value : "steer";
  const steerFields = document.querySelectorAll(".ris-control-steer");
  const uniformFields = document.querySelectorAll(".ris-control-uniform");
  const focusFields = document.querySelectorAll(".ris-control-focus");
  steerFields.forEach((el) => {
    el.style.display = mode === "steer" ? "" : "none";
  });
  uniformFields.forEach((el) => {
    el.style.display = mode === "uniform" ? "" : "none";
  });
  focusFields.forEach((el) => {
    el.style.display = mode === "focus" ? "" : "none";
  });
}

function readOptionalNumber(input, fallback) {
  const val = parseFloat(input && input.value);
  return Number.isFinite(val) ? val : fallback;
}

function readOptionalInt(input, fallback) {
  const val = parseInt(input && input.value, 10);
  return Number.isFinite(val) ? val : fallback;
}

function buildRisConfigFromUI() {
  const config = {
    schema_version: 1,
    geometry: {
      nx: readOptionalInt(ui.risGeomNx, 20),
      ny: readOptionalInt(ui.risGeomNy, 20),
      dx: readOptionalNumber(ui.risGeomDx, 0.0049),
      dy: readOptionalNumber(ui.risGeomDy, 0.0049),
      origin: [
        readOptionalNumber(ui.risOriginX, 0.0),
        readOptionalNumber(ui.risOriginY, 0.0),
        readOptionalNumber(ui.risOriginZ, 0.0),
      ],
      normal: [
        readOptionalNumber(ui.risNormalX, 1.0),
        readOptionalNumber(ui.risNormalY, 0.0),
        readOptionalNumber(ui.risNormalZ, 0.0),
      ],
      x_axis_hint: [
        readOptionalNumber(ui.risAxisX, 0.0),
        readOptionalNumber(ui.risAxisY, 1.0),
        readOptionalNumber(ui.risAxisZ, 0.0),
      ],
    },
    control: {
      mode: ui.risControlMode ? ui.risControlMode.value : "steer",
      params: {},
    },
    quantization: {
      bits: readOptionalInt(ui.risQuantBits, 0),
    },
    pattern_mode: {
      normalization: ui.risNormalization ? ui.risNormalization.value : "peak_0db",
      rx_sweep_deg: {
        start: readOptionalNumber(ui.risSweepStart, -90),
        stop: readOptionalNumber(ui.risSweepStop, 90),
        step: readOptionalNumber(ui.risSweepStep, 2),
      },
    },
    experiment: {
      frequency_hz: readOptionalNumber(ui.risFreqHz, 28000000000),
      tx_angle_deg: readOptionalNumber(ui.risTxAngle, -30),
      tx_incident_angle_deg: readOptionalNumber(ui.risTxAngle, -30),
      tx_distance_m: readOptionalNumber(ui.risTxDistance, 0.4),
      rx_distance_m: readOptionalNumber(ui.risRxDistance, 2.0),
      tx_gain_dbi: readOptionalNumber(ui.risTxGain, 15.0),
      rx_gain_dbi: readOptionalNumber(ui.risRxGain, 22.0),
      tx_power_dbm: readOptionalNumber(ui.risTxPower, 28.0),
      reflection_coeff: readOptionalNumber(ui.risReflectionCoeff, 0.84),
    },
    output: {
      base_dir: "outputs",
    },
  };

  const elementSize = readOptionalNumber(ui.risElementSize, null);
  if (elementSize !== null) {
    config.experiment.element_size_m = elementSize;
  }

  const mode = config.control.mode;
  if (mode === "steer") {
    config.control.params.azimuth_deg = readOptionalNumber(ui.risSteerAz, 0.0);
    config.control.params.elevation_deg = readOptionalNumber(ui.risSteerEl, 0.0);
    config.control.params.phase_offset_deg = readOptionalNumber(ui.risPhaseOffsetDeg, 0.0);
  } else if (mode === "uniform") {
    config.control.params.phase_deg = readOptionalNumber(ui.risUniformPhaseDeg, 0.0);
  } else if (mode === "focus") {
    config.control.params.focal_point = [
      readOptionalNumber(ui.risFocusX, 0.0),
      readOptionalNumber(ui.risFocusY, 0.0),
      readOptionalNumber(ui.risFocusZ, 0.8),
    ];
  }

  if (config.quantization.bits === 0) {
    config.quantization.bits = 0;
  }

  if (!config.pattern_mode.normalization) {
    delete config.pattern_mode.normalization;
  }

  return config;
}

function updateRisConfigPreview() {
  if (!ui.risConfigPreview) return;
  if (ui.risConfigSource && ui.risConfigSource.value === "file") {
    ui.risConfigPreview.textContent = "Using config file path.";
    return;
  }
  const cfg = buildRisConfigFromUI();
  ui.risConfigPreview.textContent = JSON.stringify(cfg, null, 2);
}

function updateRisPreview() {
  if (!ui.risPreviewSvg) return;
  const txDist = readOptionalNumber(ui.risTxDistance, 0.4);
  const rxDist = readOptionalNumber(ui.risRxDistance, 2.0);
  const txAngle = readOptionalNumber(ui.risTxAngle, -30);
  const total = Math.max(0.1, txDist + rxDist);
  const txX = 120 - (txDist / total) * 180;
  const rxX = 480 + (rxDist / total) * 60;
  const clampedTxX = Math.max(60, Math.min(240, txX));
  const clampedRxX = Math.max(360, Math.min(540, rxX));
  if (ui.risPreviewTx) ui.risPreviewTx.setAttribute("cx", String(clampedTxX));
  if (ui.risPreviewRx) ui.risPreviewRx.setAttribute("cx", String(clampedRxX));
  if (ui.risPreviewTxRay) {
    ui.risPreviewTxRay.setAttribute("x1", String(clampedTxX));
    ui.risPreviewTxRay.setAttribute("x2", "300");
  }
  if (ui.risPreviewRxRay) {
    ui.risPreviewRxRay.setAttribute("x1", "300");
    ui.risPreviewRxRay.setAttribute("x2", String(clampedRxX));
  }
  if (ui.risPreviewMeta) {
    ui.risPreviewMeta.textContent = `Tx angle ${txAngle.toFixed(1)}° · Tx ${txDist.toFixed(2)} m · Rx ${rxDist.toFixed(2)} m`;
  }
}

async function fetchJsonMaybe(url) {
  const res = await fetch(url);
  if (!res.ok) return null;
  return await res.json();
}

async function fetchTextMaybe(url) {
  const res = await fetch(url);
  if (!res.ok) return null;
  return await res.text();
}

function formatMetricValue(value) {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(4) : "n/a";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function renderRisMetrics(metrics) {
  ui.risMetrics.innerHTML = "";
  if (!metrics) {
    ui.risMetrics.textContent = "No metrics found for this run.";
    return;
  }
  Object.entries(metrics).forEach(([key, value]) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = `${key}: `;
    const val = document.createElement("span");
    val.textContent = formatMetricValue(value);
    row.append(label, val);
    ui.risMetrics.appendChild(row);
  });
}

function renderRisPlotSingle(runId, file) {
  if (!ui.risPlotImage || !ui.risPlotCaption) return;
  const label = RIS_PLOT_LABELS[file] || file;
  ui.risPlotCaption.textContent = label;
  ui.risPlotImage.src = `/runs/${runId}/plots/${file}`;
  ui.risPlotImage.alt = label;
}

function setRisStatus(text) {
  ui.risJobStatus.textContent = text;
}

function setRisResultStatus(text) {
  ui.risResultStatus.textContent = text;
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

function getProfileDefinition() {
  return RUN_PROFILES[ui.runProfile.value] || RUN_PROFILES.cpu_only;
}

function resolveConfigPath(configName) {
  const match = state.configs.find((cfg) => cfg.name === configName);
  return match ? match.path : `configs/${configName}`;
}

function getProfileConfig() {
  if (!state.configs.length) {
    return null;
  }
  const profile = getProfileDefinition();
  const match = state.configs.find((cfg) => cfg.name === profile.configName);
  return match || state.configs[0];
}

function applyRadioMapDefaults(config) {
  const radio = (config && config.data && config.data.radio_map) || {};
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

function applyCustomDefaults(config) {
  const sim = (config && config.data && config.data.simulation) || {};
  setInputValue(ui.customMaxDepth, sim.max_depth);
  setInputValue(ui.customSamplesPerSrc, sim.samples_per_src);
  setInputValue(ui.customMaxPathsPerSrc, sim.max_num_paths_per_src);
  const radio = (config && config.data && config.data.radio_map) || {};
  setInputValue(ui.customSamplesPerTx, radio.samples_per_tx);
  const runtime = (config && config.data && config.data.runtime) || {};
  if (runtime.force_cpu) {
    ui.customBackend.value = "cpu";
  } else if (runtime.prefer_gpu) {
    ui.customBackend.value = "gpu";
  }
}

function updateCustomVisibility() {
  const isCustom = ui.runProfile.value === "custom";
  ui.customOverridesSection.open = isCustom;
  ui.customOverridesSection.style.display = isCustom ? "" : "none";
}

function formatProfileLabel(profile) {
  const def = RUN_PROFILES[profile];
  return def ? def.label : profile;
}

async function fetchConfigs() {
  const res = await fetch("/api/configs");
  if (!res.ok) {
    return;
  }
  const data = await res.json();
  state.configs = data.configs || [];
  if (!ui.runProfile.value) {
    ui.runProfile.value = "cpu_only";
  }
  applyRadioMapDefaults(getProfileConfig());
  applyCustomDefaults(getProfileConfig());
  updateCustomVisibility();
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

async function fetchRisJobs() {
  const data = await fetchJsonMaybe("/api/ris/jobs");
  return data || { jobs: [] };
}

function renderRisJobList(jobs) {
  ui.risJobList.innerHTML = "";
  const sorted = [...jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const recent = sorted.slice(-5).reverse();
  recent.forEach((job) => {
    const item = document.createElement("div");
    const action = job.action ? ` · ${job.action}` : "";
    const mode = job.mode ? `/${job.mode}` : "";
    const status = job.status || "unknown";
    const error = job.error ? ` · ERROR: ${job.error}` : "";
    item.textContent = `${job.run_id}${action}${mode} · ${status}${error}`;
    ui.risJobList.appendChild(item);
  });
}

async function refreshRisRunSelect() {
  const data = await fetchJsonMaybe("/api/runs");
  const runIds = new Set();
  (data && data.runs ? data.runs : []).forEach((run) => {
    if (run.summary && run.summary.schema_version === 1) {
      runIds.add(run.run_id);
    }
  });
  state.ris.jobs.forEach((job) => {
    if (job.run_id) {
      runIds.add(job.run_id);
    }
  });
  const runList = Array.from(runIds).sort((a, b) => b.localeCompare(a));
  const previous = ui.risRunSelect.value;
  ui.risRunSelect.innerHTML = "";
  runList.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.risRunSelect.appendChild(opt);
  });
  if (runList.length > 0) {
    ui.risRunSelect.value = runList.includes(previous) ? previous : runList[0];
  }
  state.ris.runs = runList;
}

function tailLines(text, maxLines) {
  if (!text) return "";
  const lines = text.trimEnd().split("\n");
  return lines.slice(-maxLines).join("\n");
}

async function refreshRisProgressAndLog() {
  const runId = state.ris.activeRunId;
  if (!runId) {
    ui.risProgress.textContent = "";
    ui.risLog.textContent = "";
    return;
  }
  const progress = await fetchProgress(runId);
  if (progress) {
    const step = progress.step_name || "Running";
    const total = progress.total_steps || 0;
    const idx = progress.step_index != null ? progress.step_index + 1 : null;
    const pct = progress.progress != null ? Math.round(progress.progress * 100) : null;
    const pctLabel = pct !== null ? `${pct}%` : "";
    const stepLabel = total && idx ? `${step} (${idx}/${total})` : step;
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    ui.risProgress.textContent = `${progress.status || "running"} · ${stepLabel} ${pctLabel}${error}`.trim();
  } else {
    ui.risProgress.textContent = "Progress unavailable.";
  }
  const logText = await fetchTextMaybe(`/runs/${runId}/job.log`);
  ui.risLog.textContent = logText ? tailLines(logText, 120) : "No log available.";
}

async function refreshRisJobs() {
  const data = await fetchRisJobs();
  state.ris.jobs = data.jobs || [];
  renderRisJobList(state.ris.jobs);
  const sorted = [...state.ris.jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const running = sorted.find((job) => job.status === "running");
  const latest = sorted[sorted.length - 1];
  const active = state.ris.activeJobId
    ? sorted.find((job) => job.job_id === state.ris.activeJobId)
    : null;
  const current = active || running || latest;
  if (current) {
    state.ris.activeJobId = current.job_id;
    state.ris.activeRunId = current.run_id;
    setRisStatus(`${current.run_id} · ${current.status || "running"}`);
  } else {
    setRisStatus("Idle.");
  }
  await refreshRisRunSelect();
  await refreshRisProgressAndLog();
  if (state.ris.activeRunId) {
    ui.risRunSelect.value = state.ris.activeRunId;
    loadRisResults(state.ris.activeRunId);
  }
}

async function submitRisJob() {
  const action = ui.risAction.value;
  const payload = { action };
  const source = ui.risConfigSource ? ui.risConfigSource.value : "builder";
  if (source === "file") {
    let configPath = ui.risConfigPath.value.trim();
    if (!configPath && ui.risConfigPath.placeholder) {
      configPath = ui.risConfigPath.placeholder;
    }
    if (!configPath) {
      setRisStatus("Config path required.");
      return;
    }
    payload.config_path = configPath;
  } else {
    payload.config_data = buildRisConfigFromUI();
  }
  if (action === "run") {
    payload.mode = ui.risMode.value;
  } else {
    const refPath = ui.risReferencePath.value.trim();
    if (!refPath) {
      setRisStatus("Reference file required for validation.");
      return;
    }
    payload.ref = refPath;
  }
  setRisStatus("Submitting RIS Lab job...");
  try {
    const res = await fetch("/api/ris/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      setRisStatus(`RIS job error: ${data.error || res.status}`);
    } else {
      state.ris.activeRunId = data.run_id;
      state.ris.activeJobId = data.job_id;
      setRisStatus(`RIS job submitted: ${data.run_id}`);
    }
    await refreshRisJobs();
    await refreshRisProgressAndLog();
  } catch (err) {
    setRisStatus("RIS job error: network failure");
  }
}

async function loadRisResults(runId) {
  if (!runId) {
    setRisResultStatus("Select a run to load results.");
    renderRisMetrics(null);
    if (ui.risPlotImage) ui.risPlotImage.src = "";
    return;
  }
  setRisResultStatus(`Loading ${runId}...`);
  const [metrics, progress] = await Promise.all([
    fetchJsonMaybe(`/runs/${runId}/metrics.json`),
    fetchProgress(runId),
  ]);
  renderRisMetrics(metrics);
  const defaultPlot = "phase_map.png";
  renderRisPlotSingle(runId, defaultPlot);
  if (ui.risPlotTabs) {
    ui.risPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.plot === defaultPlot);
    });
  }
  if (progress && progress.status === "failed") {
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    setRisResultStatus(`Run failed${error}`);
  } else if (progress && progress.status) {
    setRisResultStatus(`Run status: ${progress.status}`);
  } else {
    setRisResultStatus("Results loaded.");
  }
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
  if (ui.toggleGeometry.checked) {
    loadMeshes();
  }
  addMarkers();
  addAlignmentMarkers();
  addRays();
  addHeatmap();
  geometryGroup.visible = ui.toggleGeometry.checked;
  markerGroup.visible = ui.toggleMarkers.checked;
  rayGroup.visible = ui.toggleRays.checked;
  heatmapGroup.visible = ui.toggleHeatmap.checked;
  alignmentGroup.visible = ui.toggleGuides.checked;
  updateHeatmapScaleVisibility();
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
    controls.enabled = false;
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

function endDrag() {
  if (dragging) {
    dragging = null;
  }
  controls.enabled = true;
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
    const label = job.profile ? ` · ${formatProfileLabel(job.profile)}` : "";
    item.textContent = `${job.run_id}${label} · ${job.status}${guard}`;
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
      const label = job.profile ? ` · ${formatProfileLabel(job.profile)}` : "";
      item.textContent = `${job.run_id}${label} · ${job.status}${stepLabel}${pctLabel}`;
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

async function submitJob() {
  const profile = getProfileDefinition();
  const payload = {
    kind: "run",
    profile: ui.runProfile.value,
    base_config: resolveConfigPath(profile.configName),
  };
  if (profile.qualityPreset) {
    payload.preset = profile.qualityPreset;
  }
  if (profile.runtime) {
    payload.runtime = profile.runtime;
  }
  if (ui.runProfile.value === "custom") {
    const backend = ui.customBackend.value;
    payload.runtime = {
      force_cpu: backend === "cpu",
      prefer_gpu: backend === "gpu",
    };
    const sim = {};
    const maxDepth = readNumber(ui.customMaxDepth);
    const samplesPerSrc = readNumber(ui.customSamplesPerSrc);
    const maxPathsPerSrc = readNumber(ui.customMaxPathsPerSrc);
    if (maxDepth !== null) sim.max_depth = maxDepth;
    if (samplesPerSrc !== null) sim.samples_per_src = samplesPerSrc;
    if (maxPathsPerSrc !== null) sim.max_num_paths_per_src = maxPathsPerSrc;
    if (Object.keys(sim).length) {
      payload.simulation = sim;
    }
    const radio = { auto_size: ui.radioMapAuto.checked };
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
    const samplesPerTx = readNumber(ui.customSamplesPerTx);
    if (samplesPerTx !== null) {
      radio.samples_per_tx = samplesPerTx;
    }
    if (Object.keys(radio).length) {
      payload.radio_map = radio;
    }
  }
  const scenePayload = JSON.parse(JSON.stringify(state.sceneOverride || {}));
  scenePayload.tx = { position: state.markers.tx };
  scenePayload.rx = { position: state.markers.rx };
  payload.scene = scenePayload;
  setMeta("Submitting run...");
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
  console.log("Starting bindUI...");
  if (!ui.refreshRuns) console.error("ui.refreshRuns is missing");
  ui.refreshRuns.addEventListener("click", fetchRuns);
  
  if (!ui.runSelect) console.error("ui.runSelect is missing");
  ui.runSelect.addEventListener("change", () => loadRun(ui.runSelect.value));
  
  if (!ui.sceneRunSelect) console.error("ui.sceneRunSelect is missing");
  ui.sceneRunSelect.addEventListener("change", async () => {
    state.sceneSourceRunId = ui.sceneRunSelect.value;
    const details = await fetchRunDetails(state.sceneSourceRunId);
    state.sceneOverride = details && details.config ? details.config.scene : null;
  });
  
  if (!ui.runProfile) console.error("ui.runProfile is missing");
  ui.runProfile.addEventListener("change", () => {
    applyRadioMapDefaults(getProfileConfig());
    applyCustomDefaults(getProfileConfig());
    updateCustomVisibility();
  });
  
  if (!ui.applyMarkers) console.error("ui.applyMarkers is missing");
  ui.applyMarkers.addEventListener("click", () => {
    state.markers.tx = [parseFloat(ui.txX.value), parseFloat(ui.txY.value), parseFloat(ui.txZ.value)];
    state.markers.rx = [parseFloat(ui.rxX.value), parseFloat(ui.rxY.value), parseFloat(ui.rxZ.value)];
    rebuildScene();
  });
  
  if (!ui.meshRotation) console.error("ui.meshRotation is missing");
  ui.meshRotation.addEventListener("input", () => {
    ui.meshRotationLabel.textContent = `${ui.meshRotation.value}`;
    rebuildScene();
  });
  
  if (!ui.runSim) console.error("ui.runSim is missing");
  ui.runSim.addEventListener("click", () => submitJob());
  
  console.log("Binding RIS controls...");
  if (!ui.mainTabStrip) console.error("ui.mainTabStrip is missing");
  ui.mainTabStrip.addEventListener("click", (event) => {
    const target = event.target;
    if (target instanceof HTMLButtonElement && target.dataset.mainTab) {
      setMainTab(target.dataset.mainTab);
    }
  });
  
  if (!ui.risAction) console.error("ui.risAction is missing");
  ui.risAction.addEventListener("change", updateRisActionVisibility);
  
  if (!ui.risStart) console.error("ui.risStart is missing");
  ui.risStart.addEventListener("click", submitRisJob);
  
  if (!ui.risRefresh) console.error("ui.risRefresh is missing");
  ui.risRefresh.addEventListener("click", refreshRisJobs);
  
  if (!ui.risLoadResults) console.error("ui.risLoadResults is missing");
  ui.risLoadResults.addEventListener("click", () => loadRisResults(ui.risRunSelect.value));
  
  if (!ui.risRunSelect) console.error("ui.risRunSelect is missing");
  ui.risRunSelect.addEventListener("change", () => loadRisResults(ui.risRunSelect.value));

  if (!ui.risPlotTabs) console.error("ui.risPlotTabs is missing");
  ui.risPlotTabs.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const file = target.dataset.plot;
    if (!file || !state.ris.activeRunId) return;
    ui.risPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
      btn.classList.toggle("is-active", btn === target);
    });
    renderRisPlotSingle(state.ris.activeRunId, file);
  });
  
  if (!ui.risConfigSource) console.error("ui.risConfigSource is missing");
  ui.risConfigSource.addEventListener("change", () => {
    updateRisConfigSourceVisibility();
    updateRisConfigPreview();
  });
  
  if (!ui.risControlMode) console.error("ui.risControlMode is missing");
  ui.risControlMode.addEventListener("change", () => {
    updateRisControlVisibility();
    updateRisConfigPreview();
  });

  const risPreviewInputs = [
    ui.risConfigPath,
    ui.risFreqHz,
    ui.risTxAngle,
    ui.risTxDistance,
    ui.risRxDistance,
    ui.risTxGain,
    ui.risRxGain,
    ui.risTxPower,
    ui.risReflectionCoeff,
    ui.risGeomNx,
    ui.risGeomNy,
    ui.risGeomDx,
    ui.risGeomDy,
    ui.risOriginX,
    ui.risOriginY,
    ui.risOriginZ,
    ui.risNormalX,
    ui.risNormalY,
    ui.risNormalZ,
    ui.risAxisX,
    ui.risAxisY,
    ui.risAxisZ,
    ui.risElementSize,
    ui.risSteerAz,
    ui.risSteerEl,
    ui.risPhaseOffsetDeg,
    ui.risUniformPhaseDeg,
    ui.risFocusX,
    ui.risFocusY,
    ui.risFocusZ,
    ui.risQuantBits,
    ui.risSweepStart,
    ui.risSweepStop,
    ui.risSweepStep,
    ui.risNormalization,
  ];
  risPreviewInputs.forEach((input) => {
    if (!input) return;
    input.addEventListener("input", updateRisConfigPreview);
    if (input.tagName && input.tagName.toLowerCase() === "select") {
      input.addEventListener("change", updateRisConfigPreview);
    }
    input.addEventListener("input", updateRisPreview);
  });
  
  if (!ui.topDown) console.error("ui.topDown is missing");
  ui.topDown.addEventListener("click", () => {
    camera.position.set(0, 0, 200);
    controls.target.set(0, 0, 0);
  });
  
  if (!ui.snapshot) console.error("ui.snapshot is missing");
  ui.snapshot.addEventListener("click", () => {
    const link = document.createElement("a");
    link.download = `snapshot-${state.runId || "run"}.png`;
    link.href = renderer.domElement.toDataURL("image/png");
    link.click();
  });
  
  if (!ui.toggleGeometry) console.error("ui.toggleGeometry is missing");
  ui.toggleGeometry.addEventListener("change", () => {
    geometryGroup.visible = ui.toggleGeometry.checked;
    if (ui.toggleGeometry.checked) {
      loadMeshes();
    } else {
      geometryGroup.clear();
    }
  });
  
  if (!ui.toggleMarkers) console.error("ui.toggleMarkers is missing");
  ui.toggleMarkers.addEventListener("change", () => {
    markerGroup.visible = ui.toggleMarkers.checked;
  });
  
  if (!ui.toggleRays) console.error("ui.toggleRays is missing");
  ui.toggleRays.addEventListener("change", () => {
    rayGroup.visible = ui.toggleRays.checked;
  });
  
  if (!ui.toggleHeatmap) console.error("ui.toggleHeatmap is missing");
  ui.toggleHeatmap.addEventListener("change", () => {
    heatmapGroup.visible = ui.toggleHeatmap.checked;
    updateHeatmapScaleVisibility();
  });
  
  if (!ui.toggleGuides) console.error("ui.toggleGuides is missing");
  ui.toggleGuides.addEventListener("change", () => {
    alignmentGroup.visible = ui.toggleGuides.checked;
  });
  
  if (!ui.heatmapRotation) console.error("ui.heatmapRotation is missing");
  ui.heatmapRotation.addEventListener("input", () => {
    ui.heatmapRotationLabel.textContent = `${ui.heatmapRotation.value}`;
    heatmapGroup.clear();
    addHeatmap();
  });
  
  if (!ui.heatmapMin) console.error("ui.heatmapMin is missing");
  ui.heatmapMin.addEventListener("input", () => {
    ui.heatmapMinLabel.textContent = `${ui.heatmapMin.value}`;
    ui.heatmapMinInput.value = ui.heatmapMin.value;
    updateHeatmapScaleLabels();
    heatmapGroup.clear();
    addHeatmap();
  });
  
  if (!ui.heatmapMax) console.error("ui.heatmapMax is missing");
  ui.heatmapMax.addEventListener("input", () => {
    ui.heatmapMaxLabel.textContent = `${ui.heatmapMax.value}`;
    ui.heatmapMaxInput.value = ui.heatmapMax.value;
    updateHeatmapScaleLabels();
    heatmapGroup.clear();
    addHeatmap();
  });
  
  if (!ui.heatmapMinInput) console.error("ui.heatmapMinInput is missing");
  ui.heatmapMinInput.addEventListener("change", () => {
    ui.heatmapMin.value = ui.heatmapMinInput.value;
    ui.heatmapMinLabel.textContent = `${ui.heatmapMin.value}`;
    updateHeatmapScaleLabels();
    heatmapGroup.clear();
    addHeatmap();
  });
  
  if (!ui.heatmapMaxInput) console.error("ui.heatmapMaxInput is missing");
  ui.heatmapMaxInput.addEventListener("change", () => {
    ui.heatmapMax.value = ui.heatmapMaxInput.value;
    ui.heatmapMaxLabel.textContent = `${ui.heatmapMax.value}`;
    updateHeatmapScaleLabels();
    heatmapGroup.clear();
    addHeatmap();
  });
  
  if (!ui.randomizeMarkers) console.error("ui.randomizeMarkers is missing");
  ui.randomizeMarkers.addEventListener("click", randomizeMarkers);
  
  if (!ui.pathTypeFilter) console.error("ui.pathTypeFilter is missing");
  ui.pathTypeFilter.addEventListener("change", renderPathTable);
  
  if (!ui.pathOrderFilter) console.error("ui.pathOrderFilter is missing");
  ui.pathOrderFilter.addEventListener("input", renderPathTable);
  
  console.log("bindUI complete.");
}

try {
  initViewer();
} catch (err) {
  console.error("Viewer init failed:", err);
  setMeta("3D Viewer failed (WebGL error?)");
}
bindKeyboardNavigation();
bindUI();
updateRisActionVisibility();
updateRisConfigSourceVisibility();
updateRisControlVisibility();
updateRisConfigPreview();
updateRisPreview();
setMainTab("sim");
fetchConfigs().then(fetchRuns).then(refreshRisJobs);
setInterval(() => {
  refreshJobs();
  refreshRisJobs();
}, 3000);
