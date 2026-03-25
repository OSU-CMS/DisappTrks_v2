#!/usr/bin/env python3
process.TagProbe = cms.EDFilter('TagAndProbe',
                                tracks = cms.InputTag("IsolatedTracks"),
                                muons = cms.InputTag("slimmedMuons"),
                                electrons = cms.InputTag("slimmedElectrons"),
                                minPt = cms.double(30.0)
                                )
