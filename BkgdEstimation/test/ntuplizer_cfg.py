"""
This configuration file is mean to create the generalized Ntuples that will be used for the analysis.
For all objects the relevant corrections/ID criteria are applied

This ntuple contains the following collections

QualityLeptons:

- pT > 20GeV
- |eta| < 2.1
- passes Tight ID

QualityTracks:
- pT > 20GeV
- Passes Fiducial Selection
- >= 4 Pixel Hits
- 0 Missing Inner Hits
- 0 Missing Middle Hits
- Relative PF Isolation < 0.05
- |dxy| < 0.02cm
- |dx| < 0.5cm

If an event does not contain at least one of these then it is not included in the NTuple
"""
import os
import FWCore.ParameterSet.Config as cms
from Configuration.AlCa.GlobalTag import GlobalTag
from FWCore.ParameterSet.VarParsing import VarParsing
from DisappTrks_v2.BkgdEstimation.EcalBadCalibFilter_cff import addEcalBadCalibFilter

options = VarParsing("analysis")

options.register(
    "electronFiducialMap",
    "",
    VarParsing.multiplicity.singleton,
    VarParsing.varType.string,
    "Path to electron fiducial map",
)
options.register(
    "muonFiducialMap",
    "",
    VarParsing.multiplicity.singleton,
    VarParsing.varType.string,
    "Path to muon fiducial map",
)
options.register(
    "muonTriggerFilterName",
    "",
    VarParsing.multiplicity.singleton,
    VarParsing.varType.string,
    "Last filter label for muon trigger matching",
)
options.register(
    "electronTriggerFilterName",
    "",
    VarParsing.multiplicity.singleton,
    VarParsing.varType.string,
    "Last filter label for electron trigger matching",
)
options.register(
    "year",
    "",
    VarParsing.multiplicity.singleton,
    VarParsing.varType.string,
    "Year for of data taking (ie. 2024, 2025)"
)
options.register(
    "trigger",
    "",
    VarParsing.multiplicity.singleton,
    VarParsing.varType.string,
    "Trigger selection: 'MET', 'SingleElectron', or 'SingleMuon'",
)
options.parseArguments()


def require(name, value):
    if not value:
        raise RuntimeError(
            f"Required argument '{name}' was not provided.\n"
            f"Usage: cmsRun cfg.py {name}=<value>"
        )

#require("electronFiducialMap", options.electronFiducialMap)
#require("muonFiducialMap",     options.muonFiducialMap)
require("trigger", options.trigger)

# Define trigger sets
triggerPaths = {
    "MET": cms.vstring(
        "HLT_MET105_IsoTrk50_v*",
        "HLT_MET120_IsoTrk50_v*",
        "HLT_PFMET105_IsoTrk50_v*",
        "HLT_PFMET120_PFMHT120_IDTight_v*",
        "HLT_PFMET130_PFMHT130_IDTight_v*",
        "HLT_PFMET140_PFMHT140_IDTight_v*",
        "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_v*",
        "HLT_PFMETNoMu130_PFMHTNoMu130_IDTight_v*",
        "HLT_PFMETNoMu140_PFMHTNoMu140_IDTight_v*",
        "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_PFHT60_v*",
        "HLT_PFMETNoMu110_PFMHTNoMu110_IDTight_FilterHF_v*",
        "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_FilterHF_v*",
        "HLT_PFMETNoMu130_PFMHTNoMu130_IDTight_FilterHF_v*",
        "HLT_PFMETNoMu140_PFMHTNoMu140_IDTight_FilterHF_v*",
        "HLT_PFMET120_PFMHT120_IDTight_PFHT60_v*",
    ),
    "SingleElectron": cms.vstring(
        "HLT_Ele32_WPTight_Gsf_v*",
    ),
    "SingleMuon": cms.vstring(
        "HLT_IsoMu24_v*",
    ),
}

if options.trigger not in triggerPaths:
    raise RuntimeError(
        f"Unknown trigger '{options.trigger}'. "
        f"Choose from: {list(triggerPaths.keys())}"
    )


processName = "NTuplizer"
process = cms.Process(processName)
process.options = cms.untracked.PSet(wantSummary=cms.untracked.bool(True))

process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
process.load("Configuration.StandardSequences.GeometryDB_cff")
process.load("Configuration.StandardSequences.MagneticField_AutoFromDBCurrent_cff")
process.CaloGeometryBuilder.SelectedCalos = [
    "HCAL",
    "ZDC",
    "EcalBarrel",
    "EcalEndcap",
    "EcalPreshower",
    "TOWER",
]

# 2025: 150X_dataRun3_Prompt_v1
# 2024: 150X_dataRun3_v2
data_global_tag = '150X_dataRun3_Prompt_v1'
mc_global_tag   = '150X_mcRun3_2024_realistic_v2'
MC = False
process.GlobalTag = GlobalTag(
    process.GlobalTag, mc_global_tag if MC else data_global_tag, ""
)

