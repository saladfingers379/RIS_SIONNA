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
  followLatestRun: true,
  markers: { tx: [0, 0, 0], rx: [0, 0, 0], ris: [] },
  paths: [],
  heatmap: null,
  manifest: null,
  selectedPath: null,
  sceneOverride: null,
  sceneOverrideDirty: false,
  runInfo: null,
  runs: [],
  runConfigs: {},
  builtinScenes: [],
  configs: [],
  radioMapPlots: [],
  heatmapBase: null,
  heatmapDiff: null,
  simTuningDirty: false,
  activeTab: "sim",
  indoorInitialized: false,
  viewerScale: { enabled: false, targetSize: 160 },
  simScaleSnapshot: null,
  tabSnapshots: { sim: null, indoor: null },
  risGeometry: null,
  ris: {
    jobs: [],
    runs: [],
    activeRunId: null,
    activeJobId: null,
    selectedPlot: null,
  },
  cc: {
    jobs: [],
    runs: [],
    activeRunId: null,
    activeJobId: null,
    selectedPlot: null,
  },
};

const ui = {
  runSelect: document.getElementById("runSelect"),
  refreshRuns: document.getElementById("refreshRuns"),
  topDown: document.getElementById("topDown"),
  snapshot: document.getElementById("snapshot"),
  mainTabStrip: document.getElementById("mainTabStrip"),
  runProfile: document.getElementById("runProfile"),
  sceneSelect: document.getElementById("sceneSelect"),
  runStats: document.getElementById("runStats"),
  txX: document.getElementById("txX"),
  txY: document.getElementById("txY"),
  txZ: document.getElementById("txZ"),
  txLookX: document.getElementById("txLookX"),
  txLookY: document.getElementById("txLookY"),
  txLookZ: document.getElementById("txLookZ"),
  txLookAtRis: document.getElementById("txLookAtRis"),
  txYawDeg: document.getElementById("txYawDeg"),
  txPowerDbm: document.getElementById("txPowerDbm"),
  txPattern: document.getElementById("txPattern"),
  txPolarization: document.getElementById("txPolarization"),
  showTxDirection: document.getElementById("showTxDirection"),
  rxX: document.getElementById("rxX"),
  rxY: document.getElementById("rxY"),
  rxZ: document.getElementById("rxZ"),
  applyMarkers: document.getElementById("applyMarkers"),
  dragMarkers: document.getElementById("dragMarkers"),
  runSim: document.getElementById("runSim"),
  runSimTop: document.getElementById("runSimTop"),
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
  ccConfigSource: document.getElementById("ccConfigSource"),
  ccPreset: document.getElementById("ccPreset"),
  ccConfigPath: document.getElementById("ccConfigPath"),
  ccUseScene: document.getElementById("ccUseScene"),
  ccUseMarkers: document.getElementById("ccUseMarkers"),
  ccRole: document.getElementById("ccRole"),
  ccStart: document.getElementById("ccStart"),
  ccRefresh: document.getElementById("ccRefresh"),
  ccTrajectoryType: document.getElementById("ccTrajectoryType"),
  ccTrajectorySteps: document.getElementById("ccTrajectorySteps"),
  ccTrajectoryDt: document.getElementById("ccTrajectoryDt"),
  ccStartX: document.getElementById("ccStartX"),
  ccStartY: document.getElementById("ccStartY"),
  ccStartZ: document.getElementById("ccStartZ"),
  ccEndX: document.getElementById("ccEndX"),
  ccEndY: document.getElementById("ccEndY"),
  ccEndZ: document.getElementById("ccEndZ"),
  ccWaypoints: document.getElementById("ccWaypoints"),
  ccRwStepStd: document.getElementById("ccRwStepStd"),
  ccRwSmooth: document.getElementById("ccRwSmooth"),
  ccSpiralR0: document.getElementById("ccSpiralR0"),
  ccSpiralR1: document.getElementById("ccSpiralR1"),
  ccSpiralTurns: document.getElementById("ccSpiralTurns"),
  ccCsiType: document.getElementById("ccCsiType"),
  ccSubcarriers: document.getElementById("ccSubcarriers"),
  ccSubcarrierSpacing: document.getElementById("ccSubcarrierSpacing"),
  ccCirSampling: document.getElementById("ccCirSampling"),
  ccCirSteps: document.getElementById("ccCirSteps"),
  ccTapsBw: document.getElementById("ccTapsBw"),
  ccTapsLmin: document.getElementById("ccTapsLmin"),
  ccTapsLmax: document.getElementById("ccTapsLmax"),
  ccFeatureType: document.getElementById("ccFeatureType"),
  ccFeatureWindow: document.getElementById("ccFeatureWindow"),
  ccFeatureBeamspace: document.getElementById("ccFeatureBeamspace"),
  ccEmbedDim: document.getElementById("ccEmbedDim"),
  ccEpochs: document.getElementById("ccEpochs"),
  ccLr: document.getElementById("ccLr"),
  ccAdjWeight: document.getElementById("ccAdjWeight"),
  ccOverrideModel: document.getElementById("ccOverrideModel"),
  ccTrackingEnabled: document.getElementById("ccTrackingEnabled"),
  ccTrackingAlpha: document.getElementById("ccTrackingAlpha"),
  ccEvalDims: document.getElementById("ccEvalDims"),
  ccJobStatus: document.getElementById("ccJobStatus"),
  ccProgress: document.getElementById("ccProgress"),
  ccLog: document.getElementById("ccLog"),
  ccJobList: document.getElementById("ccJobList"),
  ccRunSelect: document.getElementById("ccRunSelect"),
  ccLoadResults: document.getElementById("ccLoadResults"),
  ccResultStatus: document.getElementById("ccResultStatus"),
  ccMetrics: document.getElementById("ccMetrics"),
  ccPlotTabs: document.getElementById("ccPlotTabs"),
  ccPlotImage: document.getElementById("ccPlotImage"),
  ccPlotCaption: document.getElementById("ccPlotCaption"),
  scaleBar: document.getElementById("scaleBar"),
  scaleBarLabel: document.getElementById("scaleBarLabel"),
  scaleBarLine: document.getElementById("scaleBarLine"),
  radioMapAuto: document.getElementById("radioMapAuto"),
  radioMapPadding: document.getElementById("radioMapPadding"),
  radioMapCellX: document.getElementById("radioMapCellX"),
  radioMapCellY: document.getElementById("radioMapCellY"),
  radioMapSizeX: document.getElementById("radioMapSizeX"),
  radioMapSizeY: document.getElementById("radioMapSizeY"),
  radioMapCenterX: document.getElementById("radioMapCenterX"),
  radioMapCenterY: document.getElementById("radioMapCenterY"),
  radioMapCenterZ: document.getElementById("radioMapCenterZ"),
  radioMapPlaneZ: document.getElementById("radioMapPlaneZ"),
  radioMapPlotStyle: document.getElementById("radioMapPlotStyle"),
  radioMapPlotMetric: document.getElementById("radioMapPlotMetric"),
  radioMapPlotShowTx: document.getElementById("radioMapPlotShowTx"),
  radioMapPlotShowRx: document.getElementById("radioMapPlotShowRx"),
  radioMapPlotShowRis: document.getElementById("radioMapPlotShowRis"),
  radioMapDiffRis: document.getElementById("radioMapDiffRis"),
  customOverridesSection: document.getElementById("customOverridesSection"),
  customBackend: document.getElementById("customBackend"),
  customFrequencyHz: document.getElementById("customFrequencyHz"),
  customMaxDepth: document.getElementById("customMaxDepth"),
  customSamplesPerSrc: document.getElementById("customSamplesPerSrc"),
  customMaxPathsPerSrc: document.getElementById("customMaxPathsPerSrc"),
  customSamplesPerTx: document.getElementById("customSamplesPerTx"),
  simScaleEnabled: document.getElementById("simScaleEnabled"),
  simScaleFactor: document.getElementById("simScaleFactor"),
  simSamplingEnabled: document.getElementById("simSamplingEnabled"),
  simMapResMult: document.getElementById("simMapResMult"),
  simRaySamplesMult: document.getElementById("simRaySamplesMult"),
  simMaxDepthAdd: document.getElementById("simMaxDepthAdd"),
  resetSimTuning: document.getElementById("resetSimTuning"),
  simComputePaths: document.getElementById("simComputePaths"),
  simRisEnabled: document.getElementById("simRisEnabled"),
  simRisObjects: document.getElementById("simRisObjects"),
  indoorViewerNormalize: document.getElementById("indoorViewerNormalize"),
  indoorViewerTargetSize: document.getElementById("indoorViewerTargetSize"),
  indoorSkipPaths: document.getElementById("indoorSkipPaths"),
  risGeomMode: document.getElementById("risGeomMode"),
  risWidthM: document.getElementById("risWidthM"),
  risHeightM: document.getElementById("risHeightM"),
  risTargetDxM: document.getElementById("risTargetDxM"),
  risSquareGrid: document.getElementById("risSquareGrid"),
  risDxM: document.getElementById("risDxM"),
  risNx: document.getElementById("risNx"),
  risNy: document.getElementById("risNy"),
  risGeomReset: document.getElementById("risGeomReset"),
  viewerMeta: document.getElementById("viewerMeta"),
  toggleGeometry: document.getElementById("toggleGeometry"),
  toggleMarkers: document.getElementById("toggleMarkers"),
  toggleRays: document.getElementById("toggleRays"),
  toggleHeatmap: document.getElementById("toggleHeatmap"),
  toggleGuides: document.getElementById("toggleGuides"),
  toggleRisFocus: document.getElementById("toggleRisFocus"),
  toggleRisFront: document.getElementById("toggleRisFront"),
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
  radioMapPreviewSelect: document.getElementById("radioMapPreviewSelect"),
  radioMapPreviewImage: document.getElementById("radioMapPreviewImage"),
  radioMapDiffRun: document.getElementById("radioMapDiffRun"),
  radioMapDiffToggle: document.getElementById("radioMapDiffToggle"),
  pathTypeFilter: document.getElementById("pathTypeFilter"),
  pathOrderFilter: document.getElementById("pathOrderFilter"),
  pathTableBody: document.getElementById("pathTableBody"),
  pathStats: document.getElementById("pathStats"),
  randomizeMarkers: document.getElementById("randomizeMarkers"),
  addRis: document.getElementById("addRis"),
  debugRis: document.getElementById("debugRis"),
  risPresetFocus: document.getElementById("risPresetFocus"),
  risPresetFlat: document.getElementById("risPresetFlat"),
  risPresetCenterMap: document.getElementById("risPresetCenterMap"),
  risList: document.getElementById("risList"),
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
  indoor_box_high: {
    label: "Indoor Box High",
    configName: "indoor_box_high.yaml",
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

const CC_PLOT_FILES = [
  { file: "chart_raw.png", label: "Chart (raw)" },
  { file: "chart_smoothed.png", label: "Chart (smoothed)" },
  { file: "chart_aligned.png", label: "Chart (aligned)" },
  { file: "trajectory_compare.png", label: "Trajectory vs estimate" },
  { file: "features.png", label: "Features" },
  { file: "training_losses.png", label: "Training losses" },
];
const CC_PLOT_LABELS = Object.fromEntries(CC_PLOT_FILES.map((p) => [p.file, p.label]));

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
let dragMode = null;
let dragRisIndex = null;
let dragStartYaw = 0;
let dragStartMouse = null;
let debugHeatmapMesh = null;

function getSceneScale() {
  if (geometryGroup) {
    const box = new THREE.Box3().setFromObject(geometryGroup);
    if (!box.isEmpty()) {
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      if (Number.isFinite(maxDim) && maxDim > 0) return maxDim;
    }
  }
  if (state.heatmap && Array.isArray(state.heatmap.size)) {
    const maxDim = Math.max(...state.heatmap.size);
    if (Number.isFinite(maxDim) && maxDim > 0) return maxDim;
  }
  return 100;
}

function getMarkerRadius() {
  const scale = getSceneScale();
  const raw = scale * 0.02;
  return Math.min(Math.max(raw, 0.12), 3.5);
}

function getConfigByName(name) {
  if (!state.configs.length) return null;
  return state.configs.find((cfg) => cfg.name === name) || null;
}

function applyIndoorDefaults() {
  const indoorCfg = getConfigByName("indoor_box_high.yaml");
  if (!indoorCfg) return;
  if (ui.runProfile) ui.runProfile.value = "indoor_box_high";
  applyRadioMapDefaults(indoorCfg);
  applyCustomDefaults(indoorCfg);
  applySimTuningDefaults(indoorCfg);
  applyRisSimDefaults(indoorCfg);
  updateCustomVisibility();
  resetMarkersFromConfig(indoorCfg);
}

function setSimilarityScalingLocked(locked) {
  if (ui.simScaleEnabled) {
    if (locked && !state.simScaleSnapshot) {
      state.simScaleSnapshot = {
        enabled: ui.simScaleEnabled.checked,
        factor: ui.simScaleFactor ? ui.simScaleFactor.value : "",
      };
    }
    if (locked) ui.simScaleEnabled.checked = false;
    ui.simScaleEnabled.disabled = locked;
  }
  if (ui.simScaleFactor) {
    if (locked) ui.simScaleFactor.value = "";
    ui.simScaleFactor.disabled = locked;
  }
  if (!locked && state.simScaleSnapshot) {
    if (ui.simScaleEnabled) ui.simScaleEnabled.checked = state.simScaleSnapshot.enabled;
    if (ui.simScaleFactor) ui.simScaleFactor.value = state.simScaleSnapshot.factor;
    state.simScaleSnapshot = null;
  }
}

function syncViewerScaleFromUi() {
  if (!ui.indoorViewerNormalize) return;
  state.viewerScale.enabled = Boolean(ui.indoorViewerNormalize.checked);
  const target = readNumber(ui.indoorViewerTargetSize);
  if (target !== null) state.viewerScale.targetSize = target;
  fitCamera();
}

function moveSharedPanels(targetLayout) {
  if (!targetLayout) return;
  const left = document.getElementById("simLeftPanel");
  const viewer = document.getElementById("viewerPanel");
  const right = document.getElementById("pathPanel");
  if (!left || !viewer || !right) return;
  targetLayout.appendChild(left);
  targetLayout.appendChild(viewer);
  targetLayout.appendChild(right);
}

function snapshotUiState() {
  const readText = (el) => (el ? el.value : "");
  const readCheck = (el) => (el ? Boolean(el.checked) : false);
  const readNum = (el) => {
    if (!el || el.value === "") return null;
    const num = parseFloat(el.value);
    return Number.isFinite(num) ? num : null;
  };
  return {
    runProfile: ui.runProfile ? ui.runProfile.value : "",
    markers: JSON.parse(JSON.stringify(state.markers || { tx: [0, 0, 0], rx: [0, 0, 0], ris: [] })),
    sceneOverride: state.sceneOverride ? JSON.parse(JSON.stringify(state.sceneOverride)) : null,
    sceneOverrideDirty: Boolean(state.sceneOverrideDirty),
    custom: {
      backend: readText(ui.customBackend),
      frequencyHz: readText(ui.customFrequencyHz),
      maxDepth: readText(ui.customMaxDepth),
      samplesPerSrc: readText(ui.customSamplesPerSrc),
      maxPathsPerSrc: readText(ui.customMaxPathsPerSrc),
      samplesPerTx: readText(ui.customSamplesPerTx),
    },
    radio: {
      auto: readCheck(ui.radioMapAuto),
      padding: readText(ui.radioMapPadding),
      cellX: readText(ui.radioMapCellX),
      cellY: readText(ui.radioMapCellY),
      sizeX: readText(ui.radioMapSizeX),
      sizeY: readText(ui.radioMapSizeY),
      centerX: readText(ui.radioMapCenterX),
      centerY: readText(ui.radioMapCenterY),
      centerZ: readText(ui.radioMapCenterZ),
      planeZ: readText(ui.radioMapPlaneZ),
      plotStyle: readText(ui.radioMapPlotStyle),
      plotMetric: readText(ui.radioMapPlotMetric),
      showTx: readCheck(ui.radioMapPlotShowTx),
      showRx: readCheck(ui.radioMapPlotShowRx),
      showRis: readCheck(ui.radioMapPlotShowRis),
      diffRis: readCheck(ui.radioMapDiffRis),
    },
    simTuning: {
      scaleEnabled: readCheck(ui.simScaleEnabled),
      scaleFactor: readText(ui.simScaleFactor),
      samplingEnabled: readCheck(ui.simSamplingEnabled),
      mapResMult: readText(ui.simMapResMult),
      raySamplesMult: readText(ui.simRaySamplesMult),
      maxDepthAdd: readText(ui.simMaxDepthAdd),
    },
    computePaths: readCheck(ui.simComputePaths),
    tx: {
      lookX: readText(ui.txLookX),
      lookY: readText(ui.txLookY),
      lookZ: readText(ui.txLookZ),
      lookAtRis: readCheck(ui.txLookAtRis),
      yawDeg: readText(ui.txYawDeg),
      powerDbm: readText(ui.txPowerDbm),
      pattern: readText(ui.txPattern),
      polarization: readText(ui.txPolarization),
      showDirection: readCheck(ui.showTxDirection),
      showRisFront: readCheck(ui.toggleRisFront),
    },
    ris: {
      enabled: readCheck(ui.simRisEnabled),
      geometryMode: readText(ui.risGeomMode),
      widthM: readText(ui.risWidthM),
      heightM: readText(ui.risHeightM),
      targetDxM: readText(ui.risTargetDxM),
      squareGrid: readCheck(ui.risSquareGrid),
      dxM: readText(ui.risDxM),
      nx: readText(ui.risNx),
      ny: readText(ui.risNy),
      objects: readRisItems(),
    },
    indoorViewer: {
      normalize: readCheck(ui.indoorViewerNormalize),
      targetSize: readText(ui.indoorViewerTargetSize),
      skipPaths: readCheck(ui.indoorSkipPaths),
    },
  };
}

function applyUiState(snapshot) {
  if (!snapshot) return;
  const setText = (el, value) => {
    if (!el) return;
    el.value = value === null || value === undefined ? "" : value;
  };
  const setCheck = (el, value) => {
    if (!el) return;
    el.checked = Boolean(value);
  };
  if (ui.runProfile && snapshot.runProfile) {
    ui.runProfile.value = snapshot.runProfile;
  }
  if (snapshot.custom) {
    setText(ui.customBackend, snapshot.custom.backend);
    setText(ui.customFrequencyHz, snapshot.custom.frequencyHz);
    setText(ui.customMaxDepth, snapshot.custom.maxDepth);
    setText(ui.customSamplesPerSrc, snapshot.custom.samplesPerSrc);
    setText(ui.customMaxPathsPerSrc, snapshot.custom.maxPathsPerSrc);
    setText(ui.customSamplesPerTx, snapshot.custom.samplesPerTx);
  }
  if (snapshot.radio) {
    setCheck(ui.radioMapAuto, snapshot.radio.auto);
    setText(ui.radioMapPadding, snapshot.radio.padding);
    setText(ui.radioMapCellX, snapshot.radio.cellX);
    setText(ui.radioMapCellY, snapshot.radio.cellY);
    setText(ui.radioMapSizeX, snapshot.radio.sizeX);
    setText(ui.radioMapSizeY, snapshot.radio.sizeY);
    setText(ui.radioMapCenterX, snapshot.radio.centerX);
    setText(ui.radioMapCenterY, snapshot.radio.centerY);
    setText(ui.radioMapCenterZ, snapshot.radio.centerZ);
    setText(ui.radioMapPlaneZ, snapshot.radio.planeZ);
    setText(ui.radioMapPlotStyle, snapshot.radio.plotStyle);
    setText(ui.radioMapPlotMetric, snapshot.radio.plotMetric);
    setCheck(ui.radioMapPlotShowTx, snapshot.radio.showTx);
    setCheck(ui.radioMapPlotShowRx, snapshot.radio.showRx);
    setCheck(ui.radioMapPlotShowRis, snapshot.radio.showRis);
    setCheck(ui.radioMapDiffRis, snapshot.radio.diffRis);
  }
  if (snapshot.simTuning) {
    setCheck(ui.simScaleEnabled, snapshot.simTuning.scaleEnabled);
    setText(ui.simScaleFactor, snapshot.simTuning.scaleFactor);
    setCheck(ui.simSamplingEnabled, snapshot.simTuning.samplingEnabled);
    setText(ui.simMapResMult, snapshot.simTuning.mapResMult);
    setText(ui.simRaySamplesMult, snapshot.simTuning.raySamplesMult);
    setText(ui.simMaxDepthAdd, snapshot.simTuning.maxDepthAdd);
  }
  if (snapshot.tx) {
    setText(ui.txLookX, snapshot.tx.lookX);
    setText(ui.txLookY, snapshot.tx.lookY);
    setText(ui.txLookZ, snapshot.tx.lookZ);
    setCheck(ui.txLookAtRis, snapshot.tx.lookAtRis);
    setText(ui.txYawDeg, snapshot.tx.yawDeg);
    setText(ui.txPowerDbm, snapshot.tx.powerDbm);
    setText(ui.txPattern, snapshot.tx.pattern);
    setText(ui.txPolarization, snapshot.tx.polarization);
    setCheck(ui.showTxDirection, snapshot.tx.showDirection);
    setCheck(ui.toggleRisFront, snapshot.tx.showRisFront);
  }
  if (snapshot.ris) {
    setCheck(ui.simRisEnabled, snapshot.ris.enabled);
    setText(ui.risGeomMode, snapshot.ris.geometryMode);
    setText(ui.risWidthM, snapshot.ris.widthM);
    setText(ui.risHeightM, snapshot.ris.heightM);
    setText(ui.risTargetDxM, snapshot.ris.targetDxM);
    setCheck(ui.risSquareGrid, snapshot.ris.squareGrid);
    setText(ui.risDxM, snapshot.ris.dxM);
    setText(ui.risNx, snapshot.ris.nx);
    setText(ui.risNy, snapshot.ris.ny);
    if (ui.risList) {
      clearRisList();
      const objs = Array.isArray(snapshot.ris.objects) ? snapshot.ris.objects : [];
      if (objs.length) {
        objs.forEach((obj) => addRisItem(obj));
      } else {
        addRisItem();
      }
    }
  }
  if (snapshot.indoorViewer) {
    setCheck(ui.indoorViewerNormalize, snapshot.indoorViewer.normalize);
    setText(ui.indoorViewerTargetSize, snapshot.indoorViewer.targetSize);
    setCheck(ui.indoorSkipPaths, snapshot.indoorViewer.skipPaths);
  }
  if (snapshot.computePaths !== undefined) {
    setCheck(ui.simComputePaths, snapshot.computePaths);
  }
  state.markers = snapshot.markers || state.markers;
  state.sceneOverride = snapshot.sceneOverride;
  state.sceneOverrideDirty = Boolean(snapshot.sceneOverrideDirty);
  updateInputs();
  updateRisGeometryVisibility();
  updateCustomVisibility();
  rebuildScene();
  refreshHeatmap();
}

function _degToRad(deg) {
  return (deg * Math.PI) / 180.0;
}

function _radToDeg(rad) {
  return (rad * 180.0) / Math.PI;
}

function clearRisList() {
  if (!ui.risList) return;
  ui.risList.innerHTML = "";
}

function addRisItem(initial) {
  if (!ui.risList) return;
  const template = document.getElementById("risItemTemplate");
  if (!template) return;
  const node = template.content.firstElementChild.cloneNode(true);
  const fields = (name) => node.querySelector(`[data-field="${name}"]`);
  const setVal = (name, value) => {
    const el = fields(name);
    if (el && value !== undefined && value !== null) el.value = value;
  };
  const setCheck = (name, value) => {
    const el = fields(name);
    if (el) el.checked = Boolean(value);
  };
  setCheck("enabled", initial?.enabled !== false);
  setVal("name", initial?.name || `ris${ui.risList.children.length + 1}`);
  const pos = initial?.position || [0, 0, 2];
  setVal("posX", pos[0]);
  setVal("posY", pos[1]);
  setVal("posZ", pos[2]);
  const ori = initial?.orientation || [0, 0, 0];
  setVal("oriX", _radToDeg(ori[0]));
  setVal("oriY", _radToDeg(ori[1]));
  setVal("oriZ", _radToDeg(ori[2]));
  const look = initial?.look_at || [];
  if (look.length >= 3) {
    setVal("lookX", look[0]);
    setVal("lookY", look[1]);
    setVal("lookZ", look[2]);
  }
  setVal("rows", initial?.num_rows || 12);
  setVal("cols", initial?.num_cols || 12);
  setVal("modes", initial?.num_modes || 1);
  setVal("profileKind", initial?.profile?.kind || "flat");
  if (initial?.profile?.auto_aim) {
    const autoAim = fields("autoAim");
    if (autoAim) autoAim.checked = true;
  }
  const sources = initial?.profile?.sources;
  if (Array.isArray(sources) && sources.length >= 3 && !Array.isArray(sources[0])) {
    setVal("sourceX", sources[0]);
    setVal("sourceY", sources[1]);
    setVal("sourceZ", sources[2]);
  } else if (Array.isArray(sources) && Array.isArray(sources[0])) {
    setVal("sourceX", sources[0][0]);
    setVal("sourceY", sources[0][1]);
    setVal("sourceZ", sources[0][2]);
  }
  const targets = initial?.profile?.targets;
  if (Array.isArray(targets) && targets.length >= 3 && !Array.isArray(targets[0])) {
    setVal("targetX", targets[0]);
    setVal("targetY", targets[1]);
    setVal("targetZ", targets[2]);
  } else if (Array.isArray(targets) && Array.isArray(targets[0])) {
    setVal("targetX", targets[0][0]);
    setVal("targetY", targets[0][1]);
    setVal("targetZ", targets[0][2]);
  }
  setVal("amplitude", initial?.profile?.amplitude);
  setVal("phaseBits", initial?.profile?.phase_bits);
  node.querySelector(".ris-remove").addEventListener("click", () => {
    node.remove();
  });
  const profileSelect = fields("profileKind");
  if (profileSelect) {
    profileSelect.addEventListener("change", () => {
      if (["phase_gradient_reflector", "focusing_lens"].includes(profileSelect.value)) {
        const src = state.markers.tx || [0, 0, 0];
        const tgt = state.markers.rx || [0, 0, 0];
        if (!fields("sourceX")?.value && !fields("sourceY")?.value && !fields("sourceZ")?.value) {
          setVal("sourceX", src[0]);
          setVal("sourceY", src[1]);
          setVal("sourceZ", src[2]);
        }
        if (!fields("targetX")?.value && !fields("targetY")?.value && !fields("targetZ")?.value) {
          setVal("targetX", tgt[0]);
          setVal("targetY", tgt[1]);
          setVal("targetZ", tgt[2]);
        }
      }
    });
  }
  const autoAim = fields("autoAim");
  if (autoAim) {
    autoAim.addEventListener("change", () => {
      if (autoAim.checked) {
        const src = state.markers.tx || [0, 0, 0];
        const tgt = state.markers.rx || [0, 0, 0];
        setVal("sourceX", src[0]);
        setVal("sourceY", src[1]);
        setVal("sourceZ", src[2]);
        setVal("targetX", tgt[0]);
        setVal("targetY", tgt[1]);
        setVal("targetZ", tgt[2]);
      }
    });
  }
  const disableAutoAim = () => {
    if (autoAim && autoAim.checked) {
      autoAim.checked = false;
    }
  };
  ["sourceX", "sourceY", "sourceZ", "targetX", "targetY", "targetZ"].forEach((name) => {
    const el = fields(name);
    if (!el) return;
    el.addEventListener("input", disableAutoAim);
    el.addEventListener("change", disableAutoAim);
  });
  ui.risList.appendChild(node);
}

function readRisItems() {
  if (!ui.risList) return [];
  const items = [];
  const readNum = (el) => {
    if (!el || el.value === "") return null;
    const num = parseFloat(el.value);
    return Number.isFinite(num) ? num : null;
  };
  ui.risList.querySelectorAll(".ris-item").forEach((node) => {
    const field = (name) => node.querySelector(`[data-field="${name}"]`);
    const name = (field("name")?.value || "").trim() || `ris${items.length + 1}`;
    const enabled = field("enabled") ? field("enabled").checked : true;
    const pos = [
      readNum(field("posX")),
      readNum(field("posY")),
      readNum(field("posZ")),
    ];
    const position = pos.every((v) => v !== null) ? pos : [0, 0, 2];
    const look = [
      readNum(field("lookX")),
      readNum(field("lookY")),
      readNum(field("lookZ")),
    ];
    const orientationDeg = [
      readNum(field("oriX")),
      readNum(field("oriY")),
      readNum(field("oriZ")),
    ];
    const orientation = orientationDeg.map((val) => (val === null ? null : _degToRad(val)));
    const obj = {
      name,
      enabled,
      position,
      num_rows: Math.max(1, parseInt(field("rows")?.value || "12", 10)),
      num_cols: Math.max(1, parseInt(field("cols")?.value || "12", 10)),
      num_modes: Math.max(1, parseInt(field("modes")?.value || "1", 10)),
    };
    if (look.every((v) => v !== null)) {
      obj.look_at = look;
    } else if (orientation.every((v) => v !== null)) {
      obj.orientation = orientation;
    } else if (state.markers && Array.isArray(state.markers.rx)) {
      obj.look_at = state.markers.rx;
    }
    let profileKind = field("profileKind")?.value || "flat";
    const profile = { kind: profileKind };
    const autoAim = field("autoAim");
    if (autoAim && autoAim.checked) {
      profile.auto_aim = true;
    }
    const src = [
      readNum(field("sourceX")),
      readNum(field("sourceY")),
      readNum(field("sourceZ")),
    ];
    const tgt = [
      readNum(field("targetX")),
      readNum(field("targetY")),
      readNum(field("targetZ")),
    ];
    if (profile.auto_aim && state.markers) {
      profile.sources = state.markers.tx || src;
      profile.targets = state.markers.rx || tgt;
    } else {
      if (src.every((v) => v !== null)) {
        profile.sources = src;
      }
      if (tgt.every((v) => v !== null)) {
        profile.targets = tgt;
      }
    }
    if (
      ["phase_gradient_reflector", "focusing_lens"].includes(profileKind)
      && (!profile.sources || !profile.targets)
      && state.markers
    ) {
      profile.sources = profile.sources || state.markers.tx || src;
      profile.targets = profile.targets || state.markers.rx || tgt;
    }
    const amplitude = readNum(field("amplitude"));
    if (amplitude !== null) profile.amplitude = amplitude;
    const beamwidth = readNum(field("beamwidthDeg"));
    if (beamwidth !== null) profile.beamwidth_deg = beamwidth;
    const phaseBits = readNum(field("phaseBits"));
    if (phaseBits !== null) profile.phase_bits = Math.max(0, Math.round(phaseBits));
    obj.profile = profile;
    items.push(obj);
  });
  return items;
}

function applyRisDebugPreset() {
  if (ui.simRisEnabled) ui.simRisEnabled.checked = true;
  const tx = [10.0, 0.0, 2.0];
  const rx = [6.0, 2.0, 2.0];
  const risPos = [0.0, 0.0, 2.0];
  if (ui.txX) ui.txX.value = tx[0];
  if (ui.txY) ui.txY.value = tx[1];
  if (ui.txZ) ui.txZ.value = tx[2];
  if (ui.rxX) ui.rxX.value = rx[0];
  if (ui.rxY) ui.rxY.value = rx[1];
  if (ui.rxZ) ui.rxZ.value = rx[2];
  state.markers.tx = [...tx];
  state.markers.rx = [...rx];
  state.markers.ris = [risPos];
  const mid = [(tx[0] + rx[0]) / 2, (tx[1] + rx[1]) / 2, (tx[2] + rx[2]) / 2];
  if (ui.risList) {
    if (!ui.risList.children.length) {
      addRisItem();
    }
    const node = ui.risList.querySelector(".ris-item");
    if (node) {
      const setVal = (name, value) => {
        const el = node.querySelector(`[data-field="${name}"]`);
        if (el) el.value = value;
      };
      setVal("posX", risPos[0].toFixed(2));
      setVal("posY", risPos[1].toFixed(2));
      setVal("posZ", risPos[2].toFixed(2));
      setVal("rows", 50);
      setVal("cols", 50);
      setVal("modes", 1);
      setVal("profileKind", "phase_gradient_reflector");
      const autoAim = node.querySelector('[data-field="autoAim"]');
      if (autoAim) autoAim.checked = true;
      setVal("sourceX", tx[0].toFixed(2));
      setVal("sourceY", tx[1].toFixed(2));
      setVal("sourceZ", tx[2].toFixed(2));
      setVal("targetX", rx[0].toFixed(2));
      setVal("targetY", rx[1].toFixed(2));
      setVal("targetZ", rx[2].toFixed(2));
      setVal("amplitude", 1.0);
      setVal("phaseBits", 0);
    }
  }
  if (ui.radioMapAuto) ui.radioMapAuto.checked = false;
  if (ui.radioMapCenterX) setInputValue(ui.radioMapCenterX, mid[0].toFixed(2));
  if (ui.radioMapCenterY) setInputValue(ui.radioMapCenterY, mid[1].toFixed(2));
  if (ui.radioMapCenterZ) setInputValue(ui.radioMapCenterZ, rx[2].toFixed(2));
  if (ui.radioMapPlaneZ) setInputValue(ui.radioMapPlaneZ, rx[2].toFixed(2));
  if (ui.radioMapPlotStyle) ui.radioMapPlotStyle.value = "heatmap";
  if (ui.radioMapPlotMetric) ui.radioMapPlotMetric.value = "path_gain";
  if (ui.radioMapDiffToggle) ui.radioMapDiffToggle.checked = false;
  rebuildScene();
  refreshHeatmap();
  setMeta("Applied RIS debug preset");
}

function applyIndoorHighResPreset() {
  ui.runProfile.value = "custom";
  updateCustomVisibility();
  if (ui.customBackend) ui.customBackend.value = "gpu";
  if (ui.customFrequencyHz) ui.customFrequencyHz.value = "2.8e10";
  if (ui.customMaxDepth) ui.customMaxDepth.value = "3";
  if (ui.customSamplesPerSrc) ui.customSamplesPerSrc.value = "300000";
  if (ui.customMaxPathsPerSrc) ui.customMaxPathsPerSrc.value = "300000";
  if (ui.customSamplesPerTx) ui.customSamplesPerTx.value = "250000";

  if (ui.radioMapAuto) ui.radioMapAuto.checked = false;
  if (ui.radioMapCellX) ui.radioMapCellX.value = "0.05";
  if (ui.radioMapCellY) ui.radioMapCellY.value = "0.05";
  if (ui.radioMapSizeX) ui.radioMapSizeX.value = "6.0";
  if (ui.radioMapSizeY) ui.radioMapSizeY.value = "6.0";
  if (ui.radioMapCenterX) ui.radioMapCenterX.value = "0.0";
  if (ui.radioMapCenterY) ui.radioMapCenterY.value = "0.0";
  if (ui.radioMapCenterZ) ui.radioMapCenterZ.value = "1.5";
  if (ui.radioMapPlaneZ) ui.radioMapPlaneZ.value = "1.5";

  const tx = [-3.0, -3.0, 1.5];
  const rx = [3.0, 3.0, 1.5];
  state.markers.tx = [...tx];
  state.markers.rx = [...rx];
  if (ui.txX) ui.txX.value = tx[0];
  if (ui.txY) ui.txY.value = tx[1];
  if (ui.txZ) ui.txZ.value = tx[2];
  if (ui.rxX) ui.rxX.value = rx[0];
  if (ui.rxY) ui.rxY.value = rx[1];
  if (ui.rxZ) ui.rxZ.value = rx[2];

  state.sceneOverride = {
    type: "builtin",
    builtin: "etoile",
    tx: { position: tx },
    rx: { position: rx },
  };
  state.sceneOverrideDirty = true;

  if (ui.simRisEnabled) ui.simRisEnabled.checked = true;
  if (ui.risGeomMode) ui.risGeomMode.value = "size_driven";
  if (ui.risSquareGrid) ui.risSquareGrid.checked = true;
  if (ui.risWidthM) ui.risWidthM.value = "0.2";
  if (ui.risHeightM) ui.risHeightM.value = "0.2";
  if (ui.risTargetDxM) ui.risTargetDxM.value = "0.005";

  if (ui.risList) {
    if (!ui.risList.children.length) {
      addRisItem();
    }
    const node = ui.risList.querySelector(".ris-item");
    if (node) {
      const setVal = (name, value) => {
        const el = node.querySelector(`[data-field="${name}"]`);
        if (el) el.value = value;
      };
      setVal("posX", "0.0");
      setVal("posY", "0.0");
      setVal("posZ", "1.8");
      setVal("profileKind", "phase_gradient_reflector");
      const autoAim = node.querySelector('[data-field="autoAim"]');
      if (autoAim) autoAim.checked = true;
    }
  }

  updateInputs();
  updateRisGeometryVisibility();
  rebuildScene();
  refreshHeatmap();
  setMeta("Applied Indoor High-Res preset");
}

function applyCenterMapPreset() {
  const tx = state.markers.tx || [0, 0, 0];
  const rx = state.markers.rx || [0, 0, 0];
  const mid = [(tx[0] + rx[0]) / 2, (tx[1] + rx[1]) / 2, (tx[2] + rx[2]) / 2];
  if (ui.radioMapAuto) ui.radioMapAuto.checked = false;
  if (ui.radioMapCenterX) setInputValue(ui.radioMapCenterX, mid[0].toFixed(2));
  if (ui.radioMapCenterY) setInputValue(ui.radioMapCenterY, mid[1].toFixed(2));
  if (ui.radioMapCenterZ) setInputValue(ui.radioMapCenterZ, mid[2].toFixed(2));
  if (ui.radioMapPlaneZ) setInputValue(ui.radioMapPlaneZ, mid[2].toFixed(2));
  rebuildScene();
  refreshHeatmap();
  setMeta("Centered radio map on Tx/Rx midpoint");
}

function applyRisPresetToItems(handler) {
  if (ui.simRisEnabled) ui.simRisEnabled.checked = true;
  if (!ui.risList || !ui.risList.children.length) {
    addRisItem();
  }
  ui.risList.querySelectorAll(".ris-item").forEach((node) => {
    handler(node);
  });
  rebuildScene();
}

function applyRisFocusPreset() {
  const tx = state.markers.tx || [0, 0, 0];
  const rx = state.markers.rx || [0, 0, 0];
  applyRisPresetToItems((node) => {
    const setVal = (name, value) => {
      const el = node.querySelector(`[data-field="${name}"]`);
      if (el) el.value = value;
    };
    const autoAim = node.querySelector('[data-field="autoAim"]');
    if (autoAim) autoAim.checked = false;
    setVal("profileKind", "focusing_lens");
    setVal("sourceX", tx[0].toFixed(2));
    setVal("sourceY", tx[1].toFixed(2));
    setVal("sourceZ", tx[2].toFixed(2));
    setVal("targetX", rx[0].toFixed(2));
    setVal("targetY", rx[1].toFixed(2));
    setVal("targetZ", rx[2].toFixed(2));
    setVal("amplitude", 1.0);
    setVal("phaseBits", 0);
  });
  setMeta("Applied RIS focus preset");
}

function applyRisFlatPreset() {
  applyRisPresetToItems((node) => {
    const setVal = (name, value) => {
      const el = node.querySelector(`[data-field="${name}"]`);
      if (el) el.value = value;
    };
    const autoAim = node.querySelector('[data-field="autoAim"]');
    if (autoAim) autoAim.checked = false;
    setVal("profileKind", "flat");
    setVal("amplitude", 1.0);
    setVal("phaseBits", 0);
  });
  setMeta("Applied RIS flat preset");
}

function getRisItemNode(index) {
  if (!ui.risList) return null;
  return ui.risList.querySelectorAll(".ris-item")[index] || null;
}

function updateRisItemPosition(index, pos) {
  const node = getRisItemNode(index);
  if (!node) return;
  const field = (name) => node.querySelector(`[data-field="${name}"]`);
  const setVal = (name, value) => {
    const el = field(name);
    if (el) el.value = value;
  };
  setVal("posX", pos[0].toFixed(3));
  setVal("posY", pos[1].toFixed(3));
  setVal("posZ", pos[2].toFixed(3));
}

function getRisItemYaw(index) {
  const node = getRisItemNode(index);
  if (!node) return 0;
  const el = node.querySelector('[data-field="oriZ"]');
  const val = el && el.value !== "" ? parseFloat(el.value) : 0;
  return Number.isFinite(val) ? _degToRad(val) : 0;
}

function updateRisItemYaw(index, yawRad) {
  const node = getRisItemNode(index);
  if (!node) return;
  const el = node.querySelector('[data-field="oriZ"]');
  if (el) el.value = _radToDeg(yawRad).toFixed(2);
  ["lookX", "lookY", "lookZ"].forEach((name) => {
    const lookEl = node.querySelector(`[data-field="${name}"]`);
    if (lookEl) lookEl.value = "";
  });
}

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
  updateScaleBar();
  renderer.render(scene, camera);
}

function updateScaleBar() {
  if (!ui.scaleBar || !ui.scaleBarLabel || !ui.scaleBarLine) return;
  if (!camera || !renderer || !controls) return;
  const width = renderer.domElement.clientWidth;
  const height = renderer.domElement.clientHeight;
  if (!width || !height) return;
  const center = controls.target || new THREE.Vector3(0, 0, 0);
  const z = Number.isFinite(center.z) ? center.z : 0;
  const candidates = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000];
  const minPx = 70;
  const maxPx = 180;
  let best = null;
  let bestScore = Infinity;
  candidates.forEach((length) => {
    const p1 = new THREE.Vector3(center.x - length / 2, center.y, z);
    const p2 = new THREE.Vector3(center.x + length / 2, center.y, z);
    const s1 = p1.clone().project(camera);
    const s2 = p2.clone().project(camera);
    const dx = (s2.x - s1.x) * (width / 2);
    const dy = (s2.y - s1.y) * (height / 2);
    const px = Math.hypot(dx, dy);
    if (!Number.isFinite(px) || px <= 0) return;
    const target = (minPx + maxPx) / 2;
    const score = Math.abs(px - target);
    if ((px >= minPx && px <= maxPx && score < bestScore) || (!best && score < bestScore)) {
      bestScore = score;
      best = { length, px };
    }
  });
  if (!best) return;
  const px = Math.max(24, Math.min(best.px, 260));
  ui.scaleBarLine.style.width = `${px}px`;
  let label = `${best.length} m`;
  if (best.length >= 1000) {
    label = `${(best.length / 1000).toFixed(best.length % 1000 === 0 ? 0 : 1)} km`;
  } else if (best.length < 1) {
    label = `${Math.round(best.length * 100)} cm`;
  }
  ui.scaleBarLabel.textContent = label;
}

