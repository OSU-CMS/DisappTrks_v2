/*
Filter to apply criteria needed to form the Isolated Track Selection which is
defined by:

>= 1 tracks pT > 55GeV
>= 1 tracks passing fiducial selections
>= 1 tracks with number of pixel hits >= 4
>= 1 tracks with number of missing inner hits = 0
>= 1 tracks with number of missing middle hits = 0
>= 1 tracks with relative PF-based isolation < 0.05
>= 1 tracks with |dxy| < 0.02cm WRT primary vertex
>= 1 tracks with |dz| < 0.5cm WRT primary vertex
>= 1 track-jet pairs deltaR (track, jet) > 0.5
 */

#include "IsolatedTrack.h"

class IsolatedTrack : public edm::stream::EDFilter<> {
public:
  explicit IsolatedTrack(const edm::ParameterSet &);
  ~IsolatedTrack() override = default;
  static void fillDescriptions(edm::ConfigurationDescriptions &);

private:
  bool filter(edm::Event &, const edm::EventSetup &) override;

  edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;

  const double minPt_;
  const double maxIso_;
  const double maxD0_;
  const double maxDZ_;
  const double minDR_;
};

IsolatedTrack::IsolatedTrack(const edm::ParameterSet &)
    : trackToken_(consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      minPt_(iConfig.getParameter<double>("minPt")),
      maxIso_(iConfig.getParameter<double>("maxIso")),
      maxD0_(iConfig.getParameter<double>("maxD0")),
      maxDZ_(iConfig.getParameter<double>("maxDZ")),
      minDR_(iConfig.getParameter<double>("minDR")) {
  produces<std::vector<pat::IsolatedTrack>>("IsolatedTracks");
}

bool IsolatedTrack::filter(edm::Event &, const edm::EventSetup &iSetup) {
  edm::Handle<std::vector<pat::IsolatedTrack>> tracks;

  iEvent.getByToken(trackToken_, tracks);

  for (const auto &track : *tracks) {
    if (track.pt <= minPt_)
      continue;
    if (track.hitPattern().numberOfValidPixelHits() < 4)
      continue;
    // TODO Should replace with what is listed in AN (lostInnerLayers() and
    // lostOuterLayers())
    if (track.hitPattern().trackerLayersWithoutMeasurement(
            reco::HitPattern::MISSING_INNER_HITS) != 0)
      continue;
    if (track.hitPattern().trackerLayersWithoutMeasurement(
            reco::HitPattern::TRACK_HITS) != 0)
      continue;
    if (track.pfIsolationDR03().chargedHadronIso() / track.pt() >= maxIso)
      continue;
    if (std::abs(track.dxy()) >= maxD0)
      continue;
    if (std::abs(track.dz()) >= maxDZ)
      continue;

    // TODO Include track, jet DR cut
  }
}
