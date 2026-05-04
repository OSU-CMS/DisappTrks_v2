"""
Ntuplizer configuration for the DisappTrks_v2 background estimation.

No pre-selection cuts are applied to leptons or tracks — all objects from the
slimmed/isolated collections are written to the ntuple so that analysis cuts
can be varied offline. Discriminating variables (isTight, pfRelIso04_dBeta,
isTightLepVeto, hit pattern, calo isolation, etc.) are stored as branches.

Event-level filters applied in the path:
  - HLT trigger filter
  - MET filters (goodVertices, halo, ECAL/HCAL noise, eeBadSc, ecalBadCalib)
  - Jet Veto Map
"""
import os
import FWCore.ParameterSet.Config as cms
from Configuration.AlCa.GlobalTag import GlobalTag
from FWCore.ParameterSet.VarParsing import VarParsing
from DisappTrks_v2.BkgdEstimation.EcalBadCalibFilter_cff import addEcalBadCalibFilter

# VarParsing allows you to configure the cfg file from the command-line. The format
# for using these options are:
# cmsRun ntuplizer_cfg.py year=2023 trigger=SingleElectron inputFiles=myInputFile.root maxEvents=1000
options = VarParsing("analysis")
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

# Require that the trigger and year are set, otherwise the script will crash out
def require(name, value):
    if not value:
        raise RuntimeError(
            f"Required argument '{name}' was not provided.\n"
            f"Usage: cmsRun cfg.py {name}=<value>"
        )

require("trigger", options.trigger)
require("year", options.trigger)

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

# Sets up the geometry of the detector
process.load("Configuration.StandardSequences.FrontierConditions_GlobalTag_cff")
process.load("Configuration.StandardSequences.GeometryDB_cff")
process.load("Configuration.StandardSequences.MagneticField_AutoFromDBCurrent_cff")
# This is needed to be set in order for the code to run.
# Gets rid of CASTOR which was causing issues
process.CaloGeometryBuilder.SelectedCalos = [
    "HCAL",
    "ZDC",
    "EcalBarrel",
    "EcalEndcap",
    "EcalPreshower",
    "TOWER",
]

# Sets the global tag, needs to be set manually for now!
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

# Handles the additional masking of ECAL channels that was stated in
# this Twiki: https://twiki.cern.ch/twiki/bin/viewauth/CMS/MissingETOptionalFiltersRun2#Run_3_2024_data_and_MC_Recommend
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

# ── TrackEcalDeadChannelFilter ────────────────────────────────────────────────
# Consumes: (isolatedTracks)
# Produces: ("TrackEcalDeadChannelFilter", "ecalTracks")
process.TrackEcalDeadChannelFilter = cms.EDFilter("TrackEcalDeadChannelFilter",
    tracks                           = cms.InputTag("isolatedTracks"),
    maskedEcalChannelStatusThreshold = cms.int32(3),
    minDeltaR                        = cms.double(0.05),
)

# This loads in the configuration fragments that are stored in the python directory
process.load("DisappTrks_v2.BkgdEstimation.JecAppliedJetProducer_cfi")
process.load("DisappTrks_v2.BkgdEstimation.JecAppliedMetProducer_cfi")
process.load("DisappTrks_v2.BkgdEstimation.JvmAppliedEventFilter_cfi")


# Allows you to set that year that should be used for the JEC and JVM values.
# In 2024 and 2025, the key is of the format Era2024All and Era2025All.
# In 2023 the format is Era2023PreAll and Era2023PostAll to signify 2023C and 2023D
# In 2022 the keys for year and era are formatted differently so this will need to be changed
# To see the format of the keys, check JecConfigAK4.json
process.jecAppliedMetProducer.Jets.Year = cms.string(options.year)
process.jecAppliedMetProducer.Jets.Era = cms.string("Era" + options.year + "All") # Does only work for 2024 & 25 data
process.jecAppliedJetProducer.Jets.Year = cms.string(options.year)
process.jecAppliedJetProducer.Jets.Era = cms.string("Era" + options.year + "All")
process.JvmAppliedEventFilter.Jets.Year = cms.string(options.year)

process.ntuplizer = cms.EDAnalyzer("Ntuplizer",
    tracks       = cms.InputTag("isolatedTracks"),
    met          = cms.InputTag("jecAppliedMetProducer", "CorrectedMet"),
    muons        = cms.InputTag("slimmedMuons"),
    electrons    = cms.InputTag("slimmedElectrons"),
    taus         = cms.InputTag("slimmedTaus"),
    vertices     = cms.InputTag("offlineSlimmedPrimaryVertices"),
    jets         = cms.InputTag("jecAppliedJetProducer", "CorrectedAK4"),
    treeName     = cms.string("Events"),
    triggerResults       = cms.InputTag("TriggerResults", "", "HLT"),
    triggerObjects       = cms.InputTag("slimmedPatTrigger"),
    muonTriggerFilterName     = cms.string("hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered"),
    electronTriggerFilterName = cms.string("hltEle32WPTightGsfTrackIsoFilter"),
    triggerMatchingDR    = cms.double(0.3),
    hitInefficiency      = cms.double(0.0),
    electronIdLabel      = cms.string("cutBasedElectronID-RunIIIWinter22-V1-tight"),
    tauVsJetLabel        = cms.string(""),
    tauVsEleLabel        = cms.string("byTightDeepTau2018v2p5VSe"),
    tauVsMuLabel         = cms.string("byTightDeepTau2018v2p5VSmu"),
    rhoAll               = cms.InputTag("fixedGridRhoFastjetAll"),
    rhoAllCalo           = cms.InputTag("fixedGridRhoFastjetAllCalo"),
    rhoCentralCalo       = cms.InputTag("fixedGridRhoFastjetCentralCalo"),
    maskedEcalChannelStatusThreshold = cms.int32(3)
)

process.p = cms.Path(
    process.hltFilter *
    process.metFilters *
    process.ecalBadCalibReducedMINIAODFilter*
    process.TrackEcalDeadChannelFilter *
    process.JvmAppliedEventFilter *
    process.jecAppliedJetProducer *
    process.jecAppliedMetProducer *
    process.ntuplizer
)
