// ─────────────────────────────────────────────────────────────────────────────
// TrackMinDeltaRFilter.cc  —  EDFilter + Producer
//
// Accepts events with at least one isolated track whose dR to the nearest
// object in a given collection exceeds minDeltaR (default 0.15), and puts
// a filtered collection of those passing tracks into the event under the
// instance label "deltaRTracks".
//
// Downstream filters should consume:
//   cms.InputTag("<moduleLabel>", "deltaRTracks")
//
// Intended to be run as separate instances for muons, taus, and jets:
//
//   process.TrackJetDeltaRFilter = cms.EDFilter("TrackMinDeltaRFilter",
//       tracks    = cms.InputTag("TrackEcalDeadChannelFilter", "ecalTracks"),
//       objects   = cms.InputTag("slimmedJetsPuppi"),
//       minDeltaR = cms.double(0.5),
//   )
//   process.TrackMuonDeltaRFilter = cms.EDFilter("TrackMinDeltaRFilter",
//       tracks    = cms.InputTag("TrackJetDeltaRFilter", "deltaRTracks"),
//       objects   = cms.InputTag("slimmedMuons"),
//       minDeltaR = cms.double(0.15),
//   )
//   process.TrackTauDeltaRFilter = cms.EDFilter("TrackMinDeltaRFilter",
//       tracks    = cms.InputTag("TrackMuonDeltaRFilter", "deltaRTracks"),
//       objects   = cms.InputTag("selectedTaus"),
//       minDeltaR = cms.double(0.15),
//   )
//
// The histogram name is derived from the module label so each instance
// produces a distinct histogram.
//
// Configuration
// ─────────────
//   tracks           — InputTag for pat::IsolatedTrack collection
//   objects          — InputTag for object collection (edm::View<reco::Candidate>)
//   minDeltaR        — double, minimum dR to nearest object (default 0.15)
//   generatorWeights — optional GenEventInfoProduct tag (MC only)
// ─────────────────────────────────────────────────────────────────────────────

#include <cmath>
#include <memory>
#include <string>
#include <vector>

#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/Candidate/interface/Candidate.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDFilter.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "SimDataFormats/GeneratorProducts/interface/GenEventInfoProduct.h"
#include "TH1D.h"

// ─────────────────────────────────────────────────────────────────────────────
class TrackMinDeltaRFilter
    : public edm::one::EDFilter<edm::one::SharedResources> {
public:
  explicit TrackMinDeltaRFilter(const edm::ParameterSet&);
  static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
  bool filter(edm::Event&, const edm::EventSetup&) override;

  // ── Tokens ─────────────────────────────────────────────────────────────────
  const edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> tracksToken_;
  const edm::EDGetTokenT<edm::View<reco::Candidate>>      objectsToken_;
  edm::EDGetTokenT<GenEventInfoProduct>                   genWeightToken_;
  const bool                                              useGenWeights_;

  // ── Cut parameters ─────────────────────────────────────────────────────────
  const double minDeltaR_;

  // ── Histogram (owned by TFileService) ─────────────────────────────────────
  TH1D* hCutflow_{nullptr};
};

// ─────────────────────────────────────────────────────────────────────────────
TrackMinDeltaRFilter::TrackMinDeltaRFilter(
    const edm::ParameterSet& iConfig)
    : tracksToken_(consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      objectsToken_(consumes<edm::View<reco::Candidate>>(
          iConfig.getParameter<edm::InputTag>("objects"))),
      useGenWeights_(iConfig.exists("generatorWeights")),
      minDeltaR_(iConfig.getParameter<double>("minDeltaR")) {
  usesResource("TFileService");

  // Declare the output collection under the instance label "deltaRTracks".
  // Downstream filters consume cms.InputTag("<moduleLabel>", "deltaRTracks").
  produces<std::vector<pat::IsolatedTrack>>("deltaRTracks");

  if (useGenWeights_)
    genWeightToken_ = consumes<GenEventInfoProduct>(
        iConfig.getParameter<edm::InputTag>("generatorWeights"));

  const std::string label =
      iConfig.getParameter<std::string>("@module_label");

  edm::Service<TFileService> fs;
  hCutflow_ = fs->make<TH1D>(
      ("cutflow_" + label).c_str(),
      (label + ";Cut;Events").c_str(),
      2, 0.5, 2.5);
  hCutflow_->Sumw2();
  hCutflow_->GetXaxis()->SetBinLabel(1, "Reached");
  hCutflow_->GetXaxis()->SetBinLabel(2, "Passed");
}

// ─────────────────────────────────────────────────────────────────────────────
bool TrackMinDeltaRFilter::filter(edm::Event& iEvent,
                                      const edm::EventSetup&) {
  double w = 1.0;
  if (useGenWeights_) {
    edm::Handle<GenEventInfoProduct> genInfo;
    iEvent.getByToken(genWeightToken_, genInfo);
    if (genInfo.isValid()) w = genInfo->weight();
  }

  edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
  iEvent.getByToken(tracksToken_, tracks);

  edm::Handle<edm::View<reco::Candidate>> objects;
  iEvent.getByToken(objectsToken_, objects);

  hCutflow_->Fill(1, w);  // Reached

  auto deltaRTracks = std::make_unique<std::vector<pat::IsolatedTrack>>();

  for (const auto& track : *tracks) {
    double minDR = -1.0;
    for (const auto& object : *objects) {
      const double dR = reco::deltaR(track, object);
      if (minDR < 0.0 || dR < minDR) minDR = dR;
    }

    // No objects in the event — track passes by definition.
    if (minDR >= 0.0 && minDR <= minDeltaR_) continue;

    deltaRTracks->push_back(track);
  }

  const bool pass = !deltaRTracks->empty();
  if (pass) hCutflow_->Fill(2, w);  // Passed

  // Always put the collection so downstream modules can consume unconditionally.
  iEvent.put(std::move(deltaRTracks), "deltaRTracks");

  return pass;
}

// ─────────────────────────────────────────────────────────────────────────────
void TrackMinDeltaRFilter::fillDescriptions(
    edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;

  desc.add<edm::InputTag>("tracks",  edm::InputTag("isolatedTracks"));
  desc.add<edm::InputTag>("objects", edm::InputTag("slimmedMuons"))
      ->setComment(
          "Object collection to compute dR against. "
          "Use slimmedMuons, selectedTaus, or slimmedJetsPuppi depending on instance.");
  desc.add<double>("minDeltaR", 0.15)
      ->setComment("Minimum dR between track and nearest object.");
  desc.addOptional<edm::InputTag>("generatorWeights", edm::InputTag("generator"))
      ->setComment("GenEventInfoProduct tag. Omit for data (weight defaults to 1.0).");

  descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(TrackMinDeltaRFilter);
