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
  geometryTemplateCache: new Map(),
  geometryTemplatePromises: new Map(),
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
    selectedRunId: null,
    followActiveRun: true,
    selectedPlot: null,
  },
  risSynthesis: {
    jobs: [],
    runs: [],
    seedRunScopes: {},
    activeRunId: null,
    activeJobId: null,
    selectedRunId: null,
    followActiveRun: true,
    autoLoadedViewerRunId: null,
    viewerOverlayRunId: null,
    pendingViewerOverlayRunId: null,
    viewerOverlayRequestToken: 0,
    selectedPlot: null,
    drawnBoxes: [],
    draftBox: null,
    drawMode: false,
    replaceOnNextDraw: false,
  },
  link: {
    jobs: [],
    runs: [],
    activeRunId: null,
    activeJobId: null,
    selectedPlot: null,
  },
  snapshotStudio: {
    open: false,
    renderToken: 0,
    previewUrl: "",
  },
  runBrowser: {
    open: false,
    selectedRunId: null,
    detailsByRunId: {},
  },
};

const ui = {
  runSelect: document.getElementById("runSelect"),
  refreshRuns: document.getElementById("refreshRuns"),
  runBrowserToggle: document.getElementById("runBrowserToggle"),
  runBrowserModal: document.getElementById("runBrowserModal"),
  runBrowserClose: document.getElementById("runBrowserClose"),
  runBrowserOpenRun: document.getElementById("runBrowserOpenRun"),
  runBrowserSearch: document.getElementById("runBrowserSearch"),
  runBrowserCount: document.getElementById("runBrowserCount"),
  runBrowserList: document.getElementById("runBrowserList"),
  runBrowserSubtitle: document.getElementById("runBrowserSubtitle"),
  runBrowserPreviewImage: document.getElementById("runBrowserPreviewImage"),
  runBrowserPreviewEmpty: document.getElementById("runBrowserPreviewEmpty"),
  runBrowserSelectedRun: document.getElementById("runBrowserSelectedRun"),
  runBrowserBadges: document.getElementById("runBrowserBadges"),
  runBrowserDetails: document.getElementById("runBrowserDetails"),
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
  risSynthConfigSource: document.getElementById("risSynthConfigSource"),
  risSynthConfigPath: document.getElementById("risSynthConfigPath"),
  risSynthSeedSource: document.getElementById("risSynthSeedSource"),
  risSynthSeedRun: document.getElementById("risSynthSeedRun"),
  risSynthSeedConfig: document.getElementById("risSynthSeedConfig"),
  risSynthSeedStatus: document.getElementById("risSynthSeedStatus"),
  risSynthRisName: document.getElementById("risSynthRisName"),
  risSynthBoxes: document.getElementById("risSynthBoxes"),
  risSynthIterations: document.getElementById("risSynthIterations"),
  risSynthLearningRate: document.getElementById("risSynthLearningRate"),
  risSynthLogEvery: document.getElementById("risSynthLogEvery"),
  risSynthThresholdDbm: document.getElementById("risSynthThresholdDbm"),
  risSynthObjectiveEps: document.getElementById("risSynthObjectiveEps"),
  risSynthBinarizationEnabled: document.getElementById("risSynthBinarizationEnabled"),
  risSynthOffsetSamples: document.getElementById("risSynthOffsetSamples"),
  risSynthRefineEnabled: document.getElementById("risSynthRefineEnabled"),
  risSynthCandidateBudget: document.getElementById("risSynthCandidateBudget"),
  risSynthMaxPasses: document.getElementById("risSynthMaxPasses"),
  risSynthStart: document.getElementById("risSynthStart"),
  risSynthRefresh: document.getElementById("risSynthRefresh"),
  risSynthJobStatus: document.getElementById("risSynthJobStatus"),
  risSynthProgress: document.getElementById("risSynthProgress"),
  risSynthLog: document.getElementById("risSynthLog"),
  risSynthJobList: document.getElementById("risSynthJobList"),
  risSynthRunSelect: document.getElementById("risSynthRunSelect"),
  risSynthViewerMode: document.getElementById("risSynthViewerMode"),
  risSynthApplyViewerMode: document.getElementById("risSynthApplyViewerMode"),
  risSynthLoadResults: document.getElementById("risSynthLoadResults"),
  risSynthQuantizeBits: document.getElementById("risSynthQuantizeBits"),
  risSynthQuantizeSamples: document.getElementById("risSynthQuantizeSamples"),
  risSynthQuantizeRun: document.getElementById("risSynthQuantizeRun"),
  risSynthResultStatus: document.getElementById("risSynthResultStatus"),
  risSynthMetrics: document.getElementById("risSynthMetrics"),
  risSynthPlotTabs: document.getElementById("risSynthPlotTabs"),
  risSynthPlotImage: document.getElementById("risSynthPlotImage"),
  risSynthPlotCaption: document.getElementById("risSynthPlotCaption"),
  risSynthConfigPreview: document.getElementById("risSynthConfigPreview"),
  risSynthLayout: document.getElementById("risSynthLayout"),
  risSynthRightPanel: document.getElementById("risSynthRightPanel"),
  risSynthLoadViewer: document.getElementById("risSynthLoadViewer"),
  risSynthTopDownView: document.getElementById("risSynthTopDownView"),
  risSynthDrawBoxes: document.getElementById("risSynthDrawBoxes"),
  risSynthUndoBox: document.getElementById("risSynthUndoBox"),
  risSynthClearBoxes: document.getElementById("risSynthClearBoxes"),
  risSynthViewerStatus: document.getElementById("risSynthViewerStatus"),
  linkSeedSourceType: document.getElementById("linkSeedSourceType"),
  linkSeedRun: document.getElementById("linkSeedRun"),
  linkSeedConfig: document.getElementById("linkSeedConfig"),
  linkBackend: document.getElementById("linkBackend"),
  linkEstimatorPerfect: document.getElementById("linkEstimatorPerfect"),
  linkEstimatorLsLin: document.getElementById("linkEstimatorLsLin"),
  linkEstimatorLsNn: document.getElementById("linkEstimatorLsNn"),
  linkVariantOff: document.getElementById("linkVariantOff"),
  linkVariantConfigured: document.getElementById("linkVariantConfigured"),
  linkVariantFlat: document.getElementById("linkVariantFlat"),
  linkEbnoList: document.getElementById("linkEbnoList"),
  linkBatchSize: document.getElementById("linkBatchSize"),
  linkIterations: document.getElementById("linkIterations"),
  linkFftSize: document.getElementById("linkFftSize"),
  linkNumSymbols: document.getElementById("linkNumSymbols"),
  linkScsHz: document.getElementById("linkScsHz"),
  linkBitsPerSymbol: document.getElementById("linkBitsPerSymbol"),
  linkMaxDepth: document.getElementById("linkMaxDepth"),
  linkSamplesPerSrc: document.getElementById("linkSamplesPerSrc"),
  linkNumPaths: document.getElementById("linkNumPaths"),
  linkStart: document.getElementById("linkStart"),
  linkRefresh: document.getElementById("linkRefresh"),
  linkJobStatus: document.getElementById("linkJobStatus"),
  linkProgress: document.getElementById("linkProgress"),
  linkLog: document.getElementById("linkLog"),
  linkJobList: document.getElementById("linkJobList"),
  linkRunSelect: document.getElementById("linkRunSelect"),
  linkLoadResults: document.getElementById("linkLoadResults"),
  linkResultStatus: document.getElementById("linkResultStatus"),
  linkMetrics: document.getElementById("linkMetrics"),
  linkPlotTabs: document.getElementById("linkPlotTabs"),
  linkPlotImage: document.getElementById("linkPlotImage"),
  linkPlotCaption: document.getElementById("linkPlotCaption"),
  linkSeedViewerStatus: document.getElementById("linkSeedViewerStatus"),
  linkSeedViewerFrame: document.getElementById("linkSeedViewerFrame"),
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
  radioMapZStackEnabled: document.getElementById("radioMapZStackEnabled"),
  radioMapZStackControls: document.getElementById("radioMapZStackControls"),
  radioMapZStackBelow: document.getElementById("radioMapZStackBelow"),
  radioMapZStackAbove: document.getElementById("radioMapZStackAbove"),
  radioMapZStackSpacing: document.getElementById("radioMapZStackSpacing"),
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
  campaign2ShowSpecularPath: document.getElementById("campaign2ShowSpecularPath"),
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
  snapshotStudio: document.getElementById("snapshotStudio"),
  snapshotStudioClose: document.getElementById("snapshotStudioClose"),
  snapshotRefreshPreview: document.getElementById("snapshotRefreshPreview"),
  snapshotPreviewImage: document.getElementById("snapshotPreviewImage"),
  snapshotPreviewMeta: document.getElementById("snapshotPreviewMeta"),
  snapshotStudioStatus: document.getElementById("snapshotStudioStatus"),
  snapshotPreset: document.getElementById("snapshotPreset"),
  snapshotTheme: document.getElementById("snapshotTheme"),
  snapshotWidth: document.getElementById("snapshotWidth"),
  snapshotHeight: document.getElementById("snapshotHeight"),
  snapshotScale: document.getElementById("snapshotScale"),
  snapshotView: document.getElementById("snapshotView"),
  snapshotProjection: document.getElementById("snapshotProjection"),
  snapshotFov: document.getElementById("snapshotFov"),
  snapshotMargin: document.getElementById("snapshotMargin"),
  snapshotTitle: document.getElementById("snapshotTitle"),
  snapshotIncludeTitle: document.getElementById("snapshotIncludeTitle"),
  snapshotIncludeMeta: document.getElementById("snapshotIncludeMeta"),
  snapshotIncludeScaleBar: document.getElementById("snapshotIncludeScaleBar"),
  snapshotIncludeFrame: document.getElementById("snapshotIncludeFrame"),
  snapshotDownload: document.getElementById("snapshotDownload"),
  snapshotCopy: document.getElementById("snapshotCopy"),
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
  showSpecularPath: true,
  coarseCellSizeM: 0.10,
};

