
# Create Skims for Tag and Probe studies for background estimation
import FWCore.ParameterSet.Config as cms

processName = "ZtoEleProbeTrk"
process = cms.Process(processName)

process.options = cms.untracked.PSet(
    wantSummary = cms.untracked.bool(True)
)

process.MessageLogger.cerr.CutflowAnalyzer = cms.untracked.PSet(
    limit = cms.untracked.int32(100)
)

# Setup Global Tag
process.load('Configuration.StandardSequences.FrontierConditions_GlobalTag_cff')
process.load("Configuration.StandardSequences.GeometryDB_cff")
process.load("Configuration.StandardSequences.MagneticField_AutoFromDBCurrent_cff")
process.CaloGeometryBuilder.SelectedCalos = [
    "HCAL", "ZDC", "EcalBarrel", "EcalEndcap", "EcalPreshower", "TOWER",
]

from Configuration.AlCa.GlobalTag import GlobalTag
data_global_tag = '150X_dataRun3_v2'
mc_global_tag   = '150X_mcRun3_2024_realistic_v2'
MC = False
process.GlobalTag = GlobalTag(process.GlobalTag,
                              mc_global_tag if MC else data_global_tag, '')

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring(
        'root://cmseos.fnal.gov//eos/uscms/store/user/lpclonglived/DisappTrks/EGamma0/ElectronTagSkim_2024G_v1_EGamma0/260303_183737/0001/skim_ElectronTagSkim_2026_03_03_12h35m53s_1037.root'),
    inputCommands = cms.untracked.vstring(
            'keep *',
            'drop *_*_eventvariables_*',
        )
    
)

process.maxEvents = cms.untracked.PSet(input = cms.untracked.int32(-1))

# Used to store histograms
process.TFileService = cms.Service("TFileService",
    fileName = cms.string("ZtoEleProbeTrk.root")
)

# ─────────────────────────────────────────────────────────────────────────────
# Producer chain — each filter consumes the output of the previous one,
# guaranteeing all cuts act on the same track object.
#
# ZtoProbeTrkTrackSelections        → "probeTracks"
# ElectronFiducial   → "fiducialTracks"   (consumes probeTracks)
# MuonFiducial       → "fiducialTracks"   (consumes ElectronFiducial output)
# EcalDeadChannel    → "ecalTracks"       (consumes MuonFiducial output)
# JetDeltaR          → "deltaRTracks"     (consumes ecalTracks)
# MuonDeltaR         → "deltaRTracks"     (consumes JetDeltaR output)
# TauDeltaR          → "deltaRTracks"     (consumes MuonDeltaR output)
#
# ─────────────────────────────────────────────────────────────────────────────

process.hltFilter = cms.EDFilter("HLTHighLevel",
    TriggerResultsTag  = cms.InputTag("TriggerResults", "", "HLT"),
    HLTPaths           = cms.vstring("HLT_Ele32_WPTight_Gsf_v*"),
    eventSetupPathsKey = cms.string(""),
    andOr              = cms.bool(True),
    throw              = cms.bool(False),
)

process.QualityCut = cms.EDFilter("QualityCut",
    src          = cms.InputTag("slimmedElectrons"),
    met          = cms.InputTag("jecAppliedMetProducer:CorrectedMet"),
    vertices     = cms.InputTag("offlineSlimmedPrimaryVertices"),
    minPt        = cms.double(32.0),
    maxEta       = cms.double(2.1),
    tightIdLabel = cms.string("cutBasedElectronID-RunIIIWinter22-V1-tight"),
    triggerObjects = cms.InputTag("slimmedPatTrigger"),
    instanceLabel = cms.string("QualityCut")
)



