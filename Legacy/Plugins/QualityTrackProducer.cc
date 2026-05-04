#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"

// Produces a quality track collection (qualityTracks) from pat::IsolatedTracks
// requiring: pT > minPt, >= minPixelHits pixel hits, 0 missing inner/middle hits,
// relative PF isolation < maxRelIso, |dxy| < maxDxy, |dz| < maxDz.
// Expects fiducially filtered tracks as input (e.g. from TrackFiducialFilter).
class QualityTrackProducer : public edm::stream::EDProducer<> {
public:
    explicit QualityTrackProducer(const edm::ParameterSet&);
    ~QualityTrackProducer() override = default;
    static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
    void produce(edm::Event&, const edm::EventSetup&) override;

    const edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;

    const double minPt_;
    const int    minPixelHits_;
    const double maxRelIso_;
    const double maxDxy_;
    const double maxDz_;
};

QualityTrackProducer::QualityTrackProducer(const edm::ParameterSet& iConfig)
    : trackToken_   (consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      minPt_        (iConfig.getParameter<double>("minPt")),
      minPixelHits_ (iConfig.getParameter<int>   ("minPixelHits")),
      maxRelIso_    (iConfig.getParameter<double>("maxRelIso")),
      maxDxy_       (iConfig.getParameter<double>("maxDxy")),
      maxDz_        (iConfig.getParameter<double>("maxDz"))
{
    produces<std::vector<pat::IsolatedTrack>>("qualityTracks");
}

void QualityTrackProducer::produce(edm::Event& iEvent, const edm::EventSetup&) {
    auto qualityTracks = std::make_unique<std::vector<pat::IsolatedTrack>>();

    edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
    iEvent.getByToken(trackToken_, tracks);

    for (const auto& track : *tracks) {
        if (track.pt() <= minPt_) continue;
        if (track.hitPattern().numberOfValidPixelHits() < minPixelHits_) continue;
        if (track.hitPattern().trackerLayersWithoutMeasurement(
                reco::HitPattern::MISSING_INNER_HITS) != 0) continue;
        if (track.hitPattern().trackerLayersWithoutMeasurement(
                reco::HitPattern::TRACK_HITS) != 0) continue;
        if (track.pfIsolationDR03().chargedHadronIso() / track.pt() >= maxRelIso_) continue;
        if (std::abs(track.dxy()) >= maxDxy_) continue;
        if (std::abs(track.dz())  >= maxDz_)  continue;
        qualityTracks->push_back(track);
    }

    iEvent.put(std::move(qualityTracks), "qualityTracks");
}

void QualityTrackProducer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("tracks",       edm::InputTag("isolatedTracks"));
    desc.add<double>       ("minPt",        20.0);
    desc.add<int>          ("minPixelHits", 4);
    desc.add<double>       ("maxRelIso",    0.05);
    desc.add<double>       ("maxDxy",       0.02);
    desc.add<double>       ("maxDz",        0.5);
    descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(QualityTrackProducer);
