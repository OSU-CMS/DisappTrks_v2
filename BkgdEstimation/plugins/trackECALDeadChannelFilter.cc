// ─────────────────────────────────────────────────────────────────────────────
// TrackEcalDeadChannelFilter.cc  —  EDFilter + Producer
//
// Accepts events with at least one isolated track whose minimum dR to any
// masked ECAL channel exceeds minDeltaR (default 0.05), and puts a filtered
// collection of those passing tracks into the event under the instance label
// "ecalTracks".
//
// Downstream filters should consume:
//   cms.InputTag("TrackEcalDeadChannelFilter", "ecalTracks")
//
// The masked channel map is rebuilt each run from the conditions database,
// replicating OSUGenericTrackProducer::getChannelStatusMaps exactly:
//
//   • Loop over all EB (ieta, iphi) and EE (ix, iy, iz) DetIds.
//   • Look up each channel's status code from EcalChannelStatus.
//   • If status & 0x1F >= maskedEcalChannelStatusThreshold, record the
//     channel's (eta, phi) position from CaloGeometry.
//
// Configuration
// ─────────────
//   tracks                          — InputTag for pat::IsolatedTrack collection
//   maskedEcalChannelStatusThreshold — int, minimum status code to mask (default 3)
//   minDeltaR                       — double, minimum dR to masked channel (default 0.05)
//   generatorWeights                — optional GenEventInfoProduct tag (MC only)
// ─────────────────────────────────────────────────────────────────────────────

#include <cmath>
#include <map>
#include <memory>
#include <vector>

#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/DetId/interface/DetId.h"
#include "DataFormats/EcalDetId/interface/EBDetId.h"
#include "DataFormats/EcalDetId/interface/EEDetId.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/Run.h"
#include "FWCore/Framework/interface/one/EDFilter.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "Geometry/CaloGeometry/interface/CaloGeometry.h"
#include "Geometry/CaloGeometry/interface/CaloSubdetectorGeometry.h"
#include "Geometry/CaloGeometry/interface/CaloCellGeometry.h"
#include "Geometry/Records/interface/CaloGeometryRecord.h"
#include "SimDataFormats/GeneratorProducts/interface/GenEventInfoProduct.h"
#include "CondFormats/EcalObjects/interface/EcalChannelStatus.h"
#include "CondFormats/DataRecord/interface/EcalChannelStatusRcd.h"
#include "TH1D.h"

// ─────────────────────────────────────────────────────────────────────────────
class TrackEcalDeadChannelFilter
    : public edm::one::EDFilter<edm::one::SharedResources,
                                edm::one::WatchRuns> {
public:
  explicit TrackEcalDeadChannelFilter(const edm::ParameterSet&);
  static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
  void beginRun(const edm::Run&, const edm::EventSetup&) override;
  void endRun  (const edm::Run&, const edm::EventSetup&) override {}
  bool filter  (edm::Event&,     const edm::EventSetup&) override;

  double minDRToMaskedChannel(const pat::IsolatedTrack& track) const;

  // ── Tokens ─────────────────────────────────────────────────────────────────
  const edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> tracksToken_;
  edm::EDGetTokenT<GenEventInfoProduct>                   genWeightToken_;
  const bool                                              useGenWeights_;

  // ── EventSetup tokens (BeginRun) ───────────────────────────────────────────
  const edm::ESGetToken<CaloGeometry,      CaloGeometryRecord>   caloGeometryToken_;
  const edm::ESGetToken<EcalChannelStatus, EcalChannelStatusRcd> ecalStatusToken_;

  // ── Cut parameters ─────────────────────────────────────────────────────────
  const int    maskedEcalChannelStatusThreshold_;
  const double minDeltaR_;

  // ── Per-run masked channel map ─────────────────────────────────────────────
  std::map<DetId, std::pair<double, double>> maskedChannels_;

  // ── Histogram (owned by TFileService) ─────────────────────────────────────
  TH1D* hCutflow_{nullptr};
};