function setMeta(text) {
  ui.viewerMeta.textContent = text;
}

function readNumber(input) {
  const val = parseFloat(input.value);
  return Number.isFinite(val) ? val : null;
}

function readScientificNumber(input) {
  if (!input || input.value === "") return null;
  const val = Number(input.value.trim());
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
  if (state.activeTab) {
    state.tabSnapshots[state.activeTab] = snapshotUiState();
  }
  const buttons = ui.mainTabStrip.querySelectorAll(".main-tab-button");
  const panels = document.querySelectorAll(".main-tab-panel");
  buttons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.mainTab === tabName);
  });
  panels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.mainTab === tabName);
  });
  state.activeTab = tabName;
  const indoorLayout = document.getElementById("indoorLayout");
  const simLayout = document.getElementById("simLayout");
  const indoorSection = document.getElementById("indoorViewerSection");
  if (tabName === "indoor") {
    const firstIndoor = !state.indoorInitialized;
    moveSharedPanels(indoorLayout);
    if (indoorSection) indoorSection.style.display = "";
    setSimilarityScalingLocked(true);
    if (state.tabSnapshots.indoor) {
      applyUiState(state.tabSnapshots.indoor);
    } else if (firstIndoor) {
      applyIndoorDefaults();
      state.indoorInitialized = true;
      if (ui.indoorViewerNormalize) {
        ui.indoorViewerNormalize.checked = true;
      }
    }
    if (ui.indoorViewerNormalize && ui.indoorViewerTargetSize && ui.indoorViewerTargetSize.value === "") {
      ui.indoorViewerTargetSize.value = String(state.viewerScale.targetSize || 160);
    }
    syncViewerScaleFromUi();
    requestAnimationFrame(() => {
      refreshViewerSize();
      fitCamera();
    });
  } else {
    if (tabName === "sim") {
      moveSharedPanels(simLayout);
    }
    if (indoorSection) indoorSection.style.display = "none";
    setSimilarityScalingLocked(false);
    state.viewerScale.enabled = false;
    if (state.tabSnapshots.sim) {
      applyUiState(state.tabSnapshots.sim);
    }
    fitCamera();
    requestAnimationFrame(() => {
      refreshViewerSize();
      fitCamera();
    });
  }
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