# ── ZtoProbeTrkTrackSelections ───────────────────────────────────────────────────────────────
# Produces: ("ZtoProbeTrkTrackSelections", "probeTracks")
process.ZtoProbeTrkTrackSelections = cms.EDFilter("ZtoProbeTrkTrackSelections",
    tracks       = cms.InputTag("isolatedTracks"),
    muons        = cms.InputTag("selectedMuons"),
    electrons    = cms.InputTag("QualityCut:qualityLeptons"),
    jets         = cms.InputTag("jecAppliedJetProducer:CorrectedAK4"),   # CHS jets — matches old framework
    minPt        = cms.double(30),
    minLayers    = cms.int32(4),
    useExclusive = cms.bool(False),
    minDeltaRJet = cms.double(0.5),
    instanceLabel = cms.string("ZtoProbeTrkTrackSelections")
)

# ── Event-level Z pair filter (pure filter, no output collection) ─────────────
# Consumes probeTracks but does not produce a chained collection since the
# exactly-one-pair requirement is event-level not per-track.

# ── TrackElectronFiducialFilter ───────────────────────────────────────────────
# Consumes: ("ZtoProbeTrkTrackSelections", "probeTracks")
# Produces: ("TrackElectronFiducialFilter", "fiducialTracks")
process.TrackElectronFiducialFilter = cms.EDFilter("TrackFiducialFilter",
    tracks = cms.InputTag("ZtoProbeTrkTrackSelections:probeTracks"),
    useEraByEraFiducialMaps = cms.bool(False),
    fiducialMaps = cms.VPSet(
        cms.PSet(
            histFile           = cms.FileInPath("DisappTrks_v2/data/electronFiducialMap_2024G_data.root"),
            era                = cms.string(""),
            beforeVetoHistName = cms.string("beforeVeto"),
            afterVetoHistName  = cms.string("afterVeto"),
            thresholdForVeto   = cms.double(2.0),
        ),
    ),
)

# ── TrackMuonFiducialFilter ───────────────────────────────────────────────────
# Consumes: ("TrackElectronFiducialFilter", "fiducialTracks")
# Produces: ("TrackMuonFiducialFilter", "fiducialTracks")
process.TrackMuonFiducialFilter = cms.EDFilter("TrackFiducialFilter",
    tracks = cms.InputTag("TrackElectronFiducialFilter:fiducialTracks"),
    useEraByEraFiducialMaps = cms.bool(False),
    fiducialMaps = cms.VPSet(
        cms.PSet(
            histFile           = cms.FileInPath("DisappTrks_v2/data/muonFiducialMap_2024G_data.root"),
            era                = cms.string(""),
            beforeVetoHistName = cms.string("beforeVeto"),
            afterVetoHistName  = cms.string("afterVeto"),
            thresholdForVeto   = cms.double(2.0),
        ),
    ),
)

# ── TrackEcalDeadChannelFilter ────────────────────────────────────────────────
# Consumes: ("TrackMuonFiducialFilter", "fiducialTracks")
# Produces: ("TrackEcalDeadChannelFilter", "ecalTracks")
process.TrackEcalDeadChannelFilter = cms.EDFilter("TrackEcalDeadChannelFilter",
    tracks                           = cms.InputTag("TrackMuonFiducialFilter:fiducialTracks"),
    maskedEcalChannelStatusThreshold = cms.int32(3),
    minDeltaR                        = cms.double(0.05),
)

# ── JvmAppliedEventFilter ─────────────────────────────────────────────────────
# Event-level jet veto map — no track collection input/output.
process.JvmAppliedEventFilter = cms.EDFilter("JvmAppliedEventFilter",
    Jets = cms.PSet(
        SourcesAK4 = cms.InputTag("slimmedJetsPuppi"),
        Year       = cms.string("2024"),
        JvmConfig  = cms.FileInPath("DisappTrks_v2/data/JvmConfig.json"),
    ),
)
process.TrackDRMinJetAnalyzer = cms.EDAnalyzer("TrackDRMinJetAnalyzer",
    tracks = cms.InputTag("TrackTauDeltaRFilter", "deltaRTracks"),
    jets   = cms.InputTag("slimmedJetsPuppi"),
)


