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

This file is currently hard-coded for 2022 data (22Sep2023 re-miniAOD), with
the original 2024/2025 settings commented out and marked "newer data". The
2022 numbers (Global Tags, JEC eras, JVM keys, MET-filter process name,
trigger list, electron ID label) follow AN-2024-155 v4 §2-4.
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
require("year", options.year)

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
#
# 2022 — values taken from AN-2024-155 v4, section 2.1 / 2.2.
#   Analysis CMSSW: CMSSW_13_0_13. Inputs are the 22Sep2023 re-miniAOD.
#   Lumi JSON: Cert_Collisions2022_355100_362760_Golden.json
#
#   DATA GTs used in the AN for 2022 (both appear; PromptAnalysis_v1 is also
#   the GT used for 2023, so it's the safer default if you're not sure):
#     130X_dataRun3_v2
#     130X_dataRun3_PromptAnalysis_v1
#
#   MC GTs (Run3Summer22MiniAODv4 / Run3Summer22EEMiniAODv4 MiniAOD step):
#     pre-EE  (eras C, D)   : 130X_mcRun3_2022_realistic_v5
#     post-EE (eras E, F, G): 130X_mcRun3_2022_realistic_postEE_v6
#
# data_global_tag = '150X_dataRun3_Prompt_v1'                 # 24newer data
# mc_global_tag   = '150X_mcRun3_2024_realistic_v2'           # 24 newer data
data_global_tag = '130X_dataRun3_PromptAnalysis_v1'        #Did Mike use this for 2022 data?
#data_global_tag = '130X_dataRun3_V2'
mc_global_tag   = '130X_mcRun3_2022_realistic_postEE_v6'   # change to ...realistic_v5 for 2022 C/D MC
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
    # TriggerResultsTag  = cms.InputTag("TriggerResults", "", "RECO"), # Should be RECO for 2025 and PAT for 2024  # newer data
    TriggerResultsTag  = cms.InputTag("TriggerResults", "", "PAT"),  # 2022 22Sep2023 re-reco MINIAOD uses PAT
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
# In 2022 the keys are split into 2022Pre (Run C/D) and 2022Post (Run E/F/G),
#   with per-run era keys Era2022C/D/E/F/G (no *All key exists for 2022).
#
# The 2022 pre-/post-EE split (and the corresponding JVM map split) matches
# the analysis split in AN-2024-155 v4 §2.2: eras C, D = pre-EE; eras E, F, G
# = post-EE (ECAL endcap water leak). The JVM map for 2022Post is the JME-POG
# recommended Summer22EE_23Sep2023_RunEFG_V1, which already encodes the EFG
# water-leak veto region described in AN §4.2.
# To see the format of the keys, check JecConfigAK4.json.
#
# Hard-coded here for 2022 Run G (post-EE). Change jec_year_key / jec_era_key
# to match the era of the input file:
#   2022Pre  -> Era2022C, Era2022D
#   2022Post -> Era2022E, Era2022F, Era2022G
jec_year_key = "2022Post"
jec_era_key  = "Era2022E"
jvm_year_key = "2022Post"

# process.jecAppliedMetProducer.Jets.Year = cms.string(options.year)                              # newer data
# process.jecAppliedMetProducer.Jets.Era  = cms.string("Era" + options.year + "All")              # newer data
# process.jecAppliedJetProducer.Jets.Year = cms.string(options.year)                              # newer data
# process.jecAppliedJetProducer.Jets.Era  = cms.string("Era" + options.year + "All")              # newer data
# process.JvmAppliedEventFilter.Jets.Year = cms.string(options.year)                              # newer data
process.jecAppliedMetProducer.Jets.Year = cms.string(jec_year_key)
process.jecAppliedMetProducer.Jets.Era  = cms.string(jec_era_key)
process.jecAppliedJetProducer.Jets.Year = cms.string(jec_year_key)
process.jecAppliedJetProducer.Jets.Era  = cms.string(jec_era_key)
process.JvmAppliedEventFilter.Jets.Year = cms.string(jvm_year_key)

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