// ─────────────────────────────────────────────────────────────────────────────
TrackEcalDeadChannelFilter::TrackEcalDeadChannelFilter(
    const edm::ParameterSet& iConfig)
    : tracksToken_(consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      useGenWeights_(iConfig.exists("generatorWeights")),
      caloGeometryToken_(esConsumes<edm::Transition::BeginRun>()),
      ecalStatusToken_  (esConsumes<edm::Transition::BeginRun>()),
      maskedEcalChannelStatusThreshold_(
          iConfig.getParameter<int>("maskedEcalChannelStatusThreshold")),
      minDeltaR_(iConfig.getParameter<double>("minDeltaR")) {
  usesResource("TFileService");

  // Declare the output collection under the instance label "ecalTracks".
  // Downstream filters consume cms.InputTag("TrackEcalDeadChannelFilter", "ecalTracks").
  produces<std::vector<pat::IsolatedTrack>>("ecalTracks");

  if (useGenWeights_)
    genWeightToken_ = consumes<GenEventInfoProduct>(
        iConfig.getParameter<edm::InputTag>("generatorWeights"));

  edm::Service<TFileService> fs;
  hCutflow_ = fs->make<TH1D>(
      "cutflow_TrackEcalDeadChannelFilter",
      "TrackEcalDeadChannelFilter;Cut;Events",
      2, 0.5, 2.5);
  hCutflow_->Sumw2();
  hCutflow_->GetXaxis()->SetBinLabel(1, "Reached");
  hCutflow_->GetXaxis()->SetBinLabel(2, "Passed");
}

// ─────────────────────────────────────────────────────────────────────────────
void TrackEcalDeadChannelFilter::beginRun(const edm::Run&,
                                           const edm::EventSetup& iSetup) {
  maskedChannels_.clear();

  const auto& caloGeometry = iSetup.getData(caloGeometryToken_);
  const auto& ecalStatus   = iSetup.getData(ecalStatusToken_);

  // ── EB channels ────────────────────────────────────────────────────────────
  for (int ieta = -85; ieta <= 85; ++ieta) {
    for (int iphi = 0; iphi <= 360; ++iphi) {
      if (!EBDetId::validDetId(ieta, iphi)) continue;

      const EBDetId detid(ieta, iphi, EBDetId::ETAPHIMODE);
      const auto chit = ecalStatus.find(detid);
      const int status = (chit != ecalStatus.end())
          ? chit->getStatusCode() & 0x1F : -1;

      if (status < maskedEcalChannelStatusThreshold_) continue;

      const auto* subGeom  = caloGeometry.getSubdetectorGeometry(detid);
      const auto  cellGeom = subGeom->getGeometry(detid);
      maskedChannels_[detid] = {cellGeom->getPosition().eta(),
                                cellGeom->getPosition().phi()};
    }
  }

  // ── EE channels ────────────────────────────────────────────────────────────
  for (int ix = 0; ix <= 100; ++ix) {
    for (int iy = 0; iy <= 100; ++iy) {
      for (int iz = -1; iz <= 1; iz += 2) {
        if (!EEDetId::validDetId(ix, iy, iz)) continue;

        const EEDetId detid(ix, iy, iz, EEDetId::XYMODE);
        const auto chit = ecalStatus.find(detid);
        const int status = (chit != ecalStatus.end())
            ? chit->getStatusCode() & 0x1F : -1;

        if (status < maskedEcalChannelStatusThreshold_) continue;

        const auto* subGeom  = caloGeometry.getSubdetectorGeometry(detid);
        const auto  cellGeom = subGeom->getGeometry(detid);
        maskedChannels_[detid] = {cellGeom->getPosition().eta(),
                                  cellGeom->getPosition().phi()};
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
double TrackEcalDeadChannelFilter::minDRToMaskedChannel(
    const pat::IsolatedTrack& track) const {
  double minDR = -1.0;
  for (const auto& entry : maskedChannels_) {
    const double dR = reco::deltaR(
        track.eta(), track.phi(),
        entry.second.first, entry.second.second);
    if (minDR < 0.0 || dR < minDR) minDR = dR;
  }
  return minDR;
}

// ─────────────────────────────────────────────────────────────────────────────
bool TrackEcalDeadChannelFilter::filter(edm::Event& iEvent,
                                         const edm::EventSetup&) {
  double w = 1.0;
  if (useGenWeights_) {
    edm::Handle<GenEventInfoProduct> genInfo;
    iEvent.getByToken(genWeightToken_, genInfo);
    if (genInfo.isValid()) w = genInfo->weight();
  }

  edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
  iEvent.getByToken(tracksToken_, tracks);

  hCutflow_->Fill(1, w);  // Reached

  auto ecalTracks = std::make_unique<std::vector<pat::IsolatedTrack>>();

  for (const auto& track : *tracks) {
    const double minDR = minDRToMaskedChannel(track);

    // minDR < 0 means no masked channels exist — treat as passing.
    if (minDR >= 0.0 && minDR <= minDeltaR_) continue;

    ecalTracks->push_back(track);
  }

  const bool pass = !ecalTracks->empty();
  if (pass) hCutflow_->Fill(2, w);  // Passed

  // Always put the collection so downstream modules can consume unconditionally.
  iEvent.put(std::move(ecalTracks), "ecalTracks");

  return true;
}

// ─────────────────────────────────────────────────────────────────────────────
void TrackEcalDeadChannelFilter::fillDescriptions(
    edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;

  desc.add<edm::InputTag>("tracks", edm::InputTag("isolatedTracks"));
  desc.add<int>("maskedEcalChannelStatusThreshold", 3);
  desc.add<double>("minDeltaR", 0.05);
  desc.addOptional<edm::InputTag>("generatorWeights", edm::InputTag("generator"));

  descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(TrackEcalDeadChannelFilter);
