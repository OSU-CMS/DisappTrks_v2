// -*- C++ -*-
//
// Package:    DisappTrks/TagAndProbe
// Class:      TrackLayerFilter
//
/**\class TrackLayerFilter TrackLayerFilter.cc DisappTrks/TagAndProbe/plugins/TrackLayerFilter.cc

 Description: Selects events containing at least one isolated track with
              a number of tracker layers with hits >= minLayers.
*/

#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/stream/EDFilter.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/Utilities/interface/StreamID.h"

#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"

class TrackLayerFilter : public edm::stream::EDFilter<> {
public:
    explicit TrackLayerFilter(const edm::ParameterSet&);
    ~TrackLayerFilter() override = default;
    static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
    void beginStream(edm::StreamID) override {}
    bool filter(edm::Event&, const edm::EventSetup&) override;
    void endStream() override {}

    edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;
    const int minLayers_;
};

TrackLayerFilter::TrackLayerFilter(const edm::ParameterSet& iConfig)
    : trackToken_(consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      minLayers_(iConfig.getParameter<int>("minLayers")) {}

bool TrackLayerFilter::filter(edm::Event& iEvent, const edm::EventSetup& iSetup) {
    edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
    iEvent.getByToken(trackToken_, tracks);

    for (const auto& track : *tracks) {
    edm::LogPrint("TrackLayerFilter") 
        << "track pt=" << track.pt() 
        << " layers=" << track.hitPattern().trackerLayersWithMeasurement();

        if (track.hitPattern().trackerLayersWithMeasurement() == minLayers_)
            return true;
    }
    return false;
}

void TrackLayerFilter::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("tracks",    edm::InputTag("isolatedTracks"));
    desc.add<int>          ("minLayers", 4);
    descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(TrackLayerFilter);