const SNAPSHOT_PRESETS = {
  report_landscape: { width: 1600, height: 900 },
  report_portrait: { width: 1200, height: 1600 },
  square: { width: 1400, height: 1400 },
  uhd_4k: { width: 3840, height: 2160 },
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
const RIS_PLOT_FILES_BY_MODE = {
  pattern: new Set(["phase_map.png", "pattern_cartesian.png", "pattern_polar.png"]),
  validate: new Set(["phase_map.png", "validation_overlay.png"]),
  compare: new Set([
    "phase_map.png",
    "compare_overlay_norm_db.png",
    "compare_overlay_abs_db.png",
    "compare_error_db.png",
  ]),
};
const RIS_SYNTH_PLOT_FILES = [
  { file: "target_region_overlay.png", label: "ROI overlay" },
  { file: "radio_map_ris_off.png", label: "RIS off" },
  { file: "radio_map_continuous.png", label: "Optimal Sionna RIS" },
  { file: "radio_map_1bit.png", label: "1-Bit" },
  { file: "radio_map_quantized.png", label: "Quantized" },
  { file: "radio_map_diff_continuous_vs_off.png", label: "Continuous vs RIS off" },
  { file: "radio_map_diff_1bit_vs_off.png", label: "1-Bit vs RIS off" },
  { file: "radio_map_diff_1bit_vs_continuous.png", label: "1-Bit vs continuous" },
  { file: "radio_map_diff_quantized_vs_off.png", label: "Quantized vs RIS off" },
  { file: "radio_map_diff_quantized_vs_continuous.png", label: "Quantized vs continuous" },
  { file: "objective_trace.png", label: "Objective trace" },
  { file: "phase_continuous.png", label: "Continuous phase" },
  { file: "phase_1bit.png", label: "1-Bit phase" },
  { file: "phase_quantized.png", label: "Quantized phase" },
  { file: "cdf_roi_rx_power.png", label: "ROI Rx power CDF" },
];
const RIS_SYNTH_PLOT_LABELS = Object.fromEntries(RIS_SYNTH_PLOT_FILES.map((p) => [p.file, p.label]));
const LINK_PLOT_FILES = [
  { file: "ber_vs_ebno.png", label: "BER" },
  { file: "variant_path_gain_db.png", label: "Path Gain" },
  { file: "variant_delay_spread_ns.png", label: "Delay Spread" },
  { file: "variant_path_delay_hist_ns.png", label: "Path Delay" },
  { file: "variant_ris_phase.png", label: "RIS Phase" },
  { file: "variant_ris_amplitude.png", label: "RIS Amplitude" },
];
const LINK_PLOT_LABELS = {
  "ber_vs_ebno.png": "BER vs Eb/N0",
  "variant_path_gain_db.png": "Path gain by RIS variant",
  "variant_delay_spread_ns.png": "Delay spread by RIS variant",
  "variant_path_delay_hist_ns.png": "Path delay distribution",
  "variant_ris_phase.png": "RIS phase by variant",
  "variant_ris_amplitude.png": "RIS amplitude by variant",
};

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

function isIndoorScopeTab(tabName = state.activeTab) {
  return tabName === "indoor" || tabName === "campaign" || tabName === "campaign2";
}

function getActiveProfileKey(tabName = state.activeTab) {
  if (isIndoorScopeTab(tabName)) {
    return "indoor_box_high";
  }
  return ui.runProfile && ui.runProfile.value ? ui.runProfile.value : "cpu_only";
}

function usesSharedViewerTab(tabName) {
  return isSimScopeTab(tabName) || tabName === "ris-synth";
}

function getRunScopeForTab(tabName = state.activeTab) {
  return isIndoorScopeTab(tabName) ? "indoor" : "sim";
}

function hasActiveRisSynthesisViewerOverlay(scope = getRunScopeForTab()) {
  return Boolean(
    scope === "sim"
      && state.activeTab === "ris-synth"
      && (state.risSynthesis.viewerOverlayRunId || state.risSynthesis.pendingViewerOverlayRunId)
  );
}

function clearRisSynthesisViewerOverlay(options = {}) {
  const { keepMode = false, cancelPending = true } = options;
  if (cancelPending) {
    state.risSynthesis.viewerOverlayRequestToken += 1;
  }
  state.risSynthesis.autoLoadedViewerRunId = null;
  state.risSynthesis.viewerOverlayRunId = null;
  state.risSynthesis.pendingViewerOverlayRunId = null;
  if (!keepMode && ui.risSynthViewerMode) {
    ui.risSynthViewerMode.value = "active";
  }
}

function syncRisSynthesisSelectedRun(runId, options = {}) {
  const { followActive = false } = options;
  const nextRunId = runId || null;
  state.risSynthesis.selectedRunId = nextRunId;
  state.risSynthesis.followActiveRun = Boolean(followActive);
  if (ui.risSynthRunSelect && nextRunId && ui.risSynthRunSelect.value !== nextRunId) {
    ui.risSynthRunSelect.value = nextRunId;
  }
}

function syncRisSelectedRun(runId, options = {}) {
  const { followActive = false } = options;
  const nextRunId = runId || null;
  state.ris.selectedRunId = nextRunId;
  state.ris.followActiveRun = Boolean(followActive);
  if (ui.risRunSelect && nextRunId && ui.risRunSelect.value !== nextRunId) {
    ui.risRunSelect.value = nextRunId;
  }
}

function getRequestedRunScope() {
  return isIndoorScopeTab(state.activeTab) || getActiveProfileKey() === "indoor_box_high" ? "indoor" : "sim";
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

function cloneGeometryTemplate(template) {
  return template ? template.clone(true) : null;
}

function getCachedGeometryTemplate(assetKey) {
  if (!assetKey) return null;
  const template = state.geometryTemplateCache.get(assetKey) || null;
  if (!template) return null;
  state.geometryTemplateCache.delete(assetKey);
  state.geometryTemplateCache.set(assetKey, template);
  return template;
}

function cacheGeometryTemplate(assetKey, template) {
  if (!assetKey || !template) return template;
  if (state.geometryTemplateCache.has(assetKey)) {
    state.geometryTemplateCache.delete(assetKey);
  }
  state.geometryTemplateCache.set(assetKey, template);
  return template;
}

async function getOrBuildGeometryTemplate(assetKey, builder) {
  if (!assetKey) return null;
  const cached = getCachedGeometryTemplate(assetKey);
  if (cached) return cached;
  const pending = state.geometryTemplatePromises.get(assetKey);
  if (pending) return await pending;
  const promise = (async () => {
    const built = await builder();
    return cacheGeometryTemplate(assetKey, built);
  })();
  state.geometryTemplatePromises.set(assetKey, promise);
  try {
    return await promise;
  } finally {
    state.geometryTemplatePromises.delete(assetKey);
  }
}

let renderer;
let scene;
let camera;
let controls;
let geometryGroup;
let markerGroup;
let rayGroup;
let heatmapGroup;
let risSynthRoiGroup;
let alignmentGroup;
let campaignPreviewGroup;
let highlightLine;
let dragging = null;
let dragMode = null;
let dragRisIndex = null;
let dragStartYaw = 0;
let dragStartMouse = null;
let debugHeatmapMesh = null;
let snapshotPreviewTimer = null;
const TX_RX_MARKER_BASE_SCALE = 0.2;
const RIS_SYNTH_ROI_ELEVATION_M = 0.08;

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
    showSpecularPath: cfgCampaign.show_specular_path ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.showSpecularPath,
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
  if (ui.campaign2ShowSpecularPath) ui.campaign2ShowSpecularPath.checked = Boolean(defaults.showSpecularPath);
  setInputValue(ui.campaign2CoarseCell, defaults.coarseCellSizeM);
  syncCampaign2FixedRxPosition(config, { force: true });
}

function getCampaign2FixedRxPosition(config = getIndoorChamberConfig()) {
  const cfg = (config && config.data) || {};
  const scene = cfg.scene || {};
  const campaign = cfg.campaign || {};
  const experiment = cfg.experiment || {};
  const risObjects = cfg.ris && Array.isArray(cfg.ris.objects) ? cfg.ris.objects : [];
  const baseRis = risObjects.find((item) => item && item.enabled !== false) || risObjects[0] || {};
  const baseRisPos = Array.isArray(baseRis.position) && baseRis.position.length >= 3
    ? [Number(baseRis.position[0]), Number(baseRis.position[1]), Number(baseRis.position[2])]
    : [0.0, 1.3, 1.5];
  const baseRx = scene.rx && Array.isArray(scene.rx.position) && scene.rx.position.length >= 3
    ? [Number(scene.rx.position[0]), Number(scene.rx.position[1]), Number(scene.rx.position[2])]
    : [0.0, -0.7, 1.6];

  let baseReferenceYawDeg = 0.0;
  if (Array.isArray(baseRis.orientation) && baseRis.orientation.length >= 1) {
    baseReferenceYawDeg = _radToDeg(baseRis.orientation[0]);
  } else if (Array.isArray(baseRis.look_at) && baseRis.look_at.length >= 3) {
    const dx = Number(baseRis.look_at[0]) - baseRisPos[0];
    const dy = Number(baseRis.look_at[1]) - baseRisPos[1];
    if (Math.abs(dx) > 1e-9 || Math.abs(dy) > 1e-9) {
      baseReferenceYawDeg = _radToDeg(Math.atan2(dy, dx));
    }
  }

  const targetDistanceM = readNumber(ui.campaign2TargetDistance)
    ?? Number(experiment.rx_ris_distance_m)
    ?? IEEE_TAP_CAMPAIGN2_DEFAULTS.targetDistanceM;
  const targetHeightOffsetM = campaign.target_height_offset_m !== undefined && campaign.target_height_offset_m !== null
    ? Number(campaign.target_height_offset_m)
    : (baseRx[2] - baseRisPos[2]);
  const baseTargetAngleDeg = normalizeAngleDeg(
    _radToDeg(Math.atan2(baseRx[1] - baseRisPos[1], baseRx[0] - baseRisPos[0])) - baseReferenceYawDeg
  );
  const activeRisPose = getActiveRisPose() || { position: baseRisPos, yawDeg: baseReferenceYawDeg };
  return campaignPositionOnArcOriented(
    activeRisPose.position,
    Number.isFinite(targetDistanceM) ? targetDistanceM : IEEE_TAP_CAMPAIGN2_DEFAULTS.targetDistanceM,
    baseTargetAngleDeg,
    activeRisPose.yawDeg,
    Number.isFinite(targetHeightOffsetM) ? targetHeightOffsetM : 0.0
  ).map((value) => Number(Number(value).toFixed(4)));
}

function syncCampaign2FixedRxPosition(config = getIndoorChamberConfig(), options = {}) {
  const { force = false, rebuild = true } = options;
  const desired = getCampaign2FixedRxPosition(config);
  const current = Array.isArray(state.markers.rx) && state.markers.rx.length >= 3
    ? [Number(state.markers.rx[0]), Number(state.markers.rx[1]), Number(state.markers.rx[2])]
    : null;
  const matchesDesired = Boolean(
    current &&
    current.every((value, idx) => Number.isFinite(value) && Math.abs(value - desired[idx]) < 1e-6)
  );
  if (!force && matchesDesired) {
    return false;
  }

  state.markers.rx = desired.slice();
  const sceneCfg = state.sceneOverride || {};
  sceneCfg.rx = Object.assign(sceneCfg.rx || {}, { position: state.markers.rx });
  state.sceneOverride = sceneCfg;
  state.sceneOverrideDirty = true;
  updateInputs();
  if (rebuild) {
    rebuildScene({ refit: false });
  }
  return true;
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

function moveViewerPanel(targetLayout, beforeNode = null) {
  if (!targetLayout) return;
  const viewer = document.getElementById("viewerPanel");
  if (!viewer) return;
  if (beforeNode && beforeNode.parentElement === targetLayout) {
    targetLayout.insertBefore(viewer, beforeNode);
    return;
  }
  targetLayout.appendChild(viewer);
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
      zStackEnabled: readCheck(ui.radioMapZStackEnabled),
      zStackBelow: readText(ui.radioMapZStackBelow),
      zStackAbove: readText(ui.radioMapZStackAbove),
      zStackSpacing: readText(ui.radioMapZStackSpacing),
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
      showSpecularPath: readCheck(ui.campaign2ShowSpecularPath),
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
    setCheck(ui.radioMapZStackEnabled, snapshot.radio.zStackEnabled);
    setText(ui.radioMapZStackBelow, snapshot.radio.zStackBelow);
    setText(ui.radioMapZStackAbove, snapshot.radio.zStackAbove);
    setText(ui.radioMapZStackSpacing, snapshot.radio.zStackSpacing);
    setText(ui.radioMapPlotStyle, snapshot.radio.plotStyle);
    setText(ui.radioMapPlotMetric, snapshot.radio.plotMetric);
    setCheck(ui.radioMapPlotShowTx, snapshot.radio.showTx);
    setCheck(ui.radioMapPlotShowRx, snapshot.radio.showRx);
    setCheck(ui.radioMapPlotShowRis, snapshot.radio.showRis);
    setCheck(ui.radioMapDiffRis, snapshot.radio.diffRis);
    syncRadioMapZStackControls({ primeDefaults: snapshot.radio.zStackEnabled });
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
    setCheck(ui.campaign2ShowSpecularPath, snapshot.campaign2.showSpecularPath !== false);
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

function backendForwardVectorFromOrientation(orientation) {
  if (!Array.isArray(orientation) || orientation.length < 3) return null;
  const a = Number(orientation[0]) || 0;
  const b = Number(orientation[1]) || 0;
  const cosA = Math.cos(a);
  const cosB = Math.cos(b);
  const sinA = Math.sin(a);
  const sinB = Math.sin(b);
  return new THREE.Vector3(
    cosA * cosB,
    sinA * cosB,
    -sinB
  );
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
  renderRisSynthesisRoiOverlay();
}

function initViewer() {
  const container = document.getElementById("viewerCanvas");
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x070c12);
  camera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 5000);
  camera.position.set(80, 80, 80);
  camera.up.set(0, 0, 1);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
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

  const hemi = new THREE.HemisphereLight(0xf7fbff, 0x0f1720, 0.92);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xf8fbff, 0.9);
  dir.position.set(50, 120, 60);
  scene.add(dir);

  geometryGroup = new THREE.Group();
  markerGroup = new THREE.Group();
  rayGroup = new THREE.Group();
  heatmapGroup = new THREE.Group();
  risSynthRoiGroup = new THREE.Group();
  alignmentGroup = new THREE.Group();
  alignmentGroup.visible = false;
  campaignPreviewGroup = new THREE.Group();
  campaignPreviewGroup.visible = false;
  scene.add(
    geometryGroup,
    markerGroup,
    rayGroup,
    heatmapGroup,
    risSynthRoiGroup,
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

function computeScaleBarMetrics(activeCamera, width, height, target = controls?.target || new THREE.Vector3(0, 0, 0)) {
  if (!activeCamera || !width || !height) return null;
  const center = target || new THREE.Vector3(0, 0, 0);
  const z = Number.isFinite(center.z) ? center.z : 0;
  const candidates = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000];
  const minPx = 70;
  const maxPx = 180;
  let best = null;
  let bestScore = Infinity;
  candidates.forEach((length) => {
    const p1 = new THREE.Vector3(center.x - length / 2, center.y, z);
    const p2 = new THREE.Vector3(center.x + length / 2, center.y, z);
    const s1 = p1.clone().project(activeCamera);
    const s2 = p2.clone().project(activeCamera);
    const dx = (s2.x - s1.x) * (width / 2);
    const dy = (s2.y - s1.y) * (height / 2);
    const px = Math.hypot(dx, dy);
    if (!Number.isFinite(px) || px <= 0) return;
    const targetPx = (minPx + maxPx) / 2;
    const score = Math.abs(px - targetPx);
    if ((px >= minPx && px <= maxPx && score < bestScore) || (!best && score < bestScore)) {
      bestScore = score;
      best = { length, px };
    }
  });
  if (!best) return null;
  const px = Math.max(24, Math.min(best.px, 260));
  let label = `${best.length} m`;
  if (best.length >= 1000) {
    label = `${(best.length / 1000).toFixed(best.length % 1000 === 0 ? 0 : 1)} km`;
  } else if (best.length < 1) {
    label = `${Math.round(best.length * 100)} cm`;
  }
  return { px, label, length: best.length };
}

function updateScaleBar() {
  if (!ui.scaleBar || !ui.scaleBarLabel || !ui.scaleBarLine) return;
  if (!camera || !renderer || !controls) return;
  const width = renderer.domElement.clientWidth;
  const height = renderer.domElement.clientHeight;
  if (!width || !height) return;
  const metrics = computeScaleBarMetrics(camera, width, height, controls.target || new THREE.Vector3(0, 0, 0));
  if (!metrics) return;
  ui.scaleBarLine.style.width = `${metrics.px}px`;
  ui.scaleBarLabel.textContent = metrics.label;
}

function setMeta(text) {
  ui.viewerMeta.textContent = text;
}

function getSnapshotDefaultTitle() {
  const sceneName =
    state.manifest?.label
    || state.runInfo?.summary?.runtime?.scene_label
    || (ui.sceneSelect && ui.sceneSelect.selectedOptions && ui.sceneSelect.selectedOptions[0]?.textContent)
    || "Scene";
  const runName = state.runId || "preview";
  return `${sceneName} · ${runName}`;
}

function setSnapshotStudioStatus(text) {
  if (ui.snapshotStudioStatus) ui.snapshotStudioStatus.textContent = text;
}

function setSnapshotPreviewMeta(text) {
  if (ui.snapshotPreviewMeta) ui.snapshotPreviewMeta.textContent = text;
}

function readSnapshotInt(input, fallback, min = 0) {
  const value = parseInt(input?.value || "", 10);
  if (!Number.isFinite(value)) return fallback;
  return Math.max(min, value);
}

function readSnapshotFloat(input, fallback, min = 0) {
  const value = parseFloat(input?.value || "");
  if (!Number.isFinite(value)) return fallback;
  return Math.max(min, value);
}

function applySnapshotPreset(presetName) {
  const preset = SNAPSHOT_PRESETS[presetName];
  if (!preset) return;
  if (ui.snapshotWidth) ui.snapshotWidth.value = String(preset.width);
  if (ui.snapshotHeight) ui.snapshotHeight.value = String(preset.height);
}

function syncSnapshotPresetFromDimensions() {
  if (!ui.snapshotPreset) return;
  const width = readSnapshotInt(ui.snapshotWidth, 0);
  const height = readSnapshotInt(ui.snapshotHeight, 0);
  const matching = Object.entries(SNAPSHOT_PRESETS).find(([, preset]) => preset.width === width && preset.height === height);
  ui.snapshotPreset.value = matching ? matching[0] : "custom";
}

function updateSnapshotStudioControlState() {
  if (ui.snapshotFov) ui.snapshotFov.disabled = ui.snapshotProjection?.value === "orthographic";
}

function getSnapshotOptions() {
  const width = readSnapshotInt(ui.snapshotWidth, 1600, 320);
  const height = readSnapshotInt(ui.snapshotHeight, 900, 240);
  const margin = readSnapshotInt(ui.snapshotMargin, 28, 0);
  return {
    preset: ui.snapshotPreset?.value || "report_landscape",
    width,
    height,
    supersample: readSnapshotInt(ui.snapshotScale, 2, 1),
    theme: ui.snapshotTheme?.value || "dark_viewer",
    view: ui.snapshotView?.value || "current",
    projection: ui.snapshotProjection?.value || "perspective",
    fov: readSnapshotFloat(ui.snapshotFov, camera?.fov || 35, 10),
    margin,
    title: (ui.snapshotTitle?.value || "").trim() || getSnapshotDefaultTitle(),
    includeTitle: Boolean(ui.snapshotIncludeTitle?.checked),
    includeMeta: Boolean(ui.snapshotIncludeMeta?.checked),
    includeScaleBar: Boolean(ui.snapshotIncludeScaleBar?.checked),
    includeFrame: Boolean(ui.snapshotIncludeFrame?.checked),
  };
}

function getSnapshotThemeConfig(themeName) {
  if (themeName === "report_light") {
    return {
      matte: "#f7f8fb",
      background: 0xf7f8fb,
      transparent: false,
      title: "#18212b",
      subtitle: "#516172",
      frame: "#cbd5df",
      scale: "#18212b",
      scaleText: "#18212b",
      footerBg: "#ffffff",
      footerText: "#314050",
    };
  }
  if (themeName === "transparent") {
    return {
      matte: null,
      background: null,
      transparent: true,
      title: "#e8eef6",
      subtitle: "#b4c0cb",
      frame: "rgba(255,255,255,0.2)",
      scale: "#e8eef6",
      scaleText: "#e8eef6",
      footerBg: "rgba(7,12,18,0.72)",
      footerText: "#e8eef6",
    };
  }
  return {
    matte: "#070c12",
    background: 0x070c12,
    transparent: false,
    title: "#f2f8ff",
    subtitle: "#8fa0b2",
    frame: "#223241",
    scale: "#f2f8ff",
    scaleText: "#f2f8ff",
    footerBg: "#0b1117",
    footerText: "#e8eef6",
  };
}

function getBoundsCorners(box) {
  const min = box.min;
  const max = box.max;
  return [
    new THREE.Vector3(min.x, min.y, min.z),
    new THREE.Vector3(min.x, min.y, max.z),
    new THREE.Vector3(min.x, max.y, min.z),
    new THREE.Vector3(min.x, max.y, max.z),
    new THREE.Vector3(max.x, min.y, min.z),
    new THREE.Vector3(max.x, min.y, max.z),
    new THREE.Vector3(max.x, max.y, min.z),
    new THREE.Vector3(max.x, max.y, max.z),
  ];
}

function getSnapshotViewDirection(viewName) {
  if (viewName === "current" && camera && controls) {
    const delta = camera.position.clone().sub(controls.target);
    if (delta.lengthSq() > 0) return delta.normalize();
  }
  if (viewName === "top") return new THREE.Vector3(0, 0, 1);
  if (viewName === "front") return new THREE.Vector3(0, -1, 0);
  if (viewName === "right") return new THREE.Vector3(1, 0, 0);
  return new THREE.Vector3(1, 1, 0.8).normalize();
}

function getCameraFrameFromDirection(box, direction, width, height) {
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 1);
  const viewDir = direction.clone().normalize();
  const worldUp = Math.abs(viewDir.dot(new THREE.Vector3(0, 0, 1))) > 0.95
    ? new THREE.Vector3(0, 1, 0)
    : new THREE.Vector3(0, 0, 1);
  const right = new THREE.Vector3().crossVectors(worldUp, viewDir).normalize();
  const up = new THREE.Vector3().crossVectors(viewDir, right).normalize();
  const corners = getBoundsCorners(box);
  let halfWidth = 0;
  let halfHeight = 0;
  let halfDepth = 0;
  corners.forEach((corner) => {
    const rel = corner.clone().sub(center);
    halfWidth = Math.max(halfWidth, Math.abs(rel.dot(right)));
    halfHeight = Math.max(halfHeight, Math.abs(rel.dot(up)));
    halfDepth = Math.max(halfDepth, Math.abs(rel.dot(viewDir)));
  });
  const aspect = Math.max(width / Math.max(height, 1), 0.1);
  let fitHalfHeight = Math.max(halfHeight, halfWidth / aspect, maxDim * 0.15);
  fitHalfHeight *= 1.16;
  const fitHalfWidth = fitHalfHeight * aspect;
  return {
    center,
    viewDir,
    right,
    up,
    halfDepth,
    fitHalfWidth,
    fitHalfHeight,
    maxDim,
  };
}

function buildSnapshotCamera(options, width, height) {
  const box = _getFitBounds();
  if (!box || box.isEmpty()) {
    const fallback = camera ? camera.clone() : new THREE.PerspectiveCamera(options.fov || 35, width / height, 0.1, 5000);
    fallback.aspect = width / height;
    fallback.updateProjectionMatrix();
    return fallback;
  }
  const direction = getSnapshotViewDirection(options.view);
  const frame = getCameraFrameFromDirection(box, direction, width, height);
  if (options.view === "current" && camera && options.projection === "perspective") {
    const cloned = camera.clone();
    cloned.aspect = width / Math.max(height, 1);
    cloned.fov = options.fov || camera.fov;
    cloned.updateProjectionMatrix();
    return cloned;
  }
  if (options.projection === "orthographic") {
    const ortho = new THREE.OrthographicCamera(
      -frame.fitHalfWidth,
      frame.fitHalfWidth,
      frame.fitHalfHeight,
      -frame.fitHalfHeight,
      0.1,
      frame.maxDim * 20 + frame.halfDepth * 10 + 100,
    );
    const distance = Math.max(frame.maxDim * 4, frame.halfDepth * 6 + 10);
    ortho.position.copy(frame.center.clone().add(frame.viewDir.clone().multiplyScalar(distance)));
    ortho.up.copy(frame.up);
    ortho.lookAt(frame.center);
    ortho.updateProjectionMatrix();
    ortho.updateMatrixWorld();
    return ortho;
  }
  const perspective = new THREE.PerspectiveCamera(options.fov || 35, width / Math.max(height, 1), 0.1, frame.maxDim * 20 + 1000);
  const vFov = THREE.MathUtils.degToRad(perspective.fov);
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * perspective.aspect);
  const distanceY = frame.fitHalfHeight / Math.tan(vFov / 2);
  const distanceX = frame.fitHalfWidth / Math.tan(hFov / 2);
  const distance = Math.max(distanceX, distanceY) + frame.halfDepth + frame.maxDim * 0.35;
  perspective.position.copy(frame.center.clone().add(frame.viewDir.clone().multiplyScalar(distance)));
  perspective.up.copy(frame.up);
  perspective.lookAt(frame.center);
  perspective.updateProjectionMatrix();
  perspective.updateMatrixWorld();
  return perspective;
}

function drawSnapshotScaleBar(ctx, theme, metrics, width, height, margin) {
  if (!metrics) return;
  const lineWidth = Math.max(2, Math.round(height * 0.002));
  const barX = margin;
  const barY = height - margin - 28;
  ctx.save();
  ctx.lineWidth = lineWidth;
  ctx.strokeStyle = theme.scale;
  ctx.fillStyle = theme.scaleText;
  ctx.font = '12px "IBM Plex Mono", monospace';
  ctx.textBaseline = "bottom";
  ctx.fillText(metrics.label, barX, barY - 8);
  ctx.beginPath();
  ctx.moveTo(barX, barY);
  ctx.lineTo(barX + metrics.px, barY);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(barX, barY - 6);
  ctx.lineTo(barX, barY + 6);
  ctx.moveTo(barX + metrics.px, barY - 6);
  ctx.lineTo(barX + metrics.px, barY + 6);
  ctx.stroke();
  ctx.restore();
}

function drawSnapshotTitle(ctx, theme, title, margin, width) {
  if (!title) return 0;
  ctx.save();
  ctx.fillStyle = theme.title;
  ctx.font = '600 24px "IBM Plex Sans", sans-serif';
  ctx.textBaseline = "top";
  ctx.fillText(title, margin, margin);
  ctx.restore();
  return 32;
}

function drawSnapshotFooter(ctx, theme, text, width, height, margin) {
  const footerHeight = 28;
  const y = height - margin - footerHeight;
  ctx.save();
  ctx.fillStyle = theme.footerBg;
  ctx.fillRect(margin, y, width - margin * 2, footerHeight);
  ctx.fillStyle = theme.footerText;
  ctx.font = '12px "IBM Plex Mono", monospace';
  ctx.textBaseline = "middle";
  ctx.fillText(text, margin + 10, y + footerHeight / 2);
  ctx.restore();
  return footerHeight + 8;
}

async function renderSnapshotCanvas(options, mode = "export") {
  if (!scene) throw new Error("Viewer scene is not ready.");
  const baseWidth = Math.max(320, Math.round(options.width));
  const baseHeight = Math.max(240, Math.round(options.height));
  const previewScale = mode === "preview" ? Math.min(1, 1100 / Math.max(baseWidth, baseHeight)) : 1;
  const outputWidth = Math.max(320, Math.round(baseWidth * previewScale));
  const outputHeight = Math.max(240, Math.round(baseHeight * previewScale));
  const supersample = mode === "preview" ? 1 : Math.max(1, options.supersample || 1);
  const renderWidth = outputWidth * supersample;
  const renderHeight = outputHeight * supersample;
  const exportCamera = buildSnapshotCamera(options, renderWidth, renderHeight);
  const theme = getSnapshotThemeConfig(options.theme);
  const rendererOptions = { antialias: true, alpha: theme.transparent, preserveDrawingBuffer: true };
  const exportRenderer = new THREE.WebGLRenderer(rendererOptions);
  const previousBackground = scene.background;
  try {
    exportRenderer.setPixelRatio(1);
    exportRenderer.setSize(renderWidth, renderHeight, false);
    scene.background = theme.transparent || theme.background === null ? null : new THREE.Color(theme.background);
    exportRenderer.render(scene, exportCamera);
    const imageCanvas = exportRenderer.domElement;
    const finalCanvas = document.createElement("canvas");
    finalCanvas.width = outputWidth;
    finalCanvas.height = outputHeight;
    const ctx = finalCanvas.getContext("2d");
    if (!ctx) throw new Error("2D export context unavailable.");
    if (theme.matte) {
      ctx.fillStyle = theme.matte;
      ctx.fillRect(0, 0, outputWidth, outputHeight);
    } else {
      ctx.clearRect(0, 0, outputWidth, outputHeight);
    }
    const margin = Math.round(options.margin * previewScale);
    let topOffset = margin;
    let bottomReserve = margin;
    if (options.includeTitle) {
      topOffset += drawSnapshotTitle(ctx, theme, options.title, margin, outputWidth);
    }
    const footerText = `${state.runId || "preview"} · ${state.paths.length} paths · ${options.projection} · ${baseWidth}x${baseHeight}`;
    if (options.includeMeta) {
      bottomReserve += drawSnapshotFooter(ctx, theme, footerText, outputWidth, outputHeight, margin);
    }
    const drawX = margin;
    const drawY = topOffset;
    const drawWidth = Math.max(1, outputWidth - margin * 2);
    const drawHeight = Math.max(1, outputHeight - topOffset - bottomReserve);
    ctx.drawImage(imageCanvas, drawX, drawY, drawWidth, drawHeight);
    if (options.includeFrame) {
      ctx.save();
      ctx.strokeStyle = theme.frame;
      ctx.lineWidth = 1;
      ctx.strokeRect(drawX + 0.5, drawY + 0.5, drawWidth - 1, drawHeight - 1);
      ctx.restore();
    }
    if (options.includeScaleBar) {
      const metrics = computeScaleBarMetrics(exportCamera, drawWidth, drawHeight, controls?.target || new THREE.Vector3(0, 0, 0));
      if (metrics) {
        drawSnapshotScaleBar(ctx, theme, metrics, outputWidth, outputHeight, margin + 12);
      }
    }
    const meta = `${options.view} · ${options.projection} · ${baseWidth}x${baseHeight} · ${options.supersample}x`;
    return { canvas: finalCanvas, meta };
  } finally {
    scene.background = previousBackground;
    exportRenderer.dispose();
  }
}

function canvasToBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("Snapshot export failed."));
    }, "image/png");
  });
}

async function updateSnapshotPreview() {
  if (!state.snapshotStudio.open) return;
  const token = ++state.snapshotStudio.renderToken;
  const options = getSnapshotOptions();
  updateSnapshotStudioControlState();
  setSnapshotStudioStatus("Rendering preview...");
  try {
    const { canvas, meta } = await renderSnapshotCanvas(options, "preview");
    if (token !== state.snapshotStudio.renderToken) return;
    const url = canvas.toDataURL("image/png");
    if (state.snapshotStudio.previewUrl) URL.revokeObjectURL?.(state.snapshotStudio.previewUrl);
    state.snapshotStudio.previewUrl = url;
    if (ui.snapshotPreviewImage) ui.snapshotPreviewImage.src = url;
    setSnapshotPreviewMeta(meta);
    setSnapshotStudioStatus("Preview ready.");
  } catch (err) {
    console.error("Snapshot preview failed:", err);
    setSnapshotStudioStatus(`Preview failed: ${err.message || err}`);
  }
}

