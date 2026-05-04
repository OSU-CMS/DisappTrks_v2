#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "DataFormats/PatCandidates/interface/Jet.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "TH1D.h"
#include <limits>

class TrackDRMinJetAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
    explicit TrackDRMinJetAnalyzer(const edm::ParameterSet& iConfig)
        : trackToken_(consumes<std::vector<pat::IsolatedTrack>>(iConfig.getParameter<edm::InputTag>("tracks"))),
          jetToken_  (consumes<std::vector<pat::Jet>>          (iConfig.getParameter<edm::InputTag>("jets")))
    {
        usesResource("TFileService");
        edm::Service<TFileService> fs;
        hDRMinJet_ = fs->make<TH1D>("dRMinJetFinalTracks",
            "dRMinJet for final passing tracks;dR_{min}(trk,jet);tracks",
            100, 0.0, 5.0);
    }
    void analyze(const edm::Event& iEvent, const edm::EventSetup&) override {
        edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
        edm::Handle<std::vector<pat::Jet>> jets;
        iEvent.getByToken(trackToken_, tracks);
        iEvent.getByToken(jetToken_,   jets);
        for (const auto& track : *tracks) {
            double minDR = std::numeric_limits<double>::max();
            for (const auto& jet : *jets) {
                if (jet.pt() <= 30.0 || std::abs(jet.eta()) >= 4.5) continue;
                minDR = std::min(minDR, reco::deltaR(track, jet));
            }
            hDRMinJet_->Fill(minDR == std::numeric_limits<double>::max() ? 99.0 : minDR);
        }
    }
private:
    edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;
    edm::EDGetTokenT<std::vector<pat::Jet>>           jetToken_;
    TH1D* hDRMinJet_;
};
DEFINE_FWK_MODULE(TrackDRMinJetAnalyzer);
