#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "TH1F.h"

class TrackCutAnalyzer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
    explicit TrackCutAnalyzer(const edm::ParameterSet&);
    static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
    void analyze(const edm::Event&, const edm::EventSetup&) override;
    void beginJob() override;

    edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;
    edm::EDGetTokenT<std::vector<pat::Muon>>          muonToken_;
    edm::EDGetTokenT<std::vector<pat::Electron>>      electronToken_;

    TH1F* hPt_;
    TH1F* hRelIso_;
    TH1F* hDxy_;
    TH1F* hDz_;
    TH1F* hNPixelHits_;
    TH1F* hNMissingInnerHits_;
    TH1F* hNMissingMiddleHits_;
    TH1F* hNMissingOuterHits_;
    TH1F* hMinDeltaR_;
};

TrackCutAnalyzer::TrackCutAnalyzer(const edm::ParameterSet& iConfig)
    : trackToken_   (consumes<std::vector<pat::IsolatedTrack>>(iConfig.getParameter<edm::InputTag>("tracks"))),
      muonToken_    (consumes<std::vector<pat::Muon>>         (iConfig.getParameter<edm::InputTag>("muons"))),
      electronToken_(consumes<std::vector<pat::Electron>>     (iConfig.getParameter<edm::InputTag>("electrons")))
{
    usesResource("TFileService");
}

void TrackCutAnalyzer::beginJob() {
    edm::Service<TFileService> fs;
    hPt_                  = fs->make<TH1F>("hPt",                 "Track p_{T};p_{T} [GeV];Entries",          100, 0,    500);
    hRelIso_              = fs->make<TH1F>("hRelIso",             "Relative isolation;Rel. iso;Entries",       100, 0,    1  );
    hDxy_                 = fs->make<TH1F>("hDxy",                "Track d_{xy};d_{xy} [cm];Entries",          100, 0,    0.1);
    hDz_                  = fs->make<TH1F>("hDz",                 "Track d_{z};d_{z} [cm];Entries",            100, 0,    1  );
    hNPixelHits_          = fs->make<TH1F>("hNPixelHits",         "Valid pixel hits;N hits;Entries",            15, 0,    15 );
    hNMissingInnerHits_   = fs->make<TH1F>("hNMissingInnerHits",  "Missing inner hits;N hits;Entries",          10, 0,    10 );
    hNMissingMiddleHits_  = fs->make<TH1F>("hNMissingMiddleHits", "Missing middle hits;N hits;Entries",         10, 0,    10 );
    hNMissingOuterHits_   = fs->make<TH1F>("hNMissingOuterHits",  "Missing outer hits;N hits;Entries",          15, 0,    15 );
    hMinDeltaR_           = fs->make<TH1F>("hMinDeltaR",          "Min #DeltaR(track, lepton);#DeltaR;Entries", 60, 0,    6  );
}

void TrackCutAnalyzer::analyze(const edm::Event& iEvent, const edm::EventSetup& iSetup) {
    edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
    edm::Handle<std::vector<pat::Muon>>          muons;
    edm::Handle<std::vector<pat::Electron>>      electrons;
    iEvent.getByToken(trackToken_,    tracks);
    iEvent.getByToken(muonToken_,     muons);
    iEvent.getByToken(electronToken_, electrons);

    for (const auto& track : *tracks) {
        double minDR = 999.;
        for (const auto& muon     : *muons)     minDR = std::min(minDR, reco::deltaR(track, muon));
        for (const auto& electron : *electrons) minDR = std::min(minDR, reco::deltaR(track, electron));

        double relIso = track.pfIsolationDR03().chargedHadronIso() / track.pt();

        hPt_                ->Fill(track.pt());
        hRelIso_            ->Fill(relIso);
        hDxy_               ->Fill(std::abs(track.dxy()));
        hDz_                ->Fill(std::abs(track.dz()));
        hNPixelHits_        ->Fill(track.hitPattern().numberOfValidPixelHits());
        hNMissingInnerHits_ ->Fill(track.hitPattern().numberOfLostHits(reco::HitPattern::MISSING_INNER_HITS));
        hNMissingMiddleHits_->Fill(track.hitPattern().numberOfLostHits(reco::HitPattern::TRACK_HITS));
        hNMissingOuterHits_ ->Fill(track.hitPattern().numberOfLostHits(reco::HitPattern::MISSING_OUTER_HITS));
        hMinDeltaR_         ->Fill(minDR);
    }
}

void TrackCutAnalyzer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("tracks",    edm::InputTag("isolatedTracks"));
    desc.add<edm::InputTag>("muons",     edm::InputTag("slimmedMuons"));
    desc.add<edm::InputTag>("electrons", edm::InputTag("slimmedElectrons"));
    descriptions.add("trackCutAnalyzer", desc);
}

DEFINE_FWK_MODULE(TrackCutAnalyzer);