function updateCcConfigSourceVisibility() {
  const source = ui.ccConfigSource ? ui.ccConfigSource.value : "preset";
  const fileFields = document.querySelectorAll(".cc-config-file");
  const presetFields = document.querySelectorAll(".cc-config-preset");
  fileFields.forEach((el) => {
    el.style.display = source === "file" ? "" : "none";
  });
  presetFields.forEach((el) => {
    el.style.display = source === "preset" ? "" : "none";
  });
}

function updateCcCsiVisibility() {
  const csiType = ui.ccCsiType ? ui.ccCsiType.value : "cfr";
  const isCfr = csiType === "cfr";
  const isCir = csiType === "cir";
  if (ui.ccSubcarriers) ui.ccSubcarriers.disabled = !isCfr;
  if (ui.ccSubcarrierSpacing) ui.ccSubcarrierSpacing.disabled = !isCfr;
  if (ui.ccCirSampling) ui.ccCirSampling.disabled = !isCir;
  if (ui.ccCirSteps) ui.ccCirSteps.disabled = !isCir;
  const tapsEnabled = csiType === "taps";
  if (ui.ccTapsBw) ui.ccTapsBw.disabled = !tapsEnabled;
  if (ui.ccTapsLmin) ui.ccTapsLmin.disabled = !tapsEnabled;
  if (ui.ccTapsLmax) ui.ccTapsLmax.disabled = !tapsEnabled;
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

function renderCcMetrics(metrics) {
  ui.ccMetrics.innerHTML = "";
  if (!metrics) {
    ui.ccMetrics.textContent = "No metrics found for this run.";
    return;
  }
  Object.entries(metrics).forEach(([key, value]) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = `${key}: `;
    const val = document.createElement("span");
    val.textContent = formatMetricValue(value);
    row.append(label, val);
    ui.ccMetrics.appendChild(row);
  });
}