function scheduleSnapshotPreview(delay = 150) {
  if (!state.snapshotStudio.open) return;
  if (snapshotPreviewTimer) window.clearTimeout(snapshotPreviewTimer);
  snapshotPreviewTimer = window.setTimeout(() => {
    snapshotPreviewTimer = null;
    updateSnapshotPreview();
  }, delay);
}

function openSnapshotStudio() {
  if (!ui.snapshotStudio) return;
  state.snapshotStudio.open = true;
  ui.snapshotStudio.classList.remove("is-hidden");
  ui.snapshotStudio.setAttribute("aria-hidden", "false");
  if (ui.snapshotTitle && !ui.snapshotTitle.value) {
    ui.snapshotTitle.value = getSnapshotDefaultTitle();
  }
  syncSnapshotPresetFromDimensions();
  updateSnapshotStudioControlState();
  scheduleSnapshotPreview(10);
}

function closeSnapshotStudio() {
  if (!ui.snapshotStudio) return;
  state.snapshotStudio.open = false;
  if (snapshotPreviewTimer) {
    window.clearTimeout(snapshotPreviewTimer);
    snapshotPreviewTimer = null;
  }
  ui.snapshotStudio.classList.add("is-hidden");
  ui.snapshotStudio.setAttribute("aria-hidden", "true");
}

