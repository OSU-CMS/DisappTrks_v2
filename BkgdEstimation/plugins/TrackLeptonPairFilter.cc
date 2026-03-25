// -*- C++ -*-
//
// Package:    DisappTrks/TagAndProbe
// Class:      TrackLeptonPairFilter
//
/**\class TrackLeptonPairFilter TrackLeptonPairFilter.cc DisappTrks/TagAndProbe/plugins/TrackLeptonPairFilter.cc

 Description: Selects events containing at least one track-lepton pair consistent
              with Z -> ll decay: 15 GeV < MZ - M(track,lepton) < 50 GeV,
              with opposite-sign charges.
*/

#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/stream/EDFilter.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/Utilities/interface/StreamID.h"

#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "DataFormats/Math/interface/LorentzVector.h"

namespace {
    constexpr float kMassZ        = 91.1876f; // PDG Z mass [GeV]
    constexpr float kMassMuon     = 0.10566f;
    constexpr float kMassElectron = 0.000511f;

    math::PtEtaPhiMLorentzVector trackP4UnderHypothesis(const pat::IsolatedTrack& track, float mass) {
        return math::PtEtaPhiMLorentzVector(track.pt(), track.eta(), track.phi(), mass);
    }

    template <typename LeptonType>
    float pairMass(const pat::IsolatedTrack& track, const LeptonType& lepton, float trackMassHypothesis) {
        const auto p4 = trackP4UnderHypothesis(track, trackMassHypothesis) + lepton.p4();
        return p4.mass();
    }

    bool inZWindow(float mass, float lowerCut, float upperCut) {
        const float diff = kMassZ - mass;
        return diff > lowerCut && diff < upperCut;
    }
} // namespace

class TrackLeptonPairFilter : public edm::stream::EDFilter<> {
public:
    explicit TrackLeptonPairFilter(const edm::ParameterSet&);
    ~TrackLeptonPairFilter() override = default;
    static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
    void beginStream(edm::StreamID) override {}
    bool filter(edm::Event&, const edm::EventSetup&) override;
    void endStream() override {}

    edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;
    edm::EDGetTokenT<std::vector<pat::Muon>>          muonToken_;
    edm::EDGetTokenT<std::vector<pat::Electron>>      electronToken_;

    const float lowerCut_; // lower bound on MZ - M(track,lepton)
    const float upperCut_; // upper bound on MZ - M(track,lepton)
};

TrackLeptonPairFilter::TrackLeptonPairFilter(const edm::ParameterSet& iConfig)
    : trackToken_   (consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      muonToken_    (consumes<std::vector<pat::Muon>>(
          iConfig.getParameter<edm::InputTag>("muons"))),
      electronToken_(consumes<std::vector<pat::Electron>>(
          iConfig.getParameter<edm::InputTag>("electrons"))),
      lowerCut_(iConfig.getParameter<double>("lowerCut")),
      upperCut_(iConfig.getParameter<double>("upperCut")) {}

bool TrackLeptonPairFilter::filter(edm::Event& iEvent, const edm::EventSetup& iSetup) {
    edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
    edm::Handle<std::vector<pat::Muon>>          muons;
    edm::Handle<std::vector<pat::Electron>>      electrons;

    iEvent.getByToken(trackToken_,    tracks);
    iEvent.getByToken(muonToken_,     muons);
    iEvent.getByToken(electronToken_, electrons);

    int nPairs = 0;

    for (const auto& track : *tracks) {

        // --- Track-muon pairs ---
        for (const auto& muon : *muons) {
            if (track.charge() + muon.charge() != 0)                                continue;
            if (!inZWindow(pairMass(track, muon, kMassMuon), lowerCut_, upperCut_)) continue;
            ++nPairs;
            if (nPairs > 1) return false; // early exit — can never recover
        }

        // --- Track-electron pairs ---
        for (const auto& electron : *electrons) {
            if (track.charge() + electron.charge() != 0)                                   continue;
            if (!inZWindow(pairMass(track, electron, kMassElectron), lowerCut_, upperCut_)) continue;
            ++nPairs;
            if (nPairs > 1) return false; // early exit — can never recover
        }
    }

    return nPairs == 1;
}

void TrackLeptonPairFilter::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("tracks",    edm::InputTag("isolatedTracks"));
    desc.add<edm::InputTag>("muons",     edm::InputTag("slimmedMuons"));
    desc.add<edm::InputTag>("electrons", edm::InputTag("slimmedElectrons"));
    desc.add<double>       ("lowerCut", 15.0);
    desc.add<double>       ("upperCut", 50.0);
    descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(TrackLeptonPairFilter);