function renderCcPlotSingle(runId, file) {
  if (!ui.ccPlotImage || !ui.ccPlotCaption) return;
  const label = CC_PLOT_LABELS[file] || file;
  ui.ccPlotCaption.textContent = label;
  ui.ccPlotImage.src = `/runs/${runId}/${file.startsWith("plots/") ? file : `plots/${file}`}`;
  ui.ccPlotImage.alt = label;
}

function setCcStatus(text) {
  ui.ccJobStatus.textContent = text;
}

function setCcResultStatus(text) {
  ui.ccResultStatus.textContent = text;
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

function loadUiSnapshot() {
  try {
    const raw = window.localStorage.getItem("sim_ui_snapshot");
    return raw ? JSON.parse(raw) : null;
  } catch (err) {
    return null;
  }
}

function saveUiSnapshot(snapshot) {
  try {
    window.localStorage.setItem("sim_ui_snapshot", JSON.stringify(snapshot));
  } catch (err) {
    // ignore
  }
}

function applyUiSnapshot() {
  const snap = loadUiSnapshot();
  if (!snap) return;
  applyUiState(snap);
}

let _persistTimer = null;
function schedulePersistUiSnapshot() {
  if (_persistTimer) window.clearTimeout(_persistTimer);
  _persistTimer = window.setTimeout(() => {
    saveUiSnapshot(snapshotUiState());
  }, 250);
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
  if (ui.radioMapPlotStyle) {
    ui.radioMapPlotStyle.value = (radio.plot_style || "heatmap").toLowerCase();
  }
  if (ui.radioMapPlotMetric) {
    const metrics = radio.plot_metrics;
    const metric = Array.isArray(metrics) ? metrics[0] : metrics;
    ui.radioMapPlotMetric.value = metric || "path_gain";
  }
  if (ui.radioMapPlotShowTx) ui.radioMapPlotShowTx.checked = radio.plot_show_tx !== undefined ? Boolean(radio.plot_show_tx) : true;
  if (ui.radioMapPlotShowRx) ui.radioMapPlotShowRx.checked = Boolean(radio.plot_show_rx);
  if (ui.radioMapPlotShowRis) ui.radioMapPlotShowRis.checked = Boolean(radio.plot_show_ris);
  if (ui.radioMapDiffRis) ui.radioMapDiffRis.checked = Boolean(radio.diff_ris);
  if (ui.toggleHeatmap && radio.plot_style) {
    ui.toggleHeatmap.checked = radio.plot_style !== "sionna";
  }
  refreshHeatmap();
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
    setInputValue(ui.radioMapPlaneZ, radio.center[2]);
  } else {
    setInputValue(ui.radioMapCenterX, null);
    setInputValue(ui.radioMapCenterY, null);
    setInputValue(ui.radioMapCenterZ, null);
    setInputValue(ui.radioMapPlaneZ, null);
  }
}

function applyCustomDefaults(config) {
  const sim = (config && config.data && config.data.simulation) || {};
  setInputValue(ui.customMaxDepth, sim.max_depth);
  setInputValue(ui.customSamplesPerSrc, sim.samples_per_src);
  setInputValue(ui.customMaxPathsPerSrc, sim.max_num_paths_per_src);
  if (ui.customFrequencyHz) {
    ui.customFrequencyHz.value = sim.frequency_hz ? Number(sim.frequency_hz).toExponential(3) : "";
  }
  const radio = (config && config.data && config.data.radio_map) || {};
  setInputValue(ui.customSamplesPerTx, radio.samples_per_tx);
  const runtime = (config && config.data && config.data.runtime) || {};
  if (runtime.force_cpu) {
    ui.customBackend.value = "cpu";
  } else if (runtime.prefer_gpu) {
    ui.customBackend.value = "gpu";
  }
}

function applySimTuningDefaults(config) {
  const sim = (config && config.data && config.data.simulation) || {};
  const scale = sim.scale_similarity || {};
  if (ui.simScaleEnabled) ui.simScaleEnabled.checked = Boolean(scale.enabled);
  setInputValue(ui.simScaleFactor, scale.factor);

  const sampling = sim.sampling_boost || {};
  if (ui.simSamplingEnabled) ui.simSamplingEnabled.checked = Boolean(sampling.enabled);
  setInputValue(ui.simMapResMult, sampling.map_resolution_multiplier);
  setInputValue(ui.simRaySamplesMult, sampling.ray_samples_multiplier);
  setInputValue(ui.simMaxDepthAdd, sampling.max_depth_add);
  state.simTuningDirty = false;
}

function resetMarkersFromConfig(config) {
  const scene = (config && config.data && config.data.scene) || {};
  const tx = scene.tx || {};
  const rx = scene.rx || {};
  if (Array.isArray(tx.position) && tx.position.length >= 3) {
    state.markers.tx = [tx.position[0], tx.position[1], tx.position[2]];
  }
  if (Array.isArray(rx.position) && rx.position.length >= 3) {
    state.markers.rx = [rx.position[0], rx.position[1], rx.position[2]];
  }
  const ris = (config && config.data && config.data.ris) || {};
  if (Array.isArray(ris.objects) && ris.objects.length) {
    state.markers.ris = ris.objects.map((obj) => obj.position || [0, 0, 0]);
  } else {
    state.markers.ris = [];
  }
  state.sceneOverride = JSON.parse(JSON.stringify(scene));
  state.sceneOverrideDirty = true;
  updateInputs();
  rebuildScene();
}

function applyRisSimDefaults(config) {
  const ris = (config && config.data && config.data.ris) || {};
  if (ui.simRisEnabled) ui.simRisEnabled.checked = Boolean(ris.enabled);
  if (ui.risGeomMode) ui.risGeomMode.value = ris.geometry_mode || "legacy";
  const size = ris.size || {};
  setInputValue(ui.risWidthM, size.width_m);
  setInputValue(ui.risHeightM, size.height_m);
  setInputValue(ui.risTargetDxM, size.target_dx_m);
  if (ui.risSquareGrid) ui.risSquareGrid.checked = true;
  const spacing = ris.spacing || {};
  setInputValue(ui.risDxM, spacing.dx_m);
  setInputValue(ui.risNx, spacing.num_cells_x);
  setInputValue(ui.risNy, spacing.num_cells_y);
  if (ui.risList) {
    clearRisList();
    if (Array.isArray(ris.objects) && ris.objects.length) {
      ris.objects.forEach((obj) => addRisItem(obj));
    } else {
      addRisItem();
    }
  }
}

function updateRisGeometryVisibility() {
  const mode = ui.risGeomMode ? ui.risGeomMode.value : "legacy";
  const showSize = mode === "size_driven";
  const showSpacing = mode === "spacing_driven";
  document.querySelectorAll(".ris-size-fields").forEach((el) => {
    el.style.display = showSize ? "" : "none";
  });
  document.querySelectorAll(".ris-spacing-fields").forEach((el) => {
    el.style.display = showSpacing ? "" : "none";
  });
  if (ui.risSquareGrid) {
    ui.risSquareGrid.style.display = mode === "legacy" ? "none" : "";
    if (mode !== "legacy") ui.risSquareGrid.checked = true;
  }
}

function updateCustomVisibility() {
  const isCustom = ui.runProfile.value === "custom" || ui.runProfile.value === "indoor_box_high";
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
  applySimTuningDefaults(getProfileConfig());
  applyRisSimDefaults(getProfileConfig());
  updateRisGeometryVisibility();
  updateCustomVisibility();
  if (state.activeTab === "indoor" && !state.indoorInitialized) {
    applyIndoorDefaults();
    state.indoorInitialized = true;
  }
}

async function fetchRuns() {
  const res = await fetch("/api/runs");
  const data = await res.json();
  state.runs = data.runs || [];
  const previous = state.runId;
  const previousDiff = ui.radioMapDiffRun ? ui.radioMapDiffRun.value : null;
  ui.runSelect.innerHTML = "";
  if (ui.radioMapDiffRun) ui.radioMapDiffRun.innerHTML = "";
  state.runs.forEach((run) => {
    const opt = document.createElement("option");
    opt.value = run.run_id;
    opt.textContent = run.run_id;
    ui.runSelect.appendChild(opt);

    if (ui.radioMapDiffRun) {
      const diffOpt = document.createElement("option");
      diffOpt.value = run.run_id;
      diffOpt.textContent = run.run_id;
      ui.radioMapDiffRun.appendChild(diffOpt);
    }
  });
  if (data.runs.length > 0) {
    state.runId = data.runs.find((r) => r.run_id === previous)?.run_id || data.runs[0].run_id;
    ui.runSelect.value = state.runId;
    if (ui.radioMapDiffRun) {
      ui.radioMapDiffRun.value = previousDiff || state.runId;
    }
    await loadRun(state.runId);
  }
}

function _sceneSelectValue(scene) {
  if (!scene || typeof scene !== "object") return "builtin:etoile";
  const type = scene.type || "builtin";
  if (type === "file" && scene.file) {
    return `file:${scene.file}`;
  }
  if (type === "builtin") {
    return `builtin:${scene.builtin || "etoile"}`;
  }
  return "builtin:etoile";
}

async function fetchBuiltinScenes() {
  if (!ui.sceneSelect) return;
  const res = await fetch("/api/scenes");
  if (!res.ok) {
    if (ui.sceneSelect) {
      ui.sceneSelect.innerHTML = "<option value=\"\">(no scenes)</option>";
    }
    return;
  }
  const data = await res.json();
  const builtinScenes = data.scenes || [];
  state.builtinScenes = builtinScenes;
  if (ui.sceneSelect) {
    let fileScenes = [];
    try {
      const fileRes = await fetch("/api/scene_files");
      if (fileRes.ok) {
        const fileData = await fileRes.json();
        fileScenes = fileData.scenes || [];
      }
    } catch (err) {
      fileScenes = [];
    }
    ui.sceneSelect.innerHTML = "";
    builtinScenes.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = `builtin:${name}`;
      opt.textContent = name;
      ui.sceneSelect.appendChild(opt);
    });
    if (fileScenes.length) {
      const spacer = document.createElement("option");
      spacer.disabled = true;
      spacer.textContent = "──────────";
      ui.sceneSelect.appendChild(spacer);
      fileScenes.forEach((entry) => {
        const opt = document.createElement("option");
        opt.value = `file:${entry.path}`;
        opt.textContent = entry.label || entry.path;
        ui.sceneSelect.appendChild(opt);
      });
    }
    const selectedValue = _sceneSelectValue(state.sceneOverride);
    const hasOption = Array.from(ui.sceneSelect.options).some((opt) => opt.value === selectedValue);
    ui.sceneSelect.value = hasOption ? selectedValue : "builtin:etoile";
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
  await refreshRisRunSelect();
  const runExists = (job) => job && job.run_id && state.ris.runs.includes(job.run_id);
  const current = [active, running, latest].find((job) => job && (job.status === "running" || runExists(job)));
  if (current) {
    state.ris.activeJobId = current.job_id;
    state.ris.activeRunId = current.run_id;
    setRisStatus(`${current.run_id} · ${current.status || "running"}`);
  } else {
    setRisStatus("Idle.");
    state.ris.activeJobId = null;
    state.ris.activeRunId = null;
  }
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
  const defaultPlot = state.ris.selectedPlot || "phase_map.png";
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

async function fetchCcJobs() {
  const data = await fetchJsonMaybe("/api/cc/jobs");
  return data || { jobs: [] };
}

function renderCcJobList(jobs) {
  ui.ccJobList.innerHTML = "";
  const sorted = [...jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const recent = sorted.slice(-5).reverse();
  recent.forEach((job) => {
    const item = document.createElement("div");
    const status = job.status || "unknown";
    const error = job.error ? ` · ERROR: ${job.error}` : "";
    item.textContent = `${job.run_id} · ${status}${error}`;
    ui.ccJobList.appendChild(item);
  });
}

async function refreshCcRunSelect() {
  const data = await fetchJsonMaybe("/api/runs");
  const runIds = [];
  for (const run of (data && data.runs ? data.runs : [])) {
    runIds.push(run.run_id);
  }
  const sorted = runIds.sort((a, b) => b.localeCompare(a));
  const previous = ui.ccRunSelect.value;
  ui.ccRunSelect.innerHTML = "";
  sorted.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.ccRunSelect.appendChild(opt);
  });
  if (sorted.length > 0) {
    ui.ccRunSelect.value = sorted.includes(previous) ? previous : sorted[0];
  }
  state.cc.runs = sorted;
}

async function refreshCcProgressAndLog() {
  const runId = state.cc.activeRunId;
  if (!runId) {
    ui.ccProgress.textContent = "";
    ui.ccLog.textContent = "";
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
    ui.ccProgress.textContent = `${progress.status || "running"} · ${stepLabel} ${pctLabel}${error}`.trim();
  } else {
    ui.ccProgress.textContent = "Progress unavailable.";
  }
  const logText = await fetchTextMaybe(`/runs/${runId}/job.log`);
  ui.ccLog.textContent = logText ? tailLines(logText, 120) : "No log available.";
}