async function downloadSnapshotExport() {
  const options = getSnapshotOptions();
  setSnapshotStudioStatus("Rendering export...");
  try {
    const { canvas } = await renderSnapshotCanvas(options, "export");
    const link = document.createElement("a");
    link.download = `snapshot-${state.runId || "run"}-${options.view}-${options.theme}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
    setSnapshotStudioStatus("PNG downloaded.");
  } catch (err) {
    console.error("Snapshot export failed:", err);
    setSnapshotStudioStatus(`Export failed: ${err.message || err}`);
  }
}

async function copySnapshotExport() {
  if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") {
    setSnapshotStudioStatus("Clipboard image export is not available in this browser.");
    return;
  }
  const options = getSnapshotOptions();
  setSnapshotStudioStatus("Rendering copy payload...");
  try {
    const { canvas } = await renderSnapshotCanvas(options, "export");
    const blob = await canvasToBlob(canvas);
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    setSnapshotStudioStatus("PNG copied to clipboard.");
  } catch (err) {
    console.error("Snapshot copy failed:", err);
    setSnapshotStudioStatus(`Copy failed: ${err.message || err}`);
  }
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

function primeRadioMapZStackDefaults() {
  if (ui.radioMapZStackBelow && ui.radioMapZStackBelow.value === "") {
    ui.radioMapZStackBelow.value = "1";
  }
  if (ui.radioMapZStackAbove && ui.radioMapZStackAbove.value === "") {
    ui.radioMapZStackAbove.value = "1";
  }
  if (ui.radioMapZStackSpacing && ui.radioMapZStackSpacing.value === "") {
    ui.radioMapZStackSpacing.value = "0.5";
  }
}

function syncRadioMapZStackControls(options = {}) {
  const { primeDefaults = false } = options;
  const enabled = Boolean(ui.radioMapZStackEnabled && ui.radioMapZStackEnabled.checked);
  if (enabled && primeDefaults) {
    primeRadioMapZStackDefaults();
  }
  [ui.radioMapZStackBelow, ui.radioMapZStackAbove, ui.radioMapZStackSpacing].forEach((el) => {
    if (el) el.disabled = !enabled;
  });
  if (ui.radioMapZStackControls) {
    ui.radioMapZStackControls.classList.toggle("is-disabled", !enabled);
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
  const risSynthLayout = document.getElementById("risSynthLayout");
  const risSynthRightPanel = document.getElementById("risSynthRightPanel");
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
      if (isCampaign2) {
        syncCampaign2FixedRxPosition(getIndoorChamberConfig(), { force: true });
      }
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
    if (ui.runProfile) ui.runProfile.value = "indoor_box_high";
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
    if (simLayout) {
      moveSharedPanels(simLayout);
    }
    if (indoorSection) indoorSection.style.display = "none";
    setSimilarityScalingLocked(false);
    state.viewerScale.enabled = false;
  } else {
    if (tabName === "sim") {
      moveSharedPanels(simLayout);
    } else if (tabName === "ris-synth") {
      moveViewerPanel(risSynthLayout, risSynthRightPanel);
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
    } else if (tabName === "ris-synth") {
      void fetchRuns("sim").then(() => loadRisSynthesisViewerRun(false));
      void refreshJobs("sim");
      void refreshRisSynthesisJobs();
      renderRisSynthesisRoiOverlay();
      if (state.heatmap && state.heatmap.values) {
        setRisSynthesisViewerStatus(`Viewer ready on ${state.runId || ui.runSelect?.value || "selected run"}.`);
      } else {
        setRisSynthesisViewerStatus("Load a sim run with a heatmap, then switch to Top-Down + Heatmap.");
      }
    }
    requestAnimationFrame(() => {
      refreshViewerSize();
      if (tabName === "ris-synth") {
        renderRisSynthesisRoiOverlay();
      }
      fitCamera();
    });
  }
  if (risSynthRoiGroup) {
    risSynthRoiGroup.visible = tabName === "ris-synth";
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

function parseRisSynthesisBoxes() {
  const raw = ui.risSynthBoxes && typeof ui.risSynthBoxes.value === "string" ? ui.risSynthBoxes.value.trim() : "[]";
  if (!raw) {
    throw new Error("Target boxes JSON is required.");
  }
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed) || !parsed.length) {
    throw new Error("Target boxes must be a non-empty JSON array.");
  }
  return parsed.map((box, index) => ({
    name: box && box.name ? String(box.name) : `roi_${index + 1}`,
    u_min_m: Number(box.u_min_m),
    u_max_m: Number(box.u_max_m),
    v_min_m: Number(box.v_min_m),
    v_max_m: Number(box.v_max_m),
  }));
}

function getRisSynthesisSeedConfigObject() {
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  if (seedSource === "active_run") {
    return (state.runInfo && state.runInfo.config) || null;
  }
  const runId = getRisSynthesisSeedRunId();
  const details = runId ? state.runConfigs[runId] : null;
  return (details && details.config) || null;
}

function getCoverageMapBoundsFromConfig(config) {
  const radio = config && config.radio_map;
  if (!radio || typeof radio !== "object" || !radio.enabled) return null;
  const center = Array.isArray(radio.center) ? radio.center : [0, 0, 0];
  const size = Array.isArray(radio.size) ? radio.size : [0, 0];
  const cellSize = Array.isArray(radio.cell_size) ? radio.cell_size : [1, 1];
  const centerX = Number(center[0]);
  const centerY = Number(center[1]);
  const sizeX = Number(size[0]);
  const sizeY = Number(size[1]);
  const cellX = Number(cellSize[0]);
  const cellY = Number(cellSize[1]);
  if (![centerX, centerY, sizeX, sizeY, cellX, cellY].every((value) => Number.isFinite(value))) {
    return null;
  }
  if (sizeX <= 0 || sizeY <= 0 || cellX <= 0 || cellY <= 0) {
    return null;
  }
  const numX = Math.max(1, Math.round(sizeX / Math.max(cellX, 1.0e-9)));
  const numY = Math.max(1, Math.round(sizeY / Math.max(cellY, 1.0e-9)));
  const halfSpanX = ((numX - 1) * 0.5) * cellX;
  const halfSpanY = ((numY - 1) * 0.5) * cellY;
  return {
    u_min_m: centerX - halfSpanX,
    u_max_m: centerX + halfSpanX,
    v_min_m: centerY - halfSpanY,
    v_max_m: centerY + halfSpanY,
    center: [centerX, centerY],
    size: [sizeX, sizeY],
    cell_size: [cellX, cellY],
  };
}

function risSynthesisBoxIntersectsBounds(box, bounds) {
  if (!box || !bounds) return false;
  return !(
    Number(box.u_max_m) < Number(bounds.u_min_m)
    || Number(box.u_min_m) > Number(bounds.u_max_m)
    || Number(box.v_max_m) < Number(bounds.v_min_m)
    || Number(box.v_min_m) > Number(bounds.v_max_m)
  );
}

function formatRisSynthesisBounds(bounds) {
  if (!bounds) return "unknown bounds";
  return `u=[${bounds.u_min_m.toFixed(2)}, ${bounds.u_max_m.toFixed(2)}], v=[${bounds.v_min_m.toFixed(2)}, ${bounds.v_max_m.toFixed(2)}]`;
}

function hasStaticCoverageMapBounds(config) {
  const radio = config && config.radio_map;
  if (!radio || typeof radio !== "object" || !radio.enabled) return false;
  return !Boolean(radio.auto_size);
}

function buildRisSynthesisConfigFromUI() {
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  const seedRunId = getRisSynthesisSeedRunId();
  const seedConfigPath = getRisSynthesisSeedConfigPath();
  if (!seedConfigPath) {
    if (seedSource === "seed_run") {
      throw new Error("Select a seed sim run.");
    }
    throw new Error(seedSource === "active_run"
      ? "Load a sim run first so target region illumination can use the active viewer scene."
      : "Seed config path is required.");
  }
  const defaultRisName = getDefaultRisNameForRisSynthesis();
  if (seedSource === "seed_run" && seedRunId) {
    const details = state.runConfigs[seedRunId];
    if (details && getRisNamesFromConfig(details.config).length === 0) {
      throw new Error(`Selected seed run ${seedRunId} does not contain any RIS objects.`);
    }
  }
  const boxes = parseRisSynthesisBoxes();
  const seedConfigObject = getRisSynthesisSeedConfigObject();
  const bounds = hasStaticCoverageMapBounds(seedConfigObject)
    ? getCoverageMapBoundsFromConfig(seedConfigObject)
    : null;
  if (bounds && !boxes.some((box) => risSynthesisBoxIntersectsBounds(box, bounds))) {
    throw new Error(
      `ROI boxes do not intersect the seed coverage map (${formatRisSynthesisBounds(bounds)}). `
      + "Load the seed run into the viewer and redraw the ROI on that heatmap."
    );
  }
  return {
    schema_version: 1,
    seed: {
      type: "config",
      config_path: seedConfigPath,
      ris_name: (ui.risSynthRisName && ui.risSynthRisName.value.trim()) || defaultRisName || "ris",
      source_run_id: seedSource === "config_file" ? null : seedRunId,
    },
    target_region: {
      plane: "coverage_map",
      boxes,
      freeze_mask: true,
    },
    objective: {
      kind: "mean_log_path_gain",
      eps: readOptionalNumber(ui.risSynthObjectiveEps, 1.0e-12),
      threshold_dbm: readOptionalNumber(ui.risSynthThresholdDbm, -90.0),
      temperature_db: 2.0,
    },
    parameterization: {
      kind: "steering_search",
      basis: "quadratic",
    },
    search: {
      azimuth_span_deg: 30.0,
      elevation_span_deg: 16.0,
      coarse_num_azimuth: 9,
      coarse_num_elevation: 5,
      coarse_cell_scale: 4.0,
      coarse_sample_scale: 0.15,
      refine_top_k: 5,
      refine_num_azimuth: 7,
      refine_num_elevation: 5,
      refine_cell_scale: 2.0,
      refine_sample_scale: 0.4,
    },
    optimizer: {
      iterations: readOptionalInt(ui.risSynthIterations, 60),
      learning_rate: readOptionalNumber(ui.risSynthLearningRate, 0.03),
      algorithm: "adam",
      log_every: readOptionalInt(ui.risSynthLogEvery, 5),
    },
    binarization: {
      enabled: ui.risSynthBinarizationEnabled ? Boolean(ui.risSynthBinarizationEnabled.checked) : false,
      method: "global_offset_sweep",
      num_offset_samples: readOptionalInt(ui.risSynthOffsetSamples, 181),
    },
    refinement: {
      enabled: ui.risSynthRefineEnabled ? Boolean(ui.risSynthRefineEnabled.checked) : false,
      method: "greedy_flip",
      candidate_budget: readOptionalInt(ui.risSynthCandidateBudget, 64),
      max_passes: readOptionalInt(ui.risSynthMaxPasses, 1),
    },
    evaluation: {
      dense_map: {
        enabled: true,
      },
    },
    output: {
      base_dir: "outputs",
    },
  };
}

function updateRisSynthesisConfigSourceVisibility() {
  const source = ui.risSynthConfigSource ? ui.risSynthConfigSource.value : "builder";
  const fileFields = document.querySelectorAll(".ris-synth-config-file");
  fileFields.forEach((el) => {
    el.style.display = source === "file" ? "" : "none";
  });
}

function getActiveViewerSeedRunId() {
  return (ui.runSelect && ui.runSelect.value) || state.runId || null;
}

function getRunSeedConfigPath(runId, details = null) {
  if (!runId) return "";
  const runDetails = details || state.runConfigs[runId] || null;
  if (runDetails && runDetails.effective_config) {
    return `outputs/${runId}/config.yaml`;
  }
  if (runDetails && runDetails.config) {
    return `outputs/${runId}/job_config.yaml`;
  }
  return `outputs/${runId}/config.yaml`;
}

function getActiveViewerSeedConfigPath() {
  const runId = getActiveViewerSeedRunId();
  return runId ? getRunSeedConfigPath(runId, state.runInfo) : null;
}

function getRisSynthesisSeedRunId() {
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  if (seedSource === "active_run") {
    return getActiveViewerSeedRunId();
  }
  if (seedSource === "seed_run") {
    return (ui.risSynthSeedRun && ui.risSynthSeedRun.value) || null;
  }
  return null;
}

function getRisSynthesisSeedConfigPath() {
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  if (seedSource === "config_file") {
    return (ui.risSynthSeedConfig && ui.risSynthSeedConfig.value.trim()) || "";
  }
  const runId = getRisSynthesisSeedRunId();
  return runId ? getRunSeedConfigPath(runId) : "";
}

function getActiveViewerSceneLabel() {
  return getSceneLabelFromConfig(state.runInfo && state.runInfo.config ? state.runInfo.config : null);
}

function getSceneLabelFromConfig(config) {
  const sceneCfg = config && config.scene ? config.scene : null;
  if (!sceneCfg || typeof sceneCfg !== "object") return null;
  if (sceneCfg.type === "file" && sceneCfg.file) return String(sceneCfg.file);
  if (sceneCfg.type === "builtin" && sceneCfg.builtin) return `builtin:${sceneCfg.builtin}`;
  return null;
}

function getDefaultRisNameFromActiveRun() {
  const risObjects = (((state.runInfo || {}).config || {}).ris || {}).objects || [];
  if (!Array.isArray(risObjects) || !risObjects.length) return null;
  const first = risObjects.find((item) => item && item.name) || risObjects[0];
  return first && first.name ? String(first.name) : null;
}

function getRisNamesFromConfig(config) {
  const risObjects = (((config || {}).ris || {}).objects || []);
  if (!Array.isArray(risObjects)) return [];
  return risObjects
    .map((item) => (item && item.name ? String(item.name) : ""))
    .filter(Boolean);
}

async function ensureRunDetailsCached(runId) {
  if (!runId) return null;
  if (state.runConfigs[runId]) return state.runConfigs[runId];
  const details = await fetchRunDetails(runId);
  if (details) {
    state.runConfigs[runId] = details;
  }
  return details;
}

function getDefaultRisNameForRisSynthesis() {
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  if (seedSource === "active_run") {
    return getDefaultRisNameFromActiveRun();
  }
  const runId = getRisSynthesisSeedRunId();
  const details = runId ? state.runConfigs[runId] : null;
  const risNames = getRisNamesFromConfig((details && details.config) || null);
  return risNames[0] || null;
}

async function updateRisSynthesisSeedStatus() {
  if (!ui.risSynthSeedStatus) return;
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  if (seedSource === "seed_run") {
    const runId = getRisSynthesisSeedRunId();
    if (!runId) {
      ui.risSynthSeedStatus.textContent = "Select a completed sim run to use as the seed scene.";
      return;
    }
    const details = await ensureRunDetailsCached(runId);
    const sceneLabel = getSceneLabelFromConfig(details && details.config ? details.config : null);
    const configPath = getRisSynthesisSeedConfigPath();
    const risNames = getRisNamesFromConfig((details && details.config) || null);
    const bounds = hasStaticCoverageMapBounds((details && details.config) || null)
      ? getCoverageMapBoundsFromConfig((details && details.config) || null)
      : null;
    if (ui.risSynthRisName && (!ui.risSynthRisName.value.trim() || ui.risSynthRisName.value.trim() === "ris")) {
      if (risNames[0]) ui.risSynthRisName.value = risNames[0];
    }
    const sceneText = sceneLabel ? ` · scene ${sceneLabel}` : "";
    const risText = risNames.length ? ` · RIS ${risNames.join(", ")}` : " · no RIS objects found";
    const boundsText = bounds ? ` · map ${formatRisSynthesisBounds(bounds)}` : "";
    ui.risSynthSeedStatus.textContent = `Using sim run ${runId}${sceneText}${risText}${boundsText} → ${configPath}`;
    return;
  }
  if (seedSource === "active_run") {
    const runId = getActiveViewerSeedRunId();
    const configPath = getActiveViewerSeedConfigPath();
    const sceneLabel = getActiveViewerSceneLabel();
    const bounds = hasStaticCoverageMapBounds((state.runInfo && state.runInfo.config) || null)
      ? getCoverageMapBoundsFromConfig((state.runInfo && state.runInfo.config) || null)
      : null;
    if (!runId || !configPath) {
      ui.risSynthSeedStatus.textContent = "Active viewer run is not loaded yet. Load a sim run first.";
      return;
    }
    const sceneText = sceneLabel ? ` · scene ${sceneLabel}` : "";
    const boundsText = bounds ? ` · map ${formatRisSynthesisBounds(bounds)}` : "";
    ui.risSynthSeedStatus.textContent = `Using active viewer run ${runId}${sceneText}${boundsText} → ${configPath}`;
    if (ui.risSynthRisName && !ui.risSynthRisName.value.trim()) {
      const defaultRisName = getDefaultRisNameFromActiveRun();
      if (defaultRisName) ui.risSynthRisName.value = defaultRisName;
    }
    return;
  }
  const configPath = (ui.risSynthSeedConfig && ui.risSynthSeedConfig.value.trim()) || "";
  ui.risSynthSeedStatus.textContent = configPath
    ? `Using seed config file ${configPath}`
    : "Enter a seed config file path or switch back to Active viewer run.";
}

function updateRisSynthesisSeedSourceVisibility() {
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  document.querySelectorAll(".ris-synth-seed-run-field").forEach((el) => {
    el.style.display = seedSource === "seed_run" ? "" : "none";
  });
  document.querySelectorAll(".ris-synth-seed-config-field").forEach((el) => {
    el.style.display = seedSource === "config_file" ? "" : "none";
  });
  void updateRisSynthesisSeedStatus();
}

function updateRisSynthesisBinarizationVisibility() {
  const enabled = ui.risSynthBinarizationEnabled ? Boolean(ui.risSynthBinarizationEnabled.checked) : false;
  [ui.risSynthOffsetSamples, ui.risSynthRefineEnabled, ui.risSynthCandidateBudget, ui.risSynthMaxPasses].forEach((el) => {
    if (el) el.disabled = !enabled;
  });
}

function updateRisSynthesisConfigPreview() {
  if (!ui.risSynthConfigPreview) return;
  if (ui.risSynthConfigSource && ui.risSynthConfigSource.value === "file") {
    ui.risSynthConfigPreview.textContent = "Using config file path.";
    return;
  }
  try {
    ui.risSynthConfigPreview.textContent = JSON.stringify(buildRisSynthesisConfigFromUI(), null, 2);
  } catch (err) {
    ui.risSynthConfigPreview.textContent = `Config error: ${err instanceof Error ? err.message : String(err)}`;
  }
}

function setRisSynthesisViewerStatus(text) {
  if (ui.risSynthViewerStatus) {
    ui.risSynthViewerStatus.textContent = text;
  }
}

function getNextRisSynthesisRoiName() {
  const existingBoxes = state.risSynthesis.replaceOnNextDraw ? [] : (state.risSynthesis.drawnBoxes || []);
  const taken = new Set(existingBoxes.map((box) => String(box?.name || "")));
  let index = Math.max(existingBoxes.length, 0) + 1;
  while (taken.has(`roi_${index}`)) {
    index += 1;
  }
  return `roi_${index}`;
}

function normalizeRisSynthesisBox(box, index = 0) {
  if (!box || typeof box !== "object") return null;
  const u0 = Number(box.u_min_m);
  const u1 = Number(box.u_max_m);
  const v0 = Number(box.v_min_m);
  const v1 = Number(box.v_max_m);
  if (![u0, u1, v0, v1].every((value) => Number.isFinite(value))) {
    return null;
  }
  return {
    name: box.name ? String(box.name) : `roi_${index + 1}`,
    u_min_m: Math.min(u0, u1),
    u_max_m: Math.max(u0, u1),
    v_min_m: Math.min(v0, v1),
    v_max_m: Math.max(v0, v1),
  };
}

function getRisSynthesisMaskStatsFromCellCenters(cellCenters, boxes) {
  if (!Array.isArray(cellCenters) || !cellCenters.length || !Array.isArray(cellCenters[0]) || !cellCenters[0].length) {
    return null;
  }
  const normalizedBoxes = (boxes || [])
    .map((box, index) => normalizeRisSynthesisBox(box, index))
    .filter(Boolean);
  if (!normalizedBoxes.length) {
    return { count: 0, bounds: null };
  }
  let count = 0;
  let uMin = Infinity;
  let uMax = -Infinity;
  let vMin = Infinity;
  let vMax = -Infinity;
  cellCenters.forEach((row) => {
    row.forEach((cell) => {
      if (!Array.isArray(cell) || cell.length < 2) return;
      const u = Number(cell[0]);
      const v = Number(cell[1]);
      if (!Number.isFinite(u) || !Number.isFinite(v)) return;
      if (u < uMin) uMin = u;
      if (u > uMax) uMax = u;
      if (v < vMin) vMin = v;
      if (v > vMax) vMax = v;
      if (normalizedBoxes.some((box) => (
        u >= box.u_min_m
        && u <= box.u_max_m
        && v >= box.v_min_m
        && v <= box.v_max_m
      ))) {
        count += 1;
      }
    });
  });
  const bounds = Number.isFinite(uMin) && Number.isFinite(vMin)
    ? { u_min_m: uMin, u_max_m: uMax, v_min_m: vMin, v_max_m: vMax }
    : null;
  return { count, bounds };
}

function formatRisSynthesisCellCenterBounds(bounds) {
  if (!bounds) return "unknown bounds";
  return `u=[${bounds.u_min_m.toFixed(2)}, ${bounds.u_max_m.toFixed(2)}], v=[${bounds.v_min_m.toFixed(2)}, ${bounds.v_max_m.toFixed(2)}]`;
}

function getRisSynthesisViewerSeedRunId() {
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  if (seedSource === "config_file") return null;
  return getRisSynthesisSeedRunId();
}

function isViewingRisSynthesisSeedHeatmap() {
  const seedRunId = getRisSynthesisViewerSeedRunId();
  if (!seedRunId) return Boolean(state.heatmap && state.heatmap.cell_centers);
  return Boolean(
    state.runId === seedRunId
      && !state.risSynthesis.viewerOverlayRunId
      && !state.risSynthesis.pendingViewerOverlayRunId
      && state.heatmap
      && state.heatmap.cell_centers
  );
}

async function getRisSynthesisSeedHeatmap() {
  if (isViewingRisSynthesisSeedHeatmap()) {
    return state.heatmap;
  }
  const seedRunId = getRisSynthesisViewerSeedRunId();
  if (!seedRunId) return null;
  const heatmap = await fetchJsonMaybe(`/runs/${seedRunId}/viewer/heatmap.json`);
  return heatmap && heatmap.cell_centers ? heatmap : null;
}

async function validateRisSynthesisBoxesAgainstSeedGrid(boxes) {
  const heatmap = await getRisSynthesisSeedHeatmap();
  if (!heatmap || !heatmap.cell_centers) {
    return { ok: true, count: null, bounds: null };
  }
  const stats = getRisSynthesisMaskStatsFromCellCenters(heatmap.cell_centers, boxes);
  if (!stats) {
    return { ok: true, count: null, bounds: null };
  }
  return {
    ok: stats.count > 0,
    count: stats.count,
    bounds: stats.bounds,
  };
}

async function ensureRisSynthesisViewerMatchesSeedRun() {
  const seedRunId = getRisSynthesisViewerSeedRunId();
  if (!seedRunId) {
    return Boolean(state.heatmap && state.heatmap.values);
  }
  if (isViewingRisSynthesisSeedHeatmap()) {
    return true;
  }
  await loadRisSynthesisViewerRun(true);
  return isViewingRisSynthesisSeedHeatmap();
}

function syncRisSynthesisDrawModeUi() {
  if (ui.risSynthDrawBoxes) {
    ui.risSynthDrawBoxes.textContent = state.risSynthesis.drawMode ? "Stop Drawing" : "Draw ROIs";
  }
}

function setRisSynthesisDrawMode(enabled) {
  state.risSynthesis.drawMode = Boolean(enabled);
  state.risSynthesis.draftBox = null;
  state.risSynthesis.replaceOnNextDraw = Boolean(enabled && (state.risSynthesis.drawnBoxes || []).length);
  if (controls) {
    controls.enabled = true;
  }
  syncRisSynthesisDrawModeUi();
  renderRisSynthesisRoiOverlay();
}

function syncRisSynthesisBoxesTextareaFromState() {
  if (!ui.risSynthBoxes) return;
  ui.risSynthBoxes.value = JSON.stringify(state.risSynthesis.drawnBoxes || [], null, 2);
  if (ui.risSynthConfigSource && ui.risSynthConfigSource.value !== "builder") {
    ui.risSynthConfigSource.value = "builder";
    updateRisSynthesisConfigSourceVisibility();
  }
  updateRisSynthesisConfigPreview();
}

function syncRisSynthesisBoxesStateFromTextarea(options = {}) {
  const { quiet = false } = options;
  try {
    const boxes = parseRisSynthesisBoxes()
      .map((box, index) => normalizeRisSynthesisBox(box, index))
      .filter(Boolean);
    if (!boxes.length) {
      throw new Error("At least one ROI box is required.");
    }
    state.risSynthesis.drawnBoxes = boxes;
    state.risSynthesis.draftBox = null;
    renderRisSynthesisRoiOverlay();
    if (!quiet) {
      setRisSynthesisViewerStatus(`${boxes.length} ROI box${boxes.length === 1 ? "" : "es"} ready.`);
    }
    return true;
  } catch (err) {
    if (!quiet) {
      setRisSynthesisViewerStatus(`ROI JSON error: ${err instanceof Error ? err.message : String(err)}`);
    }
    return false;
  }
}

function getRisSynthesisOverlayBaseZ() {
  if (debugHeatmapMesh) {
    const box = new THREE.Box3().setFromObject(debugHeatmapMesh);
    if (!box.isEmpty()) {
      return box.max.z + RIS_SYNTH_ROI_ELEVATION_M;
    }
  }
  const active = getActiveHeatmap();
  if (active && Array.isArray(active.center) && Number.isFinite(Number(active.center[2]))) {
    return Number(active.center[2]) + RIS_SYNTH_ROI_ELEVATION_M;
  }
  return getFloorElevation() + RIS_SYNTH_ROI_ELEVATION_M;
}

function addRisSynthesisRoiOverlayBox(box, options = {}) {
  if (!risSynthRoiGroup) return;
  const { draft = false } = options;
  const z = getRisSynthesisOverlayBaseZ();
  const corners = [
    new THREE.Vector3(box.u_min_m, box.v_min_m, z),
    new THREE.Vector3(box.u_max_m, box.v_min_m, z),
    new THREE.Vector3(box.u_max_m, box.v_max_m, z),
    new THREE.Vector3(box.u_min_m, box.v_max_m, z),
  ];
  const line = new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(corners),
    new THREE.LineBasicMaterial({
      color: draft ? 0xf59e0b : 0x22c55e,
      transparent: true,
      opacity: draft ? 0.95 : 0.9,
    }),
  );
  line.renderOrder = 4;
  risSynthRoiGroup.add(line);

  const shape = new THREE.Shape();
  shape.moveTo(box.u_min_m, box.v_min_m);
  shape.lineTo(box.u_max_m, box.v_min_m);
  shape.lineTo(box.u_max_m, box.v_max_m);
  shape.lineTo(box.u_min_m, box.v_max_m);
  shape.closePath();
  const fill = new THREE.Mesh(
    new THREE.ShapeGeometry(shape),
    new THREE.MeshBasicMaterial({
      color: draft ? 0xf59e0b : 0x22c55e,
      transparent: true,
      opacity: draft ? 0.14 : 0.09,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  );
  fill.position.z = z - 0.01;
  fill.renderOrder = 3;
  risSynthRoiGroup.add(fill);
}

function renderRisSynthesisRoiOverlay() {
  if (!risSynthRoiGroup) return;
  risSynthRoiGroup.clear();
  risSynthRoiGroup.visible = state.activeTab === "ris-synth";
  (state.risSynthesis.drawnBoxes || []).forEach((box, index) => {
    const normalized = normalizeRisSynthesisBox(box, index);
    if (normalized) {
      addRisSynthesisRoiOverlayBox(normalized);
    }
  });
  if (state.risSynthesis.draftBox) {
    const draft = normalizeRisSynthesisBox(state.risSynthesis.draftBox, state.risSynthesis.drawnBoxes.length);
    if (draft) {
      addRisSynthesisRoiOverlayBox(draft, { draft: true });
    }
  }
}

function getViewerBounds(options = {}) {
  const { preferHeatmap = false } = options;
  if (preferHeatmap && debugHeatmapMesh) {
    const heatmapBox = new THREE.Box3().setFromObject(debugHeatmapMesh);
    if (!heatmapBox.isEmpty()) {
      return heatmapBox;
    }
  }
  return _getFitBounds();
}

function setTopDownView(options = {}) {
  const { preferHeatmap = false } = options;
  const box = getViewerBounds({ preferHeatmap });
  if (!box || box.isEmpty()) {
    camera.position.set(0.2, 0.2, 200);
    controls.target.set(0, 0, 0);
    controls.update();
    return;
  }
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, 1.0);
  const halfFov = THREE.MathUtils.degToRad(camera.fov * 0.5);
  const distance = Math.max((maxDim * 1.2) / (2 * Math.tan(halfFov || 1)), size.z + maxDim, 20.0);
  camera.position.set(center.x + maxDim * 0.001, center.y + maxDim * 0.001, center.z + distance);
  controls.target.copy(center);
  camera.lookAt(center);
  controls.update();
}

function prepareRisSynthesisViewer() {
  if (ui.toggleHeatmap && !ui.toggleHeatmap.checked) {
    ui.toggleHeatmap.checked = true;
    heatmapGroup.visible = true;
    updateHeatmapScaleVisibility();
  }
  if (ui.heatmapRotation) {
    ui.heatmapRotation.value = "0";
  }
  if (ui.heatmapRotationLabel) {
    ui.heatmapRotationLabel.textContent = "0";
  }
  refreshHeatmap();
  renderRisSynthesisRoiOverlay();
  setTopDownView({ preferHeatmap: true });
}

function getRisSynthesisHeatmapHit(event) {
  if (!debugHeatmapMesh) return null;
  const mouse = getMouse(event);
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObject(debugHeatmapMesh, true);
  if (!hits.length) return null;
  return hits[0].point.clone();
}

async function loadRisSynthesisViewerRun(force = false) {
  const seedSource = ui.risSynthSeedSource ? ui.risSynthSeedSource.value : "seed_run";
  const runId = seedSource === "seed_run"
    ? getRisSynthesisSeedRunId()
    : (ui.runSelect ? ui.runSelect.value : null);
  if (!runId) {
    setRisSynthesisViewerStatus("No seed sim run is selected.");
    return;
  }
  const scope = seedSource === "seed_run"
    ? (state.risSynthesis.seedRunScopes[runId] || "sim")
    : getRunScopeForTab();
  clearRisSynthesisViewerOverlay();
  await loadRun(runId, scope, { force });
  if (state.heatmap && state.heatmap.values) {
    setRisSynthesisViewerStatus(`Viewer loaded ${runId}. Use Top-Down + Heatmap before drawing.`);
  } else {
    setRisSynthesisViewerStatus(`Loaded ${runId}, but this run has no heatmap to draw on.`);
  }
  renderRisSynthesisRoiOverlay();
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatRunBrowserTimestamp(runId) {
  const match = String(runId || "").match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
  if (!match) return "Unknown time";
  const [, year, month, day, hour, minute, second] = match;
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

function formatRunBrowserDuration(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) return "n/a";
  if (seconds < 60) return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return `${mins}m ${String(secs).padStart(2, "0")}s`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return `${hours}h ${String(remMins).padStart(2, "0")}m`;
}

function formatRunBrowserNumber(value, digits = 1, suffix = "") {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  return `${value.toFixed(digits)}${suffix}`;
}

function getRunBrowserScopeLabel(scope) {
  return scope === "indoor" ? "Indoor" : "Simulation";
}

function getRunBrowserKindLabel(kind) {
  if (kind === "campaign") return "Campaign";
  if (kind === "link_level") return "Link";
  if (kind === "ris_lab") return "RIS Lab";
  if (kind === "ris_synthesis") return "Target Region Illumination";
  return "Run";
}

function getRunBrowserSearchText(run) {
  return [
    run.run_id,
    run.scene_label,
    run.backend,
    run.quality_preset,
    run.scope,
    run.kind,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function getRunById(runId) {
  return (state.runs || []).find((run) => run && run.run_id === runId) || null;
}

function formatMetricValue(value) {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(4) : "n/a";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function resolveRunArtifactHref(runId, value) {
  if (!runId || typeof value !== "string" || !value.trim()) return null;
  const trimmed = value.trim();
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://") || trimmed.startsWith("/")) {
    return trimmed;
  }
  let rel = trimmed.replace(/\\/g, "/");
  const runPrefix = `outputs/${runId}/`;
  if (rel.startsWith(runPrefix)) {
    rel = rel.slice(runPrefix.length);
  }
  if (!rel) return null;
  return `/runs/${runId}/${rel}`;
}

function appendMetricValue(row, key, value, runId = null) {
  const label = document.createElement("strong");
  label.textContent = `${key}: `;
  row.appendChild(label);
  const href = resolveRunArtifactHref(runId, value);
  if (href && /\.(ya?ml|npy|png)$/i.test(String(value))) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = String(value);
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    row.appendChild(link);
    return;
  }
  const val = document.createElement("span");
  val.textContent = formatMetricValue(value);
  row.appendChild(val);
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

function renderLinkMetrics(summary) {
  ui.linkMetrics.innerHTML = "";
  if (!summary) {
    ui.linkMetrics.textContent = "No link-level metrics found for this run.";
    return;
  }
  const rows = [
    ["seed_type", summary.seed ? summary.seed.type : null],
    ["seed_run_id", summary.seed ? summary.seed.run_id : null],
    ["seed_config_path", summary.seed ? summary.seed.config_path : null],
    ["prepared_seed_run_id", summary.seed ? summary.seed.prepared_run_id : null],
    ["rt_backend", summary.runtime ? summary.runtime.rt_backend : null],
    ["mitsuba_variant", summary.runtime ? summary.runtime.mitsuba_variant : null],
    ["rt_max_depth", summary.evaluation ? summary.evaluation.rt_max_depth : null],
    ["rt_samples_per_src", summary.evaluation ? summary.evaluation.rt_samples_per_src : null],
    ["seed_rt_max_depth", summary.evaluation ? summary.evaluation.seed_rt_max_depth : null],
    ["seed_rt_samples_per_src", summary.evaluation ? summary.evaluation.seed_rt_samples_per_src : null],
    ["estimators", summary.evaluation ? (summary.evaluation.estimators || []).join(", ") : null],
    ["ebno_db_list", summary.evaluation ? (summary.evaluation.ebno_db_list || []).join(", ") : null],
    ["ber_reference_mode", summary.evaluation ? summary.evaluation.ber_reference_mode : null],
    ["ber_reference_path_gain_db", summary.evaluation ? summary.evaluation.ber_reference_path_gain_db : null],
  ];
  rows.forEach(([key, value]) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = `${key}: `;
    const val = document.createElement("span");
    val.textContent = formatMetricValue(value);
    row.append(label, val);
    ui.linkMetrics.appendChild(row);
  });
  const warnings = Array.isArray(summary.warnings) ? summary.warnings : [];
  warnings.forEach((warning, index) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = `warning_${index + 1}: `;
    const val = document.createElement("span");
    val.textContent = formatMetricValue(warning);
    row.append(label, val);
    ui.linkMetrics.appendChild(row);
  });
  const variants = summary.results || {};
  Object.values(variants).forEach((variant) => {
    const row = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = `${variant.label || variant.key}: `;
    const val = document.createElement("span");
    const parts = [];
    if (variant.path_gain_db !== undefined && variant.path_gain_db !== null) {
      parts.push(`gain ${formatMetricValue(variant.path_gain_db)} dB`);
    }
    if (variant.rms_delay_spread_ns !== undefined && variant.rms_delay_spread_ns !== null) {
      parts.push(`delay ${formatMetricValue(variant.rms_delay_spread_ns)} ns`);
    }
    if (variant.num_ris_paths !== undefined && variant.num_ris_paths !== null) {
      parts.push(`RIS paths ${formatMetricValue(variant.num_ris_paths)}`);
    }
    val.textContent = parts.join(" · ") || "n/a";
    row.append(label, val);
    ui.linkMetrics.appendChild(row);
  });
}

function renderLinkPlotSingle(runId, file) {
  if (!ui.linkPlotImage || !ui.linkPlotCaption) return;
  const label = LINK_PLOT_LABELS[file] || file;
  ui.linkPlotCaption.textContent = label;
  ui.linkPlotImage.onerror = () => {
    setLinkResultStatus(`Plot not found for this run: ${file}`);
  };
  ui.linkPlotImage.onload = () => {
    if (state.link.activeRunId === runId) {
      setLinkResultStatus("Results loaded.");
    }
  };
  ui.linkPlotImage.src = `/runs/${runId}/plots/${file}?v=${Date.now()}`;
  ui.linkPlotImage.alt = label;
}

function renderLinkPlotTabs(plots, activeFile) {
  if (!ui.linkPlotTabs) return;
  ui.linkPlotTabs.innerHTML = "";
  const requested = Array.isArray(plots) && plots.length
    ? plots
    : LINK_PLOT_FILES.map((plot) => plot.file);
  requested.forEach((file, index) => {
    const meta = LINK_PLOT_FILES.find((plot) => plot.file === file);
    const button = document.createElement("button");
    button.className = `plot-tab-button${file === activeFile || (!activeFile && index === 0) ? " is-active" : ""}`;
    button.dataset.plot = file;
    button.type = "button";
    button.textContent = meta ? meta.label : (LINK_PLOT_LABELS[file] || file);
    ui.linkPlotTabs.appendChild(button);
  });
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
  ui.campaignPlotImage.src = `/runs/${runId}/plots/${file}?v=${Date.now()}`;
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
  ui.campaign2PlotImage.src = `/runs/${runId}/plots/${file}?v=${Date.now()}`;
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

function setRisSynthesisStatus(text) {
  ui.risSynthJobStatus.textContent = text;
}

function setRisSynthesisResultStatus(text) {
  ui.risSynthResultStatus.textContent = text;
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

function setLinkStatus(text) {
  ui.linkJobStatus.textContent = text;
}

function setLinkResultStatus(text) {
  ui.linkResultStatus.textContent = text;
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
  return RUN_PROFILES[getActiveProfileKey()] || RUN_PROFILES.cpu_only;
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
  const zStack = radio && typeof radio.z_stack === "object" && radio.z_stack ? radio.z_stack : {};
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
  if (ui.radioMapZStackEnabled) {
    ui.radioMapZStackEnabled.checked = Boolean(zStack.enabled);
  }
  setInputValue(ui.radioMapZStackBelow, zStack.num_below);
  setInputValue(ui.radioMapZStackAbove, zStack.num_above);
  setInputValue(ui.radioMapZStackSpacing, zStack.spacing_m);
  syncRadioMapZStackControls({ primeDefaults: Boolean(zStack.enabled) });
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
  const isCustom = getActiveProfileKey() === "custom" || isIndoorScopeTab(state.activeTab);
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
  void refreshLinkSeedOptions();
}

async function fetchRuns(scope = getRunScopeForTab()) {
  const res = await fetch(`/api/runs?scope=${encodeURIComponent(scope)}`);
  const data = await res.json();
  state.runs = data.runs || [];
  state.runBrowser.detailsByRunId = Object.fromEntries(
    Object.entries(state.runBrowser.detailsByRunId || {}).filter(([runId]) => state.runs.some((run) => run.run_id === runId)),
  );
  const isActiveScope = usesSharedViewerTab(state.activeTab) && getRunScopeForTab() === scope;
  const preserveTargetRegionViewer = isActiveScope && hasActiveRisSynthesisViewerOverlay(scope);
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
    if (isActiveScope && !preserveTargetRegionViewer) {
      state.runId = nextRunId;
      ui.runSelect.value = nextRunId;
    }
    if (ui.radioMapDiffRun && isActiveScope && !preserveTargetRegionViewer) {
      ui.radioMapDiffRun.value = previousDiff || nextRunId;
    }
    if (
      !preserveTargetRegionViewer
      && !state.loadingRun
      && state.lastLoadedRunByScope[scope] !== nextRunId
      && isActiveScope
    ) {
      await loadRun(nextRunId, scope);
    }
  } else if (isActiveScope) {
    state.runId = null;
  }
  renderRunBrowserList();
  if (scope === "sim") {
    void refreshLinkSeedOptions();
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

function renderRunBrowserBadges(run) {
  if (!ui.runBrowserBadges) return;
  const badges = [
    getRunBrowserScopeLabel(run.scope),
    getRunBrowserKindLabel(run.kind),
    run.backend,
    run.quality_preset ? `${run.quality_preset} preset` : null,
    run.has_viewer ? "Viewer ready" : "No viewer",
  ].filter(Boolean);
  ui.runBrowserBadges.innerHTML = badges
    .map((badge) => `<span class="run-browser-badge">${escapeHtml(badge)}</span>`)
    .join("");
}

function renderRunBrowserPreview(run) {
  if (!ui.runBrowserPreviewImage || !ui.runBrowserPreviewEmpty) return;
  const thumbnailPath = run && run.thumbnail_path ? run.thumbnail_path : "";
  if (!thumbnailPath) {
    ui.runBrowserPreviewImage.style.display = "none";
    ui.runBrowserPreviewImage.removeAttribute("src");
    ui.runBrowserPreviewEmpty.style.display = "block";
    ui.runBrowserPreviewEmpty.textContent = run && run.has_viewer
      ? "This run has viewer data, but no saved thumbnail was found."
      : "This run does not have a saved scene preview yet.";
    return;
  }
  ui.runBrowserPreviewEmpty.style.display = "none";
  ui.runBrowserPreviewImage.style.display = "block";
  ui.runBrowserPreviewImage.alt = run.thumbnail_label || "Run preview";
  ui.runBrowserPreviewImage.onerror = () => {
    ui.runBrowserPreviewImage.style.display = "none";
    ui.runBrowserPreviewEmpty.style.display = "block";
    ui.runBrowserPreviewEmpty.textContent = "Saved preview could not be loaded for this run.";
  };
  ui.runBrowserPreviewImage.src = `${thumbnailPath}?v=${encodeURIComponent(run.run_id)}`;
}

function renderRunBrowserDetails(run, detail = null) {
  if (!ui.runBrowserSelectedRun || !ui.runBrowserDetails) return;
  if (!run) {
    ui.runBrowserSelectedRun.textContent = "No run selected";
    if (ui.runBrowserBadges) ui.runBrowserBadges.innerHTML = "";
    ui.runBrowserDetails.textContent = "Choose a run from the list to inspect its details before opening it in the viewer.";
    renderRunBrowserPreview(null);
    return;
  }

  const config = detail && detail.config ? detail.config : null;
  const scene = config && config.scene ? config.scene : null;
  const summary = run.summary || {};
  const metrics = summary.metrics || {};
  const txPos = scene && scene.tx && Array.isArray(scene.tx.position) ? scene.tx.position.join(", ") : "n/a";
  const rxPos = scene && scene.rx && Array.isArray(scene.rx.position) ? scene.rx.position.join(", ") : "n/a";
  const risObjects = config && config.ris && Array.isArray(config.ris.objects)
    ? config.ris.objects.filter((item) => item && item.enabled !== false)
    : [];
  const radioMap = config && config.radio_map ? config.radio_map : null;
  const detailCards = [
    ["Timestamp", formatRunBrowserTimestamp(run.run_id)],
    ["Scene", run.scene_label || "n/a"],
    ["Backend", run.backend || "n/a"],
    ["Duration", formatRunBrowserDuration(run.duration_s)],
    ["Frequency", formatRunBrowserNumber(run.frequency_ghz, 1, " GHz")],
    ["Max depth", run.max_depth ?? "n/a"],
    ["Valid paths", run.path_count ?? "n/a"],
    ["Total path gain", formatRunBrowserNumber(run.total_path_gain_db, 2, " dB")],
    ["Rx power", formatRunBrowserNumber(run.rx_power_dbm, 2, " dBm")],
    ["Tx position", txPos],
    ["Rx position", rxPos],
    ["RIS objects", risObjects.length || (metrics.num_ris_paths ? "Configured" : "None")],
  ];

  if (radioMap && Array.isArray(radioMap.size) && Array.isArray(radioMap.cell_size)) {
    detailCards.push([
      "Radio map",
      `${radioMap.size[0]} x ${radioMap.size[1]} m @ ${radioMap.cell_size[0]} x ${radioMap.cell_size[1]} m`,
    ]);
  }

  const notes = [];
  if (!run.has_viewer) {
    notes.push("Viewer assets are missing for this run, so it cannot be opened in the 3D viewer.");
  }
  if (!detail) {
    notes.push("Loading saved config details...");
  }

  ui.runBrowserSelectedRun.textContent = run.run_id;
  renderRunBrowserBadges(run);
  ui.runBrowserDetails.innerHTML = `
    ${detailCards.map(([label, value]) => `
      <div class="run-browser-detail">
        <div class="run-browser-detail-label">${escapeHtml(label)}</div>
        <div class="run-browser-detail-value">${escapeHtml(value)}</div>
      </div>
    `).join("")}
    ${notes.map((note) => `<div class="run-browser-detail-note">${escapeHtml(note)}</div>`).join("")}
  `;
  renderRunBrowserPreview(run);
}

function renderRunBrowserList() {
  if (!ui.runBrowserList || !ui.runBrowserCount) return;
  const filterText = (ui.runBrowserSearch ? ui.runBrowserSearch.value : "").trim().toLowerCase();
  const scope = getRunScopeForTab();
  const allRuns = Array.isArray(state.runs) ? state.runs : [];
  const filteredRuns = filterText ? allRuns.filter((run) => getRunBrowserSearchText(run).includes(filterText)) : allRuns;

  if (ui.runBrowserSubtitle) {
    ui.runBrowserSubtitle.textContent = `${getRunBrowserScopeLabel(scope)} scope · browse saved runs and inspect a preview before loading.`;
  }
  ui.runBrowserCount.textContent = `${filteredRuns.length} / ${allRuns.length} runs`;

  if (!filteredRuns.length) {
    state.runBrowser.selectedRunId = null;
    ui.runBrowserList.innerHTML = '<div class="run-browser-detail-note">No runs match the current filter.</div>';
    renderRunBrowserDetails(null);
    if (ui.runBrowserOpenRun) ui.runBrowserOpenRun.disabled = true;
    return;
  }

  const selectedRunId = filteredRuns.some((run) => run.run_id === state.runBrowser.selectedRunId)
    ? state.runBrowser.selectedRunId
    : (filteredRuns.find((run) => run.run_id === state.runId)?.run_id || filteredRuns[0].run_id);
  state.runBrowser.selectedRunId = selectedRunId;

  ui.runBrowserList.innerHTML = "";
  filteredRuns.forEach((run) => {
    const item = document.createElement("div");
    item.className = "run-browser-item";
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    if (run.run_id === state.runBrowser.selectedRunId) item.classList.add("is-selected");
    if (run.run_id === state.runId) item.classList.add("is-current");
    const sceneLabel = run.scene_label || "Unnamed scene";
    const backendLabel = run.backend || "backend n/a";
    const statusLabel = run.has_viewer ? "Viewer ready" : "No viewer";
    item.title = [run.run_id, sceneLabel, backendLabel, statusLabel].join(" · ");
    item.innerHTML = `
      <div class="run-browser-item-head">
        <div class="run-browser-item-id" title="${escapeHtml(run.run_id)}">
          <span class="run-browser-item-id-text">${escapeHtml(run.run_id)}</span>
        </div>
        <span class="run-browser-status ${run.has_viewer ? "is-ready" : "is-missing"}">${escapeHtml(statusLabel)}</span>
      </div>
      <div class="run-browser-item-meta">
        <div class="run-browser-item-scene" title="${escapeHtml(sceneLabel)}">${escapeHtml(sceneLabel)}</div>
        <div class="run-browser-item-time" title="${escapeHtml(formatRunBrowserTimestamp(run.run_id))}">${escapeHtml(formatRunBrowserTimestamp(run.run_id))}</div>
      </div>
      <div class="run-browser-item-foot">
        <div class="run-browser-item-summary" title="${escapeHtml(backendLabel)}">${escapeHtml(backendLabel)}</div>
        <div class="run-browser-item-time" title="${escapeHtml(formatRunBrowserDuration(run.duration_s))}">${escapeHtml(formatRunBrowserDuration(run.duration_s))}</div>
      </div>
    `;
    item.addEventListener("click", () => {
      void selectRunBrowserRun(run.run_id);
    });
    item.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      void selectRunBrowserRun(run.run_id);
    });
    item.addEventListener("dblclick", () => {
      if (!run.has_viewer) return;
      void activateRunFromBrowser(run.run_id);
    });
    ui.runBrowserList.appendChild(item);
  });

  const selectedRun = getRunById(state.runBrowser.selectedRunId);
  renderRunBrowserDetails(selectedRun, state.runBrowser.detailsByRunId[state.runBrowser.selectedRunId] || null);
  if (ui.runBrowserOpenRun) ui.runBrowserOpenRun.disabled = !(selectedRun && selectedRun.has_viewer);
}

async function selectRunBrowserRun(runId) {
  if (!runId) return;
  state.runBrowser.selectedRunId = runId;
  renderRunBrowserList();
  if (state.runBrowser.detailsByRunId[runId]) {
    renderRunBrowserDetails(getRunById(runId), state.runBrowser.detailsByRunId[runId]);
    return;
  }
  const details = await fetchRunDetails(runId);
  if (!details) return;
  state.runBrowser.detailsByRunId[runId] = details;
  if (state.runBrowser.selectedRunId === runId) {
    renderRunBrowserDetails(getRunById(runId), details);
  }
}

function closeRunBrowser() {
  if (!ui.runBrowserModal) return;
  state.runBrowser.open = false;
  ui.runBrowserModal.classList.remove("is-open");
  ui.runBrowserModal.setAttribute("aria-hidden", "true");
}

async function openRunBrowser() {
  if (!ui.runBrowserModal) return;
  state.runBrowser.open = true;
  ui.runBrowserModal.classList.add("is-open");
  ui.runBrowserModal.setAttribute("aria-hidden", "false");
  renderRunBrowserList();
  if (ui.runBrowserSearch) {
    requestAnimationFrame(() => ui.runBrowserSearch.focus());
  }
  await fetchRuns(getRunScopeForTab());
  if (state.runBrowser.selectedRunId) {
    await selectRunBrowserRun(state.runBrowser.selectedRunId);
  } else if (state.runId) {
    await selectRunBrowserRun(state.runId);
  }
}

async function activateRunFromBrowser(runId) {
  const run = getRunById(runId);
  if (!run || !run.has_viewer) return;
  const scope = getRunScopeForTab();
  state.followLatestRun = false;
  state.followLatestRunByScope[scope] = false;
  state.sceneOverrideDirty = false;
  state.scopedRunIds[scope] = runId;
  if (ui.runSelect) {
    ui.runSelect.value = runId;
  }
  closeRunBrowser();
  await loadRun(runId, scope);
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
  const previous = state.ris.selectedRunId || ui.risRunSelect.value;
  ui.risRunSelect.innerHTML = "";
  runList.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.risRunSelect.appendChild(opt);
  });
  if (runList.length > 0) {
    const selectedRunId = runList.includes(previous) ? previous : runList[0];
    syncRisSelectedRun(selectedRunId, { followActive: state.ris.followActiveRun });
  } else {
    syncRisSelectedRun(null, { followActive: state.ris.followActiveRun });
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
  if (state.ris.followActiveRun && state.ris.activeRunId) {
    syncRisSelectedRun(state.ris.activeRunId, { followActive: true });
  } else if (
    !state.ris.selectedRunId
    || !state.ris.runs.includes(state.ris.selectedRunId)
  ) {
    const fallbackRunId = state.ris.activeRunId || state.ris.runs[0] || null;
    syncRisSelectedRun(
      fallbackRunId,
      { followActive: Boolean(fallbackRunId && fallbackRunId === state.ris.activeRunId) }
    );
  }
  if (state.ris.selectedRunId) {
    await loadRisResults(state.ris.selectedRunId);
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
      syncRisSelectedRun(data.run_id, { followActive: true });
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
    syncRisSelectedRun(null, { followActive: false });
    setRisResultStatus("Select a run to load results.");
    renderRisMetrics(null);
    if (ui.risPlotImage) ui.risPlotImage.src = "";
    return;
  }
  syncRisSelectedRun(runId, { followActive: state.ris.followActiveRun && runId === state.ris.activeRunId });
  setRisResultStatus(`Loading ${runId}...`);
  const [metrics, progress] = await Promise.all([
    fetchJsonMaybe(`/runs/${runId}/metrics.json`),
    fetchProgress(runId),
  ]);
  renderRisMetrics(metrics);
  const mode = metrics && typeof metrics.mode === "string" ? metrics.mode : null;
  const allowedPlots = mode && RIS_PLOT_FILES_BY_MODE[mode]
    ? RIS_PLOT_FILES_BY_MODE[mode]
    : null;
  const defaultPlot = !metrics
    ? "phase_map.png"
    : (allowedPlots && allowedPlots.has(state.ris.selectedPlot))
      ? state.ris.selectedPlot
      : "phase_map.png";
  state.ris.selectedPlot = defaultPlot;
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

async function fetchRisSynthesisJobs() {
  const data = await fetchJsonMaybe("/api/ris-synth/jobs");
  return data || { jobs: [] };
}

function renderRisSynthesisMetrics(runId, summary, metrics) {
  if (!ui.risSynthMetrics) return;
  ui.risSynthMetrics.innerHTML = "";
  const runtime = summary && summary.runtime ? summary.runtime : {};
  const variants = metrics && metrics.variants ? metrics.variants : {};
  const artifacts = summary && summary.artifacts ? summary.artifacts : {};
  const quantization = summary && summary.quantization ? summary.quantization : (metrics && metrics.quantization ? metrics.quantization : {});
  const rows = [
    ["action", summary && summary.action ? summary.action : "run"],
    ["rt_backend", runtime.rt_backend],
    ["mitsuba_variant", runtime.mitsuba_variant],
    ["seed_scene", summary && summary.seed ? summary.seed.config_path : null],
    ["seed_run_id", summary && summary.seed ? summary.seed.source_run_id : null],
    ["source_run_id", summary && summary.source ? summary.source.run_id : null],
    ["mask_cells", metrics && metrics.target_region ? metrics.target_region.num_masked_cells : null],
    ["continuous_objective", metrics && metrics.objective ? metrics.objective.continuous_final : null],
    ["1bit_objective", metrics && metrics.objective ? metrics.objective.one_bit_best : null],
    ["quantized_objective", metrics && metrics.objective ? metrics.objective.quantized_best : null],
    ["best_offset_rad", metrics && metrics.objective ? metrics.objective.best_offset_rad : null],
    ["quantization_bits", quantization.bits],
    ["quantization_levels", quantization.levels],
    ["quantization_method", quantization.method],
    ["continuous_profile_config", artifacts.continuous_seed_config_path],
    ["continuous_profile_snippet", artifacts.continuous_profile_snippet_path],
    ["continuous_phase_array", artifacts.continuous_phase_array_path],
    ["continuous_amp_array", artifacts.continuous_amp_array_path],
  ];
  if (artifacts.one_bit_seed_config_path) {
    rows.push(["1bit_profile_config", artifacts.one_bit_seed_config_path]);
  }
  if (artifacts.one_bit_profile_snippet_path) {
    rows.push(["1bit_profile_snippet", artifacts.one_bit_profile_snippet_path]);
  }
  if (artifacts.one_bit_phase_array_path) {
    rows.push(["1bit_phase_array", artifacts.one_bit_phase_array_path]);
  }
  if (artifacts.one_bit_amp_array_path) {
    rows.push(["1bit_amp_array", artifacts.one_bit_amp_array_path]);
  }
  if (artifacts.quantized_seed_config_path) {
    rows.push(["quantized_profile_config", artifacts.quantized_seed_config_path]);
  }
  if (artifacts.quantized_profile_snippet_path) {
    rows.push(["quantized_profile_snippet", artifacts.quantized_profile_snippet_path]);
  }
  if (artifacts.quantized_phase_array_path) {
    rows.push(["quantized_phase_array", artifacts.quantized_phase_array_path]);
  }
  if (artifacts.quantized_amp_array_path) {
    rows.push(["quantized_amp_array", artifacts.quantized_amp_array_path]);
  }
  Object.entries(variants).forEach(([key, value]) => {
    rows.push([`${key}_mean_rx_power_dbm`, value.mean_rx_power_dbm]);
    rows.push([`${key}_coverage_fraction`, value.coverage_fraction_above_threshold]);
  });
  rows.forEach(([key, value]) => {
    const row = document.createElement("div");
    appendMetricValue(row, key, value, runId);
    ui.risSynthMetrics.appendChild(row);
  });
}

function renderRisSynthesisPlotTabs(summary) {
  if (!ui.risSynthPlotTabs) return;
  const available = new Set((summary && summary.artifacts && Array.isArray(summary.artifacts.plot_files))
    ? summary.artifacts.plot_files
    : RIS_SYNTH_PLOT_FILES.map((plot) => plot.file));
  let firstVisible = null;
  ui.risSynthPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
    const visible = available.has(btn.dataset.plot);
    btn.style.display = visible ? "" : "none";
    if (visible && !firstVisible) {
      firstVisible = btn.dataset.plot;
    }
  });
  if (state.risSynthesis.selectedPlot && available.has(state.risSynthesis.selectedPlot)) {
    return state.risSynthesis.selectedPlot;
  }
  return firstVisible || "target_region_overlay.png";
}

function renderRisSynthesisPlotSingle(runId, file) {
  if (!ui.risSynthPlotImage || !ui.risSynthPlotCaption) return;
  const label = RIS_SYNTH_PLOT_LABELS[file] || file;
  ui.risSynthPlotCaption.textContent = label;
  ui.risSynthPlotImage.src = `/runs/${runId}/plots/${file}?v=${Date.now()}`;
  ui.risSynthPlotImage.alt = label;
}

function renderRisSynthesisJobList(jobs) {
  ui.risSynthJobList.innerHTML = "";
  const sorted = [...jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const recent = sorted.slice(-5).reverse();
  recent.forEach((job) => {
    const item = document.createElement("div");
    const status = job.status || "unknown";
    const action = job.action === "quantize"
      ? `quantize ${job.bits || "?"}-bit`
      : (job.action || "run");
    const error = job.error ? ` · ERROR: ${job.error}` : "";
    item.textContent = `${job.run_id} · ${action} · ${status}${error}`;
    ui.risSynthJobList.appendChild(item);
  });
}

async function refreshRisSynthesisRunSelect() {
  const data = await fetchJsonMaybe("/api/runs?kind=ris_synthesis");
  const runList = (data && data.runs ? data.runs : []).map((run) => run.run_id).sort((a, b) => b.localeCompare(a));
  state.risSynthesis.runs = runList;
  const previous = state.risSynthesis.selectedRunId || ui.risSynthRunSelect.value;
  ui.risSynthRunSelect.innerHTML = "";
  runList.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.risSynthRunSelect.appendChild(opt);
  });
  if (runList.length > 0) {
    const selectedRunId = runList.includes(previous) ? previous : runList[0];
    syncRisSynthesisSelectedRun(selectedRunId, { followActive: state.risSynthesis.followActiveRun });
  } else {
    syncRisSynthesisSelectedRun(null, { followActive: state.risSynthesis.followActiveRun });
  }
}

async function refreshRisSynthesisSeedRunOptions() {
  if (!ui.risSynthSeedRun) return;
  const data = await fetchJsonMaybe("/api/runs");
  const runs = Array.isArray(data && data.runs) ? data.runs : [];
  const seedRuns = runs
    .filter((run) => run && run.kind === "run" && run.run_id)
    .sort((a, b) => String(b.run_id).localeCompare(String(a.run_id)));
  state.risSynthesis.seedRunScopes = Object.fromEntries(
    seedRuns.map((run) => [run.run_id, run.scope || "sim"]),
  );
  const preferred = ui.risSynthSeedRun.value || getActiveViewerSeedRunId() || "";
  ui.risSynthSeedRun.innerHTML = "";
  seedRuns.forEach((run) => {
    const opt = document.createElement("option");
    opt.value = run.run_id;
    const scope = run.scope && run.scope !== "sim" ? ` · ${run.scope}` : "";
    const scene = run.scene_label ? ` · ${run.scene_label}` : "";
    opt.textContent = `${run.run_id}${scope}${scene}`;
    ui.risSynthSeedRun.appendChild(opt);
  });
  if (seedRuns.length) {
    const selectable = seedRuns.map((run) => run.run_id);
    ui.risSynthSeedRun.value = selectable.includes(preferred) ? preferred : selectable[0];
    await ensureRunDetailsCached(ui.risSynthSeedRun.value);
  }
}

async function refreshRisSynthesisProgressAndLog() {
  const runId = state.risSynthesis.activeRunId;
  if (!runId) {
    ui.risSynthProgress.textContent = "";
    ui.risSynthLog.textContent = "";
    return;
  }
  const progress = await fetchProgress(runId);
  if (progress) {
    const step = progress.step_name || "Running";
    const total = progress.total_steps || 0;
    const idx = progress.step_index != null ? progress.step_index + 1 : null;
    const pct = progress.progress != null ? Math.round(progress.progress * 100) : null;
    const stepLabel = total && idx ? `${step} (${idx}/${total})` : step;
    const pctLabel = pct !== null ? ` · ${pct}%` : "";
    const iterLabel = progress.current_iteration ? ` · iter ${progress.current_iteration}/${progress.total_iterations || "?"}` : "";
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    ui.risSynthProgress.textContent = `${progress.status || "running"} · ${stepLabel}${pctLabel}${iterLabel}${error}`;
  } else {
    ui.risSynthProgress.textContent = "Progress unavailable.";
  }
  const logText = await fetchTextMaybe(`/runs/${runId}/job.log`);
  ui.risSynthLog.textContent = logText ? tailLines(logText, 120) : "No log available.";
}

async function refreshRisSynthesisJobs() {
  const data = await fetchRisSynthesisJobs();
  state.risSynthesis.jobs = data.jobs || [];
  renderRisSynthesisJobList(state.risSynthesis.jobs);
  const sorted = [...state.risSynthesis.jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const running = sorted.find((job) => job.status === "running");
  const latest = sorted[sorted.length - 1];
  const active = state.risSynthesis.activeJobId
    ? sorted.find((job) => job.job_id === state.risSynthesis.activeJobId)
    : null;
  await refreshRisSynthesisSeedRunOptions();
  await refreshRisSynthesisRunSelect();
  const runExists = (job) => job && job.run_id && state.risSynthesis.runs.includes(job.run_id);
  const current = [active, running, latest].find((job) => job && (job.status === "running" || runExists(job)));
  if (current) {
    state.risSynthesis.activeJobId = current.job_id;
    state.risSynthesis.activeRunId = current.run_id;
    setRisSynthesisStatus(`${current.run_id} · ${current.status || "running"}`);
  } else {
    setRisSynthesisStatus("Idle.");
    state.risSynthesis.activeJobId = null;
    state.risSynthesis.activeRunId = null;
  }
  await refreshRisSynthesisProgressAndLog();
  if (state.risSynthesis.followActiveRun && state.risSynthesis.activeRunId) {
    syncRisSynthesisSelectedRun(state.risSynthesis.activeRunId, { followActive: true });
  } else if (
    !state.risSynthesis.selectedRunId
    || !state.risSynthesis.runs.includes(state.risSynthesis.selectedRunId)
  ) {
    const fallbackRunId = state.risSynthesis.activeRunId || state.risSynthesis.runs[0] || null;
    syncRisSynthesisSelectedRun(fallbackRunId, { followActive: Boolean(fallbackRunId && fallbackRunId === state.risSynthesis.activeRunId) });
  }
  if (state.risSynthesis.selectedRunId) {
    await loadRisSynthesisResults(state.risSynthesis.selectedRunId);
  }
  await updateRisSynthesisSeedStatus();
}

async function submitRisSynthesisJob() {
  const payload = {};
  const source = ui.risSynthConfigSource ? ui.risSynthConfigSource.value : "builder";
  if (source === "file") {
    let configPath = ui.risSynthConfigPath.value.trim();
    if (!configPath && ui.risSynthConfigPath.placeholder) {
      configPath = ui.risSynthConfigPath.placeholder;
    }
    if (!configPath) {
      setRisSynthesisStatus("Config path required.");
      return;
    }
    payload.config_path = configPath;
  } else {
    try {
      if (ui.risSynthSeedSource && ui.risSynthSeedSource.value === "seed_run") {
        await updateRisSynthesisSeedStatus();
      }
      if (!syncRisSynthesisBoxesStateFromTextarea({ quiet: true })) {
        setRisSynthesisStatus("Config error: fix the ROI JSON before starting a new run.");
        return;
      }
      payload.config_data = buildRisSynthesisConfigFromUI();
      const roiValidation = await validateRisSynthesisBoxesAgainstSeedGrid(payload.config_data.target_region.boxes);
      if (!roiValidation.ok) {
        const boundsText = formatRisSynthesisCellCenterBounds(roiValidation.bounds);
        setRisSynthesisStatus(
          `Config error: ROI boxes do not hit any seed-grid cells (${boundsText}). `
          + "Load the seed run into the viewer and redraw on that heatmap."
        );
        return;
      }
    } catch (err) {
      setRisSynthesisStatus(`Config error: ${err instanceof Error ? err.message : String(err)}`);
      return;
    }
  }
  setRisSynthesisStatus("Submitting target region illumination job...");
  try {
    const res = await fetch("/api/ris-synth/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      setRisSynthesisStatus(`Target region illumination job error: ${String(data.error || res.status)}`);
    } else {
      state.risSynthesis.activeRunId = data.run_id;
      state.risSynthesis.activeJobId = data.job_id;
      syncRisSynthesisSelectedRun(data.run_id, { followActive: true });
      clearRisSynthesisViewerOverlay();
      setRisSynthesisStatus(`Target region illumination job submitted: ${data.run_id}`);
    }
    await refreshRisSynthesisJobs();
  } catch (err) {
    setRisSynthesisStatus("Target region illumination job error: network failure");
  }
}

async function submitRisSynthesisQuantizationJob() {
  const selectedRunId = ui.risSynthRunSelect ? ui.risSynthRunSelect.value : "";
  if (!selectedRunId) {
    setRisSynthesisResultStatus("Select a target region illumination run to quantize.");
    return;
  }
  setRisSynthesisResultStatus(`Preparing quantization from ${selectedRunId}...`);
  let sourceRunId = selectedRunId;
  const selectedSummary = await fetchJsonMaybe(`/runs/${selectedRunId}/summary.json`);
  if (!selectedSummary) {
    setRisSynthesisResultStatus(`Could not load summary for ${selectedRunId}.`);
    return;
  }
  const artifacts = selectedSummary.artifacts || {};
  if (
    selectedSummary.action !== "quantize"
    && !artifacts.continuous_phase_array_path
  ) {
    setRisSynthesisResultStatus(
      `Run ${selectedRunId} does not expose a continuous RIS phase artifact, so it cannot be post-quantized.`
    );
    return;
  }
  if (
    selectedSummary
    && selectedSummary.action === "quantize"
    && selectedSummary.source
    && selectedSummary.source.run_id
  ) {
    sourceRunId = String(selectedSummary.source.run_id);
  }
  const bits = readOptionalInt(ui.risSynthQuantizeBits, 2);
  const numOffsetSamples = readOptionalInt(ui.risSynthQuantizeSamples, 181);
  if (!bits || bits < 1) {
    setRisSynthesisResultStatus("Quantize bits must be >= 1.");
    return;
  }
  if (!numOffsetSamples || numOffsetSamples < 1) {
    setRisSynthesisResultStatus("Quantize offset samples must be >= 1.");
    return;
  }
  setRisSynthesisResultStatus(`Submitting ${bits}-bit quantization from ${sourceRunId}...`);
  setRisSynthesisStatus(`Submitting ${bits}-bit quantization job from ${sourceRunId}...`);
  try {
    const res = await fetch("/api/ris-synth/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "quantize",
        source_run_id: sourceRunId,
        bits,
        num_offset_samples: numOffsetSamples,
      }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      const message = `Target region illumination quantization error: ${String(data.error || res.status)}`;
      setRisSynthesisStatus(message);
      setRisSynthesisResultStatus(message);
    } else {
      state.risSynthesis.activeRunId = data.run_id;
      state.risSynthesis.activeJobId = data.job_id;
      syncRisSynthesisSelectedRun(data.run_id, { followActive: true });
      clearRisSynthesisViewerOverlay();
      setRisSynthesisStatus(`Target region illumination quantization submitted: ${data.run_id}`);
      setRisSynthesisResultStatus(`Quantization job submitted: ${data.run_id}`);
    }
    await refreshRisSynthesisJobs();
    await refreshRisSynthesisProgressAndLog();
  } catch (_err) {
    setRisSynthesisStatus("Target region illumination quantization error: network failure");
    setRisSynthesisResultStatus("Target region illumination quantization error: network failure");
  }
}

async function loadRisSynthesisResults(runId) {
  if (!runId) {
    setRisSynthesisResultStatus("Select a run to load results.");
    renderRisSynthesisMetrics(null, null, null);
    if (ui.risSynthPlotImage) ui.risSynthPlotImage.src = "";
    return;
  }
  syncRisSynthesisSelectedRun(runId, { followActive: state.risSynthesis.followActiveRun });
  setRisSynthesisResultStatus(`Loading ${runId}...`);
  const [summary, metrics, progress] = await Promise.all([
    fetchJsonMaybe(`/runs/${runId}/summary.json`),
    fetchJsonMaybe(`/runs/${runId}/metrics.json`),
    fetchProgress(runId),
  ]);
  renderRisSynthesisMetrics(runId, summary, metrics);
  const defaultPlot = renderRisSynthesisPlotTabs(summary);
  state.risSynthesis.selectedPlot = defaultPlot;
  renderRisSynthesisPlotSingle(runId, defaultPlot);
  if (ui.risSynthPlotTabs) {
    ui.risSynthPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.plot === defaultPlot);
    });
  }
  if (progress && progress.status === "failed") {
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    setRisSynthesisResultStatus(`Run failed${error}`);
  } else if (progress && progress.status) {
    setRisSynthesisResultStatus(`Run status: ${progress.status}`);
  } else {
    setRisSynthesisResultStatus("Results loaded.");
  }
}

async function refreshLinkSeedOptions() {
  const [runData] = await Promise.all([
    fetchJsonMaybe("/api/runs?scope=sim&kind=run"),
  ]);
  const runs = (runData && runData.runs ? runData.runs : []).map((run) => run.run_id);
  const previousRun = ui.linkSeedRun ? ui.linkSeedRun.value : "";
  if (ui.linkSeedRun) {
    ui.linkSeedRun.innerHTML = "";
    runs.forEach((runId) => {
      const opt = document.createElement("option");
      opt.value = runId;
      opt.textContent = runId;
      ui.linkSeedRun.appendChild(opt);
    });
    if (runs.length > 0) {
      ui.linkSeedRun.value = runs.includes(previousRun) ? previousRun : runs[0];
    }
  }
  const previousConfig = ui.linkSeedConfig ? ui.linkSeedConfig.value : "";
  if (ui.linkSeedConfig) {
    const configEntries = [...(state.configs || [])].sort((a, b) => {
      const aRis = Boolean(a && a.data && a.data.ris && a.data.ris.enabled);
      const bRis = Boolean(b && b.data && b.data.ris && b.data.ris.enabled);
      if (aRis !== bRis) return aRis ? -1 : 1;
      return String(a.name || a.path || "").localeCompare(String(b.name || b.path || ""));
    });
    ui.linkSeedConfig.innerHTML = "";
    configEntries.forEach((cfg) => {
      const risEnabled = Boolean(cfg && cfg.data && cfg.data.ris && cfg.data.ris.enabled);
      const opt = document.createElement("option");
      opt.value = cfg.path;
      opt.textContent = `${cfg.name || cfg.path}${risEnabled ? " · RIS" : " · no RIS"}`;
      ui.linkSeedConfig.appendChild(opt);
    });
    const values = Array.from(ui.linkSeedConfig.options || []).map((opt) => opt.value);
    if (values.length > 0) {
      const preferredConfig = configEntries.find((cfg) => cfg.path === "configs/ashby_ris_link.yaml" && cfg.data && cfg.data.ris && cfg.data.ris.enabled)
        || configEntries.find((cfg) => cfg.path === "configs/ris_preview.yaml" && cfg.data && cfg.data.ris && cfg.data.ris.enabled)
        || configEntries.find((cfg) => cfg.data && cfg.data.ris && cfg.data.ris.enabled)
        || configEntries[0];
      ui.linkSeedConfig.value = values.includes(previousConfig) ? previousConfig : preferredConfig.path;
    }
  }
  void updateLinkSeedViewer();
}

function updateLinkSeedSourceVisibility() {
  const source = ui.linkSeedSourceType ? ui.linkSeedSourceType.value : "run";
  document.querySelectorAll(".link-seed-run-field").forEach((el) => {
    el.style.display = source === "run" ? "" : "none";
  });
  document.querySelectorAll(".link-seed-config-field").forEach((el) => {
    el.style.display = source === "config" ? "" : "none";
  });
  void updateLinkSeedViewer();
}

function setLinkSeedViewerStatus(text) {
  if (ui.linkSeedViewerStatus) ui.linkSeedViewerStatus.textContent = text;
}

function _activeLinkJob() {
  const jobs = state.link.jobs || [];
  if (state.link.activeJobId) {
    const byId = jobs.find((job) => job.job_id === state.link.activeJobId);
    if (byId) return byId;
  }
  if (state.link.activeRunId) {
    const byRun = jobs.find((job) => job.run_id === state.link.activeRunId);
    if (byRun) return byRun;
  }
  return jobs.find((job) => job.status === "running") || jobs[jobs.length - 1] || null;
}

function resolveLinkViewerRunId(summary = null) {
  if (summary && summary.seed) {
    if (summary.seed.prepared_run_id) return summary.seed.prepared_run_id;
    if (summary.seed.run_id) return summary.seed.run_id;
  }
  const activeJob = _activeLinkJob();
  if (activeJob) {
    if (activeJob.seed_type === "run" && activeJob.seed_run_id) {
      return activeJob.seed_run_id;
    }
    if (activeJob.seed_type === "config" && activeJob.run_id) {
      return `${activeJob.run_id}__seed`;
    }
  }
  const source = ui.linkSeedSourceType ? ui.linkSeedSourceType.value : "run";
  if (source === "run" && ui.linkSeedRun && ui.linkSeedRun.value) {
    return ui.linkSeedRun.value;
  }
  return null;
}

async function updateLinkSeedViewer(summary = null) {
  if (!ui.linkSeedViewerFrame) return;
  const source = ui.linkSeedSourceType ? ui.linkSeedSourceType.value : "run";
  const runId = resolveLinkViewerRunId(summary);
  if (!runId) {
    ui.linkSeedViewerFrame.src = "about:blank";
    ui.linkSeedViewerFrame.dataset.runId = "";
    setLinkSeedViewerStatus(
      source === "config"
        ? "Viewer will appear after the prepared seed outdoor run starts."
        : "Select a seed run to view the scene."
    );
    return;
  }
  const manifest = await fetchJsonMaybe(`/runs/${runId}/viewer/scene_manifest.json`);
  if (!manifest) {
    ui.linkSeedViewerFrame.src = "about:blank";
    ui.linkSeedViewerFrame.dataset.runId = "";
    setLinkSeedViewerStatus(
      source === "config"
        ? `Prepared seed run ${runId} has not written its viewer yet.`
        : `Viewer not available for seed run ${runId}.`
    );
    return;
  }
  const src = `/runs/${runId}/viewer/index.html?v=${Date.now()}`;
  if (ui.linkSeedViewerFrame.dataset.runId !== runId) {
    ui.linkSeedViewerFrame.src = src;
    ui.linkSeedViewerFrame.dataset.runId = runId;
  }
  setLinkSeedViewerStatus(`Viewing seed scene: ${runId}`);
}

async function fetchLinkJobs() {
  const data = await fetchJsonMaybe("/api/link/jobs");
  return data || { jobs: [] };
}

function renderLinkJobList(jobs) {
  ui.linkJobList.innerHTML = "";
  const sorted = [...jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const recent = sorted.slice(-5).reverse();
  recent.forEach((job) => {
    const item = document.createElement("div");
    const seed = job.seed_run_id ? ` · seed ${job.seed_run_id}` : job.seed_config_path ? ` · ${job.seed_config_path}` : "";
    const error = job.error ? ` · ERROR: ${job.error}` : "";
    item.textContent = `${job.run_id}${seed} · ${job.status || "unknown"}${error}`;
    ui.linkJobList.appendChild(item);
  });
}

async function refreshLinkRunSelect() {
  const data = await fetchJsonMaybe("/api/link/runs");
  const runList = (data && data.runs ? data.runs : []).map((run) => run.run_id).sort((a, b) => b.localeCompare(a));
  const previous = ui.linkRunSelect.value;
  ui.linkRunSelect.innerHTML = "";
  runList.forEach((runId) => {
    const opt = document.createElement("option");
    opt.value = runId;
    opt.textContent = runId;
    ui.linkRunSelect.appendChild(opt);
  });
  if (runList.length > 0) {
    ui.linkRunSelect.value = runList.includes(previous) ? previous : runList[0];
  }
  state.link.runs = runList;
}

async function refreshLinkProgressAndLog() {
  const runId = state.link.activeRunId;
  if (!runId) {
    ui.linkProgress.textContent = "";
    ui.linkLog.textContent = "";
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
    ui.linkProgress.textContent = `${progress.status || "running"} · ${stepLabel} ${pctLabel}${error}`.trim();
  } else {
    ui.linkProgress.textContent = "Progress unavailable.";
  }
  const logText = await fetchTextMaybe(`/runs/${runId}/job.log`);
  ui.linkLog.textContent = logText ? tailLines(logText, 120) : "No log available.";
}

async function refreshLinkJobs() {
  const data = await fetchLinkJobs();
  state.link.jobs = data.jobs || [];
  renderLinkJobList(state.link.jobs);
  await refreshLinkRunSelect();
  await refreshLinkSeedOptions();
  const sorted = [...state.link.jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const running = sorted.find((job) => job.status === "running");
  const latest = sorted[sorted.length - 1];
  const active = state.link.activeJobId
    ? sorted.find((job) => job.job_id === state.link.activeJobId)
    : null;
  const runExists = (job) => job && job.run_id && state.link.runs.includes(job.run_id);
  const current = [active, running, latest].find((job) => job && (job.status === "running" || runExists(job)));
  if (current) {
    state.link.activeJobId = current.job_id;
    state.link.activeRunId = current.run_id;
    setLinkStatus(`${current.run_id} · ${current.status || "running"}`);
  } else {
    state.link.activeJobId = null;
    state.link.activeRunId = null;
    setLinkStatus("Idle.");
  }
  await refreshLinkProgressAndLog();
  await updateLinkSeedViewer();
  if (state.link.activeRunId && ui.linkRunSelect) {
    ui.linkRunSelect.value = state.link.activeRunId;
    if (state.activeTab === "link") {
      loadLinkResults(state.link.activeRunId);
    }
  }
}

function buildLinkJobPayload() {
  const sourceType = ui.linkSeedSourceType ? ui.linkSeedSourceType.value : "run";
  const estimators = [];
  if (ui.linkEstimatorPerfect && ui.linkEstimatorPerfect.checked) estimators.push("perfect_csi");
  if (ui.linkEstimatorLsLin && ui.linkEstimatorLsLin.checked) estimators.push("ls_lin");
  if (ui.linkEstimatorLsNn && ui.linkEstimatorLsNn.checked) estimators.push("ls_nn");
  if (!estimators.length) {
    setLinkStatus("Choose at least one estimator.");
    return null;
  }
  const risVariants = [];
  if (ui.linkVariantOff && ui.linkVariantOff.checked) risVariants.push("ris_off");
  if (ui.linkVariantConfigured && ui.linkVariantConfigured.checked) risVariants.push("ris_configured");
  if (ui.linkVariantFlat && ui.linkVariantFlat.checked) risVariants.push("ris_flat");
  if (!risVariants.length) {
    setLinkStatus("Choose at least one RIS variant.");
    return null;
  }

  const payload = {
    seed_type: sourceType,
    estimators,
    ris_variants: risVariants,
    runtime: {
      prefer_gpu: !ui.linkBackend || ui.linkBackend.value !== "cpu",
      mitsuba_variant: "auto",
      tensorflow_import: "auto",
    },
    evaluation: {
      ebno_db_list: ui.linkEbnoList ? ui.linkEbnoList.value : "0,5,10,15,20",
      batch_size: readNumber(ui.linkBatchSize) || 32,
      iterations_per_ebno: readNumber(ui.linkIterations) || 8,
      fft_size: readNumber(ui.linkFftSize) || 64,
      num_ofdm_symbols: readNumber(ui.linkNumSymbols) || 14,
      subcarrier_spacing_hz: readNumber(ui.linkScsHz) || 30000,
      num_bits_per_symbol: readNumber(ui.linkBitsPerSymbol) || 2,
      num_paths: readNumber(ui.linkNumPaths) || 32,
    },
  };
  const rtMaxDepth = readNumber(ui.linkMaxDepth);
  const rtSamplesPerSrc = readNumber(ui.linkSamplesPerSrc);
  if (rtMaxDepth !== null) payload.evaluation.max_depth = rtMaxDepth;
  if (rtSamplesPerSrc !== null) payload.evaluation.samples_per_src = rtSamplesPerSrc;
  if (sourceType === "run") {
    if (!ui.linkSeedRun || !ui.linkSeedRun.value) {
      setLinkStatus("Select a seed run.");
      return null;
    }
    payload.seed_run_id = ui.linkSeedRun.value;
  } else {
    if (!ui.linkSeedConfig || !ui.linkSeedConfig.value) {
      setLinkStatus("Select a seed config.");
      return null;
    }
    payload.seed_config_path = ui.linkSeedConfig.value;
    payload.prepare_seed_run = true;
  }
  return payload;
}

async function submitLinkJob() {
  const payload = buildLinkJobPayload();
  if (!payload) return;
  setLinkStatus("Submitting link-level job...");
  try {
    const res = await fetch("/api/link/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      setLinkStatus(`Link job error: ${String(data.error || res.status)}`);
    } else {
      state.link.activeRunId = data.run_id;
      state.link.activeJobId = data.job_id;
      setLinkStatus(`Link job submitted: ${data.run_id}`);
    }
    await refreshLinkJobs();
  } catch (_err) {
    setLinkStatus("Link job error: network failure");
  }
}

async function loadLinkResults(runId) {
  if (!runId) {
    setLinkResultStatus("Select a link-level run to load results.");
    renderLinkMetrics(null);
    if (ui.linkPlotImage) ui.linkPlotImage.src = "";
    await updateLinkSeedViewer();
    return;
  }
  setLinkResultStatus(`Loading ${runId}...`);
  const [summary, progress] = await Promise.all([
    fetchJsonMaybe(`/runs/${runId}/summary.json`),
    fetchProgress(runId),
  ]);
  renderLinkMetrics(summary);
  await updateLinkSeedViewer(summary);
  const availablePlots = Array.isArray(summary && summary.plots) && summary.plots.length
    ? summary.plots
    : LINK_PLOT_FILES.map((plot) => plot.file);
  const defaultPlot = availablePlots.includes(state.link.selectedPlot)
    ? state.link.selectedPlot
    : (availablePlots[0] || "ber_vs_ebno.png");
  renderLinkPlotTabs(availablePlots, defaultPlot);
  renderLinkPlotSingle(runId, defaultPlot);
  state.link.selectedPlot = defaultPlot;
  if (progress && progress.status === "failed") {
    const error = progress.error ? ` · ERROR: ${progress.error}` : "";
    setLinkResultStatus(`Run failed${error}`);
  } else if (progress && progress.status) {
    setLinkResultStatus(`Run status: ${progress.status}`);
  } else {
    setLinkResultStatus("Results loaded.");
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
  syncCampaign2FixedRxPosition(getIndoorChamberConfig(), { force: true, rebuild: false });
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
    show_specular_path: ui.campaign2ShowSpecularPath ? ui.campaign2ShowSpecularPath.checked : true,
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
  const [summary, progress, plotManifest, anglePlotManifest] = await Promise.all([
    fetchJsonMaybe(`/runs/${runId}/summary.json`),
    fetchProgress(runId),
    fetchJsonMaybe(`/runs/${runId}/data/campaign_plots.json`),
    fetchJsonMaybe(`/runs/${runId}/data/campaign_angle_radio_maps.json`),
  ]);
  renderCampaign2Metrics(summary);
  const aggregatePlots = plotManifest && Array.isArray(plotManifest.plots) ? plotManifest.plots : [];
  const anglePlots = anglePlotManifest && Array.isArray(anglePlotManifest.plots) ? anglePlotManifest.plots : [];
  const availablePlots = [...aggregatePlots, ...anglePlots];
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
  const { force = false, preserveRisSynthesisOverlay = false } = options;
  if (!runId || state.loadingRun) return;
  if (!force && state.lastLoadedRunByScope[scope] === runId && state.runId === runId) {
    return;
  }
  if (!preserveRisSynthesisOverlay) {
    clearRisSynthesisViewerOverlay();
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
    const radioControlConfig = scope === "indoor" && isIndoorScopeTab(state.activeTab)
      ? (getIndoorChamberConfig() || configWrapper)
      : configWrapper;
    updateInputs();
    renderRunStats();
    updateHeatmapControls();
    updateRadioMapPreview();
    // Keep indoor/campaign submissions anchored to the chamber radio-map defaults
    // even when the viewer loads older runs with oversized maps.
    applyRadioMapDefaults(radioControlConfig);
    if (!state.simTuningDirty) {
      applySimTuningDefaults(configWrapper);
    }
    applyRisSimDefaults(configWrapper);
    updateSceneOverrideTxFromUi();
    rebuildScene({ refit: false });
    renderPathTable();
    renderPathStats();
    renderMaterialList();
    void updateRisSynthesisSeedStatus();
    setMeta(`${runId} · ${state.paths.length} paths`);
    if (state.activeTab === "ris-synth") {
      if (state.heatmap && state.heatmap.values) {
        setRisSynthesisViewerStatus(`Viewer loaded ${runId}. Use Draw ROIs to sketch target boxes.`);
      } else {
        setRisSynthesisViewerStatus(`Loaded ${runId}, but it has no heatmap to draw on.`);
      }
    }
    if (ui.radioMapDiffToggle && ui.radioMapDiffToggle.checked) {
      await refreshHeatmapDiff();
    }
    state.lastLoadedRunId = runId;
    state.lastLoadedRunByScope[scope] = runId;
    renderRunBrowserList();
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
  const assetRunId = state.risSynthesis.viewerOverlayRunId || state.runId;
  ui.radioMapPreviewImage.src = assetRunId ? `/runs/${assetRunId}/viewer/${selected}` : "";
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

async function loadRisSynthesisViewerOverlay(runId) {
  if (!runId) return false;
  const requestToken = state.risSynthesis.viewerOverlayRequestToken + 1;
  state.risSynthesis.viewerOverlayRequestToken = requestToken;
  state.risSynthesis.autoLoadedViewerRunId = null;
  state.risSynthesis.pendingViewerOverlayRunId = runId;
  if (ui.risSynthViewerMode) {
    ui.risSynthViewerMode.value = "optimal";
  }
  const [heatmap, heatmapRunDiff, radioPlots] = await Promise.all([
    fetchJsonMaybe(`/runs/${runId}/viewer/heatmap.json`),
    fetchJsonMaybe(`/runs/${runId}/viewer/heatmap_diff.json`),
    fetchJsonMaybe(`/runs/${runId}/viewer/radio_map_plots.json`),
  ]);
  if (state.risSynthesis.viewerOverlayRequestToken !== requestToken) {
    return false;
  }
  if (!heatmap || !heatmap.values) {
    state.risSynthesis.pendingViewerOverlayRunId = null;
    return false;
  }
  state.risSynthesis.pendingViewerOverlayRunId = null;
  state.risSynthesis.viewerOverlayRunId = runId;
  state.heatmap = heatmap;
  state.heatmapRunDiff = heatmapRunDiff;
  state.radioMapPlots = (radioPlots && radioPlots.plots) ? radioPlots.plots : [];
  if (ui.radioMapDiffToggle && ui.radioMapDiffToggle.checked && heatmapRunDiff) {
    state.heatmapDiff = heatmapRunDiff;
  } else if (ui.radioMapDiffToggle && !ui.radioMapDiffToggle.checked) {
    state.heatmapDiff = null;
  }
  updateHeatmapControls();
  updateRadioMapPreview();
  refreshHeatmap();
  renderRisSynthesisRoiOverlay();
  return true;
}

async function applyRisSynthesisViewerMode() {
  const mode = ui.risSynthViewerMode ? ui.risSynthViewerMode.value : "active";
  if (mode === "optimal") {
    const runId = (ui.risSynthRunSelect && ui.risSynthRunSelect.value)
      || state.risSynthesis.selectedRunId
      || state.risSynthesis.activeRunId;
    if (!runId) {
      setRisSynthesisViewerStatus("Select a completed target region illumination run first.");
      return;
    }
    const loaded = await loadRisSynthesisViewerOverlay(runId);
    if (!loaded) {
      setRisSynthesisViewerStatus(`Run ${runId} does not have an optimal viewer heatmap yet.`);
      return;
    }
    setRisSynthesisViewerStatus(`Showing optimized heatmap from ${runId}.`);
    return;
  }
  const scope = getRunScopeForTab();
  const activeRunId = (ui.runSelect && ui.runSelect.value) || state.runId;
  if (!activeRunId) {
    clearRisSynthesisViewerOverlay();
    setRisSynthesisViewerStatus("Load a sim run before switching back to the active heatmap.");
    return;
  }
  await loadRun(activeRunId, scope, { force: true });
  setRisSynthesisViewerStatus(`Showing active sim heatmap from ${activeRunId}.`);
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

function getCampaign2SpecularTurntableAngleDeg(targetAngleDeg, txIncidenceAngleDeg) {
  return normalizeAngleDeg(Number(targetAngleDeg) + Number(txIncidenceAngleDeg));
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
  const showSpecularPath = !ui.campaign2ShowSpecularPath || ui.campaign2ShowSpecularPath.checked;
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
  const txZOffset = Array.isArray(state.markers.tx) && state.markers.tx.length >= 3
    ? Number(state.markers.tx[2]) - Number(risPose.position[2])
    : 0.0;
  const targetZOffset = Array.isArray(state.markers.rx) && state.markers.rx.length >= 3
    ? Number(state.markers.rx[2]) - Number(risPose.position[2])
    : Number(IEEE_TAP_CAMPAIGN2_DEFAULTS.rxHeightM) - Number(risPose.position[2]);
  const txPositions = turntableAngles.map((angle) => (
    campaignPositionOnArcOriented(risPose.position, txRisDistance, txIncidence, risPose.yawDeg + angle, txZOffset)
  ));
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
    const targetPos = campaignPositionOnArcOriented(
      risPose.position,
      targetDistance,
      targetAngle,
      risPose.yawDeg,
      targetZOffset
    );
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
    if (showSpecularPath) {
      const specularTurntableAngle = getCampaign2SpecularTurntableAngleDeg(targetAngle, txIncidence);
      const specularTxPos = campaignPositionOnArcOriented(
        risPose.position,
        txRisDistance,
        txIncidence,
        risPose.yawDeg + specularTurntableAngle,
        txZOffset
      );
      const specularLine = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(specularTxPos[0], specularTxPos[1], specularTxPos[2]),
          new THREE.Vector3(risPose.position[0], risPose.position[1], risPose.position[2]),
          new THREE.Vector3(targetPos[0], targetPos[1], targetPos[2]),
        ]),
        new THREE.LineDashedMaterial({
          color: 0xf59e0b,
          transparent: true,
          opacity: 0.72,
          dashSize: 0.08,
          gapSize: 0.05,
        })
      );
      specularLine.computeLineDistances();
      campaignPreviewGroup.add(specularLine);
    }
  });
}

function rebuildDynamicScene({ refit = false } = {}) {
  markerGroup.clear();
  rayGroup.clear();
  heatmapGroup.clear();
  if (risSynthRoiGroup) risSynthRoiGroup.clear();
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
  renderRisSynthesisRoiOverlay();
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

function buildPreviewMesh(geom) {
  const mat = new THREE.MeshStandardMaterial({
    color: 0x9aa8b1,
    opacity: 0.6,
    transparent: true,
    side: THREE.DoubleSide,
  });
  return new THREE.Mesh(geom, mat);
}

function loadWithPromise(loader, url) {
  return new Promise((resolve, reject) => {
    loader.load(url, resolve, undefined, reject);
  });
}

async function loadPlyGeometry(loader, url) {
  const geom = await loadWithPromise(loader, url);
  if (geom && !geom.hasAttribute("normal")) {
    geom.computeVertexNormals();
  }
  return geom;
}

function refitCameraAfterMeshLoad() {
  refreshHeatmap();
  fitCamera();
}

async function loadMeshes(assetKey = state.geometryAssetKey) {
  if (!state.manifest || !assetKey || state.geometryAssetKey !== assetKey) {
    return;
  }
  const manifest = state.manifest;
  const runId = state.runId;
  const getManifestEntry = (name) => {
    const items = Array.isArray(manifest.mesh_manifest) ? manifest.mesh_manifest : [];
    return items.find((item) => item && item.file === name) || null;
  };
  try {
    const template = await getOrBuildGeometryTemplate(assetKey, async () => {
      const group = new THREE.Group();
      const base = Array.isArray(manifest.mesh_rotation_deg) ? manifest.mesh_rotation_deg : [0, 0, 0];
      const rotX = (parseFloat(base[0]) || 0) * Math.PI / 180;
      const rotY = (parseFloat(base[1]) || 0) * Math.PI / 180;
      const rotZ = (parseFloat(base[2]) || 0) * Math.PI / 180;
      if (manifest.mesh) {
        const ext = manifest.mesh.split(".").pop().toLowerCase();
        const manifestEntry = getManifestEntry(manifest.mesh);
        if (ext === "glb" || ext === "gltf") {
          const loader = new GLTFLoader();
          const gltf = await loadWithPromise(loader, `/runs/${runId}/viewer/${manifest.mesh}`);
          group.add(wrapMeshObject(gltf.scene, manifestEntry, rotX, rotY, rotZ));
        } else if (ext === "obj") {
          const loader = new OBJLoader();
          const obj = await loadWithPromise(loader, `/runs/${runId}/viewer/${manifest.mesh}`);
          group.add(wrapMeshObject(obj, manifestEntry, rotX, rotY, rotZ));
        }
      }
      if (manifest.mesh_files && manifest.mesh_files.length) {
        const loader = new PLYLoader();
        await Promise.all(manifest.mesh_files.map(async (name) => {
          const geom = await loadPlyGeometry(loader, `/runs/${runId}/viewer/${name}`);
          const mesh = buildPreviewMesh(geom);
          group.add(wrapMeshObject(mesh, getManifestEntry(name), rotX, rotY, rotZ));
        }));
      }
      return group;
    });
    if (!template || state.geometryAssetKey !== assetKey) return;
    geometryGroup.add(cloneGeometryTemplate(template));
    refitCameraAfterMeshLoad();
  } catch (err) {
    console.error("Viewer mesh load failed:", err);
    setMeta(`Viewer mesh failed to load for ${state.runId}`);
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
  try {
    const template = await getOrBuildGeometryTemplate(assetKey, async () => {
      const group = new THREE.Group();
      const loader = new PLYLoader();
      const manifestByFile = new Map(
        (Array.isArray(manifest.mesh_manifest) ? manifest.mesh_manifest : [])
          .filter((entry) => entry && entry.file)
          .map((entry) => [entry.file, entry])
      );
      await Promise.all(manifest.mesh_files.map(async (meshPath) => {
        const geom = await loadPlyGeometry(loader, `/api/scene_file_asset?path=${encodeURIComponent(meshPath)}`);
        const mesh = buildPreviewMesh(geom);
        group.add(wrapMeshObject(mesh, manifestByFile.get(meshPath) || null, 0, 0, 0));
      }));
      return group;
    });
    if (!template || state.geometryAssetKey !== assetKey) return;
    geometryGroup.add(cloneGeometryTemplate(template));
    refitCameraAfterMeshLoad();
  } catch (err) {
    console.error("Scene preview mesh load failed:", scenePath, err);
    setMeta(`Scene mesh failed to load: ${manifest.label || scenePath}`);
  }
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
      direction = backendForwardVectorFromOrientation(txCfg.orientation) || direction;
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
  const defaultColor = new THREE.Color(0xf97316);
  const risColor = new THREE.Color(0xef4444);
  const colors = [];
  state.paths.forEach((p) => {
    const color = p && p.has_ris ? risColor : defaultColor;
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

function cellCenterVector(cell) {
  if (!Array.isArray(cell) || cell.length < 3) return null;
  const x = Number(cell[0]);
  const y = Number(cell[1]);
  const z = Number(cell[2]);
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return null;
  return new THREE.Vector3(x, y, z);
}

function buildHeatmapGeometryFromCenters(centers, cellSize = [0, 0]) {
  if (!Array.isArray(centers) || !centers.length || !Array.isArray(centers[0]) || !centers[0].length) {
    return null;
  }
  const height = centers.length;
  const width = centers[0].length;
  const origin = cellCenterVector(centers[0][0]);
  if (!origin) return null;

  let uVec = null;
  let vVec = null;
  if (width > 1) {
    const next = cellCenterVector(centers[0][1]);
    if (next) uVec = next.clone().sub(origin);
  }
  if (height > 1) {
    const next = cellCenterVector(centers[1][0]);
    if (next) vVec = next.clone().sub(origin);
  }
  if (!uVec || uVec.length() <= 0) {
    const fallback = Number(cellSize[0]);
    uVec = new THREE.Vector3(Number.isFinite(fallback) && fallback > 0 ? fallback : 1, 0, 0);
  }
  if (!vVec || vVec.length() <= 0) {
    const fallback = Number(cellSize[1]);
    vVec = new THREE.Vector3(0, Number.isFinite(fallback) && fallback > 0 ? fallback : 1, 0);
  }

  const uStep = uVec.length();
  const vStep = vVec.length();
  const uUnit = uVec.clone().normalize();
  const vUnit = vVec.clone().normalize();
  const centerSum = new THREE.Vector3();
  let centerCount = 0;
  centers.forEach((row) => {
    row.forEach((cell) => {
      const point = cellCenterVector(cell);
      if (point) {
        centerSum.add(point);
        centerCount += 1;
      }
    });
  });
  if (!centerCount) return null;
  const meshCenter = centerSum.multiplyScalar(1 / centerCount);

  const positions = [];
  const uvs = [];
  const addVertex = (point, u, v) => {
    const local = point.clone().sub(meshCenter);
    positions.push(local.x, local.y, local.z);
    uvs.push(u, v);
  };

  for (let y = 0; y < height; y++) {
    if (!Array.isArray(centers[y]) || centers[y].length !== width) return null;
    for (let x = 0; x < width; x++) {
      const center = cellCenterVector(centers[y][x]);
      if (!center) return null;
      const left = center.clone().addScaledVector(uUnit, -0.5 * uStep);
      const right = center.clone().addScaledVector(uUnit, 0.5 * uStep);
      const bottomLeft = left.clone().addScaledVector(vUnit, -0.5 * vStep);
      const bottomRight = right.clone().addScaledVector(vUnit, -0.5 * vStep);
      const topLeft = left.clone().addScaledVector(vUnit, 0.5 * vStep);
      const topRight = right.clone().addScaledVector(vUnit, 0.5 * vStep);
      const u0 = x / width;
      const u1 = (x + 1) / width;
      const v0 = y / height;
      const v1 = (y + 1) / height;
      addVertex(bottomLeft, u0, v0);
      addVertex(bottomRight, u1, v0);
      addVertex(topRight, u1, v1);
      addVertex(bottomLeft, u0, v0);
      addVertex(topRight, u1, v1);
      addVertex(topLeft, u0, v1);
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geo.computeVertexNormals();
  return { geometry: geo, center: meshCenter };
}

function addHeatmap() {
  debugHeatmapMesh = null;
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
  const uiRotationDeg = parseFloat(ui.heatmapRotation?.value || 0);
  const uiRotationRad = (uiRotationDeg * Math.PI) / 180;
  const centers = active.cell_centers || [];
  const grid = buildHeatmapGeometryFromCenters(centers, active.cell_size || [0, 0]);
  if (grid) {
    const mesh = new THREE.Mesh(grid.geometry, mat);
    mesh.position.copy(grid.center);
    mesh.rotation.set(0, 0, uiRotationRad);
    heatmapGroup.add(mesh);
    debugHeatmapMesh = mesh;
    heatmapGroup.visible = ui.toggleHeatmap.checked;
    return;
  }

  let widthM = null;
  let heightM = null;
  let center = null;
  let z = 0;

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
  if (state.activeTab === "ris-synth" && state.risSynthesis.drawMode) {
    const hit = getRisSynthesisHeatmapHit(event);
    if (!hit) {
      setRisSynthesisViewerStatus("ROI drawing needs a loaded heatmap. Click Top-Down + Heatmap first.");
      return;
    }
    state.risSynthesis.draftBox = {
      name: getNextRisSynthesisRoiName(),
      u_min_m: hit.x,
      u_max_m: hit.x,
      v_min_m: hit.y,
      v_max_m: hit.y,
    };
    controls.enabled = false;
    renderRisSynthesisRoiOverlay();
    return;
  }
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
  if (state.activeTab === "ris-synth" && state.risSynthesis.drawMode && state.risSynthesis.draftBox) {
    const hit = getRisSynthesisHeatmapHit(event);
    if (!hit) return;
    state.risSynthesis.draftBox = normalizeRisSynthesisBox({
      name: state.risSynthesis.draftBox.name || getNextRisSynthesisRoiName(),
      u_min_m: state.risSynthesis.draftBox.u_min_m,
      u_max_m: hit.x,
      v_min_m: state.risSynthesis.draftBox.v_min_m,
      v_max_m: hit.y,
    }, state.risSynthesis.drawnBoxes.length);
    renderRisSynthesisRoiOverlay();
    return;
  }
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
  if (state.activeTab === "ris-synth" && state.risSynthesis.drawMode && state.risSynthesis.draftBox) {
    const nextIndex = state.risSynthesis.replaceOnNextDraw ? 0 : state.risSynthesis.drawnBoxes.length;
    const box = normalizeRisSynthesisBox(state.risSynthesis.draftBox, nextIndex);
    state.risSynthesis.draftBox = null;
    controls.enabled = true;
    if (!box) {
      renderRisSynthesisRoiOverlay();
      return;
    }
    const width = Math.abs(box.u_max_m - box.u_min_m);
    const height = Math.abs(box.v_max_m - box.v_min_m);
    if (width < 1.0e-3 || height < 1.0e-3) {
      renderRisSynthesisRoiOverlay();
      setRisSynthesisViewerStatus("ROI ignored because it was too small.");
      return;
    }
    if (state.risSynthesis.replaceOnNextDraw) {
      state.risSynthesis.drawnBoxes = [box];
      state.risSynthesis.replaceOnNextDraw = false;
      syncRisSynthesisBoxesTextareaFromState();
      renderRisSynthesisRoiOverlay();
      setRisSynthesisViewerStatus(`Replaced the target ROI set with ${box.name}. Draw again to add more regions.`);
      return;
    }
    state.risSynthesis.drawnBoxes = [...(state.risSynthesis.drawnBoxes || []), box];
    syncRisSynthesisBoxesTextareaFromState();
    renderRisSynthesisRoiOverlay();
    setRisSynthesisViewerStatus(`Added ${box.name}.`);
    return;
  }
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
  const preserveTargetRegionViewer = (
    usesSharedViewerTab(state.activeTab)
      && getRunScopeForTab() === scope
      && hasActiveRisSynthesisViewerOverlay(scope)
  );
  const sorted = [...data.jobs].sort((a, b) => (a.created_at || "").localeCompare(b.created_at || ""));
  const recentJobs = sorted.slice(-3).reverse();
  const selectableRunIds = new Set(Array.from(ui.runSelect.options).map((opt) => opt.value));
  newestCompleted = sorted.slice().reverse().find((job) => (
    job.status === "completed" && selectableRunIds.has(job.run_id)
  ))?.run_id || null;
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
    !preserveTargetRegionViewer &&
    !state.loadingRun &&
    state.followLatestRunByScope[scope] &&
    newestCompleted &&
    state.scopedRunIds[scope] !== newestCompleted &&
    usesSharedViewerTab(state.activeTab) &&
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
  const profileKey = getActiveProfileKey();
  const profile = getProfileDefinition();
  const scope = getRequestedRunScope();
  const allowManualOverrides = profileKey === "custom" || profileKey === "indoor_box_high";
  const payload = {
    kind: "run",
    scope,
    profile: profileKey,
    base_config: resolveConfigPath(profile.configName),
  };
  if (profile.qualityPreset) {
    payload.preset = profile.qualityPreset;
  }
  if (profile.runtime) {
    payload.runtime = profile.runtime;
  }
  if (allowManualOverrides) {
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
  const zStackEnabled = Boolean(ui.radioMapZStackEnabled && ui.radioMapZStackEnabled.checked);
  const zStack = { enabled: zStackEnabled };
  if (zStackEnabled) {
    const numBelow = readNumber(ui.radioMapZStackBelow);
    const numAbove = readNumber(ui.radioMapZStackAbove);
    const spacingM = readNumber(ui.radioMapZStackSpacing);
    if (numBelow !== null) zStack.num_below = Math.max(0, Math.round(numBelow));
    if (numAbove !== null) zStack.num_above = Math.max(0, Math.round(numAbove));
    if (spacingM !== null) zStack.spacing_m = Math.max(0.01, spacingM);
  }
  payload.radio_map = Object.assign(payload.radio_map || {}, { z_stack: zStack });

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
  if (isIndoorScopeTab(state.activeTab) || profileKey === "indoor_box_high") {
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

  if (ui.runBrowserToggle) {
    ui.runBrowserToggle.addEventListener("click", () => {
      void openRunBrowser();
    });
  }
  if (ui.runBrowserClose) {
    ui.runBrowserClose.addEventListener("click", closeRunBrowser);
  }
  if (ui.runBrowserOpenRun) {
    ui.runBrowserOpenRun.addEventListener("click", () => {
      if (!state.runBrowser.selectedRunId) return;
      void activateRunFromBrowser(state.runBrowser.selectedRunId);
    });
  }
  if (ui.runBrowserSearch) {
    ui.runBrowserSearch.addEventListener("input", () => {
      renderRunBrowserList();
    });
  }
  if (ui.runBrowserModal) {
    ui.runBrowserModal.addEventListener("click", (event) => {
      if (event.target === ui.runBrowserModal) {
        closeRunBrowser();
      }
    });
  }

  document.addEventListener("input", schedulePersistUiSnapshot, true);
  document.addEventListener("change", schedulePersistUiSnapshot, true);
  
  if (!ui.runSelect) console.error("ui.runSelect is missing");
  ui.runSelect.addEventListener("change", () => {
    const scope = getRunScopeForTab();
    state.followLatestRun = false;
    state.followLatestRunByScope[scope] = false;
    state.sceneOverrideDirty = false;
    if (state.activeTab === "ris-synth") {
      clearRisSynthesisViewerOverlay();
    }
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
    if (isIndoorScopeTab(state.activeTab) && ui.runProfile.value !== "indoor_box_high") {
      ui.runProfile.value = "indoor_box_high";
    }
    const activeProfileKey = getActiveProfileKey();
    if (activeProfileKey === "cpu_only" || activeProfileKey === "indoor_box_high") {
      const config = getProfileConfig();
      applyRadioMapDefaults(config);
      applyCustomDefaults(config);
      applySimTuningDefaults(config);
      applyRisSimDefaults(config);
      updateRisGeometryVisibility();
      resetMarkersFromConfig(config);
      if (activeProfileKey === "indoor_box_high") {
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
      if (state.activeTab === "campaign2") {
        syncCampaign2FixedRxPosition(getIndoorChamberConfig(), { force: true, rebuild: false });
      }
      rebuildScene({ refit: false });
    });
    ui.risList.addEventListener("change", () => {
      syncCampaignPivotUiFromRis();
      autoPlaceTxFromRis({ updateScene: true });
      if (state.activeTab === "campaign2") {
        syncCampaign2FixedRxPosition(getIndoorChamberConfig(), { force: true, rebuild: false });
      }
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
    ui.campaign2ShowSpecularPath,
    ui.campaign2CoarseCell,
  ]
    .filter(Boolean)
    .forEach((el) => {
      el.addEventListener("input", () => {
        if (state.activeTab === "campaign2") {
          syncCampaign2FixedRxPosition(getIndoorChamberConfig(), { force: true, rebuild: false });
        }
        rebuildScene({ refit: false });
      });
      el.addEventListener("change", () => {
        if (state.activeTab === "campaign2") {
          syncCampaign2FixedRxPosition(getIndoorChamberConfig(), { force: true, rebuild: false });
        }
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
  if (ui.radioMapZStackEnabled) {
    ui.radioMapZStackEnabled.addEventListener("change", () => {
      syncRadioMapZStackControls({ primeDefaults: ui.radioMapZStackEnabled.checked });
      schedulePersistUiSnapshot();
    });
  }
  [ui.radioMapZStackBelow, ui.radioMapZStackAbove, ui.radioMapZStackSpacing]
    .filter(Boolean)
    .forEach((el) => {
      el.addEventListener("change", () => {
        schedulePersistUiSnapshot();
      });
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
  ui.risLoadResults.addEventListener("click", () => {
    syncRisSelectedRun(ui.risRunSelect.value, { followActive: false });
    void loadRisResults(ui.risRunSelect.value);
  });
  
  if (!ui.risRunSelect) console.error("ui.risRunSelect is missing");
  ui.risRunSelect.addEventListener("change", () => {
    syncRisSelectedRun(ui.risRunSelect.value, { followActive: false });
    void loadRisResults(ui.risRunSelect.value);
  });

  if (!ui.risPlotTabs) console.error("ui.risPlotTabs is missing");
  ui.risPlotTabs.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const file = target.dataset.plot;
    const runId = state.ris.selectedRunId || state.ris.activeRunId;
    if (!file || !runId) return;
    state.ris.selectedPlot = file;
    ui.risPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
      btn.classList.toggle("is-active", btn === target);
    });
    renderRisPlotSingle(runId, file);
  });

  if (ui.risSynthConfigSource) {
    ui.risSynthConfigSource.addEventListener("change", () => {
      updateRisSynthesisConfigSourceVisibility();
      updateRisSynthesisConfigPreview();
    });
  }
  if (ui.risSynthSeedSource) {
    ui.risSynthSeedSource.addEventListener("change", () => {
      updateRisSynthesisSeedSourceVisibility();
      updateRisSynthesisConfigPreview();
    });
  }
  if (ui.risSynthSeedRun) {
    ui.risSynthSeedRun.addEventListener("change", async () => {
      await updateRisSynthesisSeedStatus();
      updateRisSynthesisConfigPreview();
    });
  }
  if (ui.risSynthBinarizationEnabled) {
    ui.risSynthBinarizationEnabled.addEventListener("change", () => {
      updateRisSynthesisBinarizationVisibility();
      updateRisSynthesisConfigPreview();
    });
  }
  if (ui.risSynthLoadViewer) {
    ui.risSynthLoadViewer.addEventListener("click", () => {
      void loadRisSynthesisViewerRun(true);
    });
  }
  if (ui.risSynthTopDownView) {
    ui.risSynthTopDownView.addEventListener("click", async () => {
      const synced = await ensureRisSynthesisViewerMatchesSeedRun();
      if (!synced) {
        setRisSynthesisViewerStatus("Load a seed run with a heatmap before switching to top-down view.");
        return;
      }
      if (!state.heatmap || !state.heatmap.values) {
        setRisSynthesisViewerStatus("Load a sim run with a heatmap before switching to top-down view.");
        return;
      }
      prepareRisSynthesisViewer();
      setRisSynthesisViewerStatus("Top-down heatmap view ready. Drag on the map to draw ROI boxes.");
    });
  }
  if (ui.risSynthDrawBoxes) {
    ui.risSynthDrawBoxes.addEventListener("click", async () => {
      const enabling = !state.risSynthesis.drawMode;
      if (enabling) {
        const synced = await ensureRisSynthesisViewerMatchesSeedRun();
        if (!synced) {
          setRisSynthesisViewerStatus("Load the seed run into the viewer before drawing ROIs.");
          return;
        }
      }
      if (!state.heatmap || !state.heatmap.values) {
        setRisSynthesisViewerStatus("Load a sim run with a heatmap before drawing ROIs.");
        return;
      }
      if (ui.heatmapRotation && Number(ui.heatmapRotation.value) !== 0) {
        prepareRisSynthesisViewer();
      } else {
        renderRisSynthesisRoiOverlay();
      }
      setRisSynthesisDrawMode(!state.risSynthesis.drawMode);
      setRisSynthesisViewerStatus(
        state.risSynthesis.drawMode
          ? (
            state.risSynthesis.replaceOnNextDraw
              ? "ROI drawing is active. The next box will replace the current target set; keep drawing to add more regions."
              : "ROI drawing is active. Drag on the heatmap to create a box."
          )
          : "ROI drawing stopped."
      );
    });
  }
  if (ui.risSynthUndoBox) {
    ui.risSynthUndoBox.addEventListener("click", () => {
      if (!state.risSynthesis.drawnBoxes.length) {
        setRisSynthesisViewerStatus("There are no ROI boxes to undo.");
        return;
      }
      const removed = state.risSynthesis.drawnBoxes[state.risSynthesis.drawnBoxes.length - 1];
      state.risSynthesis.drawnBoxes = state.risSynthesis.drawnBoxes.slice(0, -1);
      syncRisSynthesisBoxesTextareaFromState();
      renderRisSynthesisRoiOverlay();
      setRisSynthesisViewerStatus(`Removed ${removed?.name || "last ROI"}.`);
    });
  }
  if (ui.risSynthClearBoxes) {
    ui.risSynthClearBoxes.addEventListener("click", () => {
      state.risSynthesis.drawnBoxes = [];
      state.risSynthesis.draftBox = null;
      setRisSynthesisDrawMode(false);
      syncRisSynthesisBoxesTextareaFromState();
      renderRisSynthesisRoiOverlay();
      setRisSynthesisViewerStatus("Cleared all ROI boxes.");
    });
  }
  if (ui.risSynthStart) {
    ui.risSynthStart.addEventListener("click", submitRisSynthesisJob);
  }
  if (ui.risSynthRefresh) {
    ui.risSynthRefresh.addEventListener("click", refreshRisSynthesisJobs);
  }
  if (ui.risSynthLoadResults) {
    ui.risSynthLoadResults.addEventListener("click", () => {
      syncRisSynthesisSelectedRun(ui.risSynthRunSelect.value, { followActive: false });
      void loadRisSynthesisResults(ui.risSynthRunSelect.value);
    });
  }
  if (ui.risSynthApplyViewerMode) {
    ui.risSynthApplyViewerMode.addEventListener("click", () => {
      void applyRisSynthesisViewerMode();
    });
  }
  if (ui.risSynthViewerMode) {
    ui.risSynthViewerMode.addEventListener("change", () => {
      void applyRisSynthesisViewerMode();
    });
  }
  if (ui.risSynthQuantizeRun) {
    ui.risSynthQuantizeRun.addEventListener("click", submitRisSynthesisQuantizationJob);
  }
  if (ui.risSynthRunSelect) {
    ui.risSynthRunSelect.addEventListener("change", () => {
      syncRisSynthesisSelectedRun(ui.risSynthRunSelect.value, { followActive: false });
      void loadRisSynthesisResults(ui.risSynthRunSelect.value);
    });
  }
  if (ui.risSynthPlotTabs) {
    ui.risSynthPlotTabs.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;
      const file = target.dataset.plot;
      if (!file || !state.risSynthesis.activeRunId) return;
      state.risSynthesis.selectedPlot = file;
      ui.risSynthPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
        btn.classList.toggle("is-active", btn === target);
      });
      renderRisSynthesisPlotSingle(state.risSynthesis.activeRunId, file);
    });
  }

  if (ui.linkSeedSourceType) {
    ui.linkSeedSourceType.addEventListener("change", updateLinkSeedSourceVisibility);
  }
  if (ui.linkSeedRun) {
    ui.linkSeedRun.addEventListener("change", () => {
      void updateLinkSeedViewer();
    });
  }
  if (ui.linkSeedConfig) {
    ui.linkSeedConfig.addEventListener("change", () => {
      void updateLinkSeedViewer();
    });
  }
  if (ui.linkStart) {
    ui.linkStart.addEventListener("click", submitLinkJob);
  }
  if (ui.linkRefresh) {
    ui.linkRefresh.addEventListener("click", refreshLinkJobs);
  }
  if (ui.linkLoadResults) {
    ui.linkLoadResults.addEventListener("click", () => loadLinkResults(ui.linkRunSelect.value));
  }
  if (ui.linkRunSelect) {
    ui.linkRunSelect.addEventListener("change", () => loadLinkResults(ui.linkRunSelect.value));
  }
  if (ui.linkPlotTabs) {
    ui.linkPlotTabs.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;
      const file = target.dataset.plot;
      if (!file || !state.link.activeRunId) return;
      state.link.selectedPlot = file;
      ui.linkPlotTabs.querySelectorAll(".plot-tab-button").forEach((btn) => {
        btn.classList.toggle("is-active", btn === target);
      });
      renderLinkPlotSingle(state.link.activeRunId, file);
    });
  }
  
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
      if (e.key !== "Escape") return;
      if (ui.plotLightbox.style.display !== "none") closeLightbox();
      if (state.snapshotStudio.open) closeSnapshotStudio();
      if (state.runBrowser.open) closeRunBrowser();
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
  const risSynthesisPreviewInputs = [
    ui.risSynthConfigPath,
    ui.risSynthSeedSource,
    ui.risSynthSeedRun,
    ui.risSynthSeedConfig,
    ui.risSynthRisName,
    ui.risSynthBoxes,
    ui.risSynthIterations,
    ui.risSynthLearningRate,
    ui.risSynthLogEvery,
    ui.risSynthThresholdDbm,
    ui.risSynthObjectiveEps,
    ui.risSynthBinarizationEnabled,
    ui.risSynthOffsetSamples,
    ui.risSynthRefineEnabled,
    ui.risSynthCandidateBudget,
    ui.risSynthMaxPasses,
  ];

  if (ui.radioMapPreviewSelect) {
    ui.radioMapPreviewSelect.addEventListener("change", () => {
      if (!ui.radioMapPreviewImage) return;
      const file = ui.radioMapPreviewSelect.value;
      if (!file) return;
      const assetRunId = state.risSynthesis.viewerOverlayRunId || state.runId;
      ui.radioMapPreviewImage.src = assetRunId ? `/runs/${assetRunId}/viewer/${file}` : "";
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
  risSynthesisPreviewInputs.forEach((input) => {
    if (!input) return;
    const eventName = input.tagName && input.tagName.toLowerCase() === "select" ? "change" : "input";
    input.addEventListener(eventName, updateRisSynthesisConfigPreview);
    if (eventName !== "change") {
      input.addEventListener("change", updateRisSynthesisConfigPreview);
    }
  });
  if (ui.risSynthBoxes) {
    ui.risSynthBoxes.addEventListener("input", () => {
      syncRisSynthesisBoxesStateFromTextarea({ quiet: true });
    });
    ui.risSynthBoxes.addEventListener("change", () => {
      syncRisSynthesisBoxesStateFromTextarea({ quiet: false });
    });
  }
  
  if (!ui.topDown) console.error("ui.topDown is missing");
  ui.topDown.addEventListener("click", () => {
    setTopDownView({ preferHeatmap: state.activeTab === "ris-synth" });
  });
  
  if (!ui.snapshot) console.error("ui.snapshot is missing");
  ui.snapshot.addEventListener("click", () => {
    openSnapshotStudio();
  });

  [
    ui.snapshotWidth,
    ui.snapshotHeight,
    ui.snapshotScale,
    ui.snapshotTheme,
    ui.snapshotView,
    ui.snapshotProjection,
    ui.snapshotFov,
    ui.snapshotMargin,
    ui.snapshotTitle,
    ui.snapshotIncludeTitle,
    ui.snapshotIncludeMeta,
    ui.snapshotIncludeScaleBar,
    ui.snapshotIncludeFrame,
  ].forEach((input) => {
    if (!input) return;
    const eventName = input.tagName && input.tagName.toLowerCase() === "select" ? "change" : "input";
    input.addEventListener(eventName, () => {
      if (input === ui.snapshotWidth || input === ui.snapshotHeight) {
        syncSnapshotPresetFromDimensions();
      }
      scheduleSnapshotPreview();
    });
    if (eventName !== "change") {
      input.addEventListener("change", () => scheduleSnapshotPreview());
    }
  });
  if (ui.snapshotPreset) {
    ui.snapshotPreset.addEventListener("change", () => {
      if (ui.snapshotPreset.value !== "custom") applySnapshotPreset(ui.snapshotPreset.value);
      scheduleSnapshotPreview();
    });
  }
  if (ui.snapshotStudioClose) ui.snapshotStudioClose.addEventListener("click", closeSnapshotStudio);
  if (ui.snapshotRefreshPreview) ui.snapshotRefreshPreview.addEventListener("click", () => updateSnapshotPreview());
  if (ui.snapshotDownload) ui.snapshotDownload.addEventListener("click", downloadSnapshotExport);
  if (ui.snapshotCopy) ui.snapshotCopy.addEventListener("click", copySnapshotExport);
  if (ui.snapshotStudio) {
    ui.snapshotStudio.addEventListener("click", (event) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.dataset.closeSnapshot === "true") {
        closeSnapshotStudio();
      }
    });
  }
  
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
syncRadioMapZStackControls({ primeDefaults: Boolean(ui.radioMapZStackEnabled && ui.radioMapZStackEnabled.checked) });
autoPlaceTxFromRis({ updateScene: false });
updateSceneOverrideTxFromUi();
schedulePersistUiSnapshot();
updateRisActionVisibility();
updateRisConfigSourceVisibility();
updateRisControlVisibility();
updateRisConfigPreview();
updateRisPreview();
updateRisSynthesisConfigSourceVisibility();
updateRisSynthesisSeedSourceVisibility();
updateRisSynthesisBinarizationVisibility();
updateRisSynthesisConfigPreview();
syncRisSynthesisBoxesStateFromTextarea({ quiet: true });
syncRisSynthesisDrawModeUi();
renderRisSynthesisRoiOverlay();
setRisSynthesisViewerStatus("Load a sim run with a heatmap, then switch to Top-Down + Heatmap.");
updateLinkSeedSourceVisibility();
setCampaignRunControlsState();
setCampaign2RunControlsState();
setMainTab("sim");
fetchConfigs().then(fetchRuns).then(fetchBuiltinScenes).then(() => Promise.all([refreshCampaignJobs(), refreshCampaign2Jobs(), refreshRisJobs(), refreshRisSynthesisJobs(), refreshLinkJobs()]));
setInterval(() => {
  if (usesSharedViewerTab(state.activeTab)) {
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
  if (state.activeTab === "ris-synth") {
    refreshRisSynthesisJobs();
  }
  if (state.activeTab === "link") {
    refreshLinkJobs();
  }
}, 3000);