process.source = cms.Source(
    "PoolSource", fileNames=cms.untracked.vstring(options.inputFiles)
)

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(options.maxEvents))

process.TFileService = cms.Service("TFileService", fileName=cms.string("ntuple.root"))

ecalBadCalibFilter = addEcalBadCalibFilter(process, options.year)

process.hltFilter = cms.EDFilter(
    "HLTHighLevel",
    TriggerResultsTag=cms.InputTag("TriggerResults", "", "HLT"),
    eventSetupPathsKey=cms.string(""),
    andOr=cms.bool(True),
    throw=cms.bool(False),
    HLTPaths=triggerPaths[options.trigger],
)

process.metFilters = cms.EDFilter("HLTHighLevel",
    TriggerResultsTag  = cms.InputTag("TriggerResults", "", "RECO"), # Should be RECO for 2025 and PAT for 2024
    eventSetupPathsKey = cms.string(""),
    andOr              = cms.bool(False),   # AND — must pass all filters
    throw              = cms.bool(False),
    HLTPaths           = cms.vstring(
        "Flag_goodVertices",
        "Flag_globalSuperTightHalo2016Filter",
        "Flag_EcalDeadCellTriggerPrimitiveFilter",
        "Flag_BadPFMuonFilter",
        "Flag_BadPFMuonDzFilter",
        "Flag_hfNoisyHitsFilter",
        "Flag_eeBadScFilter",                # data only
        "Flag_ecalBadCalibFilter",
    ),
)

# ── TrackElectronFiducialFilter ───────────────────────────────────────────────
# Consumes: ("ZtoProbeTrkTrackSelections", "probeTracks")
# Produces: ("TrackElectronFiducialFilter", "fiducialTracks")
process.TrackElectronFiducialFilter = cms.EDFilter(
    "TrackFiducialFilter",
    tracks=cms.InputTag("isolatedTracks"),
    useEraByEraFiducialMaps=cms.bool(False),
    fiducialMaps=cms.VPSet(
        cms.PSet(
            histFile=cms.FileInPath(options.electronFiducialMap),
            beforeVetoHistName=cms.string("beforeVeto"),
            afterVetoHistName=cms.string("afterVeto"),
            thresholdForVeto=cms.double(2.0),
        ),
    ),
)

# ── TrackMuonFiducialFilter ───────────────────────────────────────────────────
# Consumes: ("TrackElectronFiducialFilter", "fiducialTracks")
# Produces: ("TrackMuonFiducialFilter", "fiducialTracks")
process.TrackMuonFiducialFilter = cms.EDFilter(
    "TrackFiducialFilter",
    tracks=cms.InputTag("TrackElectronFiducialFilter:fiducialTracks"),
    useEraByEraFiducialMaps=cms.bool(False),
    fiducialMaps=cms.VPSet(
        cms.PSet(
            histFile=cms.FileInPath(options.muonFiducialMap),
            beforeVetoHistName=cms.string("beforeVeto"),
            afterVetoHistName=cms.string("afterVeto"),
            thresholdForVeto=cms.double(2.0),
        ),
    ),
)

# ── TrackEcalDeadChannelFilter ────────────────────────────────────────────────
# Consumes: ("TrackMuonFiducialFilter", "fiducialTracks")
# Produces: ("TrackEcalDeadChannelFilter", "ecalTracks")
process.TrackEcalDeadChannelFilter = cms.EDFilter("TrackEcalDeadChannelFilter",
    # Value for 2024 where fiducial maps are available
    #tracks                           = cms.InputTag("TrackMuonFiducialFilter:fiducialTracks"),
    tracks                           = cms.InputTag("isolatedTracks"),
    maskedEcalChannelStatusThreshold = cms.int32(3),
    minDeltaR                        = cms.double(0.05),
)

process.load("DisappTrks_v2.BkgdEstimation.JecAppliedJetProducer_cfi")
process.load("DisappTrks_v2.BkgdEstimation.JecAppliedMetProducer_cfi")
process.load("DisappTrks_v2.BkgdEstimation.JvmAppliedEventFilter_cfi")

process.jecAppliedMetProducer.Jets.Year = cms.string(options.year)
process.jecAppliedMetProducer.Jets.Era = cms.string("Era" + options.year + "All") # Does only work for 2024 & 25 data
#process.jecAppliedMetProducer.Jets.Era = cms.string("Era2022C") # Does only work for 2024 & 25 data
process.jecAppliedJetProducer.Jets.Year = cms.string(options.year)
process.jecAppliedJetProducer.Jets.Era = cms.string("Era" + options.year + "All")
#process.jecAppliedJetProducer.Jets.Era = cms.string("Era2022C")
process.JvmAppliedEventFilter.Jets.Year = cms.string(options.year)