async function refreshCcJobs() {
  const data = await fetchCcJobs();
  state.cc.jobs = data.jobs || [];
  renderCcJobList(state.cc.jobs);
  const sorted = [...state.cc.jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const running = sorted.find((job) => job.status === "running");
  const latest = sorted[sorted.length - 1];
  const active = state.cc.activeJobId
    ? sorted.find((job) => job.job_id === state.cc.activeJobId)
    : null;
  await refreshCcRunSelect();
  const runExists = (job) => job && job.run_id && state.cc.runs.includes(job.run_id);
  const current = [active, running, latest].find((job) => job && (job.status === "running" || runExists(job)));
  if (current) {
    state.cc.activeJobId = current.job_id;
    state.cc.activeRunId = current.run_id;
    setCcStatus(`${current.run_id} · ${current.status || "running"}`);
  } else {
    setCcStatus("Idle.");
    state.cc.activeJobId = null;
    state.cc.activeRunId = null;
  }
  await refreshCcProgressAndLog();
  if (state.cc.activeRunId) {
    ui.ccRunSelect.value = state.cc.activeRunId;
  }
}

function parseWaypoints(text) {
  if (!text) return [];
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => line.split(",").map((v) => parseFloat(v.trim())))
    .filter((vals) => vals.length === 3 && vals.every((v) => Number.isFinite(v)));
}

async function submitCcJob() {
  const source = ui.ccConfigSource ? ui.ccConfigSource.value : "preset";
  const payload = { kind: "channel_charting" };
  if (source === "file") {
    let configPath = ui.ccConfigPath.value.trim();
    if (!configPath && ui.ccConfigPath.placeholder) {
      configPath = ui.ccConfigPath.placeholder;
    }
    if (!configPath) {
      setCcStatus("Config path required.");
      return;
    }
    payload.base_config = configPath;
  } else {
    payload.base_config = ui.ccPreset.value;
  }

  if (ui.ccUseScene && ui.ccUseScene.checked) {
    if (state.sceneOverride) {
      payload.scene = JSON.parse(JSON.stringify(state.sceneOverride));
    }
  }
  if (ui.ccUseMarkers && ui.ccUseMarkers.checked) {
    payload.scene = payload.scene || {};
    payload.scene.tx = Object.assign(payload.scene.tx || {}, { position: state.markers.tx });
    payload.scene.rx = Object.assign(payload.scene.rx || {}, { position: state.markers.rx });
  }

  const cc = {};
  if (ui.ccRole && ui.ccRole.value) {
    cc.role = ui.ccRole.value;
  }
  const traj = {};
  const trajType = ui.ccTrajectoryType ? ui.ccTrajectoryType.value : "straight";
  traj.type = trajType;
  const steps = readNumber(ui.ccTrajectorySteps);
  const dt = readNumber(ui.ccTrajectoryDt);
  if (steps !== null) traj.num_steps = Math.max(1, Math.round(steps));
  if (dt !== null) traj.dt_s = dt;
  const start = [readNumber(ui.ccStartX), readNumber(ui.ccStartY), readNumber(ui.ccStartZ)];
  if (start.every((v) => v !== null)) traj.start = start;
  const end = [readNumber(ui.ccEndX), readNumber(ui.ccEndY), readNumber(ui.ccEndZ)];
  if (end.every((v) => v !== null)) traj.end = end;
  if (trajType === "waypoints") {
    const wp = parseWaypoints(ui.ccWaypoints ? ui.ccWaypoints.value : "");
    if (wp.length) traj.waypoints = wp;
  } else if (trajType === "random_walk") {
    const stepStd = readNumber(ui.ccRwStepStd);
    const smoothAlpha = readNumber(ui.ccRwSmooth);
    traj.random_walk = {};
    if (stepStd !== null) traj.random_walk.step_std = stepStd;
    if (smoothAlpha !== null) traj.random_walk.smooth_alpha = smoothAlpha;
  } else if (trajType === "spiral") {
    const r0 = readNumber(ui.ccSpiralR0);
    const r1 = readNumber(ui.ccSpiralR1);
    const turns = readNumber(ui.ccSpiralTurns);
    traj.spiral = {};
    if (r0 !== null) traj.spiral.radius_start = r0;
    if (r1 !== null) traj.spiral.radius_end = r1;
    if (turns !== null) traj.spiral.turns = turns;
  }
  cc.trajectory = traj;

  const csi = { type: ui.ccCsiType ? ui.ccCsiType.value : "cfr" };
  if (csi.type === "cfr") {
    const sc = readNumber(ui.ccSubcarriers);
    const spacing = readNumber(ui.ccSubcarrierSpacing);
    csi.ofdm = {};
    if (sc !== null) csi.ofdm.num_subcarriers = Math.round(sc);
    if (spacing !== null) csi.ofdm.subcarrier_spacing_hz = spacing;
  }
  if (csi.type === "cir") {
    const sampling = readNumber(ui.ccCirSampling);
    const stepsCir = readNumber(ui.ccCirSteps);
    csi.cir = {};
    if (sampling !== null) csi.cir.sampling_frequency_hz = sampling;
    if (stepsCir !== null) csi.cir.num_time_steps = Math.round(stepsCir);
  }
  if (csi.type === "taps") {
    const bw = readNumber(ui.ccTapsBw);
    const lmin = readNumber(ui.ccTapsLmin);
    const lmax = readNumber(ui.ccTapsLmax);
    csi.taps = {};
    if (bw !== null) csi.taps.bandwidth_hz = bw;
    if (lmin !== null) csi.taps.l_min = Math.round(lmin);
    if (lmax !== null) csi.taps.l_max = Math.round(lmax);
  }
  cc.csi = csi;

  const features = { type: ui.ccFeatureType ? ui.ccFeatureType.value : "r2m" };
  const window = readNumber(ui.ccFeatureWindow);
  if (window !== null) features.window = Math.max(1, Math.round(window));
  const beamspace = ui.ccFeatureBeamspace ? ui.ccFeatureBeamspace.checked : true;
  if (features.type === "beamspace_mag") {
    features.beamspace_mag = { beamspace };
  } else {
    features.r2m = { beamspace };
  }
  cc.features = features;

  if (ui.ccOverrideModel && ui.ccOverrideModel.checked) {
    const model = {};
    const embedDim = readNumber(ui.ccEmbedDim);
    const epochs = readNumber(ui.ccEpochs);
    const lr = readNumber(ui.ccLr);
    const adj = readNumber(ui.ccAdjWeight);
    if (embedDim !== null) model.embedding_dim = Math.round(embedDim);
    if (epochs !== null) model.epochs = Math.round(epochs);
    if (lr !== null) model.learning_rate = lr;
    if (adj !== null) model.adjacency_weight = adj;
    cc.model = model;
  }

  const tracking = {};
  if (ui.ccTrackingEnabled) tracking.enabled = ui.ccTrackingEnabled.checked;
  const alpha = readNumber(ui.ccTrackingAlpha);
  if (alpha !== null) tracking.alpha = alpha;
  cc.tracking = tracking;

  const evaluation = {};
  const dims = readNumber(ui.ccEvalDims);
  if (dims !== null) evaluation.dims = Math.round(dims);
  cc.evaluation = evaluation;

  payload.channel_charting = cc;

  setCcStatus("Submitting channel charting job...");
  try {
    const res = await fetch("/api/cc/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      setCcStatus(`CC job error: ${data.error || res.status}`);
    } else {
      state.cc.activeRunId = data.run_id;
      state.cc.activeJobId = data.job_id;
      setCcStatus(`CC job submitted: ${data.run_id}`);
    }
    await refreshCcJobs();
    await refreshCcProgressAndLog();
  } catch (err) {
    setCcStatus("CC job error: network failure");
  }
}

async function loadCcResults(runId) {
  if (!runId) {
    setCcResultStatus("Select a run to load results.");
    renderCcMetrics(null);
    if (ui.ccPlotImage) ui.ccPlotImage.src = "";
    return;
  }
  state.cc.activeRunId = runId;
  setCcResultStatus(`Loading ${runId}...`);
  const manifest = await fetchJsonMaybe(`/runs/${runId}/manifest.json`);
  renderCcMetrics(manifest ? manifest.metrics : null);
  const defaultPlot = state.cc.selectedPlot || "chart_raw.png";
  renderCcPlotSingle(runId, defaultPlot);
  if (ui.ccPlotTabs) {
    ui.ccPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.plot === defaultPlot);
    });
  }
  if (!manifest) {
    setCcResultStatus("manifest.json not found for this run.");
    return;
  }
  setCcResultStatus("Results loaded.");
}

