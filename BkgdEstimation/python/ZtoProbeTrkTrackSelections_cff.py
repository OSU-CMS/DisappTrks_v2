#!/usr/bin/env python3
import FWCore.ParameterSet.Config as cms

ZtoProbeTrkTrackSelections = cms.EDFilter("ZtoProbeTrkTrackSelections",
    tracks       = cms.InputTag("isolatedTracks"),
    muons        = cms.InputTag("slimmedMuons"),
    electrons    = cms.InputTag("slimmedElectrons"),
    jets         = cms.InputTag("slimmedJetsPuppi"),   # CHS jets — matches old framework
    minPt        = cms.double(30),
    minLayers    = cms.int32(4),
    useExclusive = cms.bool(False),
    minDeltaRJet = cms.double(0.5),
    instanceLabel = cms.string("ZtoProbeTrkTrackSelections")
)
