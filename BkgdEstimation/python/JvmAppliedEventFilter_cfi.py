
import FWCore.ParameterSet.Config as cms

JvmAppliedEventFilter = cms.EDFilter(
    "JvmAppliedEventFilter",
    Jets = cms.PSet(
        SourcesAK4 = cms.InputTag("slimmedJetsPuppi"),
        Year    = cms.string("2024"),
        JvmConfig = cms.FileInPath("DisappTrks_v2/data/JvmConfig.json"),
    )
    
)