async function loadRun(runId) {
  state.runId = runId;
  setMeta(`Loading ${runId}...`);
  try {
    const [markers, paths, manifest, heatmap, radioPlots, runInfo] = await Promise.all([
      fetch(`/runs/${runId}/viewer/markers.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/runs/${runId}/viewer/paths.json`).then((r) => (r.ok ? r.json() : [])),
      fetch(`/runs/${runId}/viewer/scene_manifest.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/runs/${runId}/viewer/heatmap.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/runs/${runId}/viewer/radio_map_plots.json`).then((r) => (r.ok ? r.json() : null)),
      fetchRunDetails(runId),
    ]);
    state.markers = markers || state.markers;
    if (!state.markers.ris) {
      state.markers.ris = [];
    }
    state.paths = paths || [];
    state.manifest = manifest;
    state.heatmap = heatmap;
    state.radioMapPlots = (radioPlots && radioPlots.plots) ? radioPlots.plots : [];
    state.runInfo = runInfo;
    if (state.markers.ris.length === 0) {
      const risObjects = (runInfo && runInfo.config && runInfo.config.ris && runInfo.config.ris.objects) || [];
      if (Array.isArray(risObjects) && risObjects.length) {
        state.markers.ris = risObjects.map((obj) => obj.position || [0, 0, 0]);
      }
    }
    const configWrapper = runInfo && runInfo.config ? { data: runInfo.config } : getProfileConfig();
    if (state.markers.ris.length === 0) {
      const risObjects = (configWrapper.data && configWrapper.data.ris && configWrapper.data.ris.objects) || [];
      if (Array.isArray(risObjects) && risObjects.length) {
        state.markers.ris = risObjects.map((obj) => obj.position || [0, 0, 0]);
      }
    }
    updateInputs();
    renderRunStats();
    updateHeatmapControls();
    updateRadioMapPreview();
    applyRadioMapDefaults(configWrapper);
    if (!state.simTuningDirty) {
      applySimTuningDefaults(configWrapper);
    }
    applyRisSimDefaults(configWrapper);
    applyUiSnapshot();
    updateSceneOverrideTxFromUi();
    rebuildScene();
    renderPathTable();
    renderPathStats();
    setMeta(`${runId} · ${state.paths.length} paths`);
    if (ui.radioMapDiffToggle && ui.radioMapDiffToggle.checked) {
      await refreshHeatmapDiff();
    }
  } catch (err) {
    console.error("Load run failed:", err);
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
  const sceneCfg = state.sceneOverride || (state.runInfo && state.runInfo.config && state.runInfo.config.scene) || {};
  const txCfg = sceneCfg.tx || {};
  const txLookAt = Array.isArray(txCfg.look_at) ? txCfg.look_at : null;
  const lookAtRis = Boolean(txCfg.look_at_ris);
  if (ui.txLookAtRis) ui.txLookAtRis.checked = lookAtRis;
  if (lookAtRis && Array.isArray(state.markers.ris) && state.markers.ris.length) {
    const risPos = state.markers.ris[0];
    if (ui.txLookX) setInputValue(ui.txLookX, risPos[0]);
    if (ui.txLookY) setInputValue(ui.txLookY, risPos[1]);
    if (ui.txLookZ) setInputValue(ui.txLookZ, risPos[2]);
  } else {
    if (ui.txLookX) setInputValue(ui.txLookX, txLookAt ? txLookAt[0] : null);
    if (ui.txLookY) setInputValue(ui.txLookY, txLookAt ? txLookAt[1] : null);
    if (ui.txLookZ) setInputValue(ui.txLookZ, txLookAt ? txLookAt[2] : null);
  }
  if (ui.txPowerDbm && txCfg.power_dbm !== undefined && txCfg.power_dbm !== null) {
    setInputValue(ui.txPowerDbm, txCfg.power_dbm);
  }
  const txOrientation = Array.isArray(txCfg.orientation) ? txCfg.orientation : null;
  if (ui.txYawDeg) {
    const yaw = txOrientation && txOrientation.length >= 3 ? txOrientation[2] : null;
    setInputValue(ui.txYawDeg, yaw !== null ? (yaw * 180) / Math.PI : null);
  }
  const arraysCfg = sceneCfg.arrays || {};
  const txArr = arraysCfg.tx || {};
  if (ui.txPattern && txArr.pattern) ui.txPattern.value = txArr.pattern;
  if (ui.txPolarization && txArr.polarization) ui.txPolarization.value = txArr.polarization;
  if (ui.risList) {
    ui.risList.querySelectorAll(".ris-item").forEach((node) => {
      const autoAim = node.querySelector('[data-field="autoAim"]');
      if (!autoAim || !autoAim.checked) return;
      const setVal = (name, value) => {
        const el = node.querySelector(`[data-field="${name}"]`);
        if (el) el.value = value;
      };
      setVal("sourceX", state.markers.tx[0]);
      setVal("sourceY", state.markers.tx[1]);
      setVal("sourceZ", state.markers.tx[2]);
      setVal("targetX", state.markers.rx[0]);
      setVal("targetY", state.markers.rx[1]);
      setVal("targetZ", state.markers.rx[2]);
    });
  }
}

function updateSceneOverrideTxFromUi() {
  const sceneCfg = state.sceneOverride || {};
  sceneCfg.tx = Object.assign(sceneCfg.tx || {}, { position: state.markers.tx });
  const txPower = readNumber(ui.txPowerDbm);
  if (txPower !== null) {
    sceneCfg.tx.power_dbm = txPower;
  } else if (sceneCfg.tx && "power_dbm" in sceneCfg.tx) {
    delete sceneCfg.tx.power_dbm;
  }
  const lookAtRis = ui.txLookAtRis ? ui.txLookAtRis.checked : false;
  const lookX = readNumber(ui.txLookX);
  const lookY = readNumber(ui.txLookY);
  const lookZ = readNumber(ui.txLookZ);
  if (lookAtRis) {
    if (Array.isArray(state.markers.ris) && state.markers.ris.length) {
      const risPos = state.markers.ris[0];
      sceneCfg.tx.look_at = [risPos[0], risPos[1], risPos[2]];
      sceneCfg.tx.look_at_ris = true;
      if ("orientation" in sceneCfg.tx) delete sceneCfg.tx.orientation;
      if (ui.txLookX) ui.txLookX.value = risPos[0];
      if (ui.txLookY) ui.txLookY.value = risPos[1];
      if (ui.txLookZ) ui.txLookZ.value = risPos[2];
    } else {
      if (sceneCfg.tx && "look_at_ris" in sceneCfg.tx) delete sceneCfg.tx.look_at_ris;
      setMeta("Tx look-at RIS: no RIS objects available");
    }
  } else if (lookX !== null && lookY !== null && lookZ !== null) {
    sceneCfg.tx.look_at = [lookX, lookY, lookZ];
    if ("orientation" in sceneCfg.tx) delete sceneCfg.tx.orientation;
    if (sceneCfg.tx && "look_at_ris" in sceneCfg.tx) delete sceneCfg.tx.look_at_ris;
  } else if (sceneCfg.tx && "look_at" in sceneCfg.tx) {
    delete sceneCfg.tx.look_at;
    if (sceneCfg.tx && "look_at_ris" in sceneCfg.tx) delete sceneCfg.tx.look_at_ris;
  }
  const yawDeg = readNumber(ui.txYawDeg);
  if (yawDeg !== null && (sceneCfg.tx.look_at === undefined || sceneCfg.tx.look_at === null)) {
    const yawRad = (yawDeg * Math.PI) / 180.0;
    sceneCfg.tx.orientation = [0.0, 0.0, yawRad];
  } else if (sceneCfg.tx && "orientation" in sceneCfg.tx) {
    delete sceneCfg.tx.orientation;
  }
  const txPattern = ui.txPattern && ui.txPattern.value ? ui.txPattern.value : "iso";
  const txPol = ui.txPolarization && ui.txPolarization.value ? ui.txPolarization.value : "V";
  sceneCfg.arrays = sceneCfg.arrays || {};
  sceneCfg.arrays.tx = Object.assign(sceneCfg.arrays.tx || {}, {
    pattern: txPattern,
    polarization: txPol,
  });
  state.sceneOverride = sceneCfg;
  state.sceneOverrideDirty = true;
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
  const risPaths = metrics.num_ris_paths ?? "n/a";
  const maxDepth = sim.max_depth ?? "n/a";
  const rxPower = metrics.rx_power_dbm_estimate !== undefined ? metrics.rx_power_dbm_estimate.toFixed(2) : "n/a";
  const pathGain = metrics.total_path_gain_db !== undefined ? metrics.total_path_gain_db.toFixed(2) : "n/a";
  let risGeometryLine = "";
  const risObjects = info && info.summary && info.summary.runtime ? info.summary.runtime.ris_objects : null;
  if (Array.isArray(risObjects) && risObjects.length && risObjects[0].geometry) {
    const geom = risObjects[0].geometry;
    const dx = typeof geom.dx_m === "number" ? geom.dx_m.toFixed(6) : "n/a";
    const dy = typeof geom.dy_m === "number" ? geom.dy_m.toFixed(6) : "n/a";
    const nx = geom.nx ?? "n/a";
    const ny = geom.ny ?? "n/a";
    let total = geom.num_elements;
    if (total === undefined && typeof nx === "number" && typeof ny === "number") {
      total = nx * ny;
    }
    const totalText = total !== undefined ? ` N=${total}` : "";
    risGeometryLine = `<div><strong>RIS geometry:</strong> Nx=${nx} Ny=${ny}${totalText} · dx=${dx} dy=${dy}</div>`;
  }
  ui.runStats.innerHTML = `
    <div><strong>Frequency:</strong> ${freqGHz} GHz</div>
    <div><strong>Max depth:</strong> ${maxDepth}</div>
    <div><strong>Valid paths:</strong> ${numPaths}</div>
    <div><strong>RIS paths:</strong> ${risPaths}</div>
    <div><strong>Total path gain:</strong> ${pathGain} dB</div>
    <div><strong>Rx power (est.):</strong> ${rxPower} dBm</div>
    ${risGeometryLine}
    <div><strong>Scene:</strong> ${sceneLabel}</div>
  `;
}

function updateHeatmapControls() {
  const active = getActiveHeatmap();
  if (!active || !active.values) {
    updateHeatmapScaleVisibility(false);
    return;
  }
  const values = active.values.flat();
  let min = Infinity;
  let max = -Infinity;
  values.forEach((v) => {
    if (v < min) min = v;
    if (v > max) max = v;
  });
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
    : Boolean(ui.toggleHeatmap.checked && getActiveHeatmap() && getActiveHeatmap().values);
  ui.heatmapScale.classList.toggle("is-hidden", !visible);
}

function getRisGeometryForIndex(idx) {
  const runtime = state.runInfo && state.runInfo.summary && state.runInfo.summary.runtime
    ? state.runInfo.summary.runtime.ris_objects
    : null;
  if (Array.isArray(runtime) && runtime[idx] && runtime[idx].geometry) {
    return runtime[idx].geometry;
  }
  const mode = ui.risGeomMode ? ui.risGeomMode.value : "legacy";
  if (!mode || mode === "legacy") return null;
  if (mode === "size_driven") {
    const width = readNumber(ui.risWidthM);
    const height = readNumber(ui.risHeightM);
    const targetDx = readNumber(ui.risTargetDxM);
    if (width === null || height === null || targetDx === null) return null;
    const nx = Math.max(1, Math.round(width / targetDx) + 1);
    const ny = Math.max(1, Math.round(height / targetDx) + 1);
    const dx = nx > 1 ? width / (nx - 1) : width;
    const dy = ny > 1 ? height / (ny - 1) : height;
    return { width_m: width, height_m: height, nx, ny, dx_m: dx, dy_m: dy };
  }
  if (mode === "spacing_driven") {
    const dx = readNumber(ui.risDxM);
    const nx = readNumber(ui.risNx);
    const ny = readNumber(ui.risNy);
    if (dx === null || nx === null || ny === null) return null;
    const width = (nx - 1) * dx;
    const height = (ny - 1) * dx;
    return { width_m: width, height_m: height, nx, ny, dx_m: dx, dy_m: dx };
  }
  return null;
}

function updateRadioMapPreview() {
  if (!ui.radioMapPreviewSelect || !ui.radioMapPreviewImage) return;
  const plots = state.radioMapPlots || [];
  ui.radioMapPreviewSelect.innerHTML = "";
  if (!plots.length) {
    ui.radioMapPreviewSelect.innerHTML = "<option value=\"\">(no plots)</option>";
    ui.radioMapPreviewImage.src = "";
    return;
  }
  plots.forEach((plot) => {
    const opt = document.createElement("option");
    opt.value = plot.file;
    opt.textContent = plot.label || plot.file;
    ui.radioMapPreviewSelect.appendChild(opt);
  });
  const selected = ui.radioMapPreviewSelect.value || plots[0].file;
  ui.radioMapPreviewSelect.value = selected;
  ui.radioMapPreviewImage.src = `/runs/${state.runId}/viewer/${selected}`;
}

function getActiveHeatmap() {
  if (ui.radioMapDiffToggle && ui.radioMapDiffToggle.checked) {
    return state.heatmapDiff;
  }
  return state.heatmap;
}

async function loadHeatmapForRun(runId) {
  const res = await fetch(`/runs/${runId}/viewer/heatmap.json`);
  if (!res.ok) return null;
  return await res.json();
}

function computeHeatmapDiff(current, base) {
  if (!current || !base) return null;
  if (!current.values || !base.values) return null;
  if (current.values.length !== base.values.length) return null;
  const height = current.values.length;
  const width = current.values[0].length || 0;
  if (!width) return null;
  if (base.values[0].length !== width) return null;
  const diffValues = [];
  for (let y = 0; y < height; y++) {
    const row = [];
    for (let x = 0; x < width; x++) {
      row.push(current.values[y][x] - base.values[y][x]);
    }
    diffValues.push(row);
  }
  return {
    metric: `diff_${current.metric || "map"}`,
    grid_shape: current.grid_shape,
    values: diffValues,
    cell_centers: current.cell_centers,
    center: current.center,
    size: current.size,
    cell_size: current.cell_size,
    orientation: current.orientation,
  };
}

async function refreshHeatmapDiff() {
  if (!ui.radioMapDiffToggle || !ui.radioMapDiffToggle.checked) {
    state.heatmapDiff = null;
    updateHeatmapControls();
    refreshHeatmap();
    return;
  }
  const baseRun = ui.radioMapDiffRun ? ui.radioMapDiffRun.value : null;
  if (!baseRun || !state.heatmap) {
    state.heatmapDiff = null;
    updateHeatmapControls();
    refreshHeatmap();
    return;
  }
  const base = await loadHeatmapForRun(baseRun);
  const diff = computeHeatmapDiff(state.heatmap, base);
  if (!diff) {
    setMeta("Heatmap diff failed: grid mismatch");
    state.heatmapDiff = null;
  } else {
    state.heatmapDiff = diff;
  }
  updateHeatmapControls();
  refreshHeatmap();
}

function rebuildScene() {
  geometryGroup.clear();
  markerGroup.clear();
  rayGroup.clear();
  heatmapGroup.clear();
  alignmentGroup.clear();
  highlightLine = null;

  if (ui.simRisEnabled && ui.simRisEnabled.checked) {
    const risItems = readRisItems();
    state.markers.ris = risItems.map((item) => item.position || [0, 0, 0]);
  } else {
    state.markers.ris = [];
  }

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

function getMeshRotationRad() {
  const base = state.manifest && Array.isArray(state.manifest.mesh_rotation_deg)
    ? state.manifest.mesh_rotation_deg
    : [0, 0, 0];
  const bx = (parseFloat(base[0]) || 0) * Math.PI / 180;
  const by = (parseFloat(base[1]) || 0) * Math.PI / 180;
  const bz = (parseFloat(base[2]) || 0) * Math.PI / 180;
  return [bx, by, bz];
}

async function loadMeshes() {
  if (!state.manifest) {
    return;
  }
  const [rotX, rotY, rotZ] = getMeshRotationRad();
  if (state.manifest.mesh) {
    const ext = state.manifest.mesh.split(".").pop().toLowerCase();
    if (ext === "glb" || ext === "gltf") {
      const loader = new GLTFLoader();
      loader.load(`/runs/${state.runId}/viewer/${state.manifest.mesh}`, (gltf) => {
        gltf.scene.rotation.set(rotX, rotY, rotZ);
        geometryGroup.add(gltf.scene);
        refreshHeatmap();
      });
    } else if (ext === "obj") {
      const loader = new OBJLoader();
      loader.load(`/runs/${state.runId}/viewer/${state.manifest.mesh}`, (obj) => {
        obj.rotation.set(rotX, rotY, rotZ);
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
        mesh.rotation.set(rotX, rotY, rotZ);
        geometryGroup.add(mesh);
        refreshHeatmap();
      });
    });
  }
}

function addMarkers() {
  const markerRadius = getMarkerRadius();
  const txMat = new THREE.MeshStandardMaterial({ color: 0xdc2626, emissive: 0xdc2626, emissiveIntensity: 0.4 });
  const rxMat = new THREE.MeshStandardMaterial({ color: 0x2563eb, emissive: 0x2563eb, emissiveIntensity: 0.4 });
  const geo = new THREE.SphereGeometry(markerRadius, 16, 16);
  const tx = new THREE.Mesh(geo, txMat);
  const rx = new THREE.Mesh(geo, rxMat);
  tx.name = "tx";
  rx.name = "rx";
  tx.position.set(...state.markers.tx);
  rx.position.set(...state.markers.rx);
  markerGroup.add(tx, rx);
  const focusTargets = [];
  if (ui.showTxDirection && ui.showTxDirection.checked) {
    const sceneCfg = state.sceneOverride || (state.runInfo && state.runInfo.config && state.runInfo.config.scene) || {};
    const txCfg = sceneCfg.tx || {};
    const origin = new THREE.Vector3(...state.markers.tx);
    let direction = new THREE.Vector3(1, 0, 0);
    if (Array.isArray(txCfg.look_at) && txCfg.look_at.length >= 3) {
      direction = new THREE.Vector3(
        txCfg.look_at[0] - origin.x,
        txCfg.look_at[1] - origin.y,
        txCfg.look_at[2] - origin.z
      );
    } else if (Array.isArray(txCfg.orientation) && txCfg.orientation.length >= 3) {
      const yaw = txCfg.orientation[2];
      direction = new THREE.Vector3(Math.cos(yaw), Math.sin(yaw), 0);
    }
    if (direction.lengthSq() < 1e-6) {
      direction = new THREE.Vector3(1, 0, 0);
    }
    direction.normalize();
    const arrowLength = Math.max(markerRadius * 8, 1.5);
    const arrowHeadLength = Math.max(markerRadius * 2.0, 0.6);
    const arrowHeadWidth = Math.max(markerRadius * 1.0, 0.4);
    const arrow = new THREE.ArrowHelper(direction, origin, arrowLength, 0xf97316, arrowHeadLength, arrowHeadWidth);
    arrow.name = "tx_direction";
    markerGroup.add(arrow);
  }
  const risMat = new THREE.MeshStandardMaterial({ color: 0x111827, emissive: 0x111827, emissiveIntensity: 0.4 });
  const risFrontColor = 0xf97316;
  const risItems = ui.simRisEnabled && ui.simRisEnabled.checked ? readRisItems() : [];
  const risMarkers = risItems.length ? risItems : (Array.isArray(state.markers.ris) ? state.markers.ris.map((p) => ({ position: p })) : []);
  risMarkers.forEach((item, idx) => {
    const pos = item.position || item;
    if (!Array.isArray(pos) || pos.length < 3) return;
    const geom = getRisGeometryForIndex(idx);
    const width = geom && typeof geom.width_m === "number" ? geom.width_m : 3.5;
    const height = geom && typeof geom.height_m === "number" ? geom.height_m : 3.5;
    const thickness = Math.max(Math.min(width, height) * 0.02, 0.02);
    const risGeo = new THREE.BoxGeometry(thickness, width, height);
    const ris = new THREE.Mesh(risGeo, risMat);
    ris.name = `ris_${idx}`;
    ris.position.set(pos[0], pos[1], pos[2]);
  const orientation = Array.isArray(item.orientation) && item.orientation.length >= 3 ? item.orientation : null;
  let yaw = orientation ? orientation[2] : getRisItemYaw(idx);
  if (!orientation && Array.isArray(item.look_at) && item.look_at.length >= 3) {
    const dx = item.look_at[0] - pos[0];
    const dy = item.look_at[1] - pos[1];
    yaw = Math.atan2(dy, dx);
  }
  const roll = orientation ? orientation[0] : 0;
  const pitch = orientation ? orientation[1] : 0;
    ris.rotation.set(Math.PI / 2 + roll, pitch, yaw);
    markerGroup.add(ris);

    if (ui.toggleRisFront && ui.toggleRisFront.checked) {
      const origin = new THREE.Vector3(pos[0], pos[1], pos[2]);
      let frontDir = new THREE.Vector3(1, 0, 0);
      let target = null;
      if (item.profile) {
        const targets = item.profile.targets;
        if (Array.isArray(targets) && targets.length >= 3 && typeof targets[0] === "number") {
          target = targets;
        } else if (Array.isArray(targets) && Array.isArray(targets[0]) && targets[0].length >= 3) {
          target = targets[0];
        } else if (item.profile.auto_aim && Array.isArray(state.markers.rx)) {
          target = state.markers.rx;
        }
      }
      if (Array.isArray(target) && target.length >= 3) {
        frontDir = new THREE.Vector3(
          target[0] - pos[0],
          target[1] - pos[1],
          target[2] - pos[2]
        );
      } else if (Array.isArray(item.look_at) && item.look_at.length >= 3) {
        frontDir = new THREE.Vector3(
          item.look_at[0] - pos[0],
          item.look_at[1] - pos[1],
          item.look_at[2] - pos[2]
        );
      } else {
        const euler = new THREE.Euler(roll, pitch, yaw, "XYZ");
        frontDir.applyEuler(euler);
      }
      if (frontDir.lengthSq() < 1e-6) {
        frontDir = new THREE.Vector3(1, 0, 0);
      }
      frontDir.normalize();
      const arrowLength = Math.max(Math.min(width, height) * 0.65, 0.6);
      const arrowHeadLength = Math.max(arrowLength * 0.28, 0.25);
      const arrowHeadWidth = Math.max(arrowLength * 0.12, 0.12);
      const arrow = new THREE.ArrowHelper(frontDir, origin, arrowLength, risFrontColor, arrowHeadLength, arrowHeadWidth);
      arrow.name = `ris_front_${idx}`;
      markerGroup.add(arrow);
    }
    if (ui.toggleRisFocus && ui.toggleRisFocus.checked && item.profile) {
      let target = null;
      if (item.profile.auto_aim && Array.isArray(state.markers.rx)) {
        target = state.markers.rx;
      } else if (Array.isArray(item.profile.targets)) {
        const t = item.profile.targets;
        if (t.length >= 3 && typeof t[0] === "number") {
          target = t;
        } else if (Array.isArray(t[0]) && t[0].length >= 3) {
          target = t[0];
        }
      }
      if (Array.isArray(target) && target.length >= 3) {
        focusTargets.push({ target, source: pos });
      }
    }
  });

  if (ui.toggleRisFocus && ui.toggleRisFocus.checked && focusTargets.length) {
    const focusMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0xf59e0b, emissiveIntensity: 0.6 });
    const focusGeo = new THREE.SphereGeometry(Math.max(markerRadius * 0.8, 0.12), 14, 14);
    const lineMat = new THREE.LineBasicMaterial({ color: 0xf59e0b });
    focusTargets.forEach(({ target, source }) => {
      const focus = new THREE.Mesh(focusGeo, focusMat);
      focus.position.set(target[0], target[1], target[2]);
      markerGroup.add(focus);
      const pts = [
        new THREE.Vector3(source[0], source[1], source[2]),
        new THREE.Vector3(target[0], target[1], target[2]),
      ];
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat);
      markerGroup.add(line);
    });
  }
}

