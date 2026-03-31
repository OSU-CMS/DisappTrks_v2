#!/usr/bin/env python3
import FWCore.ParameterSet.Config as cms

processName = "ElectronCR"
process = cms.Process(processName)

process.options = cms.untracked.PSet(
    wantSummary = cms.untracked.bool(True)
)

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

process.TFileService = cms.Service("TFileService",
                                   fileName = cms.string("hist_ElectronCR.root"))

process.hltFilter = cms.EDFilter("HLTHighLevel",
    TriggerResultsTag  = cms.InputTag("TriggerResults", "", "HLT"),
    HLTPaths           = cms.vstring("HLT_Ele32_WPTight_Gsf_v*"),
    eventSetupPathsKey = cms.string(""),
    andOr              = cms.bool(True),
    throw              = cms.bool(False),
)

process.selectedElectrons = cms.EDProducer("PATElectronSelector",
    src = cms.InputTag("slimmedElectrons"),
    cut = cms.string("pt > 35.0 && abs(eta) < 2.1 && electronID('cutBasedElectronID-RunIIIWinter22-V1-tight') > 0.5"),
)

process.randomElectron = cms.EDProducer("RandomElectronProducer",
                                        src = cms.InputTag("selectedElectrons")
                                        )



process.load('DisappTrks_v2.BkgdEstimation.JvmAppliedEventFilter_cfi')
process.load('DisappTrks_v2.IsolatedTracks.BasicSelectionJetCuts_cff')

process.JvmAppliedEventFilter = cms.EDFilter("JvmAppliedEventFilter",
    Jets = cms.PSet(
        SourcesAK4 = cms.InputTag("slimmedJetsPuppi"),
        Year       = cms.string("2024"),
        JvmConfig  = cms.FileInPath("DisappTrks_v2/data/JvmConfig.json"),
    ),
)

process.load('DisappTrks_v2.BkgdEstimation.ZtoProbeTrkTrackSelections_cff')

process.TrackElectronDeltaRFilter = cms.EDFilter("TrackMinDeltaRFilter",
    tracks    = cms.InputTag("ZtoProbeTrkTrackSelections", "probeTracks"),
    objects   = cms.InputTag("randomElectron"),
    minDeltaR = cms.double(0.1),
)

process.mypath = cms.Path(
    process.hltFilter
    process.selectedElectrons
    process.randomElectron
    process.BasicSelection
    process.JvmAppliedEventFilter
    process.ZtoProbeTrkTrackSelections
    process.TrackElectronDeltaRFilter
)