# Does something like this exist?
process.tightLepVetoJets = cms.EDFilter("PATJetSelector",
    src = cms.InputTag("jecAppliedJetProducer", "CorrectedAK4"),
    cut = cms.string(
        # Central region |eta| <= 2.6
        "(abs(eta) <= 2.6"
        " && neutralHadronEnergyFraction < 0.99"
        " && neutralEmEnergyFraction < 0.9"
        " && numberOfDaughters > 1"
        " && muonEnergyFraction < 0.8"
        " && chargedHadronEnergyFraction > 0.01"
        " && chargedMultiplicity > 0"
        " && chargedEmEnergyFraction < 0.8)"
        # Transition region 2.6 < |eta| <= 2.7
        " || (abs(eta) > 2.6 && abs(eta) <= 2.7"
        " && neutralHadronEnergyFraction < 0.9"
        " && neutralEmEnergyFraction < 0.99"
        " && muonEnergyFraction < 0.8"
        " && chargedEmEnergyFraction < 0.8)"
        # Forward region 2.7 < |eta| <= 3.0
        " || (abs(eta) > 2.7 && abs(eta) <= 3.0"
        " && neutralHadronEnergyFraction < 0.99)"
        # Very forward region |eta| > 3.0
        " || (abs(eta) > 3.0"
        " && neutralEmEnergyFraction < 0.4"
        " && neutralMultiplicity >= 2)"
    )
)

process.leptonCollectionsProducer = cms.EDProducer(
    "LeptonCollectionsProducer",
    electrons=cms.InputTag("slimmedElectrons"),
    muons=cms.InputTag("slimmedMuons"),
    taus=cms.InputTag("slimmedTaus"),
    vertices=cms.InputTag("offlineSlimmedPrimaryVertices"),
    minPt=cms.double(20.0),
    maxEta=cms.double(2.1),
    electronIdLabel=cms.string("cutBasedElectronID-RunIIIWinter22-V1-tight"),
    tauVsJetLabel=cms.string(""),
    tauVsEleLabel=cms.string("byTightDeepTau2018v2p5VSe"),
    tauVsMuLabel=cms.string("byTightDeepTau2018v2p5VSmu"),
)

process.qualityTrackProducer = cms.EDProducer(
    "QualityTrackProducer",
    tracks=cms.InputTag("TrackEcalDeadChannelFilter", "ecalTracks"),
    minPt=cms.double(20.0),
    minPixelHits=cms.int32(4),
    maxRelIso=cms.double(0.05),
    maxDxy=cms.double(0.02),
    maxDz=cms.double(0.5),
)

process.ntuplizer = cms.EDAnalyzer("Ntuplizer",
    tracks       = cms.InputTag("qualityTrackProducer",      "qualityTracks"),
    met          = cms.InputTag("jecAppliedMetProducer",     "CorrectedMet"),
    muons        = cms.InputTag("leptonCollectionsProducer", "qualityMuons"),
    electrons    = cms.InputTag("leptonCollectionsProducer", "qualityElectrons"),
    vertices     = cms.InputTag("offlineSlimmedPrimaryVertices"),
    jets         = cms.InputTag("jecAppliedJetProducer",     "CorrectedAK4"),
    tightJets    = cms.InputTag("tightLepVetoJets"),
    taus         = cms.InputTag("leptonCollectionsProducer", "qualityTaus"),
    allMuons     = cms.InputTag("slimmedMuons"),
    allElectrons = cms.InputTag("slimmedElectrons"),
    allTaus      = cms.InputTag("slimmedTaus"),
    treeName     = cms.string("Events"),
    triggerResults=cms.InputTag("TriggerResults", "", "HLT"),
    triggerObjects=cms.InputTag("slimmedPatTrigger"),
    triggerMatchingDR=cms.double(0.3),
    rhoAll         =cms.InputTag("fixedGridRhoFastjetAll"),
    rhoAllCalo     =cms.InputTag("fixedGridRhoFastjetAllCalo"),
    rhoCentralCalo =cms.InputTag("fixedGridRhoFastjetCentralCalo"),
)

process.p = cms.Path(
    process.hltFilter *
    process.metFilters *
    process.ecalBadCalibReducedMINIAODFilter
#    process.TrackElectronFiducialFilter * # Removed in 2025 since the fiducial maps weren't already created
#    process.TrackMuonFiducialFilter *
    # process.TrackEcalDeadChannelFilter *
    # process.JvmAppliedEventFilter *
    # process.jecAppliedJetProducer *
    # process.jecAppliedMetProducer *
    # process.leptonCollectionsProducer *
    # process.qualityTrackProducer *
    # process.ntuplizer
)