function addAlignmentMarkers() {
  const markerRadius = getMarkerRadius();
  // Reference height for markers (slightly above ground)
  const markerZ = Math.max(markerRadius * 1.5, 0.2);
  const axisLength = Math.max(getSceneScale() * 0.6, markerRadius * 12);
  const markerSize = Math.max(markerRadius * 1.2, 0.12);

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
    let xMin = Infinity;
    let xMax = -Infinity;
    let yMin = Infinity;
    let yMax = -Infinity;
    centers.forEach((row) => {
      row.forEach((c) => {
        const x = c[0];
        const y = c[1];
        if (x < xMin) xMin = x;
        if (x > xMax) xMax = x;
        if (y < yMin) yMin = y;
        if (y > yMax) yMax = y;
      });
    });
    xMin -= cellSize[0] * 0.5;
    xMax += cellSize[0] * 0.5;
    yMin -= cellSize[1] * 0.5;
    yMax += cellSize[1] * 0.5;
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
    let xMin = Infinity;
    let xMax = -Infinity;
    let yMin = Infinity;
    let yMax = -Infinity;
    centers.forEach((row) => {
      row.forEach((c) => {
        const x = c[0];
        const y = c[1];
        if (x < xMin) xMin = x;
        if (x > xMax) xMax = x;
        if (y < yMin) yMin = y;
        if (y > yMax) yMax = y;
      });
    });
    if (Number.isFinite(xMin) && Number.isFinite(yMin)) {
      return { xMin, xMax, yMin, yMax };
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
  const active = getActiveHeatmap();
  if (!active) {
    return;
  }
  const values = active.values || [];
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
      const c = (ui.radioMapDiffToggle && ui.radioMapDiffToggle.checked)
        ? heatmapColorDiff(t)
        : heatmapColor(t);
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

  const centers = active.cell_centers || [];
  if (centers.length) {
    let xMin = Infinity;
    let xMax = -Infinity;
    let yMin = Infinity;
    let yMax = -Infinity;
    let zSum = 0;
    let zCount = 0;
    centers.forEach((row) => {
      row.forEach((c) => {
        const x = c[0];
        const y = c[1];
        const zc = c[2];
        if (x < xMin) xMin = x;
        if (x > xMax) xMax = x;
        if (y < yMin) yMin = y;
        if (y > yMax) yMax = y;
        if (Number.isFinite(zc)) {
          zSum += zc;
          zCount += 1;
        }
      });
    });
    const cellSize = active.cell_size || [0, 0];
    widthM = xMax - xMin + (cellSize[0] || 0);
    heightM = yMax - yMin + (cellSize[1] || 0);
    center = [
      (xMax + xMin) / 2,
      (yMax + yMin) / 2,
      zCount ? zSum / zCount : 0,
    ];
    z = center[2];
  } else if (active.size && active.center) {
    widthM = active.size[0];
    heightM = active.size[1];
    center = active.center;
    z = Array.isArray(active.center) ? active.center[2] || 0 : 0;
  } else if (active.grid_shape && active.cell_size && active.center) {
    widthM = active.grid_shape[1] * active.cell_size[0];
    heightM = active.grid_shape[0] * active.cell_size[1];
    center = active.center;
    z = Array.isArray(active.center) ? active.center[2] || 0 : 0;
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

  if (active.orientation && active.orientation.length >= 3) {
    mesh.rotation.set(
      active.orientation[0],
      active.orientation[1],
      active.orientation[2] + uiRotationRad
    );
  } else {
    mesh.rotation.set(0, 0, uiRotationRad);
  }
  heatmapGroup.add(mesh);
  debugHeatmapMesh = mesh;
  heatmapGroup.visible = ui.toggleHeatmap.checked;
}

function _lerpColor(a, b, t) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

function _gradientColor(stops, t) {
  if (t <= 0) return stops[0].color;
  if (t >= 1) return stops[stops.length - 1].color;
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i];
    const b = stops[i + 1];
    if (t >= a.pos && t <= b.pos) {
      const k = (t - a.pos) / (b.pos - a.pos || 1);
      return _lerpColor(a.color, b.color, k);
    }
  }
  return stops[stops.length - 1].color;
}

function heatmapColor(t) {
  const stops = [
    { pos: 0.0, color: [12, 74, 110] },
    { pos: 0.25, color: [20, 184, 166] },
    { pos: 0.5, color: [250, 204, 21] },
    { pos: 0.75, color: [249, 115, 22] },
    { pos: 1.0, color: [220, 38, 38] },
  ];
  return _gradientColor(stops, t);
}

function heatmapColorDiff(t) {
  const stops = [
    { pos: 0.0, color: [30, 64, 175] },
    { pos: 0.35, color: [59, 130, 246] },
    { pos: 0.5, color: [255, 255, 255] },
    { pos: 0.65, color: [248, 113, 113] },
    { pos: 1.0, color: [190, 24, 93] },
  ];
  return _gradientColor(stops, t);
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
  const maxDim = Math.max(size.x, size.y, size.z);
  let radius = Math.max(maxDim * 1.2, 1);
  if (state.viewerScale && state.viewerScale.enabled) {
    const target = Number(state.viewerScale.targetSize) || maxDim;
    if (maxDim > 0 && Number.isFinite(target) && target > 0) {
      const scaleFactor = target / maxDim;
      if (Number.isFinite(scaleFactor) && scaleFactor > 0) {
        radius = radius / scaleFactor;
        radius = Math.max(radius, maxDim * 0.5, 1);
      }
    }
  }
  camera.position.set(center.x + radius, center.y + radius, center.z + radius);
  controls.target.copy(center);
}

function refreshViewerSize() {
  const container = document.getElementById("viewerCanvas");
  if (!container || !renderer || !camera) return;
  const width = container.clientWidth || 1;
  const height = container.clientHeight || 1;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
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
    const target = hits[0].object;
    if (target.name === "tx" || target.name === "rx") {
      dragging = target;
      dragMode = "move";
    } else if (target.name.startsWith("ris_")) {
      dragging = target;
      dragMode = event.shiftKey ? "rotate" : "move";
      dragRisIndex = parseInt(target.name.split("_")[1], 10);
      dragStartYaw = getRisItemYaw(dragRisIndex);
      dragStartMouse = { x: event.clientX, y: event.clientY };
    } else {
      return;
    }
    controls.enabled = false;
  }
}

function onMouseMove(event) {
  if (!dragging) return;
  if (dragMode === "rotate" && dragging.name.startsWith("ris_")) {
    const dx = event.clientX - (dragStartMouse?.x || event.clientX);
    const yaw = dragStartYaw + dx * 0.01;
    dragging.rotation.z = yaw;
    updateRisItemYaw(dragRisIndex, yaw);
    return;
  }
  const mouse = getMouse(event);
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const point = new THREE.Vector3();
  raycaster.ray.intersectPlane(plane, point);
  dragging.position.copy(point);
  if (dragging.name === "tx") {
    state.markers.tx = [point.x, point.y, point.z];
  } else if (dragging.name === "rx") {
    state.markers.rx = [point.x, point.y, point.z];
  } else if (dragging.name.startsWith("ris_")) {
    updateRisItemPosition(dragRisIndex, [point.x, point.y, point.z]);
  }
  updateInputs();
}