process.selectedTaus = cms.EDFilter("PATTauSelector",
    src    = cms.InputTag("slimmedTaus"),
    cut    = cms.string(
        "pt > 20 && "
        "tauID('decayModeFindingNewDMs') > 0.5 && "
        "tauID('byVVVLooseDeepTau2018v2p5VSe') > 0.5 && "
        "tauID('byVLooseDeepTau2018v2p5VSmu') > 0.5"
    ),
    filter = cms.bool(False),
)


process.selectedMuons = cms.EDFilter("PATMuonSelector",
    src    = cms.InputTag("slimmedMuons"),
    cut    = cms.string(
        "pt > 26 && "
        "abs(eta) < 2.4 && "
        "isLooseMuon && "
        "isPFMuon"
    ),
    filter = cms.bool(False),
)


# ── TrackMuonDeltaRFilter ─────────────────────────────────────────────────────
# Consumes: ("TrackJetDeltaRFilter", "deltaRTracks")
# Produces: ("TrackMuonDeltaRFilter", "deltaRTracks")
process.TrackMuonDeltaRFilter = cms.EDFilter("TrackMinDeltaRFilter",
    tracks    = cms.InputTag("TrackEcalDeadChannelFilter:ecalTracks"),
    objects   = cms.InputTag("selectedMuons"),
    minDeltaR = cms.double(0.15),
)

# ── TrackTauDeltaRFilter ──────────────────────────────────────────────────────
# Consumes: ("TrackMuonDeltaRFilter", "deltaRTracks")
# Produces: ("TrackTauDeltaRFilter", "deltaRTracks")
process.TrackTauDeltaRFilter = cms.EDFilter("TrackMinDeltaRFilter",
    tracks    = cms.InputTag("TrackMuonDeltaRFilter:deltaRTracks"),
    objects   = cms.InputTag("selectedTaus"),
    minDeltaR = cms.double(0.15),
)


# ── Output module ─────────────────────────────────────────────────────────────
process.out = cms.OutputModule("PoolOutputModule",
    fileName = cms.untracked.string("electronFiducialFilter.root"),
    outputCommands = cms.untracked.vstring(
        'drop *',
        'keep patElectrons_slimmedElectrons__*',
        'keep patIsolatedTracks_isolatedTracks__*',
        'keep *_TrackElectronFiducialFilter_fiducialTracks_*',
        'keep *_TrackMuonDeltaRFilter_deltaRTracks_*',
        'keep *_TrackTauDeltaRFilter_deltaRTracks_*',
        'keep *_QualityCut_qualityLeptons_*'
    )
)
process.load('DisappTrks_v2.BkgdEstimation.JecAppliedJetProducer_cfi')
process.load('DisappTrks_v2.BkgdEstimation.JecAppliedMetProducer_cfi')
process.load('DisappTrks_v2.BkgdEstimation.JvmAppliedEventFilter_cfi')

# ── Main path ─────────────────────────────────────────────────────────────────
process.mypath = cms.Path(
    process.hltFilter                   * # Ensure event comes from correct HLT Trigger
    process.jecAppliedJetProducer       * # Apply Jet corrections
    process.jecAppliedMetProducer       * # Apply MET Corrections
    process.selectedTaus                * # Apply tau IDs and corrections
    process.selectedMuons               * # Apply muon IDs and corrections
    process.QualityCut                  * # Apply quality cuts on lepton
    process.ZtoProbeTrkTrackSelections  * # Apply track quality cuts
    process.TrackElectronFiducialFilter * # Passes electron fiducial map
    process.TrackMuonFiducialFilter     * # Passes muon fiducial map
    process.TrackEcalDeadChannelFilter  * # Passes ecal fiducial map
    process.JvmAppliedEventFilter       * # Passes Jet Veto Map
    process.TrackMuonDeltaRFilter       * # Check if track is close to muon
    process.TrackTauDeltaRFilter          # Check if track is close to tau
)


process.cutflowEndPath = cms.EndPath(process.out)
