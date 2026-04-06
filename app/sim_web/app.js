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
  followLatestRunByScope: { sim: true, indoor: true },
  loadingRun: false,
  lastLoadedRunId: null,
  lastLoadedRunByScope: { sim: null, indoor: null },
  scopedRunIds: { sim: null, indoor: null },
  markers: { tx: [0, 0, 0], rx: [0, 0, 0], ris: [] },
  paths: [],
  heatmap: null,
  heatmapRunDiff: null,
  manifest: null,
  selectedPath: null,
  sceneOverride: null,
  sceneOverrideDirty: false,
  runInfo: null,
  runs: [],
  runConfigs: {},
  builtinScenes: [],
  fileScenes: [],
  sceneFileManifestCache: {},
  configs: [],
  radioMapPlots: [],
  heatmapBase: null,
  heatmapDiff: null,
  simTuningDirty: false,
  activeTab: "sim",
  indoorInitialized: false,
  campaignInitialized: false,
  campaign2Initialized: false,
  viewerScale: { enabled: false, targetSize: 160 },
  txRxOrbScale: 1.0,
  geometryAssetKey: null,
  simScaleSnapshot: null,
  tabSnapshots: { sim: null, indoor: null, campaign: null, campaign2: null, models: null },
  risGeometry: null,
  campaign: {
    jobs: [],
    runs: [],
    activeRunId: null,
    activeJobId: null,
    selectedPlot: null,
    availablePlots: [],
    plotLabels: {},
    runAllActive: false,
  },
  campaign2: {
    jobs: [],
    runs: [],
    activeRunId: null,
    activeJobId: null,
    selectedPlot: null,
    availablePlots: [],
    plotLabels: {},
    runAllActive: false,
  },
  ris: {
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
  txAutoPlaceRis: document.getElementById("txAutoPlaceRis"),
  txYawDeg: document.getElementById("txYawDeg"),
  txPowerDbm: document.getElementById("txPowerDbm"),
  txPattern: document.getElementById("txPattern"),
  txPolarization: document.getElementById("txPolarization"),
  showTxDirection: document.getElementById("showTxDirection"),
  rxX: document.getElementById("rxX"),
  rxY: document.getElementById("rxY"),
  rxZ: document.getElementById("rxZ"),
  applyIeeeTapPreset: document.getElementById("applyIeeeTapPreset"),
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
  risCompareField: document.getElementById("risCompareField"),
  risCompareUseSionna: document.getElementById("risCompareUseSionna"),
  risCompareUsePaths: document.getElementById("risCompareUsePaths"),
  risCompareUseCoverage: document.getElementById("risCompareUseCoverage"),
  risCompareAngles: document.getElementById("risCompareAngles"),
  risCompareNormalization: document.getElementById("risCompareNormalization"),
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
  plotLightbox: document.getElementById("plotLightbox"),
  plotLightboxImg: document.getElementById("plotLightboxImg"),
  plotLightboxClose: document.getElementById("plotLightboxClose"),
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
  floorElevation: document.getElementById("floorElevation"),
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
  simRisIsolation: document.getElementById("simRisIsolation"),
  simRisEnabled: document.getElementById("simRisEnabled"),
  simRisObjects: document.getElementById("simRisObjects"),
  indoorViewerNormalize: document.getElementById("indoorViewerNormalize"),
  indoorViewerTargetSize: document.getElementById("indoorViewerTargetSize"),
  indoorSkipPaths: document.getElementById("indoorSkipPaths"),
  campaignSweepDevice: document.getElementById("campaignSweepDevice"),
  campaignRadius: document.getElementById("campaignRadius"),
  campaignRadiusSlider: document.getElementById("campaignRadiusSlider"),
  campaignChunkSize: document.getElementById("campaignChunkSize"),
  campaignStartAngle: document.getElementById("campaignStartAngle"),
  campaignStopAngle: document.getElementById("campaignStopAngle"),
  campaignStepAngle: document.getElementById("campaignStepAngle"),
  campaignArcHeightOffset: document.getElementById("campaignArcHeightOffset"),
  campaignPivotX: document.getElementById("campaignPivotX"),
  campaignPivotY: document.getElementById("campaignPivotY"),
  campaignPivotZ: document.getElementById("campaignPivotZ"),
  campaignPivotFollowRis: document.getElementById("campaignPivotFollowRis"),
  campaignPivotUseRis: document.getElementById("campaignPivotUseRis"),
  campaignCompactOutput: document.getElementById("campaignCompactOutput"),
  campaignDisableRender: document.getElementById("campaignDisableRender"),
  campaignPruneRuns: document.getElementById("campaignPruneRuns"),
  campaignCoarseCell: document.getElementById("campaignCoarseCell"),
  campaignResumeRun: document.getElementById("campaignResumeRun"),
  campaignStart: document.getElementById("campaignStart"),
  campaignRunAll: document.getElementById("campaignRunAll"),
  campaignRefresh: document.getElementById("campaignRefresh"),
  campaignJobStatus: document.getElementById("campaignJobStatus"),
  campaignProgress: document.getElementById("campaignProgress"),
  campaignLog: document.getElementById("campaignLog"),
  campaignJobList: document.getElementById("campaignJobList"),
  campaignRunSelect: document.getElementById("campaignRunSelect"),
  campaignLoadResults: document.getElementById("campaignLoadResults"),
  campaignResultStatus: document.getElementById("campaignResultStatus"),
  campaignMetrics: document.getElementById("campaignMetrics"),
  campaignPlotTabs: document.getElementById("campaignPlotTabs"),
  campaignPlotImage: document.getElementById("campaignPlotImage"),
  campaignPlotCaption: document.getElementById("campaignPlotCaption"),
  campaign2TargetAngles: document.getElementById("campaign2TargetAngles"),
  campaign2Polarization: document.getElementById("campaign2Polarization"),
  campaign2ChunkSize: document.getElementById("campaign2ChunkSize"),
  campaign2FrequencyStart: document.getElementById("campaign2FrequencyStart"),
  campaign2FrequencyStop: document.getElementById("campaign2FrequencyStop"),
  campaign2FrequencyStep: document.getElementById("campaign2FrequencyStep"),
  campaign2StartAngle: document.getElementById("campaign2StartAngle"),
  campaign2StopAngle: document.getElementById("campaign2StopAngle"),
  campaign2StepAngle: document.getElementById("campaign2StepAngle"),
  campaign2TxRisDistance: document.getElementById("campaign2TxRisDistance"),
  campaign2TargetDistance: document.getElementById("campaign2TargetDistance"),
  campaign2TxIncidenceAngle: document.getElementById("campaign2TxIncidenceAngle"),
  campaign2CompactOutput: document.getElementById("campaign2CompactOutput"),
  campaign2DisableRender: document.getElementById("campaign2DisableRender"),
  campaign2PruneRuns: document.getElementById("campaign2PruneRuns"),
  campaign2CoarseCell: document.getElementById("campaign2CoarseCell"),
  campaign2ResumeRun: document.getElementById("campaign2ResumeRun"),
  campaign2Start: document.getElementById("campaign2Start"),
  campaign2RunAll: document.getElementById("campaign2RunAll"),
  campaign2Refresh: document.getElementById("campaign2Refresh"),
  campaign2JobStatus: document.getElementById("campaign2JobStatus"),
  campaign2Progress: document.getElementById("campaign2Progress"),
  campaign2Log: document.getElementById("campaign2Log"),
  campaign2JobList: document.getElementById("campaign2JobList"),
  campaign2RunSelect: document.getElementById("campaign2RunSelect"),
  campaign2LoadResults: document.getElementById("campaign2LoadResults"),
  campaign2ResultStatus: document.getElementById("campaign2ResultStatus"),
  campaign2Metrics: document.getElementById("campaign2Metrics"),
  campaign2PlotTabs: document.getElementById("campaign2PlotTabs"),
  campaign2PlotImage: document.getElementById("campaign2PlotImage"),
  campaign2PlotCaption: document.getElementById("campaign2PlotCaption"),
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
  txRxOrbScale: document.getElementById("txRxOrbScale"),
  txRxOrbScaleValue: document.getElementById("txRxOrbScaleValue"),
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
  heatmapScaleBar: document.querySelector("#heatmapScale .heatmap-scale-bar"),
  heatmapScaleMin: document.getElementById("heatmapScaleMin"),
  heatmapScaleMax: document.getElementById("heatmapScaleMax"),
  heatmapMin: document.getElementById("heatmapMin"),
  heatmapMax: document.getElementById("heatmapMax"),
  heatmapMinLabel: document.getElementById("heatmapMinLabel"),
  heatmapMaxLabel: document.getElementById("heatmapMaxLabel"),
  heatmapMinInput: document.getElementById("heatmapMinInput"),
  heatmapMaxInput: document.getElementById("heatmapMaxInput"),
  materialList: document.getElementById("materialList"),
  meshList: document.getElementById("meshList"),
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

const IEEE_TAP_CHAMBER_CONFIG = "indoor_box_ieee_tap_chamber.yaml";
const IEEE_TAP_CAMPAIGN_DEFAULTS = {
  sweepDevice: "rx",
  radiusM: 1.1,
  chunkSize: 12,
  startAngleDeg: -90,
  stopAngleDeg: 90,
  stepDeg: 2,
  arcHeightOffsetM: 0.0,
  pivot: [0.0, 1.3, 1.5],
  compactOutput: false,
  disableRender: true,
  pruneRuns: false,
  coarseCellSizeM: 0.10,
};

const IEEE_TAP_CAMPAIGN2_DEFAULTS = {
  targetAngles: "0,15,45,60",
  polarization: "both",
  chunkSize: 1,
  frequencyStartGhz: 27.0,
  frequencyStopGhz: 29.0,
  frequencyStepGhz: 1.0,
  startAngleDeg: -90,
  stopAngleDeg: 90,
  stepDeg: 2,
  txRisDistanceM: 0.4,
  targetDistanceM: 2.0,
  txIncidenceAngleDeg: -30.0,
  compactOutput: true,
  disableRender: true,
  pruneRuns: true,
  coarseCellSizeM: 0.10,
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
    label: "Indoor Chamber (IEEE TAP)",
    configName: IEEE_TAP_CHAMBER_CONFIG,
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
  { file: "compare_overlay_norm_db.png", label: "QUB vs Sionna (normalized)" },
  { file: "compare_overlay_abs_db.png", label: "QUB vs Sionna (absolute)" },
  { file: "compare_error_db.png", label: "QUB vs Sionna error" },
];
const RIS_PLOT_LABELS = Object.fromEntries(RIS_PLOT_FILES.map((p) => [p.file, p.label]));

const CAMPAIGN_PLOT_FILES = [
  { file: "campaign_rx_power_dbm.png", label: "Campaign Rx power" },
  { file: "campaign_path_gain_db.png", label: "Campaign path gain" },
  { file: "campaign_rx_power_compare_dbm.png", label: "Campaign Rx power (RIS on vs off)" },
  { file: "campaign_path_gain_compare_db.png", label: "Campaign path gain (RIS on vs off)" },
  { file: "campaign_rx_power_delta_db.png", label: "Campaign Rx power delta (RIS on - off)" },
  { file: "campaign_path_gain_delta_db.png", label: "Campaign path gain delta (RIS on - off)" },
];
const CAMPAIGN_PLOT_LABELS = Object.fromEntries(CAMPAIGN_PLOT_FILES.map((p) => [p.file, p.label]));

function isSimScopeTab(tabName) {
  return tabName === "sim" || tabName === "indoor" || tabName === "campaign" || tabName === "campaign2";
}

function getRunScopeForTab(tabName = state.activeTab) {
  return tabName === "indoor" || tabName === "campaign" || tabName === "campaign2" ? "indoor" : "sim";
}

function getRequestedRunScope() {
  return state.activeTab === "indoor" || state.activeTab === "campaign" || state.activeTab === "campaign2" || ui.runProfile.value === "indoor_box_high" ? "indoor" : "sim";
}

function getScopedUiSnapshotKey(tabName = state.activeTab) {
  if (tabName === "campaign") return "sim_ui_snapshot_campaign";
  if (tabName === "campaign2") return "sim_ui_snapshot_campaign2";
  return getRunScopeForTab(tabName) === "indoor" ? "sim_ui_snapshot_indoor" : "sim_ui_snapshot_sim";
}

function getFileSceneEntry(filePath) {
  if (!filePath || !Array.isArray(state.fileScenes)) return null;
  return state.fileScenes.find((entry) => entry && entry.path === filePath) || null;
}

function getActiveSceneConfig() {
  if (state.sceneOverride && typeof state.sceneOverride === "object") {
    return state.sceneOverride;
  }
  const profileCfg = getProfileConfig();
  return (profileCfg && profileCfg.data && profileCfg.data.scene) || null;
}

function getActiveSceneFilePath() {
  const sceneCfg = getActiveSceneConfig();
  if (!sceneCfg || typeof sceneCfg !== "object") return null;
  if (sceneCfg.type !== "file" || !sceneCfg.file) return null;
  return String(sceneCfg.file);
}

function getSceneFileAssetKey(scenePath) {
  return scenePath ? `scene-file:${scenePath}` : null;
}

function getGeometryAssetKey(_runId = state.runId, manifest = state.manifest) {
  if (!manifest) return null;
  const meshFiles = Array.isArray(manifest.mesh_files) ? manifest.mesh_files.join("|") : "";
  const meshManifest = Array.isArray(manifest.mesh_manifest)
    ? manifest.mesh_manifest.map((entry) => `${entry.shape_id || ""}:${entry.source || ""}:${entry.file || ""}`).join("|")
    : "";
  const rotation = Array.isArray(manifest.mesh_rotation_deg) ? manifest.mesh_rotation_deg.join(",") : "";
  const proxy = manifest.proxy ? JSON.stringify(manifest.proxy) : "";
  return [manifest.mesh || "", meshFiles, meshManifest, rotation, proxy].join("::");
}

let renderer;
let scene;
let camera;
let controls;
let geometryGroup;
let markerGroup;
let rayGroup;
let heatmapGroup;
let alignmentGroup;
let campaignPreviewGroup;
let highlightLine;
let dragging = null;
let dragMode = null;
let dragRisIndex = null;
let dragStartYaw = 0;
let dragStartMouse = null;
let debugHeatmapMesh = null;
const TX_RX_MARKER_BASE_SCALE = 0.2;

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

function getTxRxOrbScaleFactor() {
  if (!Number.isFinite(state.txRxOrbScale)) return 1.0;
  return Math.min(Math.max(state.txRxOrbScale, 0.15), 1.0);
}

function getTxRxOrbRadius() {
  const base = getMarkerRadius();
  const factor = getTxRxOrbScaleFactor();
  return Math.min(Math.max(base * TX_RX_MARKER_BASE_SCALE * factor, 0.03), 3.5);
}

function syncTxRxOrbScaleFromUi(refreshMarkers = true) {
  const value = readNumber(ui.txRxOrbScale);
  const next = value === null ? 1.0 : value;
  state.txRxOrbScale = Math.min(Math.max(next, 0.15), 1.0);
  if (ui.txRxOrbScaleValue) {
    ui.txRxOrbScaleValue.textContent = `${Math.round(state.txRxOrbScale * 100)}%`;
  }
  if (!refreshMarkers || !markerGroup) return;
  rebuildDynamicScene({ refit: false });
}

function getConfigByName(name) {
  if (!state.configs.length) return null;
  return state.configs.find((cfg) => cfg.name === name) || null;
}

function getIndoorChamberConfig() {
  return getConfigByName(IEEE_TAP_CHAMBER_CONFIG) || getConfigByName("indoor_box_high.yaml");
}

function hasConfigRisSetup(config) {
  const ris = (config && config.data && config.data.ris) || {};
  if (!ris || typeof ris !== "object") return false;
  if (Array.isArray(ris.objects) && ris.objects.length) return true;
  if (ris.geometry_mode) return true;
  if (ris.size && Object.keys(ris.size).length) return true;
  if (ris.spacing && Object.keys(ris.spacing).length) return true;
  return false;
}

function applyIndoorDefaults() {
  const indoorCfg = getIndoorChamberConfig();
  if (!indoorCfg) return;
  if (ui.runProfile) ui.runProfile.value = "indoor_box_high";
  applyRadioMapDefaults(indoorCfg);
  applyCustomDefaults(indoorCfg);
  applySimTuningDefaults(indoorCfg);
  // Preserve an already-configured RIS when switching from the normal sim tab into
  // Indoor for the first time. The indoor chamber profile does not define its own
  // RIS objects, so blindly applying RIS defaults here would replace a working
  // setup with the blank UI placeholder.
  if (hasConfigRisSetup(indoorCfg)) {
    applyRisSimDefaults(indoorCfg);
  }
  updateCustomVisibility();
  resetMarkersFromConfig(indoorCfg);
  if (ui.txAutoPlaceRis) ui.txAutoPlaceRis.checked = true;
  autoPlaceTxFromRis({ updateScene: true });
  applyIeeeTapCampaignDefaults(indoorCfg);
  applyIeeeTapCampaign2Defaults(indoorCfg);
}

function applyIeeeTapCampaignDefaults(config = getIndoorChamberConfig()) {
  const cfgCampaign = (config && config.data && config.data.campaign) || {};
  const risObjects = ((config && config.data && config.data.ris) || {}).objects || [];
  const risPivot = Array.isArray(risObjects[0]?.position) ? risObjects[0].position : IEEE_TAP_CAMPAIGN_DEFAULTS.pivot;
  const defaults = {
    sweepDevice: cfgCampaign.sweep_device ?? IEEE_TAP_CAMPAIGN_DEFAULTS.sweepDevice,
    radiusM: cfgCampaign.radius_m ?? IEEE_TAP_CAMPAIGN_DEFAULTS.radiusM,
    chunkSize: cfgCampaign.max_angles_per_job ?? IEEE_TAP_CAMPAIGN_DEFAULTS.chunkSize,
    startAngleDeg: cfgCampaign.start_angle_deg ?? IEEE_TAP_CAMPAIGN_DEFAULTS.startAngleDeg,
    stopAngleDeg: cfgCampaign.stop_angle_deg ?? IEEE_TAP_CAMPAIGN_DEFAULTS.stopAngleDeg,
    stepDeg: cfgCampaign.step_deg ?? IEEE_TAP_CAMPAIGN_DEFAULTS.stepDeg,
    arcHeightOffsetM: cfgCampaign.arc_height_offset_m ?? IEEE_TAP_CAMPAIGN_DEFAULTS.arcHeightOffsetM,
    pivot: Array.isArray(cfgCampaign.pivot) && cfgCampaign.pivot.length >= 3 ? cfgCampaign.pivot : risPivot,
    compactOutput: cfgCampaign.compact_output ?? IEEE_TAP_CAMPAIGN_DEFAULTS.compactOutput,
    disableRender: cfgCampaign.disable_render ?? IEEE_TAP_CAMPAIGN_DEFAULTS.disableRender,
    pruneRuns: cfgCampaign.prune_angle_outputs ?? IEEE_TAP_CAMPAIGN_DEFAULTS.pruneRuns,
    coarseCellSizeM: cfgCampaign.coarse_cell_size_m ?? IEEE_TAP_CAMPAIGN_DEFAULTS.coarseCellSizeM,
  };
  if (ui.campaignSweepDevice) ui.campaignSweepDevice.value = defaults.sweepDevice;
  setInputValue(ui.campaignRadius, defaults.radiusM);
  setInputValue(ui.campaignRadiusSlider, defaults.radiusM);
  setInputValue(ui.campaignChunkSize, defaults.chunkSize);
  setInputValue(ui.campaignStartAngle, defaults.startAngleDeg);
  setInputValue(ui.campaignStopAngle, defaults.stopAngleDeg);
  setInputValue(ui.campaignStepAngle, defaults.stepDeg);
  setInputValue(ui.campaignArcHeightOffset, defaults.arcHeightOffsetM);
  setInputValue(ui.campaignPivotX, defaults.pivot[0]);
  setInputValue(ui.campaignPivotY, defaults.pivot[1]);
  setInputValue(ui.campaignPivotZ, defaults.pivot[2]);
  if (ui.campaignPivotFollowRis) ui.campaignPivotFollowRis.checked = true;
  if (ui.campaignCompactOutput) ui.campaignCompactOutput.checked = Boolean(defaults.compactOutput);
  if (ui.campaignDisableRender) ui.campaignDisableRender.checked = Boolean(defaults.disableRender);
  if (ui.campaignPruneRuns) ui.campaignPruneRuns.checked = Boolean(defaults.pruneRuns);
  setInputValue(ui.campaignCoarseCell, defaults.coarseCellSizeM);
  syncCampaignPivotControls();
}

function applyIeeeTapCampaign2Defaults(config = getIndoorChamberConfig()) {
  const cfgCampaign = (config && config.data && config.data.campaign) || {};
  const experiment = (config && config.data && config.data.experiment) || {};
  const defaults = {
    targetAngles: IEEE_TAP_CAMPAIGN2_DEFAULTS.targetAngles,
    polarization: IEEE_TAP_CAMPAIGN2_DEFAULTS.polarization,
    chunkSize: cfgCampaign.max_cases_per_job ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.chunkSize,
    frequencyStartGhz: IEEE_TAP_CAMPAIGN2_DEFAULTS.frequencyStartGhz,
    frequencyStopGhz: IEEE_TAP_CAMPAIGN2_DEFAULTS.frequencyStopGhz,
    frequencyStepGhz: IEEE_TAP_CAMPAIGN2_DEFAULTS.frequencyStepGhz,
    startAngleDeg: cfgCampaign.start_angle_deg ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.startAngleDeg,
    stopAngleDeg: cfgCampaign.stop_angle_deg ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.stopAngleDeg,
    stepDeg: cfgCampaign.step_deg ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.stepDeg,
    txRisDistanceM: experiment.tx_ris_distance_m ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.txRisDistanceM,
    targetDistanceM: experiment.rx_ris_distance_m ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.targetDistanceM,
    txIncidenceAngleDeg: experiment.tx_incidence_azimuth_deg ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.txIncidenceAngleDeg,
    compactOutput: cfgCampaign.compact_output ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.compactOutput,
    disableRender: cfgCampaign.disable_render ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.disableRender,
    pruneRuns: cfgCampaign.prune_angle_outputs ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.pruneRuns,
    coarseCellSizeM: cfgCampaign.coarse_cell_size_m ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.coarseCellSizeM,
  };
  setInputValue(ui.campaign2TargetAngles, defaults.targetAngles);
  if (ui.campaign2Polarization) ui.campaign2Polarization.value = defaults.polarization;
  setInputValue(ui.campaign2ChunkSize, defaults.chunkSize);
  setInputValue(ui.campaign2FrequencyStart, defaults.frequencyStartGhz);
  setInputValue(ui.campaign2FrequencyStop, defaults.frequencyStopGhz);
  setInputValue(ui.campaign2FrequencyStep, defaults.frequencyStepGhz);
  setInputValue(ui.campaign2StartAngle, defaults.startAngleDeg);
  setInputValue(ui.campaign2StopAngle, defaults.stopAngleDeg);
  setInputValue(ui.campaign2StepAngle, defaults.stepDeg);
  setInputValue(ui.campaign2TxRisDistance, defaults.txRisDistanceM);
  setInputValue(ui.campaign2TargetDistance, defaults.targetDistanceM);
  setInputValue(ui.campaign2TxIncidenceAngle, defaults.txIncidenceAngleDeg);
  if (ui.campaign2CompactOutput) ui.campaign2CompactOutput.checked = Boolean(defaults.compactOutput);
  if (ui.campaign2DisableRender) ui.campaign2DisableRender.checked = Boolean(defaults.disableRender);
  if (ui.campaign2PruneRuns) ui.campaign2PruneRuns.checked = Boolean(defaults.pruneRuns);
  setInputValue(ui.campaign2CoarseCell, defaults.coarseCellSizeM);
}

function applyIeeeTapChamberPreset() {
  const indoorCfg = getIndoorChamberConfig();
  if (!indoorCfg) {
    setMeta(`Preset config not available: ${IEEE_TAP_CHAMBER_CONFIG}`);
    return;
  }
  if (ui.runProfile) ui.runProfile.value = "indoor_box_high";
  applyRadioMapDefaults(indoorCfg);
  applyCustomDefaults(indoorCfg);
  applySimTuningDefaults(indoorCfg);
  applyRisSimDefaults(indoorCfg);
  updateRisGeometryVisibility();
  updateCustomVisibility();
  resetMarkersFromConfig(indoorCfg);
  if (ui.txAutoPlaceRis) ui.txAutoPlaceRis.checked = true;
  autoPlaceTxFromRis({ updateScene: true });
  applyIeeeTapCampaignDefaults(indoorCfg);
  schedulePersistUiSnapshot();
  setMeta("Applied IEEE TAP chamber preset");
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
    risIsolation: readCheck(ui.simRisIsolation),
    tx: {
      lookX: readText(ui.txLookX),
      lookY: readText(ui.txLookY),
      lookZ: readText(ui.txLookZ),
      lookAtRis: readCheck(ui.txLookAtRis),
      autoPlaceRis: readCheck(ui.txAutoPlaceRis),
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
      labConfigSource: readText(ui.risConfigSource),
      labConfigPath: readText(ui.risConfigPath),
      labAction: readText(ui.risAction),
      labMode: readText(ui.risMode),
      labReferencePath: readText(ui.risReferencePath),
      compareUseSionna: readCheck(ui.risCompareUseSionna),
      compareUsePaths: readCheck(ui.risCompareUsePaths),
      compareUseCoverage: readCheck(ui.risCompareUseCoverage),
      compareAngles: readText(ui.risCompareAngles),
      compareNormalization: readText(ui.risCompareNormalization),
    },
    indoorViewer: {
      normalize: readCheck(ui.indoorViewerNormalize),
      targetSize: readText(ui.indoorViewerTargetSize),
      skipPaths: readCheck(ui.indoorSkipPaths),
    },
    campaign: {
      sweepDevice: readText(ui.campaignSweepDevice),
      radius: readText(ui.campaignRadius),
      radiusSlider: readText(ui.campaignRadiusSlider),
      chunkSize: readText(ui.campaignChunkSize),
      startAngle: readText(ui.campaignStartAngle),
      stopAngle: readText(ui.campaignStopAngle),
      stepAngle: readText(ui.campaignStepAngle),
      arcHeightOffset: readText(ui.campaignArcHeightOffset),
      pivotX: readText(ui.campaignPivotX),
      pivotY: readText(ui.campaignPivotY),
      pivotZ: readText(ui.campaignPivotZ),
      pivotFollowRis: readCheck(ui.campaignPivotFollowRis),
      compactOutput: readCheck(ui.campaignCompactOutput),
      disableRender: readCheck(ui.campaignDisableRender),
      pruneRuns: readCheck(ui.campaignPruneRuns),
      coarseCell: readText(ui.campaignCoarseCell),
      resumeRun: readText(ui.campaignResumeRun),
    },
    campaign2: {
      targetAngles: readText(ui.campaign2TargetAngles),
      polarization: readText(ui.campaign2Polarization),
      chunkSize: readText(ui.campaign2ChunkSize),
      frequencyStart: readText(ui.campaign2FrequencyStart),
      frequencyStop: readText(ui.campaign2FrequencyStop),
      frequencyStep: readText(ui.campaign2FrequencyStep),
      startAngle: readText(ui.campaign2StartAngle),
      stopAngle: readText(ui.campaign2StopAngle),
      stepAngle: readText(ui.campaign2StepAngle),
      txRisDistance: readText(ui.campaign2TxRisDistance),
      targetDistance: readText(ui.campaign2TargetDistance),
      txIncidenceAngle: readText(ui.campaign2TxIncidenceAngle),
      compactOutput: readCheck(ui.campaign2CompactOutput),
      disableRender: readCheck(ui.campaign2DisableRender),
      pruneRuns: readCheck(ui.campaign2PruneRuns),
      coarseCell: readText(ui.campaign2CoarseCell),
      resumeRun: readText(ui.campaign2ResumeRun),
    },
    viewer: {
      floorElevation: readText(ui.floorElevation),
      txRxOrbScale: readText(ui.txRxOrbScale),
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
    setCheck(ui.txAutoPlaceRis, snapshot.tx.autoPlaceRis);
    setText(ui.txYawDeg, snapshot.tx.yawDeg);
    setText(ui.txPowerDbm, snapshot.tx.powerDbm);
    setText(ui.txPattern, snapshot.tx.pattern);
    setText(ui.txPolarization, snapshot.tx.polarization);
    setCheck(ui.showTxDirection, snapshot.tx.showDirection);
    setCheck(ui.toggleRisFront, snapshot.tx.showRisFront);
    syncTxAutoPlacementControls();
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
    setText(ui.risConfigSource, snapshot.ris.labConfigSource);
    setText(ui.risConfigPath, snapshot.ris.labConfigPath);
    setText(ui.risAction, snapshot.ris.labAction);
    setText(ui.risMode, snapshot.ris.labMode);
    setText(ui.risReferencePath, snapshot.ris.labReferencePath);
    setCheck(ui.risCompareUseSionna, snapshot.ris.compareUseSionna);
    setCheck(ui.risCompareUsePaths, snapshot.ris.compareUsePaths);
    setCheck(ui.risCompareUseCoverage, snapshot.ris.compareUseCoverage);
    setText(ui.risCompareAngles, snapshot.ris.compareAngles);
    setText(ui.risCompareNormalization, snapshot.ris.compareNormalization);
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
  if (snapshot.campaign) {
    setText(ui.campaignSweepDevice, snapshot.campaign.sweepDevice);
    setText(ui.campaignRadius, snapshot.campaign.radius);
    setText(ui.campaignRadiusSlider, snapshot.campaign.radiusSlider || snapshot.campaign.radius);
    setText(ui.campaignChunkSize, snapshot.campaign.chunkSize);
    setText(ui.campaignStartAngle, snapshot.campaign.startAngle);
    setText(ui.campaignStopAngle, snapshot.campaign.stopAngle);
    setText(ui.campaignStepAngle, snapshot.campaign.stepAngle);
    setText(ui.campaignArcHeightOffset, snapshot.campaign.arcHeightOffset);
    setText(ui.campaignPivotX, snapshot.campaign.pivotX);
    setText(ui.campaignPivotY, snapshot.campaign.pivotY);
    setText(ui.campaignPivotZ, snapshot.campaign.pivotZ);
    setCheck(ui.campaignPivotFollowRis, snapshot.campaign.pivotFollowRis !== false);
    setCheck(ui.campaignCompactOutput, snapshot.campaign.compactOutput);
    setCheck(ui.campaignDisableRender, snapshot.campaign.disableRender);
    setCheck(ui.campaignPruneRuns, snapshot.campaign.pruneRuns);
    setText(ui.campaignCoarseCell, snapshot.campaign.coarseCell);
    setText(ui.campaignResumeRun, snapshot.campaign.resumeRun);
    syncCampaignPivotControls();
  }
  if (snapshot.campaign2) {
    setText(ui.campaign2TargetAngles, snapshot.campaign2.targetAngles);
    setText(ui.campaign2Polarization, snapshot.campaign2.polarization);
    setText(ui.campaign2ChunkSize, snapshot.campaign2.chunkSize);
    setText(ui.campaign2FrequencyStart, snapshot.campaign2.frequencyStart);
    setText(ui.campaign2FrequencyStop, snapshot.campaign2.frequencyStop);
    setText(ui.campaign2FrequencyStep, snapshot.campaign2.frequencyStep);
    setText(ui.campaign2StartAngle, snapshot.campaign2.startAngle);
    setText(ui.campaign2StopAngle, snapshot.campaign2.stopAngle);
    setText(ui.campaign2StepAngle, snapshot.campaign2.stepAngle);
    setText(ui.campaign2TxRisDistance, snapshot.campaign2.txRisDistance);
    setText(ui.campaign2TargetDistance, snapshot.campaign2.targetDistance);
    setText(ui.campaign2TxIncidenceAngle, snapshot.campaign2.txIncidenceAngle);
    setCheck(ui.campaign2CompactOutput, snapshot.campaign2.compactOutput);
    setCheck(ui.campaign2DisableRender, snapshot.campaign2.disableRender);
    setCheck(ui.campaign2PruneRuns, snapshot.campaign2.pruneRuns);
    setText(ui.campaign2CoarseCell, snapshot.campaign2.coarseCell);
    setText(ui.campaign2ResumeRun, snapshot.campaign2.resumeRun);
  }
  if (snapshot.viewer) {
    setText(ui.floorElevation, snapshot.viewer.floorElevation);
    setText(ui.txRxOrbScale, snapshot.viewer.txRxOrbScale);
    syncTxRxOrbScaleFromUi(false);
  }
  if (snapshot.computePaths !== undefined) {
    setCheck(ui.simComputePaths, snapshot.computePaths);
  }
  if (snapshot.risIsolation !== undefined) {
    setCheck(ui.simRisIsolation, snapshot.risIsolation);
  }
  state.markers = snapshot.markers || state.markers;
  state.sceneOverride = snapshot.sceneOverride;
  state.sceneOverrideDirty = Boolean(snapshot.sceneOverrideDirty);
  updateInputs();
  updateRisGeometryVisibility();
  updateRisActionVisibility();
  updateRisConfigSourceVisibility();
  updateCustomVisibility();
  rebuildScene({ refit: false });
  refreshHeatmap();
}

function _degToRad(deg) {
  return (deg * Math.PI) / 180.0;
}

function _radToDeg(rad) {
  return (rad * 180.0) / Math.PI;
}

function risUiOrientationToBackend(orientation) {
  if (!Array.isArray(orientation) || orientation.length < 3) return null;
  return [orientation[2], orientation[1], orientation[0]];
}

function risBackendOrientationToUi(orientation) {
  if (!Array.isArray(orientation) || orientation.length < 3) return null;
  return [orientation[2], orientation[1], orientation[0]];
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
  const clearVal = (name) => {
    const el = fields(name);
    if (el) el.value = "";
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
  const ori = risBackendOrientationToUi(initial?.orientation) || [0, 0, 0];
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
  const disableLookAt = () => {
    ["lookX", "lookY", "lookZ"].forEach((name) => {
      const el = fields(name);
      if (el) el.value = "";
    });
  };
  ["oriX", "oriY", "oriZ"].forEach((name) => {
    const el = fields(name);
    if (!el) return;
    el.addEventListener("input", () => {
      disableLookAt();
    });
    el.addEventListener("change", () => {
      disableLookAt();
    });
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
    const orientationUi = orientationDeg.map((val) => (val === null ? null : _degToRad(val)));
    const hasLook = look.every((v) => v !== null);
    const hasOrientation = orientationUi.every((v) => v !== null);
    const obj = {
      name,
      enabled,
      position,
      num_rows: Math.max(1, parseInt(field("rows")?.value || "12", 10)),
      num_cols: Math.max(1, parseInt(field("cols")?.value || "12", 10)),
      num_modes: Math.max(1, parseInt(field("modes")?.value || "1", 10)),
    };
    if (hasLook) {
      obj.look_at = look;
    } else if (hasOrientation) {
      obj.orientation = risUiOrientationToBackend(orientationUi);
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
  if (ui.txLookAtRis) ui.txLookAtRis.checked = true;
  if (ui.txLookX) ui.txLookX.value = risPos[0];
  if (ui.txLookY) ui.txLookY.value = risPos[1];
  if (ui.txLookZ) ui.txLookZ.value = risPos[2];
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
      // Force RIS front-face toward Tx/Rx side for this debug geometry.
      setVal("lookX", mid[0].toFixed(2));
      setVal("lookY", mid[1].toFixed(2));
      setVal("lookZ", mid[2].toFixed(2));
      setVal("oriX", "");
      setVal("oriY", "");
      setVal("oriZ", "");
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
  rebuildScene({ refit: false });
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
  rebuildScene({ refit: false });
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
  rebuildScene({ refit: false });
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
  rebuildScene({ refit: false });
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
  syncCampaignPivotUiFromRis();
  autoPlaceTxFromRis({ updateScene: true });
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
  const autoAim = node.querySelector('[data-field="autoAim"]');
  if (autoAim && autoAim.checked) autoAim.checked = false;
  ["lookX", "lookY", "lookZ"].forEach((name) => {
    const lookEl = node.querySelector(`[data-field="${name}"]`);
    if (lookEl) lookEl.value = "";
  });
  autoPlaceTxFromRis({ updateScene: true });
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
  campaignPreviewGroup = new THREE.Group();
  campaignPreviewGroup.visible = false;
  scene.add(
    geometryGroup,
    markerGroup,
    rayGroup,
    heatmapGroup,
    alignmentGroup,
    campaignPreviewGroup
  );

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

function updateCampaignPreviewVisibility() {
  if (!campaignPreviewGroup) return;
  campaignPreviewGroup.visible = state.activeTab === "campaign" || state.activeTab === "campaign2";
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

function syncMarkersFromInputs(options = {}) {
  const { rebuild = false, persist = false } = options;
  const tx = [readNumber(ui.txX), readNumber(ui.txY), readNumber(ui.txZ)];
  const rx = [readNumber(ui.rxX), readNumber(ui.rxY), readNumber(ui.rxZ)];
  if (!txAutoPlacementEnabled() && tx.every((value) => value !== null)) {
    state.markers.tx = tx;
  }
  if (rx.every((value) => value !== null)) {
    state.markers.rx = rx;
  }
  autoPlaceTxFromRis({ updateScene: false });
  updateSceneOverrideTxFromUi();
  const sceneCfg = state.sceneOverride || {};
  sceneCfg.rx = Object.assign(sceneCfg.rx || {}, { position: state.markers.rx });
  state.sceneOverride = sceneCfg;
  state.sceneOverrideDirty = true;
  if (rebuild) {
    rebuildScene({ refit: false });
  }
  if (persist) {
    schedulePersistUiSnapshot();
  }
}

function getFloorElevation() {
  const override = readNumber(ui.floorElevation);
  if (override !== null) return override;
  const proxyElev = state.manifest && state.manifest.proxy && state.manifest.proxy.ground
    ? state.manifest.proxy.ground.elevation
    : null;
  return proxyElev !== undefined && proxyElev !== null ? proxyElev : 0;
}

function setInputValue(input, value) {
  if (value === undefined || value === null) {
    input.value = "";
  } else {
    input.value = value;
  }
}

function setCampaignUiVisible(isVisible) {
  document.querySelectorAll(".campaign-only").forEach((el) => {
    el.classList.toggle("is-active", isVisible);
  });
  document.querySelectorAll(".campaign2-only").forEach((el) => {
    el.classList.toggle("is-active", state.activeTab === "campaign2");
  });
}

function setMainTab(tabName) {
  if (!ui.mainTabStrip) return;
  if (state.activeTab && state.activeTab !== tabName) {
    state.tabSnapshots[state.activeTab] = snapshotUiState();
    if (isSimScopeTab(state.activeTab)) {
      saveUiSnapshot(state.tabSnapshots[state.activeTab], state.activeTab);
    }
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
  setCampaignUiVisible(tabName === "campaign");
  updateCampaignPreviewVisibility();
  const indoorLayout = document.getElementById("indoorLayout");
  const campaignLayout = document.getElementById("campaignLayout");
  const campaign2Layout = document.getElementById("campaign2Layout");
  const simLayout = document.getElementById("simLayout");
  const indoorSection = document.getElementById("indoorViewerSection");
  if (tabName === "indoor" || tabName === "campaign" || tabName === "campaign2") {
    const isCampaign = tabName === "campaign";
    const isCampaign2 = tabName === "campaign2";
    const targetLayout = isCampaign ? campaignLayout : isCampaign2 ? campaign2Layout : indoorLayout;
    const firstVisit = isCampaign ? !state.campaignInitialized : isCampaign2 ? !state.campaign2Initialized : !state.indoorInitialized;
    moveSharedPanels(targetLayout);
    if (indoorSection) indoorSection.style.display = "";
    setSimilarityScalingLocked(true);
    const snapshotKey = isCampaign ? "campaign" : isCampaign2 ? "campaign2" : "indoor";
    const savedSnapshot = state.tabSnapshots[snapshotKey] || loadUiSnapshot(snapshotKey);
    if (savedSnapshot) {
      state.tabSnapshots[snapshotKey] = savedSnapshot;
      if (isCampaign) {
        state.campaignInitialized = true;
      } else if (isCampaign2) {
        state.campaign2Initialized = true;
      } else {
        state.indoorInitialized = true;
      }
      applyUiState(savedSnapshot);
    } else if (firstVisit) {
      applyIndoorDefaults();
      if (isCampaign) {
        state.campaignInitialized = true;
      } else if (isCampaign2) {
        state.campaign2Initialized = true;
      } else {
        state.indoorInitialized = true;
      }
      if (ui.indoorViewerNormalize) {
        ui.indoorViewerNormalize.checked = true;
      }
      if (ui.runProfile) ui.runProfile.value = "indoor_box_high";
      if (isCampaign2) {
        applyIeeeTapCampaign2Defaults();
      }
    }
    if (!savedSnapshot && ui.runProfile) {
      ui.runProfile.value = "indoor_box_high";
    }
    if (ui.indoorViewerNormalize && ui.indoorViewerTargetSize && ui.indoorViewerTargetSize.value === "") {
      ui.indoorViewerTargetSize.value = String(state.viewerScale.targetSize || 160);
    }
    syncViewerScaleFromUi();
    requestAnimationFrame(() => {
      refreshViewerSize();
      fitCamera();
    });
    void fetchRuns("indoor");
    void refreshJobs("indoor");
    if (isCampaign) {
      void refreshCampaignJobs();
    }
  } else if (tabName === "models") {
    if (indoorSection) indoorSection.style.display = "none";
    setSimilarityScalingLocked(false);
    state.viewerScale.enabled = false;
  } else {
    if (tabName === "sim") {
      moveSharedPanels(simLayout);
    }
    if (indoorSection) indoorSection.style.display = "none";
    setSimilarityScalingLocked(false);
    state.viewerScale.enabled = false;
    if (tabName === "sim") {
      const simSnapshot = state.tabSnapshots.sim || loadUiSnapshot("sim");
      if (simSnapshot) {
        state.tabSnapshots.sim = simSnapshot;
        applyUiState(simSnapshot);
      }
      void fetchRuns("sim");
      void refreshJobs("sim");
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
  const isCompare = action === "compare";
  ui.risReferenceField.style.display = isValidate ? "" : "none";
  if (ui.risCompareField) {
    ui.risCompareField.style.display = isCompare ? "" : "none";
  }
  ui.risMode.disabled = isValidate || isCompare;
  if (ui.risStart) {
    ui.risStart.textContent = isCompare ? "Run QUB vs Sionna" : "Run RIS Lab";
  }
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

function parseNumberList(input, fallback) {
  const raw = input && typeof input.value === "string" ? input.value : "";
  const parsed = raw
    .split(",")
    .map((part) => parseFloat(part.trim()))
    .filter((value) => Number.isFinite(value));
  return parsed.length ? parsed : fallback;
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
    compare: {
      normalization: ui.risCompareNormalization ? ui.risCompareNormalization.value : "peak_0db",
      sionna: {
        enabled: ui.risCompareUseSionna ? Boolean(ui.risCompareUseSionna.checked) : false,
        compute_paths: ui.risCompareUsePaths ? Boolean(ui.risCompareUsePaths.checked) : true,
        coverage_map: ui.risCompareUseCoverage ? Boolean(ui.risCompareUseCoverage.checked) : true,
        num_angles: readOptionalInt(ui.risCompareAngles, 25),
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
  if (!config.compare.normalization) {
    delete config.compare.normalization;
  }
  if (!config.compare.sionna.enabled) {
    config.compare.sionna.compute_paths = false;
    config.compare.sionna.coverage_map = false;
  }
  if (config.compare.sionna.num_angles < 11) {
    config.compare.sionna.num_angles = 11;
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

async function fetchSceneFileManifest(scenePath) {
  if (!scenePath) return null;
  if (state.sceneFileManifestCache[scenePath]) {
    return state.sceneFileManifestCache[scenePath];
  }
  const manifest = await fetchJsonMaybe(`/api/scene_file_manifest?path=${encodeURIComponent(scenePath)}`);
  if (manifest) {
    state.sceneFileManifestCache[scenePath] = manifest;
  }
  return manifest;
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

function renderCampaignMetrics(summary) {
  ui.campaignMetrics.innerHTML = "";
  if (!summary || !summary.metrics) {
    ui.campaignMetrics.textContent = "No campaign metrics found for this run.";
    return;
  }
  const metrics = summary.metrics;
  const rows = [
    ["requested_angles", metrics.requested_angles],
    ["completed_angles", metrics.completed_angles],
    ["remaining_angles", metrics.remaining_angles],
    ["chunk_processed_angles", metrics.chunk_processed_angles],
    ["ris_off_probe_angles", metrics.ris_off_probe_angles],
    ["sweep_device", metrics.sweep_device],
    ["radius_m", metrics.radius_m],
    ["compact_output", metrics.compact_output],
    ["campaign_complete", summary.campaign_complete],
  ];
  rows.forEach(([key, value]) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = `${key}: `;
    const val = document.createElement("span");
    val.textContent = formatMetricValue(value);
    row.append(label, val);
    ui.campaignMetrics.appendChild(row);
  });
}

function renderCampaignPlotSingle(runId, file) {
  if (!ui.campaignPlotImage || !ui.campaignPlotCaption) return;
  const label = (state.campaign.plotLabels && state.campaign.plotLabels[file]) || CAMPAIGN_PLOT_LABELS[file] || file;
  ui.campaignPlotCaption.textContent = label;
  ui.campaignPlotImage.src = `/runs/${runId}/plots/${file}`;
  ui.campaignPlotImage.alt = label;
}

function renderCampaignPlotTabs(plots, activeFile) {
  if (!ui.campaignPlotTabs) return;
  ui.campaignPlotTabs.innerHTML = "";
  const items = Array.isArray(plots) && plots.length ? plots : CAMPAIGN_PLOT_FILES;
  items.forEach((plot, index) => {
    const button = document.createElement("button");
    button.className = `plot-tab-button${plot.file === activeFile || (!activeFile && index === 0) ? " is-active" : ""}`;
    button.dataset.plot = plot.file;
    button.type = "button";
    button.textContent = plot.label || CAMPAIGN_PLOT_LABELS[plot.file] || plot.file;
    ui.campaignPlotTabs.appendChild(button);
  });
}

function renderCampaign2Metrics(summary) {
  ui.campaign2Metrics.innerHTML = "";
  if (!summary || !summary.metrics) {
    ui.campaign2Metrics.textContent = "No campaign metrics found for this run.";
    return;
  }
  const metrics = summary.metrics;
  const rows = [
    ["mode", metrics.mode],
    ["requested_cases", metrics.requested_cases],
    ["completed_cases", metrics.completed_cases],
    ["remaining_cases", metrics.remaining_cases],
    ["chunk_processed_cases", metrics.chunk_processed_cases],
    ["campaign_complete", summary.campaign_complete],
  ];
  rows.forEach(([key, value]) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = `${key}: `;
    const val = document.createElement("span");
    val.textContent = formatMetricValue(value);
    row.append(label, val);
    ui.campaign2Metrics.appendChild(row);
  });
}

function renderCampaign2PlotSingle(runId, file) {
  if (!ui.campaign2PlotImage || !ui.campaign2PlotCaption) return;
  const label = (state.campaign2.plotLabels && state.campaign2.plotLabels[file]) || file;
  ui.campaign2PlotCaption.textContent = label;
  ui.campaign2PlotImage.src = `/runs/${runId}/plots/${file}`;
  ui.campaign2PlotImage.alt = label;
}

function renderCampaign2PlotTabs(plots, activeFile) {
  if (!ui.campaign2PlotTabs) return;
  ui.campaign2PlotTabs.innerHTML = "";
  const items = Array.isArray(plots) ? plots : [];
  items.forEach((plot, index) => {
    const button = document.createElement("button");
    button.className = `plot-tab-button${plot.file === activeFile || (!activeFile && index === 0) ? " is-active" : ""}`;
    button.dataset.plot = plot.file;
    button.type = "button";
    button.textContent = plot.label || plot.file;
    ui.campaign2PlotTabs.appendChild(button);
  });
}

function setRisStatus(text) {
  ui.risJobStatus.textContent = text;
}

function setRisResultStatus(text) {
  ui.risResultStatus.textContent = text;
}

function setCampaignStatus(text) {
  ui.campaignJobStatus.textContent = text;
}

function setCampaignResultStatus(text) {
  ui.campaignResultStatus.textContent = text;
}

function setCampaign2Status(text) {
  ui.campaign2JobStatus.textContent = text;
}

function setCampaign2ResultStatus(text) {
  ui.campaign2ResultStatus.textContent = text;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function setCampaignRunControlsState() {
  const locked = Boolean(state.campaign && state.campaign.runAllActive);
  if (ui.campaignStart) ui.campaignStart.disabled = locked;
  if (ui.campaignRunAll) {
    ui.campaignRunAll.disabled = locked;
    ui.campaignRunAll.textContent = locked ? "Running All Chunks..." : "Run All Chunks";
  }
}

function setCampaign2RunControlsState() {
  const locked = Boolean(state.campaign2 && state.campaign2.runAllActive);
  if (ui.campaign2Start) ui.campaign2Start.disabled = locked;
  if (ui.campaign2RunAll) {
    ui.campaign2RunAll.disabled = locked;
    ui.campaign2RunAll.textContent = locked ? "Running All Chunks..." : "Run All Chunks";
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

function getProfileDefinition() {
  return RUN_PROFILES[ui.runProfile.value] || RUN_PROFILES.cpu_only;
}

function loadUiSnapshot(tabName = "sim") {
  try {
    const raw = window.localStorage.getItem(getScopedUiSnapshotKey(tabName));
    if (raw) return JSON.parse(raw);
    if (getRunScopeForTab(tabName) === "sim") {
      const legacy = window.localStorage.getItem("sim_ui_snapshot");
      return legacy ? JSON.parse(legacy) : null;
    }
    return null;
  } catch (err) {
    return null;
  }
}

function saveUiSnapshot(snapshot, tabName = state.activeTab || "sim") {
  try {
    const key = getScopedUiSnapshotKey(tabName);
    window.localStorage.setItem(key, JSON.stringify(snapshot));
    if (getRunScopeForTab(tabName) === "sim") {
      window.localStorage.setItem("sim_ui_snapshot", JSON.stringify(snapshot));
    }
  } catch (err) {
    // ignore
  }
}

function applyUiSnapshot(tabName = state.activeTab || "sim") {
  const snap = loadUiSnapshot(tabName);
  if (!snap) return;
  applyUiState(snap);
}

let _persistTimer = null;
function schedulePersistUiSnapshot() {
  if (!isSimScopeTab(state.activeTab)) return;
  if (_persistTimer) window.clearTimeout(_persistTimer);
  _persistTimer = window.setTimeout(() => {
    const snapshot = snapshotUiState();
    state.tabSnapshots[state.activeTab] = snapshot;
    saveUiSnapshot(snapshot, state.activeTab);
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
  const zOnlyRaw = radio.center_z_only;
  const zOnly = zOnlyRaw === undefined || zOnlyRaw === null ? null : Number(zOnlyRaw);
  const centerZ = Number.isFinite(zOnly)
    ? zOnly
    : (Array.isArray(radio.center) && radio.center.length >= 3 ? radio.center[2] : null);
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
    setInputValue(ui.radioMapCenterZ, centerZ);
    setInputValue(ui.radioMapPlaneZ, centerZ);
  } else {
    setInputValue(ui.radioMapCenterX, null);
    setInputValue(ui.radioMapCenterY, null);
    setInputValue(ui.radioMapCenterZ, centerZ);
    setInputValue(ui.radioMapPlaneZ, centerZ);
  }
}

function applyCustomDefaults(config) {
  const sim = (config && config.data && config.data.simulation) || {};
  setInputValue(ui.customMaxDepth, sim.max_depth);
  setInputValue(ui.customSamplesPerSrc, sim.samples_per_src);
  setInputValue(ui.customMaxPathsPerSrc, sim.max_num_paths_per_src);
  if (ui.simRisIsolation) {
    if (typeof sim.ris_isolation === "boolean") {
      ui.simRisIsolation.checked = Boolean(sim.ris_isolation);
    } else {
      ui.simRisIsolation.checked = false;
    }
  }
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
  rebuildScene({ refit: false });
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

async function fetchRuns(scope = getRunScopeForTab()) {
  const res = await fetch(`/api/runs?scope=${encodeURIComponent(scope)}`);
  const data = await res.json();
  state.runs = data.runs || [];
  const isActiveScope = isSimScopeTab(state.activeTab) && getRunScopeForTab() === scope;
  const previous = state.scopedRunIds[scope] || state.lastLoadedRunByScope[scope] || (isActiveScope ? state.runId : null);
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
    const nextRunId = data.runs.find((r) => r.run_id === previous)?.run_id || data.runs[0].run_id;
    state.scopedRunIds[scope] = nextRunId;
    if (isActiveScope) {
      state.runId = nextRunId;
      ui.runSelect.value = nextRunId;
    }
    if (ui.radioMapDiffRun && isActiveScope) {
      ui.radioMapDiffRun.value = previousDiff || nextRunId;
    }
    if (!state.loadingRun && state.lastLoadedRunByScope[scope] !== nextRunId && isActiveScope) {
      await loadRun(nextRunId, scope);
    }
  } else if (isActiveScope) {
    state.runId = null;
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

function parseSceneSelectValue(value) {
  if (!value) return null;
  if (value.startsWith("file:")) {
    const filePath = value.slice("file:".length);
    return filePath ? { type: "file", file: filePath } : null;
  }
  if (value.startsWith("builtin:")) {
    const name = value.slice("builtin:".length);
    return name ? { type: "builtin", builtin: name } : null;
  }
  return null;
}

function clampNumber(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function applyIndoorFileSceneDefaults(entry, override) {
  const bounds = entry && entry.bounds;
  if (!bounds || !Array.isArray(bounds.bbox_min) || !Array.isArray(bounds.bbox_max)) return;
  const min = bounds.bbox_min;
  const max = bounds.bbox_max;
  const size = bounds.size || [max[0] - min[0], max[1] - min[1], max[2] - min[2]];
  const center = bounds.center || [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
  const majorAxis = size[0] >= size[1] ? 0 : 1;
  const minorAxis = majorAxis === 0 ? 1 : 0;
  const marginMajor = Math.max(size[majorAxis] * 0.2, 0.2);
  const planeZ = clampNumber(1.5, min[2] + 0.15, max[2] - 0.15);
  const tx = center.slice();
  const rx = center.slice();
  tx[majorAxis] = min[majorAxis] + marginMajor;
  rx[majorAxis] = max[majorAxis] - marginMajor;
  tx[minorAxis] = center[minorAxis];
  rx[minorAxis] = center[minorAxis];
  tx[2] = planeZ;
  rx[2] = planeZ;

  state.markers.tx = tx;
  state.markers.rx = rx;
  if (ui.runProfile) ui.runProfile.value = "indoor_box_high";
  if (ui.radioMapAuto) ui.radioMapAuto.checked = true;
  if (ui.radioMapPadding && ui.radioMapPadding.value === "") {
    ui.radioMapPadding.value = "0.2";
  }
  setInputValue(ui.radioMapCenterX, center[0]);
  setInputValue(ui.radioMapCenterY, center[1]);
  setInputValue(ui.radioMapCenterZ, planeZ);
  setInputValue(ui.radioMapPlaneZ, planeZ);
  if (ui.floorElevation) ui.floorElevation.value = "";
  setInputValue(ui.txLookX, center[0]);
  setInputValue(ui.txLookY, center[1]);
  setInputValue(ui.txLookZ, planeZ);
  if (ui.txLookAtRis) ui.txLookAtRis.checked = false;

  const nextScene = override && typeof override === "object"
    ? JSON.parse(JSON.stringify(override))
    : {};
  nextScene.tx = Object.assign(nextScene.tx || {}, { position: tx, look_at: [center[0], center[1], planeZ] });
  nextScene.rx = Object.assign(nextScene.rx || {}, { position: rx });
  if ("floor_elevation" in nextScene) delete nextScene.floor_elevation;
  state.sceneOverride = nextScene;
  state.sceneOverrideDirty = true;
  updateInputs();
  rebuildScene({ refit: false });
  setMeta(`Indoor defaults applied for ${entry.label || entry.path}`);
}

function applySceneSourceOverride(override) {
  if (!override || !override.type) return;
  const next = state.sceneOverride && typeof state.sceneOverride === "object"
    ? JSON.parse(JSON.stringify(state.sceneOverride))
    : {};
  if (override.type === "file") {
    if (!override.file) return;
    next.type = "file";
    next.file = override.file;
    if ("builtin" in next) delete next.builtin;
  } else if (override.type === "builtin") {
    if (!override.builtin) return;
    next.type = "builtin";
    next.builtin = override.builtin;
    if ("file" in next) delete next.file;
  } else {
    return;
  }
  state.sceneOverride = next;
  state.sceneOverrideDirty = true;
}

function populateSceneSelect(selectEl, builtinScenes, fileScenes, selectedValue) {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  builtinScenes.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = `builtin:${name}`;
    opt.textContent = name;
    selectEl.appendChild(opt);
  });
  if (fileScenes.length) {
    const spacer = document.createElement("option");
    spacer.disabled = true;
    spacer.textContent = "──────────";
    selectEl.appendChild(spacer);
    fileScenes.forEach((entry) => {
      const opt = document.createElement("option");
      opt.value = `file:${entry.path}`;
      opt.textContent = entry.label || entry.path;
      selectEl.appendChild(opt);
    });
  }
  if (selectedValue) {
    const hasOption = Array.from(selectEl.options).some((opt) => opt.value === selectedValue);
    if (hasOption) {
      selectEl.value = selectedValue;
    }
  }
}

async function fetchBuiltinScenes() {
  const res = await fetch("/api/scenes");
  if (!res.ok) {
    if (ui.sceneSelect) ui.sceneSelect.innerHTML = "<option value=\"\">(no scenes)</option>";
    return;
  }
  const data = await res.json();
  const builtinScenes = data.scenes || [];
  state.builtinScenes = builtinScenes;
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
  state.fileScenes = fileScenes;
  const selectedValue = _sceneSelectValue(state.sceneOverride);
  populateSceneSelect(ui.sceneSelect, builtinScenes, fileScenes, selectedValue);
  if (ui.sceneSelect && !ui.sceneSelect.value) ui.sceneSelect.value = "builtin:etoile";
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

async function fetchCampaignJobs() {
  const data = await fetchJsonMaybe("/api/campaign/jobs");
  return data || { jobs: [] };
}

async function fetchCampaignRuns() {
  const data = await fetchJsonMaybe("/api/campaign/runs");
  return data || { runs: [] };
}

function getCampaignModeFromJob(job) {
  return (((job || {}).campaign || {}).mode || "arc_sweep").toString().trim().toLowerCase();
}

function getCampaignModeFromRun(run) {
  const summary = (run || {}).summary || {};
  const campaign = summary.campaign || {};
  return (campaign.mode || "arc_sweep").toString().trim().toLowerCase();
}

async function fetchCampaignJobsByMode(mode) {
  const data = await fetchCampaignJobs();
  return {
    jobs: (data.jobs || []).filter((job) => getCampaignModeFromJob(job) === mode),
  };
}

async function fetchCampaignRunsByMode(mode) {
  const data = await fetchCampaignRuns();
  return {
    runs: (data.runs || []).filter((run) => getCampaignModeFromRun(run) === mode),
  };
}

function renderCampaignJobList(jobs) {
  ui.campaignJobList.innerHTML = "";
  const sorted = [...jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const recent = sorted.slice(-5).reverse();
  recent.forEach((job) => {
    const item = document.createElement("div");
    const status = job.status || "unknown";
    const resume = job.resume_run_id ? " · resume" : "";
    const error = job.error ? ` · ERROR: ${job.error}` : "";
    item.textContent = `${job.run_id} · ${status}${resume}${error}`;
    ui.campaignJobList.appendChild(item);
  });
}

async function refreshCampaignRunSelect() {
  const data = await fetchCampaignRunsByMode("arc_sweep");
  const runList = (data.runs || []).map((run) => run.run_id).sort((a, b) => b.localeCompare(a));
  state.campaign.runs = runList;

  const previousRun = ui.campaignRunSelect.value;
  ui.campaignRunSelect.innerHTML = "";
  runList.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.campaignRunSelect.appendChild(opt);
  });
  if (runList.length > 0) {
    ui.campaignRunSelect.value = runList.includes(previousRun) ? previousRun : runList[0];
  }

  const previousResume = ui.campaignResumeRun.value;
  ui.campaignResumeRun.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "New campaign run";
  ui.campaignResumeRun.appendChild(blank);
  runList.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.campaignResumeRun.appendChild(opt);
  });
  ui.campaignResumeRun.value = runList.includes(previousResume) ? previousResume : "";
}

async function refreshCampaignProgressAndLog() {
  const runId = state.campaign.activeRunId;
  if (!runId) {
    ui.campaignProgress.textContent = "";
    ui.campaignLog.textContent = "";
    return;
  }
  const progress = await fetchProgress(runId);
  if (progress) {
    const completed = progress.completed_angles != null ? progress.completed_angles : progress.step_index;
    const total = progress.total_steps || 0;
    const angle = progress.current_angle_deg != null ? ` · angle ${progress.current_angle_deg}°` : "";
    const pct = progress.progress != null ? Math.round(progress.progress * 100) : null;
    const pctLabel = pct !== null ? ` · ${pct}%` : "";
    const countLabel = total ? ` · ${completed}/${total}` : "";
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    ui.campaignProgress.textContent = `${progress.status || "running"}${countLabel}${angle}${pctLabel}${error}`.trim();
  } else {
    ui.campaignProgress.textContent = "Progress unavailable.";
  }
  const logText = await fetchTextMaybe(`/runs/${runId}/job.log`);
  ui.campaignLog.textContent = logText ? tailLines(logText, 120) : "No log available.";
}

async function refreshCampaignJobs() {
  const data = await fetchCampaignJobsByMode("arc_sweep");
  state.campaign.jobs = data.jobs || [];
  renderCampaignJobList(state.campaign.jobs);
  const sorted = [...state.campaign.jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const running = sorted.find((job) => job.status === "running");
  const latest = sorted[sorted.length - 1];
  const active = state.campaign.activeJobId
    ? sorted.find((job) => job.job_id === state.campaign.activeJobId)
    : null;
  await refreshCampaignRunSelect();
  const runExists = (job) => job && job.run_id && state.campaign.runs.includes(job.run_id);
  const current = [active, running, latest].find((job) => job && (job.status === "running" || runExists(job)));
  if (current) {
    state.campaign.activeJobId = current.job_id;
    state.campaign.activeRunId = current.run_id;
    setCampaignStatus(`${current.run_id} · ${current.status || "running"}`);
  } else {
    setCampaignStatus("Idle.");
    state.campaign.activeJobId = null;
    state.campaign.activeRunId = null;
  }
  setCampaignRunControlsState();
  await refreshCampaignProgressAndLog();
  if (state.campaign.activeRunId) {
    ui.campaignRunSelect.value = state.campaign.activeRunId;
  }
}

function getCampaignJobById(jobId) {
  if (!jobId || !Array.isArray(state.campaign.jobs)) return null;
  return state.campaign.jobs.find((job) => job && job.job_id === jobId) || null;
}

async function fetchCampaignSummary(runId) {
  if (!runId) return null;
  return await fetchJsonMaybe(`/runs/${runId}/summary.json`);
}

async function waitForCampaignJobCompletion(jobId, runId) {
  for (;;) {
    await refreshCampaignJobs();
    const job = getCampaignJobById(jobId);
    if (job && job.status && job.status !== "running") {
      return job;
    }
    const progress = runId ? await fetchProgress(runId) : null;
    if (progress && progress.status === "failed") {
      return {
        job_id: jobId,
        run_id: runId,
        status: "failed",
        error: progress.error || "Campaign failed",
      };
    }
    await sleep(1500);
  }
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
  } else if (action === "validate") {
    const refPath = ui.risReferencePath.value.trim();
    if (!refPath) {
      setRisStatus("Reference file required for validation.");
      return;
    }
    payload.ref = refPath;
  } else if (action === "compare") {
    if (source === "file") {
      const compareCfg = buildRisConfigFromUI().compare || {};
      payload.compare_overrides = compareCfg;
    }
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
      const rawError = String(data.error || res.status);
      const compareBackendMismatch =
        action === "compare"
        && /run/i.test(rawError)
        && /validate/i.test(rawError)
        && !/compare/i.test(rawError);
      if (compareBackendMismatch) {
        setRisStatus(
          `RIS job error: ${rawError}. Backend appears outdated for compare; restart simulator server and retry.`
        );
      } else {
        setRisStatus(`RIS job error: ${rawError}`);
      }
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

async function submitCampaignJob(options = {}) {
  const { skipStatus = false, resumeRunId = null } = options;
  const built = buildSimJobPayload();
  if (!built) return null;
  const { payload } = built;

  const radius = readNumber(ui.campaignRadius);
  const chunkSize = readNumber(ui.campaignChunkSize);
  const startAngle = readNumber(ui.campaignStartAngle);
  const stopAngle = readNumber(ui.campaignStopAngle);
  const stepAngle = readNumber(ui.campaignStepAngle);
  const arcHeightOffset = readNumber(ui.campaignArcHeightOffset);
  const pivot = getCampaignPivotFromUi();

  if ([radius, chunkSize, startAngle, stopAngle, stepAngle, arcHeightOffset].some((value) => value === null) || !pivot) {
    setCampaignStatus("Campaign error: fill in radius, angles, arc height, chunk size, and pivot.");
    return null;
  }

  payload.kind = "campaign";
  payload.campaign = {
    sweep_device: ui.campaignSweepDevice ? ui.campaignSweepDevice.value : "rx",
    radius_m: radius,
    reference_yaw_deg: getCampaignReferenceYawDeg(),
    max_angles_per_job: Math.max(1, Math.round(chunkSize)),
    start_angle_deg: startAngle,
    stop_angle_deg: stopAngle,
    step_deg: Math.max(1, Math.abs(stepAngle)),
    arc_height_offset_m: arcHeightOffset,
    pivot,
    compact_output: ui.campaignCompactOutput ? ui.campaignCompactOutput.checked : true,
    disable_render: ui.campaignDisableRender ? ui.campaignDisableRender.checked : true,
    prune_angle_outputs: ui.campaignPruneRuns ? ui.campaignPruneRuns.checked : true,
  };
  const coarseCell = readNumber(ui.campaignCoarseCell);
  if (coarseCell !== null) {
    payload.campaign.coarse_cell_size_m = coarseCell;
  }
  const effectiveResumeRunId = resumeRunId || (ui.campaignResumeRun && ui.campaignResumeRun.value ? ui.campaignResumeRun.value : "");
  if (effectiveResumeRunId) {
    payload.campaign.resume_run_id = effectiveResumeRunId;
  }

  if (!skipStatus) {
    setCampaignStatus("Submitting campaign job...");
  }
  try {
    const res = await fetch("/api/campaign/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      setCampaignStatus(`Campaign job error: ${data.error || res.status}`);
      return null;
    } else {
      state.campaign.activeRunId = data.run_id;
      state.campaign.activeJobId = data.job_id;
      setCampaignStatus(`Campaign job submitted: ${data.run_id}`);
    }
    await refreshCampaignJobs();
    await refreshCampaignProgressAndLog();
    return data;
  } catch (err) {
    setCampaignStatus("Campaign job error: network failure");
    return null;
  }
}

async function submitCampaignRunAllJobs() {
  if (state.campaign.runAllActive) return;
  const runningJob = Array.isArray(state.campaign.jobs)
    ? state.campaign.jobs.find((job) => job && job.status === "running")
    : null;
  if (runningJob) {
    setCampaignStatus(`Campaign already running: ${runningJob.run_id}`);
    return;
  }

  state.campaign.runAllActive = true;
  setCampaignRunControlsState();
  let chunkIndex = 0;
  let activeRunId = ui.campaignResumeRun ? ui.campaignResumeRun.value : "";

  try {
    for (;;) {
      chunkIndex += 1;
      setCampaignStatus(
        activeRunId
          ? `Submitting chunk ${chunkIndex} into ${activeRunId}...`
          : `Submitting chunk ${chunkIndex}...`
      );
      const job = await submitCampaignJob({
        skipStatus: true,
        resumeRunId: activeRunId || null,
      });
      if (!job) {
        throw new Error("Campaign submit failed");
      }
      activeRunId = job.run_id;
      if (ui.campaignResumeRun) ui.campaignResumeRun.value = activeRunId;

      setCampaignStatus(`Running chunk ${chunkIndex} in ${activeRunId}...`);
      const completedJob = await waitForCampaignJobCompletion(job.job_id, activeRunId);
      if (!completedJob || completedJob.status === "failed") {
        const error = completedJob && completedJob.error ? completedJob.error : "Campaign chunk failed";
        throw new Error(error);
      }

      await refreshCampaignJobs();
      await loadCampaignResults(activeRunId);

      const summary = await fetchCampaignSummary(activeRunId);
      if (!summary) {
        throw new Error(`Missing campaign summary for ${activeRunId}`);
      }
      const remaining = summary && summary.metrics ? summary.metrics.remaining_angles : null;
      const complete = Boolean(summary && summary.campaign_complete);
      if (complete || remaining === 0) {
        setCampaignStatus(`Campaign complete: ${activeRunId}`);
        break;
      }

      setCampaignStatus(
        `Chunk ${chunkIndex} finished for ${activeRunId}. ${remaining ?? "More"} angles remaining; continuing...`
      );
      if (ui.campaignResumeRun) ui.campaignResumeRun.value = activeRunId;
      await sleep(400);
    }
  } catch (err) {
    const message = err instanceof Error && err.message ? err.message : "Campaign run-all failed";
    setCampaignStatus(`Campaign run-all error: ${message}`);
  } finally {
    state.campaign.runAllActive = false;
    setCampaignRunControlsState();
  }
}

async function loadCampaignResults(runId) {
  if (!runId) {
    setCampaignResultStatus("Select a campaign run to load results.");
    renderCampaignMetrics(null);
    if (ui.campaignPlotImage) ui.campaignPlotImage.src = "";
    return;
  }
  state.campaign.activeRunId = runId;
  setCampaignResultStatus(`Loading ${runId}...`);
  const [summary, progress, plotManifest] = await Promise.all([
    fetchJsonMaybe(`/runs/${runId}/summary.json`),
    fetchProgress(runId),
    fetchJsonMaybe(`/runs/${runId}/data/campaign_plots.json`),
  ]);
  renderCampaignMetrics(summary);
  const availablePlots = plotManifest && Array.isArray(plotManifest.plots) && plotManifest.plots.length
    ? plotManifest.plots
    : CAMPAIGN_PLOT_FILES;
  state.campaign.availablePlots = availablePlots;
  state.campaign.plotLabels = Object.fromEntries(availablePlots.map((plot) => [plot.file, plot.label || CAMPAIGN_PLOT_LABELS[plot.file] || plot.file]));
  const defaultPlot = availablePlots.some((plot) => plot.file === state.campaign.selectedPlot)
    ? state.campaign.selectedPlot
    : availablePlots[0].file;
  renderCampaignPlotSingle(runId, defaultPlot);
  renderCampaignPlotTabs(availablePlots, defaultPlot);
  if (progress && progress.status === "failed") {
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    setCampaignResultStatus(`Campaign failed${error}`);
    return;
  }
  if (summary && summary.campaign_complete === false) {
    const remaining = summary.metrics && summary.metrics.remaining_angles != null ? summary.metrics.remaining_angles : "n/a";
    setCampaignResultStatus(`Chunk loaded. Remaining angles: ${remaining}`);
    return;
  }
  setCampaignResultStatus("Campaign results loaded.");
}

async function refreshCampaign2RunSelect() {
  const data = await fetchCampaignRunsByMode("qub_near_field");
  const runList = (data.runs || []).map((run) => run.run_id).sort((a, b) => b.localeCompare(a));
  state.campaign2.runs = runList;

  const previousRun = ui.campaign2RunSelect.value;
  ui.campaign2RunSelect.innerHTML = "";
  runList.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.campaign2RunSelect.appendChild(opt);
  });
  if (runList.length > 0) {
    ui.campaign2RunSelect.value = runList.includes(previousRun) ? previousRun : runList[0];
  }

  const previousResume = ui.campaign2ResumeRun.value;
  ui.campaign2ResumeRun.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "New campaign run";
  ui.campaign2ResumeRun.appendChild(blank);
  runList.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.campaign2ResumeRun.appendChild(opt);
  });
  ui.campaign2ResumeRun.value = runList.includes(previousResume) ? previousResume : "";
}

function renderCampaign2JobList(jobs) {
  ui.campaign2JobList.innerHTML = "";
  const sorted = [...jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const recent = sorted.slice(-5).reverse();
  recent.forEach((job) => {
    const item = document.createElement("div");
    const status = job.status || "unknown";
    const resume = job.resume_run_id ? " · resume" : "";
    const error = job.error ? ` · ERROR: ${job.error}` : "";
    item.textContent = `${job.run_id} · ${status}${resume}${error}`;
    ui.campaign2JobList.appendChild(item);
  });
}

async function refreshCampaign2ProgressAndLog() {
  const runId = state.campaign2.activeRunId;
  if (!runId) {
    ui.campaign2Progress.textContent = "";
    ui.campaign2Log.textContent = "";
    return;
  }
  const progress = await fetchProgress(runId);
  if (progress) {
    const completed = progress.completed_angles != null ? progress.completed_angles : progress.step_index;
    const total = progress.total_steps || 0;
    const angle = progress.current_angle_deg != null ? ` · target ${progress.current_angle_deg}°` : "";
    const pct = progress.progress != null ? Math.round(progress.progress * 100) : null;
    const pctLabel = pct !== null ? ` · ${pct}%` : "";
    const countLabel = total ? ` · ${completed}/${total}` : "";
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    ui.campaign2Progress.textContent = `${progress.status || "running"}${countLabel}${angle}${pctLabel}${error}`.trim();
  } else {
    ui.campaign2Progress.textContent = "Progress unavailable.";
  }
  const logText = await fetchTextMaybe(`/runs/${runId}/job.log`);
  ui.campaign2Log.textContent = logText ? tailLines(logText, 120) : "No log available.";
}

async function refreshCampaign2Jobs() {
  const data = await fetchCampaignJobsByMode("qub_near_field");
  state.campaign2.jobs = data.jobs || [];
  renderCampaign2JobList(state.campaign2.jobs);
  const sorted = [...state.campaign2.jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const running = sorted.find((job) => job.status === "running");
  const latest = sorted[sorted.length - 1];
  const active = state.campaign2.activeJobId
    ? sorted.find((job) => job.job_id === state.campaign2.activeJobId)
    : null;
  await refreshCampaign2RunSelect();
  const runExists = (job) => job && job.run_id && state.campaign2.runs.includes(job.run_id);
  const current = [active, running, latest].find((job) => job && (job.status === "running" || runExists(job)));
  if (current) {
    state.campaign2.activeJobId = current.job_id;
    state.campaign2.activeRunId = current.run_id;
    setCampaign2Status(`${current.run_id} · ${current.status || "running"}`);
  } else {
    setCampaign2Status("Idle.");
    state.campaign2.activeJobId = null;
    state.campaign2.activeRunId = null;
  }
  setCampaign2RunControlsState();
  await refreshCampaign2ProgressAndLog();
  if (state.campaign2.activeRunId) {
    ui.campaign2RunSelect.value = state.campaign2.activeRunId;
  }
}

function getCampaign2JobById(jobId) {
  if (!jobId || !Array.isArray(state.campaign2.jobs)) return null;
  return state.campaign2.jobs.find((job) => job && job.job_id === jobId) || null;
}

function resolveCampaign2ResumeRunId() {
  if (ui.campaign2ResumeRun && ui.campaign2ResumeRun.value) {
    return ui.campaign2ResumeRun.value;
  }
  if (state.campaign2 && state.campaign2.activeRunId) {
    return state.campaign2.activeRunId;
  }
  if (ui.campaign2RunSelect && ui.campaign2RunSelect.value) {
    return ui.campaign2RunSelect.value;
  }
  return "";
}

function syncCampaign2ResumeSelection(runId) {
  if (!ui.campaign2ResumeRun || !runId) return;
  const optionExists = Array.from(ui.campaign2ResumeRun.options || []).some((option) => option.value === runId);
  if (optionExists) {
    ui.campaign2ResumeRun.value = runId;
  }
}

async function getLiveCampaign2RunningJob(preferredRunId = "") {
  const runningJobs = Array.isArray(state.campaign2.jobs)
    ? state.campaign2.jobs.filter((job) => job && job.status === "running")
    : [];
  const prioritized = preferredRunId
    ? [
        ...runningJobs.filter((job) => job.run_id === preferredRunId),
        ...runningJobs.filter((job) => job.run_id !== preferredRunId),
      ]
    : runningJobs;

  for (const job of prioritized) {
    const progress = job && job.run_id ? await fetchProgress(job.run_id) : null;
    if (!progress || progress.status === "running") {
      return job;
    }
  }
  return null;
}

async function waitForCampaign2JobCompletion(jobId, runId) {
  for (;;) {
    await refreshCampaign2Jobs();
    const job = getCampaign2JobById(jobId);
    if (job && job.status && job.status !== "running") {
      return job;
    }
    const progress = runId ? await fetchProgress(runId) : null;
    if (progress && progress.status === "failed") {
      return {
        job_id: jobId,
        run_id: runId,
        status: "failed",
        error: progress.error || "Campaign failed",
      };
    }
    await sleep(1500);
  }
}

async function submitCampaign2Job(options = {}) {
  const { skipStatus = false, resumeRunId = null } = options;
  const built = buildSimJobPayload();
  if (!built) return null;
  const { payload } = built;

  const chunkSize = readNumber(ui.campaign2ChunkSize);
  const frequencyStart = readNumber(ui.campaign2FrequencyStart);
  const frequencyStop = readNumber(ui.campaign2FrequencyStop);
  const frequencyStep = readNumber(ui.campaign2FrequencyStep);
  const startAngle = readNumber(ui.campaign2StartAngle);
  const stopAngle = readNumber(ui.campaign2StopAngle);
  const stepAngle = readNumber(ui.campaign2StepAngle);
  const txRisDistance = readNumber(ui.campaign2TxRisDistance);
  const targetDistance = readNumber(ui.campaign2TargetDistance);
  const txIncidenceAngle = readNumber(ui.campaign2TxIncidenceAngle);
  const targetAngles = parseAngleList(ui.campaign2TargetAngles ? ui.campaign2TargetAngles.value : "");

  if (
    [chunkSize, frequencyStart, frequencyStop, frequencyStep, startAngle, stopAngle, stepAngle, txRisDistance, targetDistance, txIncidenceAngle].some((value) => value === null) ||
    !targetAngles.length
  ) {
    setCampaign2Status("Campaign error: fill in target angles, sweep angles, frequency range, and geometry.");
    return null;
  }

  const polarizationMode = ui.campaign2Polarization ? ui.campaign2Polarization.value : "both";
  const polarizations = polarizationMode === "both" ? ["V", "H"] : [polarizationMode];
  const normalizedFrequencyStart = Math.min(frequencyStart, frequencyStop);
  const normalizedFrequencyStop = Math.max(frequencyStart, frequencyStop);
  const normalizedFrequencyStep =
    Math.abs(normalizedFrequencyStart - normalizedFrequencyStop) < 1e-9
      ? 1.0
      : Math.abs(frequencyStep);

  payload.kind = "campaign";
  payload.campaign = {
    mode: "qub_near_field",
    start_angle_deg: startAngle,
    stop_angle_deg: stopAngle,
    step_deg: Math.max(1, Math.abs(stepAngle)),
    max_cases_per_job: Math.max(1, Math.round(chunkSize)),
    target_angles_deg: targetAngles,
    frequency_start_ghz: normalizedFrequencyStart,
    frequency_stop_ghz: normalizedFrequencyStop,
    frequency_step_ghz: normalizedFrequencyStep,
    polarizations,
    tx_ris_distance_m: txRisDistance,
    target_distance_m: targetDistance,
    tx_incidence_angle_deg: txIncidenceAngle,
    compact_output: ui.campaign2CompactOutput ? ui.campaign2CompactOutput.checked : true,
    disable_render: ui.campaign2DisableRender ? ui.campaign2DisableRender.checked : true,
    prune_angle_outputs: ui.campaign2PruneRuns ? ui.campaign2PruneRuns.checked : true,
  };
  const coarseCell = readNumber(ui.campaign2CoarseCell);
  if (coarseCell !== null) {
    payload.campaign.coarse_cell_size_m = coarseCell;
  }
  const effectiveResumeRunId = resumeRunId || (ui.campaign2ResumeRun && ui.campaign2ResumeRun.value ? ui.campaign2ResumeRun.value : "");
  if (effectiveResumeRunId) {
    payload.campaign.resume_run_id = effectiveResumeRunId;
  }

  if (!skipStatus) {
    setCampaign2Status("Submitting campaign job...");
  }
  try {
    const res = await fetch("/api/campaign/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      setCampaign2Status(`Campaign job error: ${data.error || res.status}`);
      return null;
    }
    state.campaign2.activeRunId = data.run_id;
    state.campaign2.activeJobId = data.job_id;
    setCampaign2Status(`Campaign job submitted: ${data.run_id}`);
    await refreshCampaign2Jobs();
    syncCampaign2ResumeSelection(data.run_id);
    await refreshCampaign2ProgressAndLog();
    return data;
  } catch (err) {
    setCampaign2Status("Campaign job error: network failure");
    return null;
  }
}

async function submitCampaign2RunAllJobs() {
  if (state.campaign2.runAllActive) return;
  await refreshCampaign2Jobs();
  const preferredRunId = resolveCampaign2ResumeRunId();
  let runningJob = await getLiveCampaign2RunningJob(preferredRunId);
  if (runningJob && preferredRunId && runningJob.run_id !== preferredRunId) {
    setCampaign2Status(`Campaign already running: ${runningJob.run_id}`);
    return;
  }

  state.campaign2.runAllActive = true;
  setCampaign2RunControlsState();
  let chunkIndex = 0;
  let activeRunId = preferredRunId;

  try {
    for (;;) {
      chunkIndex += 1;
      let job = runningJob;
      if (job) {
        activeRunId = job.run_id;
        state.campaign2.activeRunId = activeRunId;
        state.campaign2.activeJobId = job.job_id;
        syncCampaign2ResumeSelection(activeRunId);
        setCampaign2Status(`Waiting for running chunk ${chunkIndex} in ${activeRunId}...`);
      } else {
        setCampaign2Status(
          activeRunId
            ? `Submitting chunk ${chunkIndex} into ${activeRunId}...`
            : `Submitting chunk ${chunkIndex}...`
        );
        job = await submitCampaign2Job({
          skipStatus: true,
          resumeRunId: activeRunId || null,
        });
        if (!job) {
          throw new Error("Campaign submit failed");
        }
      }
      activeRunId = job.run_id;
      syncCampaign2ResumeSelection(activeRunId);

      setCampaign2Status(`Running chunk ${chunkIndex} in ${activeRunId}...`);
      const completedJob = await waitForCampaign2JobCompletion(job.job_id, activeRunId);
      if (!completedJob || completedJob.status === "failed") {
        const error = completedJob && completedJob.error ? completedJob.error : "Campaign chunk failed";
        throw new Error(error);
      }

      await refreshCampaign2Jobs();
      await loadCampaign2Results(activeRunId);

      const summary = await fetchCampaignSummary(activeRunId);
      if (!summary) {
        throw new Error(`Missing campaign summary for ${activeRunId}`);
      }
      const remaining = summary && summary.metrics ? summary.metrics.remaining_cases : null;
      const complete = Boolean(summary && summary.campaign_complete);
      if (complete || remaining === 0) {
        setCampaign2Status(`Campaign complete: ${activeRunId}`);
        break;
      }

      setCampaign2Status(
        `Chunk ${chunkIndex} finished for ${activeRunId}. ${remaining ?? "More"} chunks remaining; continuing...`
      );
      syncCampaign2ResumeSelection(activeRunId);
      runningJob = null;
      await sleep(400);
    }
  } catch (err) {
    const message = err instanceof Error && err.message ? err.message : "Campaign run-all failed";
    setCampaign2Status(`Campaign run-all error: ${message}`);
  } finally {
    state.campaign2.runAllActive = false;
    setCampaign2RunControlsState();
  }
}

async function loadCampaign2Results(runId) {
  if (!runId) {
    setCampaign2ResultStatus("Select a campaign run to load results.");
    renderCampaign2Metrics(null);
    if (ui.campaign2PlotImage) ui.campaign2PlotImage.src = "";
    return;
  }
  state.campaign2.activeRunId = runId;
  setCampaign2ResultStatus(`Loading ${runId}...`);
  const [summary, progress, plotManifest] = await Promise.all([
    fetchJsonMaybe(`/runs/${runId}/summary.json`),
    fetchProgress(runId),
    fetchJsonMaybe(`/runs/${runId}/data/campaign_plots.json`),
  ]);
  renderCampaign2Metrics(summary);
  const availablePlots = plotManifest && Array.isArray(plotManifest.plots) ? plotManifest.plots : [];
  state.campaign2.availablePlots = availablePlots;
  state.campaign2.plotLabels = Object.fromEntries(availablePlots.map((plot) => [plot.file, plot.label || plot.file]));
  const defaultPlot = availablePlots.some((plot) => plot.file === state.campaign2.selectedPlot)
    ? state.campaign2.selectedPlot
    : (availablePlots[0] ? availablePlots[0].file : null);
  if (defaultPlot) {
    renderCampaign2PlotSingle(runId, defaultPlot);
  }
  renderCampaign2PlotTabs(availablePlots, defaultPlot);
  if (progress && progress.status === "failed") {
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    setCampaign2ResultStatus(`Campaign failed${error}`);
    return;
  }
  if (summary && summary.campaign_complete === false) {
    const remaining = summary.metrics && summary.metrics.remaining_cases != null ? summary.metrics.remaining_cases : "n/a";
    setCampaign2ResultStatus(`Chunk loaded. Remaining chunks: ${remaining}`);
    return;
  }
  setCampaign2ResultStatus("Campaign results loaded.");
}

async function loadRun(runId, scope = getRunScopeForTab(), options = {}) {
  const { force = false } = options;
  if (!runId || state.loadingRun) return;
  if (!force && state.lastLoadedRunByScope[scope] === runId && state.runId === runId) {
    return;
  }
  state.loadingRun = true;
  state.runId = runId;
  state.scopedRunIds[scope] = runId;
  setMeta(`Loading ${runId}...`);
  try {
    const [markers, paths, manifest, heatmap, heatmapRunDiff, radioPlots, runInfo] = await Promise.all([
      fetch(`/runs/${runId}/viewer/markers.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/runs/${runId}/viewer/paths.json`).then((r) => (r.ok ? r.json() : [])),
      fetch(`/runs/${runId}/viewer/scene_manifest.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/runs/${runId}/viewer/heatmap.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`/runs/${runId}/viewer/heatmap_diff.json`).then((r) => (r.ok ? r.json() : null)),
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
    state.heatmapRunDiff = heatmapRunDiff;
    state.radioMapPlots = (radioPlots && radioPlots.plots) ? radioPlots.plots : [];
    state.runInfo = runInfo;
    if (runInfo && runInfo.config && runInfo.config.scene) {
      state.sceneOverride = JSON.parse(JSON.stringify(runInfo.config.scene));
      state.sceneOverrideDirty = false;
    }
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
    updateSceneOverrideTxFromUi();
    rebuildScene({ refit: false });
    renderPathTable();
    renderPathStats();
    renderMaterialList();
    setMeta(`${runId} · ${state.paths.length} paths`);
    if (ui.radioMapDiffToggle && ui.radioMapDiffToggle.checked) {
      await refreshHeatmapDiff();
    }
    state.lastLoadedRunId = runId;
    state.lastLoadedRunByScope[scope] = runId;
  } catch (err) {
    console.error("Load run failed:", err);
    setMeta(`Failed to load ${runId}`);
  } finally {
    state.loadingRun = false;
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
  const selectedValue = _sceneSelectValue(sceneCfg);
  [ui.sceneSelect].filter(Boolean).forEach((selectEl) => {
    const hasOption = Array.from(selectEl.options).some((opt) => opt.value === selectedValue);
    if (hasOption) {
      selectEl.value = selectedValue;
    }
  });
  const txCfg = sceneCfg.tx || {};
  if (ui.floorElevation) {
    if (sceneCfg.type === "file" && (sceneCfg.floor_elevation === undefined || sceneCfg.floor_elevation === null)) {
      ui.floorElevation.value = "";
    } else if (sceneCfg.floor_elevation !== undefined && sceneCfg.floor_elevation !== null) {
      setInputValue(ui.floorElevation, sceneCfg.floor_elevation);
    } else if (ui.floorElevation.value === "") {
      const proxyElev = state.manifest && state.manifest.proxy && state.manifest.proxy.ground
        ? state.manifest.proxy.ground.elevation
        : null;
      if (proxyElev !== undefined && proxyElev !== null) {
        setInputValue(ui.floorElevation, proxyElev);
      }
    }
  }
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
  syncTxAutoPlacementControls();
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

function updateSceneOverrideFloorFromUi() {
  if (!ui.floorElevation) return;
  const sceneCfg = state.sceneOverride || {};
  const floorZ = readNumber(ui.floorElevation);
  if (floorZ !== null) {
    sceneCfg.floor_elevation = floorZ;
    sceneCfg.procedural = sceneCfg.procedural || {};
    sceneCfg.procedural.ground = sceneCfg.procedural.ground || {};
    sceneCfg.procedural.ground.elevation = floorZ;
  } else if ("floor_elevation" in sceneCfg) {
    delete sceneCfg.floor_elevation;
  }
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
  const risLinkProbe = metrics.ris_link_probe || null;
  const risMapIssue = metrics.radio_map_issue || null;
  const risVisibility = metrics.radio_map_visibility || null;
  let risGeometryLine = "";
  let risLinkLine = "";
  let risWarningLine = "";
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
  if (risLinkProbe && typeof risLinkProbe.delta_total_path_gain_db === "number") {
    const delta = risLinkProbe.delta_total_path_gain_db.toFixed(2);
    const on = typeof risLinkProbe.on_total_path_gain_db === "number" ? risLinkProbe.on_total_path_gain_db.toFixed(2) : "n/a";
    const off = typeof risLinkProbe.off_total_path_gain_db === "number" ? risLinkProbe.off_total_path_gain_db.toFixed(2) : "n/a";
    risLinkLine = `<div><strong>RIS link probe:</strong> ${delta} dB on-off at Tx/Rx link (on ${on} dB, off ${off} dB)</div>`;
  }
  if (risVisibility && risVisibility.beam_parallel_to_plane) {
    const angle = typeof risVisibility.ris_to_rx_angle_from_plane_deg === "number"
      ? risVisibility.ris_to_rx_angle_from_plane_deg.toFixed(2)
      : "n/a";
    risWarningLine = `<div><strong>Heatmap warning:</strong> RIS beam is ${angle} deg from the map plane, so the 2D slice can miss the actual Rx boost.</div>`;
  }
  if (risMapIssue && risMapIssue.message) {
    const action = risMapIssue.recommended_action ? ` ${risMapIssue.recommended_action}` : "";
    risWarningLine = `<div><strong>Heatmap warning:</strong> ${risMapIssue.message}${action}</div>`;
  }
  ui.runStats.innerHTML = `
    <div><strong>Frequency:</strong> ${freqGHz} GHz</div>
    <div><strong>Max depth:</strong> ${maxDepth}</div>
    <div><strong>Valid paths:</strong> ${numPaths}</div>
    <div><strong>RIS paths:</strong> ${risPaths}</div>
    <div><strong>Total path gain:</strong> ${pathGain} dB</div>
    <div><strong>Rx power (est.):</strong> ${rxPower} dBm</div>
    ${risLinkLine}
    ${risGeometryLine}
    ${risWarningLine}
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

function updateHeatmapScaleGradient() {
  if (!ui.heatmapScaleBar) return;
  const useDiff = ui.radioMapDiffToggle && ui.radioMapDiffToggle.checked;
  const stops = useDiff ? HEATMAP_DIFF_STOPS : HEATMAP_STOPS;
  const cssStops = stops.map((s) => `${_rgbToCss(s.color)} ${Math.round(s.pos * 100)}%`);
  ui.heatmapScaleBar.style.background = `linear-gradient(90deg, ${cssStops.join(", ")})`;
}

function updateHeatmapScaleVisibility(force) {
  if (!ui.heatmapScale) return;
  const visible = force !== undefined
    ? force
    : Boolean(ui.toggleHeatmap.checked && getActiveHeatmap() && getActiveHeatmap().values);
  ui.heatmapScale.classList.toggle("is-hidden", !visible);
  if (visible) {
    updateHeatmapScaleGradient();
  }
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
  const previousSelection = ui.radioMapPreviewSelect.value;
  const plots = [...(state.radioMapPlots || [])];
  const plotRank = (file) => {
    if (file === "radio_map_rx_power_dbm.png" || file.startsWith("radio_map_rx_power_dbm_z")) return 0;
    if (file === "radio_map_path_gain_db.png" || file === "radio_map_path_gain.png" || file.startsWith("radio_map_path_gain_db_z")) return 1;
    if (file === "radio_map_path_loss_db.png" || file === "radio_map_path_loss.png" || file.startsWith("radio_map_path_loss_db_z")) return 2;
    if (file.startsWith("radio_map_") && !file.includes("_diff_") && !file.includes("_ris_on_") && !file.includes("_no_ris_")) return 3;
    if (file.includes("_no_ris_") || file.includes("_ris_on_")) return 4;
    if (file.includes("_diff_")) return 5;
    return 6;
  };
  plots.sort((a, b) => {
    const rankDelta = plotRank(a.file) - plotRank(b.file);
    if (rankDelta !== 0) return rankDelta;
    return a.file.localeCompare(b.file);
  });
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
  const selected = plots.some((plot) => plot.file === previousSelection) ? previousSelection : plots[0].file;
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
  if (state.heatmapRunDiff && (!baseRun || baseRun === state.runId)) {
    state.heatmapDiff = state.heatmapRunDiff;
    updateHeatmapControls();
    refreshHeatmap();
    return;
  }
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

function computeCampaignAngleSeries(startDeg, stopDeg, stepDeg) {
  if (!Number.isFinite(startDeg) || !Number.isFinite(stopDeg) || !Number.isFinite(stepDeg) || stepDeg <= 0) {
    return [];
  }
  const direction = stopDeg >= startDeg ? 1 : -1;
  const signedStep = Math.abs(stepDeg) * direction;
  const count = Math.floor(((stopDeg - startDeg) / signedStep) + 0.5) + 1;
  if (count <= 0) return [];
  const angles = [];
  for (let idx = 0; idx < count; idx += 1) {
    angles.push(Number((startDeg + idx * signedStep).toFixed(6)));
  }
  while (angles.length) {
    const tail = angles[angles.length - 1];
    if ((direction > 0 && tail > stopDeg + 1e-6) || (direction < 0 && tail < stopDeg - 1e-6)) {
      angles.pop();
      continue;
    }
    break;
  }
  return angles;
}

function campaignPositionOnArc(pivot, radiusM, angleDeg, arcHeightOffsetM = 0) {
  const theta = (angleDeg * Math.PI) / 180.0;
  return [
    pivot[0] + radiusM * Math.cos(theta),
    pivot[1] + radiusM * Math.sin(theta),
    pivot[2] + arcHeightOffsetM,
  ];
}

function getCampaignReferenceYawDeg() {
  const risItems = ui.simRisEnabled && ui.simRisEnabled.checked ? readRisItems() : [];
  const active = risItems.find((item) => item && item.enabled !== false) || risItems[0];
  if (!active) return 0;
  if (Array.isArray(active.orientation) && active.orientation.length >= 1) {
    return _radToDeg(active.orientation[0]);
  }
  if (Array.isArray(active.look_at) && active.look_at.length >= 3 && Array.isArray(active.position) && active.position.length >= 3) {
    const dx = active.look_at[0] - active.position[0];
    const dy = active.look_at[1] - active.position[1];
    if (Math.abs(dx) > 1e-9 || Math.abs(dy) > 1e-9) {
      return _radToDeg(Math.atan2(dy, dx));
    }
  }
  return 0;
}

function normalizeAngleDeg(angleDeg) {
  let angle = Number(angleDeg) || 0;
  while (angle <= -180) angle += 360;
  while (angle > 180) angle -= 360;
  return angle;
}

function getActiveRisPose() {
  const risItems = ui.simRisEnabled && ui.simRisEnabled.checked ? readRisItems() : [];
  const active = risItems.find((item) => item && item.enabled !== false) || risItems[0];
  if (active && Array.isArray(active.position) && active.position.length >= 3) {
    let yawDeg = 0;
    if (Array.isArray(active.orientation) && active.orientation.length >= 1) {
      yawDeg = _radToDeg(active.orientation[0]);
    } else if (Array.isArray(active.look_at) && active.look_at.length >= 3) {
      const dx = active.look_at[0] - active.position[0];
      const dy = active.look_at[1] - active.position[1];
      if (Math.abs(dx) > 1e-9 || Math.abs(dy) > 1e-9) {
        yawDeg = _radToDeg(Math.atan2(dy, dx));
      }
    }
    return { position: active.position.slice(0, 3).map((v) => Number(v)), yawDeg };
  }
  return null;
}

function getTxAutoPlacementReference(config = getIndoorChamberConfig()) {
  const cfg = (config && config.data) || {};
  const experiment = cfg.experiment || {};
  const sceneTx = cfg.scene && cfg.scene.tx ? cfg.scene.tx : {};
  const risObjects = cfg.ris && Array.isArray(cfg.ris.objects) ? cfg.ris.objects : [];
  const ris = risObjects.find((item) => item && item.enabled !== false) || risObjects[0];
  const distanceM = Number(experiment.tx_ris_distance_m);
  const incidenceDeg = Number(experiment.tx_incidence_azimuth_deg);
  if (Number.isFinite(distanceM) && distanceM > 0) {
    let zOffsetM = 0.0;
    if (ris && Array.isArray(ris.position) && ris.position.length >= 3 && Array.isArray(sceneTx.position) && sceneTx.position.length >= 3) {
      zOffsetM = Number(sceneTx.position[2]) - Number(ris.position[2]);
    }
    return {
      distanceM,
      zOffsetM: Number.isFinite(zOffsetM) ? zOffsetM : 0.0,
      angleOffsetDeg: Number.isFinite(incidenceDeg) ? normalizeAngleDeg(incidenceDeg) : -30.0,
    };
  }
  return {
    distanceM: 0.4,
    zOffsetM: 0.0,
    angleOffsetDeg: -30.0,
  };
}

function txAutoPlacementEnabled() {
  return Boolean(ui.txAutoPlaceRis && ui.txAutoPlaceRis.checked);
}

function syncTxAutoPlacementControls() {
  const locked = txAutoPlacementEnabled();
  [ui.txX, ui.txY, ui.txZ, ui.txLookX, ui.txLookY, ui.txLookZ, ui.txYawDeg].forEach((el) => {
    if (el) el.disabled = locked;
  });
  if (ui.txLookAtRis) {
    if (locked) ui.txLookAtRis.checked = true;
    ui.txLookAtRis.disabled = locked;
  }
}

function autoPlaceTxFromRis(options = {}) {
  const { updateScene = true, persist = false } = options;
  if (!txAutoPlacementEnabled()) return false;
  const risPose = getActiveRisPose();
  if (!risPose) return false;
  const ref = getTxAutoPlacementReference();
  const theta = _degToRad(risPose.yawDeg + ref.angleOffsetDeg);
  const txPos = [
    Number((risPose.position[0] + ref.distanceM * Math.cos(theta)).toFixed(4)),
    Number((risPose.position[1] + ref.distanceM * Math.sin(theta)).toFixed(4)),
    Number((risPose.position[2] + ref.zOffsetM).toFixed(4)),
  ];
  state.markers.tx = txPos;
  if (ui.txLookAtRis) ui.txLookAtRis.checked = true;
  if (ui.txX) ui.txX.value = txPos[0];
  if (ui.txY) ui.txY.value = txPos[1];
  if (ui.txZ) ui.txZ.value = txPos[2];
  if (ui.txLookX) ui.txLookX.value = risPose.position[0];
  if (ui.txLookY) ui.txLookY.value = risPose.position[1];
  if (ui.txLookZ) ui.txLookZ.value = risPose.position[2];
  syncTxAutoPlacementControls();
  if (updateScene) {
    updateSceneOverrideTxFromUi();
  }
  if (persist) {
    schedulePersistUiSnapshot();
  }
  return true;
}

function getCampaignRisPivot() {
  const risItems = ui.simRisEnabled && ui.simRisEnabled.checked ? readRisItems() : [];
  const active = risItems.find((item) => item && item.enabled !== false) || risItems[0];
  if (active && Array.isArray(active.position) && active.position.length >= 3) {
    return active.position.map((v) => Number(v));
  }
  if (Array.isArray(state.markers.ris) && state.markers.ris.length && Array.isArray(state.markers.ris[0])) {
    return state.markers.ris[0].slice(0, 3).map((v) => Number(v));
  }
  return null;
}

function campaignPivotFollowsRis() {
  return !ui.campaignPivotFollowRis || ui.campaignPivotFollowRis.checked;
}

function syncCampaignPivotUiFromRis() {
  const risPivot = getCampaignRisPivot();
  if (!campaignPivotFollowsRis() || !risPivot) return false;
  setInputValue(ui.campaignPivotX, risPivot[0]);
  setInputValue(ui.campaignPivotY, risPivot[1]);
  setInputValue(ui.campaignPivotZ, risPivot[2]);
  return true;
}

function syncCampaignPivotControls() {
  const followsRis = campaignPivotFollowsRis();
  [ui.campaignPivotX, ui.campaignPivotY, ui.campaignPivotZ].forEach((el) => {
    if (el) el.disabled = followsRis;
  });
  if (ui.campaignPivotUseRis) ui.campaignPivotUseRis.disabled = followsRis;
  if (followsRis) {
    syncCampaignPivotUiFromRis();
  }
}

function getCampaignPivotFromUi() {
  syncCampaignPivotUiFromRis();
  const pivotX = readNumber(ui.campaignPivotX);
  const pivotY = readNumber(ui.campaignPivotY);
  const pivotZ = readNumber(ui.campaignPivotZ);
  if ([pivotX, pivotY, pivotZ].some((value) => value === null)) return null;
  return [pivotX, pivotY, pivotZ];
}

function syncCampaignRadiusInputs(source = "number") {
  const value = source === "slider" ? readNumber(ui.campaignRadiusSlider) : readNumber(ui.campaignRadius);
  if (value === null) return;
  const radius = Math.min(Math.max(value, 0.2), 1.3);
  setInputValue(ui.campaignRadius, radius);
  setInputValue(ui.campaignRadiusSlider, radius);
}

function campaignPositionOnArcOriented(pivot, radiusM, angleDeg, referenceYawDeg = 0, arcHeightOffsetM = 0) {
  return campaignPositionOnArc(pivot, radiusM, angleDeg + referenceYawDeg, arcHeightOffsetM);
}

function parseAngleList(text) {
  if (!text) return [];
  return text
    .split(",")
    .map((part) => Number(part.trim()))
    .filter((value) => Number.isFinite(value));
}

function renderCampaignPreview() {
  if (!campaignPreviewGroup) return;
  campaignPreviewGroup.clear();
  updateCampaignPreviewVisibility();
  if (state.activeTab !== "campaign") return;

  const radius = readNumber(ui.campaignRadius);
  const startAngle = readNumber(ui.campaignStartAngle);
  const stopAngle = readNumber(ui.campaignStopAngle);
  const stepAngle = readNumber(ui.campaignStepAngle);
  const arcHeightOffset = readNumber(ui.campaignArcHeightOffset);
  const pivot = getCampaignPivotFromUi();
  const sweepDevice = ui.campaignSweepDevice ? ui.campaignSweepDevice.value : "rx";
  if (
    radius === null ||
    startAngle === null ||
    stopAngle === null ||
    stepAngle === null ||
    arcHeightOffset === null ||
    !pivot ||
    radius <= 0 ||
    stepAngle <= 0
  ) {
    return;
  }

  const referenceYawDeg = getCampaignReferenceYawDeg();
  const angles = computeCampaignAngleSeries(startAngle, stopAngle, stepAngle);
  if (angles.length < 2) return;
  const positions = angles.map((angle) => campaignPositionOnArcOriented(pivot, radius, angle, referenceYawDeg, arcHeightOffset));
  const points = positions.map((pos) => new THREE.Vector3(pos[0], pos[1], pos[2]));
  const sweepColor = sweepDevice === "tx" ? 0xdc2626 : 0x2563eb;

  const pathLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({ color: sweepColor, transparent: true, opacity: 0.28 })
  );
  campaignPreviewGroup.add(pathLine);

  const ghostRadius = Math.max(getTxRxOrbRadius() * 0.55, 0.025);
  const ghostGeo = new THREE.SphereGeometry(ghostRadius, 12, 12);
  const ghostMat = new THREE.MeshStandardMaterial({
    color: sweepColor,
    emissive: sweepColor,
    emissiveIntensity: 0.2,
    transparent: true,
    opacity: 0.18,
  });
  const startMat = new THREE.MeshStandardMaterial({
    color: 0x10b981,
    emissive: 0x10b981,
    emissiveIntensity: 0.3,
    transparent: true,
    opacity: 0.5,
  });
  const endMat = new THREE.MeshStandardMaterial({
    color: 0xef4444,
    emissive: 0xef4444,
    emissiveIntensity: 0.3,
    transparent: true,
    opacity: 0.5,
  });
  positions.forEach((pos, idx) => {
    const marker = new THREE.Mesh(
      ghostGeo,
      idx === 0 ? startMat : idx === positions.length - 1 ? endMat : ghostMat
    );
    marker.position.set(pos[0], pos[1], pos[2]);
    campaignPreviewGroup.add(marker);
  });

  const pivotMarker = new THREE.Mesh(
    new THREE.SphereGeometry(Math.max(ghostRadius * 0.9, 0.02), 10, 10),
    new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      emissive: 0xf59e0b,
      emissiveIntensity: 0.35,
      transparent: true,
      opacity: 0.55,
    })
  );
  pivotMarker.position.set(pivot[0], pivot[1], pivot[2]);
  campaignPreviewGroup.add(pivotMarker);
}

function renderCampaign2Preview() {
  if (!campaignPreviewGroup) return;
  campaignPreviewGroup.clear();
  updateCampaignPreviewVisibility();
  if (state.activeTab !== "campaign2") return;

  const risPose = getActiveRisPose();
  if (!risPose) return;
  const startAngle = readNumber(ui.campaign2StartAngle);
  const stopAngle = readNumber(ui.campaign2StopAngle);
  const stepAngle = readNumber(ui.campaign2StepAngle);
  const txRisDistance = readNumber(ui.campaign2TxRisDistance);
  const txIncidence = readNumber(ui.campaign2TxIncidenceAngle);
  const targetDistance = readNumber(ui.campaign2TargetDistance);
  const targetAngles = parseAngleList(ui.campaign2TargetAngles ? ui.campaign2TargetAngles.value : "");
  if (
    startAngle === null ||
    stopAngle === null ||
    stepAngle === null ||
    txRisDistance === null ||
    txIncidence === null ||
    targetDistance === null ||
    txRisDistance <= 0 ||
    targetDistance <= 0 ||
    stepAngle <= 0
  ) {
    return;
  }

  const turntableAngles = computeCampaignAngleSeries(startAngle, stopAngle, stepAngle);
  if (!turntableAngles.length) return;
  const txPositions = turntableAngles.map((angle) => campaignPositionOnArcOriented(risPose.position, txRisDistance, txIncidence, risPose.yawDeg + angle, 0.0));
  const txPoints = txPositions.map((pos) => new THREE.Vector3(pos[0], pos[1], pos[2]));
  campaignPreviewGroup.add(
    new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(txPoints),
      new THREE.LineBasicMaterial({ color: 0xdc2626, transparent: true, opacity: 0.28 })
    )
  );

  const ghostRadius = Math.max(getTxRxOrbRadius() * 0.55, 0.025);
  const txGeo = new THREE.SphereGeometry(ghostRadius, 12, 12);
  const txMat = new THREE.MeshStandardMaterial({
    color: 0xdc2626,
    emissive: 0xdc2626,
    emissiveIntensity: 0.25,
    transparent: true,
    opacity: 0.22,
  });
  txPositions.forEach((pos) => {
    const marker = new THREE.Mesh(txGeo, txMat);
    marker.position.set(pos[0], pos[1], pos[2]);
    campaignPreviewGroup.add(marker);
  });

  const uniqueTargets = targetAngles.length ? targetAngles : [0];
  uniqueTargets.forEach((targetAngle, idx) => {
    const targetPos = campaignPositionOnArcOriented(risPose.position, targetDistance, targetAngle, risPose.yawDeg, 0.0);
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(risPose.position[0], risPose.position[1], risPose.position[2]),
        new THREE.Vector3(targetPos[0], targetPos[1], targetPos[2]),
      ]),
      new THREE.LineBasicMaterial({
        color: idx % 2 === 0 ? 0x2563eb : 0x10b981,
        transparent: true,
        opacity: 0.2,
      })
    );
    campaignPreviewGroup.add(line);
  });
}

function rebuildDynamicScene({ refit = false } = {}) {
  markerGroup.clear();
  rayGroup.clear();
  heatmapGroup.clear();
  alignmentGroup.clear();
  if (campaignPreviewGroup) campaignPreviewGroup.clear();
  highlightLine = null;

  if (ui.simRisEnabled && ui.simRisEnabled.checked) {
    const risItems = readRisItems();
    state.markers.ris = risItems.map((item) => item.position || [0, 0, 0]);
  } else {
    state.markers.ris = [];
  }

  addMarkers();
  addAlignmentMarkers();
  if (state.activeTab === "campaign2") {
    renderCampaign2Preview();
  } else {
    renderCampaignPreview();
  }
  addRays();
  addHeatmap();
  markerGroup.visible = ui.toggleMarkers.checked;
  rayGroup.visible = ui.toggleRays.checked;
  heatmapGroup.visible = ui.toggleHeatmap.checked;
  alignmentGroup.visible = ui.toggleGuides.checked;
  updateHeatmapScaleVisibility();
  if (refit) fitCamera();
}

function rebuildScene(options = {}) {
  const { reloadGeometry = false, refit = false } = options;
  const sceneFilePath = getActiveSceneFilePath();
  const sceneFileAssetKey = getSceneFileAssetKey(sceneFilePath);
  const assetKey = sceneFileAssetKey || getGeometryAssetKey();
  const usingSceneFilePreview = Boolean(sceneFileAssetKey && assetKey === sceneFileAssetKey);
  const shouldReloadGeometry = Boolean(
    reloadGeometry ||
    (assetKey && state.geometryAssetKey !== assetKey) ||
    (!assetKey && geometryGroup.children.length)
  );

  if (shouldReloadGeometry) {
    geometryGroup.clear();
    state.geometryAssetKey = assetKey;
    if (!usingSceneFilePreview) {
      addProxyGeometry();
    }
    if (ui.toggleGeometry.checked && assetKey) {
      if (usingSceneFilePreview) {
        loadSceneFileMeshes(sceneFilePath, assetKey);
      } else {
        loadMeshes(assetKey);
      }
    }
  } else if (state.geometryAssetKey === null && assetKey) {
    state.geometryAssetKey = assetKey;
  }

  rebuildDynamicScene({ refit: refit || shouldReloadGeometry });
  geometryGroup.visible = ui.toggleGeometry.checked;
}

function addProxyGeometry() {
  if (!state.manifest || !state.manifest.proxy) {
    return;
  }
  const proxy = state.manifest.proxy;
  if (proxy.ground) {
    const size = proxy.ground.size || [200, 200];
    const elev = getFloorElevation();
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

function getMeshManifestEntry(name) {
  const items = state.manifest && Array.isArray(state.manifest.mesh_manifest)
    ? state.manifest.mesh_manifest
    : [];
  return items.find((item) => item && item.file === name) || null;
}

function applyBaseMeshRotation(target, rotX, rotY, rotZ) {
  if (!target) return;
  if (rotX) target.rotateX(rotX);
  if (rotY) target.rotateY(rotY);
  if (rotZ) target.rotateZ(rotZ);
}

function applyTransformOps(target, ops) {
  if (!target || !Array.isArray(ops) || !ops.length) return;
  const matrix = new THREE.Matrix4().identity();
  ops.forEach((op) => {
    if (!op || !op.type) return;
    const step = new THREE.Matrix4();
    if (op.type === "translate") {
      const value = Array.isArray(op.value) ? op.value : [0, 0, 0];
      step.makeTranslation(Number(value[0]) || 0, Number(value[1]) || 0, Number(value[2]) || 0);
    } else if (op.type === "scale") {
      const value = Array.isArray(op.value) ? op.value : [1, 1, 1];
      step.makeScale(
        Number(value[0]) || 1,
        Number(value[1]) || 1,
        Number(value[2]) || 1
      );
    } else if (op.type === "rotate") {
      const axisValue = Array.isArray(op.axis) ? op.axis : [0, 0, 0];
      const axis = new THREE.Vector3(
        Number(axisValue[0]) || 0,
        Number(axisValue[1]) || 0,
        Number(axisValue[2]) || 0
      );
      if (axis.lengthSq() <= 1e-12) return;
      axis.normalize();
      step.makeRotationAxis(axis, (Number(op.angle_deg) || 0) * Math.PI / 180);
    } else if (op.type === "matrix") {
      const value = Array.isArray(op.value) ? op.value : [];
      if (value.length !== 16) return;
      step.set(...value.map((v) => Number(v) || 0));
    } else {
      return;
    }
    matrix.premultiply(step);
  });
  target.applyMatrix4(matrix);
}

function wrapMeshObject(child, manifestEntry, rotX, rotY, rotZ) {
  const root = new THREE.Group();
  applyBaseMeshRotation(root, rotX, rotY, rotZ);
  applyTransformOps(child, manifestEntry && manifestEntry.transform_ops);
  root.add(child);
  return root;
}

function refitCameraAfterMeshLoad() {
  refreshHeatmap();
  fitCamera();
}

async function loadMeshes(assetKey = state.geometryAssetKey) {
  if (!state.manifest || !assetKey || state.geometryAssetKey !== assetKey) {
    return;
  }
  const [rotX, rotY, rotZ] = getMeshRotationRad();
  if (state.manifest.mesh) {
    const ext = state.manifest.mesh.split(".").pop().toLowerCase();
    const manifestEntry = getMeshManifestEntry(state.manifest.mesh);
    if (ext === "glb" || ext === "gltf") {
      const loader = new GLTFLoader();
      loader.load(`/runs/${state.runId}/viewer/${state.manifest.mesh}`, (gltf) => {
        if (state.geometryAssetKey !== assetKey) return;
        geometryGroup.add(wrapMeshObject(gltf.scene, manifestEntry, rotX, rotY, rotZ));
        refitCameraAfterMeshLoad();
      });
    } else if (ext === "obj") {
      const loader = new OBJLoader();
      loader.load(`/runs/${state.runId}/viewer/${state.manifest.mesh}`, (obj) => {
        if (state.geometryAssetKey !== assetKey) return;
        geometryGroup.add(wrapMeshObject(obj, manifestEntry, rotX, rotY, rotZ));
        refitCameraAfterMeshLoad();
      });
    }
  }
  if (state.manifest.mesh_files && state.manifest.mesh_files.length) {
    const loader = new PLYLoader();
    state.manifest.mesh_files.forEach((name) => {
      loader.load(`/runs/${state.runId}/viewer/${name}`, (geom) => {
        if (state.geometryAssetKey !== assetKey) return;
        geom.computeVertexNormals();
        const mat = new THREE.MeshStandardMaterial({
          color: 0x9aa8b1,
          opacity: 0.6,
          transparent: true,
          side: THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geom, mat);
        geometryGroup.add(wrapMeshObject(mesh, getMeshManifestEntry(name), rotX, rotY, rotZ));
        refitCameraAfterMeshLoad();
      });
    });
  }
}

async function loadSceneFileMeshes(scenePath, assetKey = getSceneFileAssetKey(scenePath)) {
  if (!scenePath || !assetKey || state.geometryAssetKey !== assetKey) {
    return;
  }
  const manifest = await fetchSceneFileManifest(scenePath);
  if (!manifest || !Array.isArray(manifest.mesh_files) || !manifest.mesh_files.length) {
    setMeta(`Scene preview unavailable for ${scenePath}`);
    return;
  }
  setMeta(`Previewing scene ${manifest.label || scenePath}`);
  const loader = new PLYLoader();
  manifest.mesh_files.forEach((meshPath) => {
    loader.load(
      `/api/scene_file_asset?path=${encodeURIComponent(meshPath)}`,
      (geom) => {
        if (state.geometryAssetKey !== assetKey) return;
        geom.computeVertexNormals();
        const mat = new THREE.MeshStandardMaterial({
          color: 0x9aa8b1,
          opacity: 0.6,
          transparent: true,
          side: THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geom, mat);
        const item = Array.isArray(manifest.mesh_manifest)
          ? manifest.mesh_manifest.find((entry) => entry && entry.file === meshPath)
          : null;
        geometryGroup.add(wrapMeshObject(mesh, item, 0, 0, 0));
        refitCameraAfterMeshLoad();
      },
      undefined,
      (err) => {
        console.error("Scene preview mesh load failed:", meshPath, err);
        setMeta(`Scene mesh failed to load: ${meshPath}`);
      }
    );
  });
}

function addMarkers() {
  const markerRadius = getMarkerRadius();
  const txRxOrbRadius = getTxRxOrbRadius();
  const txRxScale = getTxRxOrbScaleFactor();
  const txMat = new THREE.MeshStandardMaterial({ color: 0xdc2626, emissive: 0xdc2626, emissiveIntensity: 0.4 });
  const rxMat = new THREE.MeshStandardMaterial({ color: 0x2563eb, emissive: 0x2563eb, emissiveIntensity: 0.4 });
  const geo = new THREE.SphereGeometry(txRxOrbRadius, 16, 16);
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
    const arrowLength = Math.max((Math.max(markerRadius * 8, 1.5)) * TX_RX_MARKER_BASE_SCALE * txRxScale, 0.2);
    const arrowHeadLength = Math.max((Math.max(markerRadius * 2.0, 0.6)) * TX_RX_MARKER_BASE_SCALE * txRxScale, 0.08);
    const arrowHeadWidth = Math.max((Math.max(markerRadius * 1.0, 0.4)) * TX_RX_MARKER_BASE_SCALE * txRxScale, 0.06);
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
    const orientationUi = orientation ? risBackendOrientationToUi(orientation) : null;
    let yaw = orientationUi ? orientationUi[2] : getRisItemYaw(idx);
    if (!orientation && Array.isArray(item.look_at) && item.look_at.length >= 3) {
      const dx = item.look_at[0] - pos[0];
      const dy = item.look_at[1] - pos[1];
      yaw = Math.atan2(dy, dx);
    }
    const roll = orientationUi ? orientationUi[0] : 0;
    const pitch = orientationUi ? orientationUi[1] : 0;
    ris.rotation.set(roll, pitch, yaw);
    markerGroup.add(ris);

    if (ui.toggleRisFront && ui.toggleRisFront.checked) {
      const origin = new THREE.Vector3(pos[0], pos[1], pos[2]);
      let frontDir = new THREE.Vector3(1, 0, 0);
      // "RIS Front" should show only the panel's physical front-face direction.
      // Aim/target visualization belongs to the separate RIS Focus overlay.
      const euler = new THREE.Euler(roll, pitch, yaw, "XYZ");
      frontDir.applyEuler(euler);
      if (frontDir.lengthSq() < 1e-6) {
        frontDir = new THREE.Vector3(1, 0, 0);
      }
      frontDir.normalize();
      const arrowLength = Math.max((Math.max(Math.min(width, height) * 0.65, 0.6)) * TX_RX_MARKER_BASE_SCALE * txRxScale, 0.12);
      const arrowHeadLength = Math.max((Math.max(arrowLength * 0.28, 0.25)) * TX_RX_MARKER_BASE_SCALE * txRxScale, 0.05);
      const arrowHeadWidth = Math.max((Math.max(arrowLength * 0.12, 0.12)) * TX_RX_MARKER_BASE_SCALE * txRxScale, 0.04);
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
    const focusGeo = new THREE.SphereGeometry(Math.max(txRxOrbRadius * 0.8, 0.03), 14, 14);
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
  const markerZ = getFloorElevation() + Math.max(markerRadius * 1.5, 0.2);
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
  rebuildScene({ refit: false });
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

function _rgbToCss(rgb) {
  return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
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

const HEATMAP_STOPS = [
  { pos: 0.0, color: [12, 74, 110] },
  { pos: 0.25, color: [20, 184, 166] },
  { pos: 0.5, color: [250, 204, 21] },
  { pos: 0.75, color: [249, 115, 22] },
  { pos: 1.0, color: [220, 38, 38] },
];

const HEATMAP_DIFF_STOPS = [
  { pos: 0.0, color: [30, 64, 175] },
  { pos: 0.35, color: [59, 130, 246] },
  { pos: 0.5, color: [255, 255, 255] },
  { pos: 0.65, color: [248, 113, 113] },
  { pos: 1.0, color: [190, 24, 93] },
];

function heatmapColor(t) {
  return _gradientColor(HEATMAP_STOPS, t);
}

function heatmapColorDiff(t) {
  return _gradientColor(HEATMAP_DIFF_STOPS, t);
}

function _unionBounds(box, obj) {
  if (!obj || !obj.children || !obj.children.length) return false;
  const next = new THREE.Box3().setFromObject(obj);
  if (next.isEmpty()) return false;
  box.union(next);
  return true;
}

function _boxFromMarkerState() {
  const points = [];
  const markers = state.markers || {};
  [markers.tx, markers.rx].forEach((pos) => {
    if (Array.isArray(pos) && pos.length >= 3 && pos.every((v) => Number.isFinite(v))) {
      points.push(new THREE.Vector3(pos[0], pos[1], pos[2]));
    }
  });
  if (Array.isArray(markers.ris)) {
    markers.ris.forEach((pos) => {
      if (Array.isArray(pos) && pos.length >= 3 && pos.every((v) => Number.isFinite(v))) {
        points.push(new THREE.Vector3(pos[0], pos[1], pos[2]));
      }
    });
  }
  if (!points.length) return null;
  const box = new THREE.Box3();
  box.setFromPoints(points);
  return box;
}

function _getFitBounds() {
  const primaryBox = new THREE.Box3();
  let hasPrimaryBounds = false;
  hasPrimaryBounds = _unionBounds(primaryBox, geometryGroup) || hasPrimaryBounds;
  hasPrimaryBounds = _unionBounds(primaryBox, markerGroup) || hasPrimaryBounds;
  hasPrimaryBounds = _unionBounds(primaryBox, campaignPreviewGroup) || hasPrimaryBounds;
  if (hasPrimaryBounds) {
    return primaryBox;
  }
  const heatmapBox = new THREE.Box3();
  if (_unionBounds(heatmapBox, heatmapGroup)) {
    return heatmapBox;
  }
  return _boxFromMarkerState();
}

function fitCamera() {
  const box = _getFitBounds();
  if (!box || box.isEmpty()) {
    camera.position.set(12, 12, 8);
    controls.target.set(0, 0, 0);
    controls.update();
    return;
  }
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  let radius = Math.max(maxDim * 1.1, 1);
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
  controls.update();
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

function renderMaterialList() {
  if (!ui.materialList || !ui.meshList) return;
  ui.materialList.innerHTML = "";
  ui.meshList.innerHTML = "";
  const manifest = state.manifest || {};
  const meshEntries = Array.isArray(manifest.mesh_manifest) ? manifest.mesh_manifest : [];
  const meshFiles = [];
  if (manifest.mesh) meshFiles.push({ file: manifest.mesh, display: manifest.mesh });
  if (Array.isArray(manifest.mesh_files)) {
    manifest.mesh_files.forEach((f) => meshFiles.push({ file: f, display: f }));
  }
  const meshesToRender = meshEntries.length ? meshEntries : meshFiles;
  if (meshesToRender.length === 0) {
    ui.meshList.textContent = "No mesh files for this run.";
  } else {
    meshesToRender.forEach((entry) => {
      const name = entry.display || entry.file || "mesh";
      const meta = entry.shape_id ? `id:${entry.shape_id}` : "mesh";
      const row = document.createElement("div");
      row.className = "material-row";
      row.innerHTML = `<span class="material-name">${name}</span><span class="material-value">${meta}</span>`;
      ui.meshList.appendChild(row);
    });
  }

  const mats = Array.isArray(manifest.materials) ? manifest.materials : [];
  if (!mats.length) {
    ui.materialList.textContent = "No material metadata found.";
    return;
  }
  mats.forEach((item) => {
    const name = item.object || "object";
    const mat = item.radio_material || "unknown";
    const note = item.is_placeholder ? "placeholder" : "radio";
    const row = document.createElement("div");
    row.className = "material-row";
    row.innerHTML = `<span class="material-name">${name}</span><span class="material-value">${mat} · ${note}</span>`;
    ui.materialList.appendChild(row);
  });
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
  const floorZ = getFloorElevation();
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -floorZ);
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

async function refreshJobs(scope = getRunScopeForTab()) {
  const res = await fetch(`/api/jobs?scope=${encodeURIComponent(scope)}`);
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
  if (needsRunRefresh && !state.loadingRun) {
    await fetchRuns(scope);
  }
  if (
    !state.loadingRun &&
    state.followLatestRunByScope[scope] &&
    newestCompleted &&
    state.scopedRunIds[scope] !== newestCompleted &&
    isSimScopeTab(state.activeTab) &&
    getRunScopeForTab() === scope
  ) {
    if (ui.runSelect) {
      ui.runSelect.value = newestCompleted;
    }
    await loadRun(newestCompleted, scope);
  }
}

function buildSimJobPayload() {
  syncMarkersFromInputs();
  const profile = getProfileDefinition();
  const scope = getRequestedRunScope();
  const payload = {
    kind: "run",
    scope,
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

  if (scaleEnabled) {
    const scalePayload = {
      enabled: true,
    };
    if (scaleFactor !== null) scalePayload.factor = scaleFactor;
    payload.simulation = Object.assign(payload.simulation || {}, {
      scale_similarity: scalePayload,
    });
  }
  if (samplingEnabled) {
    const samplingPayload = {
      enabled: true,
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
  if (ui.simRisIsolation && ui.simRisIsolation.checked) {
    payload.simulation = Object.assign(payload.simulation || {}, {
      ris_isolation: true,
      los: false,
      specular_reflection: false,
    });
    payload.radio_map = Object.assign(payload.radio_map || {}, {
      los: false,
      specular_reflection: false,
      diff_ris: false,
    });
  }
  if (state.activeTab === "indoor" || state.activeTab === "campaign" || state.activeTab === "campaign2" || ui.runProfile.value === "indoor_box_high") {
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
          return null;
        }
        if (!squareGrid) {
          setMeta("RIS geometry error: only square grid supported (enable dx = dy)");
          return null;
        }
        risSize.target_dy_m = risSize.target_dx_m;
      } else if (geometryMode === "spacing_driven") {
        if (dxM === null) {
          setMeta("RIS geometry error: spacing_driven requires dx/dy");
          return null;
        }
        if (nx === null || ny === null) {
          setMeta("RIS geometry error: spacing_driven requires num cells x/y");
          return null;
        }
        if (!squareGrid) {
          setMeta("RIS geometry error: only square grid supported (enable dx = dy)");
          return null;
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
    const override = parseSceneSelectValue(ui.sceneSelect.value || "");
    if (override) applySceneSourceOverride(override);
  }
  const profileConfig = getProfileConfig();
  const baseScene = !state.sceneOverrideDirty
    ? ((profileConfig && profileConfig.data && profileConfig.data.scene) || state.sceneOverride || {})
    : (state.sceneOverride || {});
  const scenePayload = JSON.parse(JSON.stringify(baseScene));
  const floorZ = readNumber(ui.floorElevation);
  if (floorZ !== null) {
    scenePayload.floor_elevation = floorZ;
    if (scenePayload.type === "procedural" || scenePayload.procedural) {
      scenePayload.procedural = scenePayload.procedural || {};
      scenePayload.procedural.ground = scenePayload.procedural.ground || {};
      scenePayload.procedural.ground.elevation = floorZ;
    }
  }
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
  return { payload, scope };
}

async function submitJob() {
  const built = buildSimJobPayload();
  if (!built) return;
  const { payload, scope } = built;
  setMeta("Submitting run...");
  try {
    state.followLatestRunByScope[scope] = true;
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
    await refreshJobs(scope);
  } catch (err) {
    setMeta("Job error: network failure");
  }
}

function bindUI() {
  console.log("Starting bindUI...");
  syncCampaignPivotControls();
  syncCampaignRadiusInputs("number");
  syncTxAutoPlacementControls();
  if (!ui.refreshRuns) console.error("ui.refreshRuns is missing");
  ui.refreshRuns.addEventListener("click", async () => {
    const scope = getRunScopeForTab();
    await fetchRuns(scope);
    await refreshJobs(scope);
  });

  document.addEventListener("input", schedulePersistUiSnapshot, true);
  document.addEventListener("change", schedulePersistUiSnapshot, true);
  
  if (!ui.runSelect) console.error("ui.runSelect is missing");
  ui.runSelect.addEventListener("change", () => {
    const scope = getRunScopeForTab();
    state.followLatestRun = false;
    state.followLatestRunByScope[scope] = false;
    state.sceneOverrideDirty = false;
    state.scopedRunIds[scope] = ui.runSelect.value || null;
    if (!state.loadingRun) {
      loadRun(ui.runSelect.value, scope);
    }
  });
  
  if (!ui.sceneSelect) console.error("ui.sceneSelect is missing");
  ui.sceneSelect.addEventListener("change", () => {
    const value = ui.sceneSelect.value || "";
    const override = parseSceneSelectValue(value) || (value ? { type: "builtin", builtin: value } : null);
    if (override) applySceneSourceOverride(override);
    if ((state.activeTab === "indoor" || state.activeTab === "campaign" || state.activeTab === "campaign2") && override && override.type === "file") {
      const entry = getFileSceneEntry(override.file);
      if (entry) applyIndoorFileSceneDefaults(entry, override);
    }
    rebuildScene({ reloadGeometry: true, refit: false });
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
      if (ui.runProfile.value === "indoor_box_high") {
        applyIeeeTapCampaignDefaults();
      }
    }
    updateCustomVisibility();
    schedulePersistUiSnapshot();
  });

  if (ui.applyIeeeTapPreset) {
    ui.applyIeeeTapPreset.addEventListener("click", applyIeeeTapChamberPreset);
  }

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
  if (ui.simRisIsolation) {
    ui.simRisIsolation.addEventListener("change", () => {
      if (ui.simRisIsolation.checked) {
        if (ui.radioMapDiffRis) ui.radioMapDiffRis.checked = false;
        if (ui.radioMapDiffToggle) {
          ui.radioMapDiffToggle.checked = false;
          refreshHeatmapDiff();
        }
        setMeta("RIS-only isolation enabled (LOS/specular off)");
      } else {
        setMeta("RIS-only isolation disabled");
      }
    });
  }
  
  if (!ui.applyMarkers) console.error("ui.applyMarkers is missing");
  ui.applyMarkers.addEventListener("click", () => {
    syncMarkersFromInputs({ rebuild: true, persist: true });
  });
  [ui.txX, ui.txY, ui.txZ, ui.rxX, ui.rxY, ui.rxZ]
    .filter(Boolean)
    .forEach((input) => {
      input.addEventListener("change", () => {
        syncMarkersFromInputs({ rebuild: true, persist: true });
      });
    });
  
  // mesh rotation controls removed
  
  if (!ui.runSim) console.error("ui.runSim is missing");
  ui.runSim.addEventListener("click", () => submitJob());
  if (ui.runSimTop) {
    ui.runSimTop.addEventListener("click", () => submitJob());
  }
  if (ui.campaignStart) {
    ui.campaignStart.addEventListener("click", submitCampaignJob);
  }
  if (ui.campaignRunAll) {
    ui.campaignRunAll.addEventListener("click", submitCampaignRunAllJobs);
  }
  if (ui.campaignRefresh) {
    ui.campaignRefresh.addEventListener("click", refreshCampaignJobs);
  }
  if (ui.campaignLoadResults) {
    ui.campaignLoadResults.addEventListener("click", () => loadCampaignResults(ui.campaignRunSelect.value));
  }
  if (ui.campaignRunSelect) {
    ui.campaignRunSelect.addEventListener("change", () => loadCampaignResults(ui.campaignRunSelect.value));
  }
  if (ui.campaignPlotTabs) {
    ui.campaignPlotTabs.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;
      const file = target.dataset.plot;
      if (!file || !state.campaign.activeRunId) return;
      state.campaign.selectedPlot = file;
      ui.campaignPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
        btn.classList.toggle("is-active", btn === target);
      });
      renderCampaignPlotSingle(state.campaign.activeRunId, file);
    });
  }
  if (ui.campaign2Start) {
    ui.campaign2Start.addEventListener("click", submitCampaign2Job);
  }
  if (ui.campaign2RunAll) {
    ui.campaign2RunAll.addEventListener("click", submitCampaign2RunAllJobs);
  }
  if (ui.campaign2Refresh) {
    ui.campaign2Refresh.addEventListener("click", refreshCampaign2Jobs);
  }
  if (ui.campaign2LoadResults) {
    ui.campaign2LoadResults.addEventListener("click", () => loadCampaign2Results(ui.campaign2RunSelect.value));
  }
  if (ui.campaign2RunSelect) {
    ui.campaign2RunSelect.addEventListener("change", () => loadCampaign2Results(ui.campaign2RunSelect.value));
  }
  if (ui.campaign2PlotTabs) {
    ui.campaign2PlotTabs.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;
      const file = target.dataset.plot;
      if (!file || !state.campaign2.activeRunId) return;
      state.campaign2.selectedPlot = file;
      ui.campaign2PlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
        btn.classList.toggle("is-active", btn === target);
      });
      renderCampaign2PlotSingle(state.campaign2.activeRunId, file);
    });
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
    ui.risList.addEventListener("input", () => {
      syncCampaignPivotUiFromRis();
      autoPlaceTxFromRis({ updateScene: true });
      rebuildScene({ refit: false });
    });
    ui.risList.addEventListener("change", () => {
      syncCampaignPivotUiFromRis();
      autoPlaceTxFromRis({ updateScene: true });
      rebuildScene({ refit: false });
    });
  }
  if (ui.campaignRadius) {
    ui.campaignRadius.addEventListener("input", () => {
      syncCampaignRadiusInputs("number");
      rebuildScene({ refit: false });
    });
    ui.campaignRadius.addEventListener("change", () => {
      syncCampaignRadiusInputs("number");
      rebuildScene({ refit: false });
      schedulePersistUiSnapshot();
    });
  }
  if (ui.campaignRadiusSlider) {
    ui.campaignRadiusSlider.addEventListener("input", () => {
      syncCampaignRadiusInputs("slider");
      rebuildScene({ refit: false });
    });
    ui.campaignRadiusSlider.addEventListener("change", () => {
      syncCampaignRadiusInputs("slider");
      rebuildScene({ refit: false });
      schedulePersistUiSnapshot();
    });
  }
  if (ui.campaignPivotFollowRis) {
    ui.campaignPivotFollowRis.addEventListener("change", () => {
      syncCampaignPivotControls();
      rebuildScene({ refit: false });
      schedulePersistUiSnapshot();
    });
  }
  if (ui.campaignPivotUseRis) {
    ui.campaignPivotUseRis.addEventListener("click", () => {
      if (syncCampaignPivotUiFromRis()) {
        rebuildScene({ refit: false });
        schedulePersistUiSnapshot();
        setMeta("Campaign pivot aligned to RIS");
      } else {
        setMeta("No RIS position available for campaign pivot");
      }
    });
  }
  [
    ui.campaignSweepDevice,
    ui.campaignChunkSize,
    ui.campaignStartAngle,
    ui.campaignStopAngle,
    ui.campaignStepAngle,
    ui.campaignArcHeightOffset,
    ui.campaignPivotX,
    ui.campaignPivotY,
    ui.campaignPivotZ,
  ]
    .filter(Boolean)
    .forEach((el) => {
      el.addEventListener("input", () => rebuildScene({ refit: false }));
      el.addEventListener("change", () => {
        rebuildScene({ refit: false });
        schedulePersistUiSnapshot();
      });
    });
  [
    ui.campaign2TargetAngles,
    ui.campaign2Polarization,
    ui.campaign2ChunkSize,
    ui.campaign2FrequencyStart,
    ui.campaign2FrequencyStop,
    ui.campaign2FrequencyStep,
    ui.campaign2StartAngle,
    ui.campaign2StopAngle,
    ui.campaign2StepAngle,
    ui.campaign2TxRisDistance,
    ui.campaign2TargetDistance,
    ui.campaign2TxIncidenceAngle,
    ui.campaign2CoarseCell,
  ]
    .filter(Boolean)
    .forEach((el) => {
      el.addEventListener("input", () => rebuildScene({ refit: false }));
      el.addEventListener("change", () => {
        rebuildScene({ refit: false });
        schedulePersistUiSnapshot();
      });
    });
  [ui.campaign2CompactOutput, ui.campaign2DisableRender, ui.campaign2PruneRuns]
    .filter(Boolean)
    .forEach((el) => {
      el.addEventListener("change", () => {
        schedulePersistUiSnapshot();
      });
    });
  if (ui.txPattern) ui.txPattern.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txPolarization) ui.txPolarization.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txPowerDbm) ui.txPowerDbm.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txLookX) ui.txLookX.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txLookY) ui.txLookY.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txLookZ) ui.txLookZ.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.txYawDeg) ui.txYawDeg.addEventListener("change", updateSceneOverrideTxFromUi);
  if (ui.showTxDirection) ui.showTxDirection.addEventListener("change", () => rebuildScene({ refit: false }));
  if (ui.toggleRisFocus) ui.toggleRisFocus.addEventListener("change", () => rebuildScene({ refit: false }));
  if (ui.txPattern) ui.txPattern.addEventListener("change", () => {
    updateSceneOverrideTxFromUi();
    schedulePersistUiSnapshot();
  });
  if (ui.txPolarization) ui.txPolarization.addEventListener("change", () => {
    updateSceneOverrideTxFromUi();
    schedulePersistUiSnapshot();
  });
  if (ui.txAutoPlaceRis) ui.txAutoPlaceRis.addEventListener("change", () => {
    syncTxAutoPlacementControls();
    if (txAutoPlacementEnabled()) {
      autoPlaceTxFromRis({ updateScene: true, persist: true });
    } else {
      updateSceneOverrideTxFromUi();
      schedulePersistUiSnapshot();
    }
    rebuildScene({ refit: false });
  });
  if (ui.txLookAtRis) ui.txLookAtRis.addEventListener("change", () => {
    updateSceneOverrideTxFromUi();
    schedulePersistUiSnapshot();
  });
  if (ui.radioMapPlaneZ) ui.radioMapPlaneZ.addEventListener("change", () => {
    schedulePersistUiSnapshot();
  });
  if (ui.floorElevation) {
    ui.floorElevation.addEventListener("input", () => {
      updateSceneOverrideFloorFromUi();
      rebuildScene({ reloadGeometry: true, refit: false });
      schedulePersistUiSnapshot();
    });
    ui.floorElevation.addEventListener("change", () => {
      updateSceneOverrideFloorFromUi();
      rebuildScene({ reloadGeometry: true, refit: false });
      schedulePersistUiSnapshot();
    });
  }
  
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
  // Also support lightbox for sim-tab plot images
  document.querySelectorAll(".plot-card img").forEach((img) => {
    img.style.cursor = "pointer";
    img.addEventListener("click", () => {
      if (!img.src || img.src === window.location.href) return;
      if (ui.plotLightbox && ui.plotLightboxImg) {
        ui.plotLightboxImg.src = img.src;
        ui.plotLightboxImg.alt = img.alt || "Plot";
        ui.plotLightbox.style.display = "flex";
      }
    });
  });
  if (ui.plotLightbox) {
    const closeLightbox = () => { ui.plotLightbox.style.display = "none"; };
    ui.plotLightbox.addEventListener("click", closeLightbox);
    if (ui.plotLightboxClose) ui.plotLightboxClose.addEventListener("click", closeLightbox);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && ui.plotLightbox.style.display !== "none") closeLightbox();
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
    ui.risCompareUseSionna,
    ui.risCompareUsePaths,
    ui.risCompareUseCoverage,
    ui.risCompareAngles,
    ui.risCompareNormalization,
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
      updateHeatmapScaleGradient();
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
      if (!geometryGroup.children.length) {
        rebuildScene({ reloadGeometry: true, refit: true });
      }
    } else {
      geometryGroup.clear();
    }
  });
  
  if (!ui.toggleMarkers) console.error("ui.toggleMarkers is missing");
  ui.toggleMarkers.addEventListener("change", () => {
    markerGroup.visible = ui.toggleMarkers.checked;
  });
  if (ui.txRxOrbScale) {
    ui.txRxOrbScale.addEventListener("input", () => {
      syncTxRxOrbScaleFromUi(true);
    });
    ui.txRxOrbScale.addEventListener("change", () => {
      syncTxRxOrbScaleFromUi(true);
    });
    syncTxRxOrbScaleFromUi(false);
  }
  
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
autoPlaceTxFromRis({ updateScene: false });
updateSceneOverrideTxFromUi();
schedulePersistUiSnapshot();
updateRisActionVisibility();
updateRisConfigSourceVisibility();
updateRisControlVisibility();
updateRisConfigPreview();
updateRisPreview();
setCampaignRunControlsState();
setCampaign2RunControlsState();
setMainTab("sim");
fetchConfigs().then(fetchRuns).then(fetchBuiltinScenes).then(() => Promise.all([refreshCampaignJobs(), refreshCampaign2Jobs(), refreshRisJobs()]));
setInterval(() => {
  if (isSimScopeTab(state.activeTab)) {
    refreshJobs(getRunScopeForTab());
  }
  if (state.activeTab === "campaign") {
    refreshCampaignJobs();
  }
  if (state.activeTab === "campaign2") {
    refreshCampaign2Jobs();
  }
  if (state.activeTab === "ris") {
    refreshRisJobs();
  }
}, 3000);