function endDrag() {
  if (dragging) {
    dragging = null;
    dragMode = null;
    dragRisIndex = null;
    dragStartMouse = null;
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
  if (state.followLatestRun && newestCompleted && ui.runSelect.value !== newestCompleted) {
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
  if (ui.runProfile.value === "custom" || ui.runProfile.value === "indoor_box_high") {
    const backend = ui.customBackend.value;
    payload.runtime = {
      force_cpu: backend === "cpu",
      prefer_gpu: backend === "gpu",
    };
    const sim = {};
    const maxDepth = readNumber(ui.customMaxDepth);
    const samplesPerSrc = readNumber(ui.customSamplesPerSrc);
    const maxPathsPerSrc = readNumber(ui.customMaxPathsPerSrc);
    const frequencyHz = readScientificNumber(ui.customFrequencyHz);
    if (maxDepth !== null) sim.max_depth = maxDepth;
    if (samplesPerSrc !== null) sim.samples_per_src = samplesPerSrc;
    if (maxPathsPerSrc !== null) sim.max_num_paths_per_src = maxPathsPerSrc;
    if (frequencyHz !== null) sim.frequency_hz = frequencyHz;
    if (Object.keys(sim).length) {
      payload.simulation = sim;
    }
    const radio = { auto_size: ui.radioMapAuto ? ui.radioMapAuto.checked : false };
    const padding = readNumber(ui.radioMapPadding);
    if (padding !== null) {
      radio.auto_padding = padding;
    }
    if (ui.radioMapPlotStyle && ui.radioMapPlotStyle.value) {
      radio.plot_style = ui.radioMapPlotStyle.value;
    }
    if (ui.radioMapPlotMetric && ui.radioMapPlotMetric.value) {
      radio.plot_metrics = [ui.radioMapPlotMetric.value];
    }
    if (ui.radioMapPlotShowTx) {
      radio.plot_show_tx = ui.radioMapPlotShowTx.checked;
    }
    if (ui.radioMapPlotShowRx) {
      radio.plot_show_rx = ui.radioMapPlotShowRx.checked;
    }
    if (ui.radioMapPlotShowRis) {
      radio.plot_show_ris = ui.radioMapPlotShowRis.checked;
    }
    if (ui.radioMapDiffRis) {
      radio.diff_ris = ui.radioMapDiffRis.checked;
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
      payload.radio_map = Object.assign(payload.radio_map || {}, radio);
    }
  }

  // Always allow Z-only heatmap plane control without forcing map size/cell overrides.
  const planeZ = readNumber(ui.radioMapPlaneZ);
  if (planeZ !== null) {
    payload.radio_map = Object.assign(payload.radio_map || {}, { center_z_only: planeZ });
  }

  const scaleEnabled = ui.simScaleEnabled ? ui.simScaleEnabled.checked : false;
  const scaleFactor = readNumber(ui.simScaleFactor);
  const samplingEnabled = ui.simSamplingEnabled ? ui.simSamplingEnabled.checked : false;
  const mapResMult = readNumber(ui.simMapResMult);
  const raySamplesMult = readNumber(ui.simRaySamplesMult);
  const maxDepthAddRaw = readNumber(ui.simMaxDepthAdd);
  const maxDepthAdd = maxDepthAddRaw !== null ? Math.round(maxDepthAddRaw) : null;

  if (scaleEnabled || scaleFactor !== null) {
    const scalePayload = {
      enabled: scaleEnabled || scaleFactor !== null,
    };
    if (scaleFactor !== null) scalePayload.factor = scaleFactor;
    payload.simulation = Object.assign(payload.simulation || {}, {
      scale_similarity: scalePayload,
    });
  }
  if (samplingEnabled || mapResMult !== null || raySamplesMult !== null || maxDepthAdd !== null) {
    const samplingPayload = {
      enabled: samplingEnabled || mapResMult !== null || raySamplesMult !== null || maxDepthAdd !== null,
    };
    if (mapResMult !== null) samplingPayload.map_resolution_multiplier = mapResMult;
    if (raySamplesMult !== null) samplingPayload.ray_samples_multiplier = raySamplesMult;
    if (maxDepthAdd !== null) samplingPayload.max_depth_add = maxDepthAdd;
    payload.simulation = Object.assign(payload.simulation || {}, {
      sampling_boost: samplingPayload,
    });
  }
  if (ui.simComputePaths && !ui.simComputePaths.checked) {
    payload.simulation = Object.assign(payload.simulation || {}, {
      compute_paths: false,
    });
  }
  if (state.activeTab === "indoor" || ui.runProfile.value === "indoor_box_high") {
    payload.simulation = Object.assign(payload.simulation || {}, {
      scale_similarity: { enabled: false, factor: 1.0 },
    });
    if (ui.indoorSkipPaths && ui.indoorSkipPaths.checked) {
      payload.simulation.compute_paths = false;
    }
  }
  const radioStyle = {};
  if (ui.radioMapPlotStyle && ui.radioMapPlotStyle.value) {
    radioStyle.plot_style = ui.radioMapPlotStyle.value;
  }
  if (ui.radioMapPlotMetric && ui.radioMapPlotMetric.value) {
    radioStyle.plot_metrics = [ui.radioMapPlotMetric.value];
  }
  if (ui.radioMapPlotShowTx) radioStyle.plot_show_tx = ui.radioMapPlotShowTx.checked;
  if (ui.radioMapPlotShowRx) radioStyle.plot_show_rx = ui.radioMapPlotShowRx.checked;
  if (ui.radioMapPlotShowRis) radioStyle.plot_show_ris = ui.radioMapPlotShowRis.checked;
  if (ui.radioMapDiffRis) radioStyle.diff_ris = ui.radioMapDiffRis.checked;
  if (Object.keys(radioStyle).length) {
    payload.radio_map = Object.assign(payload.radio_map || {}, radioStyle);
  }

  if (ui.simRisEnabled && ui.simRisEnabled.checked) {
    const objects = readRisItems();
    const geometryMode = ui.risGeomMode ? ui.risGeomMode.value : null;
    const risSize = {};
    const risSpacing = {};
    const widthM = readNumber(ui.risWidthM);
    const heightM = readNumber(ui.risHeightM);
    const targetDx = readNumber(ui.risTargetDxM);
    const dxM = readNumber(ui.risDxM);
    const squareGrid = ui.risSquareGrid ? ui.risSquareGrid.checked : false;
    const nx = readNumber(ui.risNx);
    const ny = readNumber(ui.risNy);
    if (widthM !== null) risSize.width_m = widthM;
    if (heightM !== null) risSize.height_m = heightM;
    if (targetDx !== null) risSize.target_dx_m = targetDx;
    if (dxM !== null) risSpacing.dx_m = dxM;
    if (nx !== null) risSpacing.num_cells_x = Math.max(1, Math.round(nx));
    if (ny !== null) risSpacing.num_cells_y = Math.max(1, Math.round(ny));
    if (geometryMode && geometryMode !== "legacy") {
      if (geometryMode === "size_driven") {
        if (widthM === null || heightM === null || targetDx === null) {
          setMeta("RIS geometry error: size_driven requires width/height + target dx/dy");
          return;
        }
        if (!squareGrid) {
          setMeta("RIS geometry error: only square grid supported (enable dx = dy)");
          return;
        }
        risSize.target_dy_m = risSize.target_dx_m;
      } else if (geometryMode === "spacing_driven") {
        if (dxM === null) {
          setMeta("RIS geometry error: spacing_driven requires dx/dy");
          return;
        }
        if (nx === null || ny === null) {
          setMeta("RIS geometry error: spacing_driven requires num cells x/y");
          return;
        }
        if (!squareGrid) {
          setMeta("RIS geometry error: only square grid supported (enable dx = dy)");
          return;
        }
        risSpacing.dy_m = risSpacing.dx_m;
      }
    }
    const risPayload = { enabled: true, objects };
    if (geometryMode && geometryMode !== "legacy") risPayload.geometry_mode = geometryMode;
    if (Object.keys(risSize).length) risPayload.size = risSize;
    if (Object.keys(risSpacing).length) risPayload.spacing = risSpacing;
    payload.ris = risPayload;
    payload.simulation = Object.assign(payload.simulation || {}, { ris: true });
    payload.radio_map = Object.assign(payload.radio_map || {}, { ris: true });
  }
  // Always honor the scene dropdown selection when submitting a job.
  if (ui.sceneSelect && ui.sceneSelect.value) {
    const value = ui.sceneSelect.value || "";
    if (value.startsWith("file:")) {
      const filePath = value.slice("file:".length);
      state.sceneOverride = { type: "file", file: filePath };
      state.sceneOverrideDirty = true;
    } else if (value.startsWith("builtin:")) {
      const name = value.slice("builtin:".length);
      state.sceneOverride = { type: "builtin", builtin: name };
      state.sceneOverrideDirty = true;
    }
  }
  const profileConfig = getProfileConfig();
  const baseScene = !state.sceneOverrideDirty
    ? ((profileConfig && profileConfig.data && profileConfig.data.scene) || state.sceneOverride || {})
    : (state.sceneOverride || {});
  const scenePayload = JSON.parse(JSON.stringify(baseScene));
  const txPayload = { position: state.markers.tx };
  const txPower = readNumber(ui.txPowerDbm);
  if (txPower !== null) txPayload.power_dbm = txPower;
  const lookX = readNumber(ui.txLookX);
  const lookY = readNumber(ui.txLookY);
  const lookZ = readNumber(ui.txLookZ);
  if (lookX !== null && lookY !== null && lookZ !== null) {
    txPayload.look_at = [lookX, lookY, lookZ];
  }
  scenePayload.tx = Object.assign(scenePayload.tx || {}, txPayload);
  scenePayload.rx = Object.assign(scenePayload.rx || {}, { position: state.markers.rx });
  const txPattern = ui.txPattern && ui.txPattern.value ? ui.txPattern.value : null;
  const txPol = ui.txPolarization && ui.txPolarization.value ? ui.txPolarization.value : null;
  if (txPattern || txPol) {
    scenePayload.arrays = scenePayload.arrays || {};
    scenePayload.arrays.tx = Object.assign(scenePayload.arrays.tx || {}, {});
    if (txPattern) scenePayload.arrays.tx.pattern = txPattern;
    if (txPol) scenePayload.arrays.tx.polarization = txPol;
  }
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

  document.addEventListener("input", schedulePersistUiSnapshot, true);
  document.addEventListener("change", schedulePersistUiSnapshot, true);
  
  if (!ui.runSelect) console.error("ui.runSelect is missing");
  ui.runSelect.addEventListener("change", () => {
    state.followLatestRun = false;
    state.sceneOverrideDirty = false;
    loadRun(ui.runSelect.value);
  });
  
  if (!ui.sceneSelect) console.error("ui.sceneSelect is missing");
  ui.sceneSelect.addEventListener("change", () => {
    const value = ui.sceneSelect.value || "";
    if (value.startsWith("file:")) {
      const filePath = value.slice("file:".length);
      state.sceneOverride = {
        type: "file",
        file: filePath,
      };
    } else {
      const name = value.startsWith("builtin:") ? value.slice("builtin:".length) : value;
      state.sceneOverride = {
        type: "builtin",
        builtin: name,
      };
    }
    state.sceneOverrideDirty = true;
  });

  if (!ui.runProfile) console.error("ui.runProfile is missing");
  ui.runProfile.addEventListener("change", () => {
    if (ui.runProfile.value === "cpu_only" || ui.runProfile.value === "indoor_box_high") {
      const config = getProfileConfig();
      applyRadioMapDefaults(config);
      applyCustomDefaults(config);
      applySimTuningDefaults(config);
      applyRisSimDefaults(config);
      updateRisGeometryVisibility();
      resetMarkersFromConfig(config);
    }
    updateCustomVisibility();
    schedulePersistUiSnapshot();
  });

  const markTuningDirty = () => {
    state.simTuningDirty = true;
  };
  [ui.simScaleEnabled, ui.simScaleFactor, ui.simSamplingEnabled, ui.simMapResMult, ui.simRaySamplesMult, ui.simMaxDepthAdd]
    .filter(Boolean)
    .forEach((el) => {
      el.addEventListener("change", markTuningDirty);
      el.addEventListener("input", markTuningDirty);
    });
  if (ui.resetSimTuning) {
    ui.resetSimTuning.addEventListener("click", () => {
      const config = getProfileConfig();
      applySimTuningDefaults(config);
      setMeta("Reset tuning to profile defaults");
    });
  }
  if (ui.indoorViewerNormalize) {
    ui.indoorViewerNormalize.addEventListener("change", () => syncViewerScaleFromUi());
  }
  if (ui.indoorViewerTargetSize) {
    ui.indoorViewerTargetSize.addEventListener("change", () => syncViewerScaleFromUi());
    ui.indoorViewerTargetSize.addEventListener("input", () => syncViewerScaleFromUi());
  }
  if (ui.indoorSkipPaths) {
    ui.indoorSkipPaths.addEventListener("change", () => {
      setMeta(ui.indoorSkipPaths.checked ? "Indoor: path tracing disabled" : "Indoor: path tracing enabled");
    });
  }
  if (ui.simComputePaths) {
    ui.simComputePaths.addEventListener("change", () => {
      setMeta(ui.simComputePaths.checked ? "Ray tracing enabled" : "Ray tracing disabled");
    });
  }
  
  if (!ui.applyMarkers) console.error("ui.applyMarkers is missing");
  ui.applyMarkers.addEventListener("click", () => {
    state.markers.tx = [parseFloat(ui.txX.value), parseFloat(ui.txY.value), parseFloat(ui.txZ.value)];
    state.markers.rx = [parseFloat(ui.rxX.value), parseFloat(ui.rxY.value), parseFloat(ui.rxZ.value)];
    updateSceneOverrideTxFromUi();
    rebuildScene();
  });
  
  // mesh rotation controls removed
  
  if (!ui.runSim) console.error("ui.runSim is missing");
  ui.runSim.addEventListener("click", () => submitJob());
  if (ui.runSimTop) {
    ui.runSimTop.addEventListener("click", () => submitJob());
  }

  if (ui.addRis) {
    ui.addRis.addEventListener("click", () => addRisItem());
  }
  if (ui.debugRis) {
    ui.debugRis.addEventListener("click", () => applyRisDebugPreset());
  }
  if (ui.risPresetFocus) {
    ui.risPresetFocus.addEventListener("click", () => applyRisFocusPreset());
  }
  if (ui.risPresetFlat) {
    ui.risPresetFlat.addEventListener("click", () => applyRisFlatPreset());
  }
  if (ui.risPresetCenterMap) {
    ui.risPresetCenterMap.addEventListener("click", () => applyCenterMapPreset());
  }
  if (ui.risGeomReset) {
    ui.risGeomReset.addEventListener("click", () => {
      const config = getProfileConfig();
      applyRisSimDefaults(config);
      updateRisGeometryVisibility();
      setMeta("Reset RIS geometry to profile defaults");
    });
  }
  if (ui.risGeomMode) {
    ui.risGeomMode.addEventListener("change", () => {
      updateRisGeometryVisibility();
    });
  }
  if (ui.risSquareGrid) {
    ui.risSquareGrid.addEventListener("change", () => {
      if (!ui.risSquareGrid.checked) return;
      if (ui.risTargetDxM && ui.risTargetDxM.value) {
        // dy mirrors dx implicitly in submit logic
      }
      if (ui.risDxM && ui.risDxM.value) {
        // dy mirrors dx implicitly in submit logic
      }
    });
  }
  if (ui.risList) {
    ui.risList.addEventListener("change", () => rebuildScene());
  }
  if (ui.txPattern) ui.txPattern.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txPolarization) ui.txPolarization.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txPowerDbm) ui.txPowerDbm.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txLookX) ui.txLookX.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txLookY) ui.txLookY.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txLookZ) ui.txLookZ.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txYawDeg) ui.txYawDeg.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.showTxDirection) ui.showTxDirection.addEventListener("change", rebuildScene);
  if (ui.toggleRisFocus) ui.toggleRisFocus.addEventListener("change", rebuildScene);
  if (ui.txPattern) ui.txPattern.addEventListener("change", () => {
    updateSceneOverrideTxFromUi();
    schedulePersistUiSnapshot();
  });
  if (ui.txPolarization) ui.txPolarization.addEventListener("change", () => {
    updateSceneOverrideTxFromUi();
    schedulePersistUiSnapshot();
  });
  if (ui.txLookAtRis) ui.txLookAtRis.addEventListener("change", () => {
    updateSceneOverrideTxFromUi();
    schedulePersistUiSnapshot();
  });
  if (ui.radioMapPlaneZ) ui.radioMapPlaneZ.addEventListener("change", () => {
    schedulePersistUiSnapshot();
  });
  
  console.log("Binding RIS controls...");
  if (!ui.mainTabStrip) console.error("ui.mainTabStrip is missing");
  ui.mainTabStrip.addEventListener("click", (event) => {
    const target = event.target;
    if (target instanceof HTMLButtonElement && target.dataset.mainTab) {
      setMainTab(target.dataset.mainTab);
    }
  });

  const rightTabStrip = document.getElementById("rightTabStrip");
  if (rightTabStrip) {
    rightTabStrip.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;
      const tab = target.dataset.rightTab;
      if (!tab) return;
      rightTabStrip.querySelectorAll(".right-tab-button").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.rightTab === tab);
      });
      document.querySelectorAll(".right-tab-panel").forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.rightTab === tab);
      });
    });
  }
  
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
    state.ris.selectedPlot = file;
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

  if (!ui.ccConfigSource) console.error("ui.ccConfigSource is missing");
  if (ui.ccConfigSource) {
    ui.ccConfigSource.addEventListener("change", updateCcConfigSourceVisibility);
  }
  if (!ui.ccCsiType) console.error("ui.ccCsiType is missing");
  if (ui.ccCsiType) {
    ui.ccCsiType.addEventListener("change", updateCcCsiVisibility);
  }
  if (!ui.ccStart) console.error("ui.ccStart is missing");
  if (ui.ccStart) ui.ccStart.addEventListener("click", submitCcJob);
  if (!ui.ccRefresh) console.error("ui.ccRefresh is missing");
  if (ui.ccRefresh) ui.ccRefresh.addEventListener("click", refreshCcJobs);
  if (!ui.ccLoadResults) console.error("ui.ccLoadResults is missing");
  if (ui.ccLoadResults) ui.ccLoadResults.addEventListener("click", () => loadCcResults(ui.ccRunSelect.value));
  if (!ui.ccRunSelect) console.error("ui.ccRunSelect is missing");
  if (ui.ccRunSelect) ui.ccRunSelect.addEventListener("change", () => loadCcResults(ui.ccRunSelect.value));
  if (!ui.ccPlotTabs) console.error("ui.ccPlotTabs is missing");
  if (ui.ccPlotTabs) {
    ui.ccPlotTabs.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;
      const file = target.dataset.plot;
      if (!file) return;
      state.cc.selectedPlot = file;
      ui.ccPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
        btn.classList.toggle("is-active", btn === target);
      });
      renderCcPlotSingle(state.cc.activeRunId || ui.ccRunSelect.value, file);
    });
  }

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

  if (ui.radioMapPreviewSelect) {
    ui.radioMapPreviewSelect.addEventListener("change", () => {
      if (!ui.radioMapPreviewImage) return;
      const file = ui.radioMapPreviewSelect.value;
      if (!file) return;
      ui.radioMapPreviewImage.src = `/runs/${state.runId}/viewer/${file}`;
    });
  }

  if (ui.radioMapDiffRun) {
    ui.radioMapDiffRun.addEventListener("change", () => {
      if (ui.radioMapDiffToggle && ui.radioMapDiffToggle.checked) {
        refreshHeatmapDiff();
      }
    });
  }
  if (ui.radioMapDiffToggle) {
    ui.radioMapDiffToggle.addEventListener("change", () => {
      refreshHeatmapDiff();
    });
  }
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
  if (!ui.toggleRisFront) console.error("ui.toggleRisFront is missing");
  ui.toggleRisFront.addEventListener("change", rebuildScene);
  
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
applyUiSnapshot();
updateSceneOverrideTxFromUi();
schedulePersistUiSnapshot();
updateRisActionVisibility();
updateRisConfigSourceVisibility();
updateRisControlVisibility();
updateRisConfigPreview();
updateRisPreview();
updateCcConfigSourceVisibility();
updateCcCsiVisibility();
setMainTab("sim");
fetchConfigs().then(fetchRuns).then(fetchBuiltinScenes).then(() => Promise.all([refreshRisJobs(), refreshCcJobs()]));
setInterval(() => {
  refreshJobs();
  refreshRisJobs();
  refreshCcJobs();
}, 3000);
