import FWCore.ParameterSet.Config as cms

BasicSelection = cms.EDFilter("BasicSelection",
    jets = cms.InputTag("slimmedJetsPuppi"),
    minJetPt = cms.double(110.0),
    maxEta = cms.double(2.4),
    maxJetJetDeltaPhi = cms.double(2.5),
)
