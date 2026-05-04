// ─────────────────────────────────────────────────────────────────────────────
// TrackDeltaRJetFilter.cc  —  EDFilter
//
// Accepts events with at least one isolated track whose dR to the nearest
// good jet exceeds minDeltaR (default 0.5).
//
// A jet is considered "good" if it passes:
//   pt > minJetPt    (default 30 GeV)
//   |eta| < maxJetEta  (default 4.5)
//   PFJetIDSelectionFunctor with TIGHTLEPVETO quality
//
// This replicates the dRMinJet calculation in OSUGenericTrackProducer::getTrackInfo.
//
// If no good jets exist in the event, minDR is set to -1 and the track is
// considered to pass (consistent with legacy behaviour where dRMinJet = -1
// is initialised and only updated when a good jet is found).
//
// Configuration
// ─────────────
//   tracks      — InputTag for pat::IsolatedTrack collection
//   jets        — InputTag for pat::Jet collection
//   minDeltaR   — double, minimum dR track must have to nearest good jet (default 0.5)
//   minJetPt    — double, minimum jet pT in GeV (default 30)
//   maxJetEta   — double, maximum |eta| for jets (default 4.5)
//   jetIdVersion — string, PFJetIDSelectionFunctor version (default "RUN3CHSruns2022FGruns2023CD")
//   generatorWeights — optional GenEventInfoProduct tag (MC only)
// ─────────────────────────────────────────────────────────────────────────────

#include <cmath>
#include <string>
#include <vector>

#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "DataFormats/PatCandidates/interface/Jet.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDFilter.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "PhysicsTools/SelectorUtils/interface/PFJetIDSelectionFunctor.h"
#include "SimDataFormats/GeneratorProducts/interface/GenEventInfoProduct.h"
#include "TH1D.h"

// ─────────────────────────────────────────────────────────────────────────────
class TrackDeltaRJetFilter
    : public edm::one::EDFilter<edm::one::SharedResources> {
public:
  explicit TrackDeltaRJetFilter(const edm::ParameterSet&);
  static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
  bool filter(edm::Event&, const edm::EventSetup&) override;

  // ── Tokens ─────────────────────────────────────────────────────────────────
  const edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> tracksToken_;
  const edm::EDGetTokenT<std::vector<pat::Jet>>           jetsToken_;
  edm::EDGetTokenT<GenEventInfoProduct>                   genWeightToken_;
  const bool                                              useGenWeights_;

  // ── Jet ID functor ─────────────────────────────────────────────────────────
  PFJetIDSelectionFunctor jetIdSelector_;

  // ── Cut parameters ─────────────────────────────────────────────────────────
  const double minDeltaR_;
  const double minJetPt_;
  const double maxJetEta_;

  // ── Histogram (owned by TFileService) ─────────────────────────────────────
  TH1D* hCutflow_{nullptr};
};

// ─────────────────────────────────────────────────────────────────────────────
TrackDeltaRJetFilter::TrackDeltaRJetFilter(const edm::ParameterSet& iConfig)
    : tracksToken_(consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      jetsToken_(consumes<std::vector<pat::Jet>>(
          iConfig.getParameter<edm::InputTag>("jets"))),
      useGenWeights_(iConfig.exists("generatorWeights")),
      jetIdSelector_(edm::ParameterSet([&]() {
        // Build the PSet that PFJetIDSelectionFunctor expects:
        //   version  — the jet ID era string
        //   quality  — always TIGHTLEPVETO to match legacy anatools::jetPassesTightLepVeto
        edm::ParameterSet ps;
        ps.addParameter<std::string>(
            "version", iConfig.getParameter<std::string>("jetIdVersion"));
        ps.addParameter<std::string>("quality", "TIGHTLEPVETO");
        return ps;
      }())),
      minDeltaR_(iConfig.getParameter<double>("minDeltaR")),
      minJetPt_  (iConfig.getParameter<double>("minJetPt")),
      maxJetEta_ (iConfig.getParameter<double>("maxJetEta")) {
  usesResource("TFileService");

  if (useGenWeights_)
    genWeightToken_ = consumes<GenEventInfoProduct>(
        iConfig.getParameter<edm::InputTag>("generatorWeights"));

  edm::Service<TFileService> fs;
  hCutflow_ = fs->make<TH1D>(
      "cutflow_TrackDeltaRJetFilter",
      "TrackDeltaRJetFilter;Cut;Events",
      2, 0.5, 2.5);
  hCutflow_->Sumw2();
  hCutflow_->GetXaxis()->SetBinLabel(1, "Reached");
  hCutflow_->GetXaxis()->SetBinLabel(2, "Passed");
}

// ─────────────────────────────────────────────────────────────────────────────
bool TrackDeltaRJetFilter::filter(edm::Event& iEvent,
                                   const edm::EventSetup&) {
  double w = 1.0;
  if (useGenWeights_) {
    edm::Handle<GenEventInfoProduct> genInfo;
    iEvent.getByToken(genWeightToken_, genInfo);
    if (genInfo.isValid()) w = genInfo->weight();
  }

  edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
  iEvent.getByToken(tracksToken_, tracks);

  edm::Handle<std::vector<pat::Jet>> jets;
  iEvent.getByToken(jetsToken_, jets);

  hCutflow_->Fill(1, w);  // Reached

  // Pre-select good jets once per event so the inner track loop is cheap.
  // A jet is good if it passes pt, eta, and tight lepton veto ID.
  // Replicates the condition in OSUGenericTrackProducer::getTrackInfo:
  //   jet.pt() > 30 && fabs(jet.eta()) < 4.5 && jetPassesTightLepVeto(jet)
  std::vector<const pat::Jet*> goodJets;
  for (const auto& jet : *jets) {
    if (jet.pt()           <= minJetPt_)  continue;
    if (std::abs(jet.eta()) >= maxJetEta_) continue;
    if (!jetIdSelector_(jet))             continue;
    goodJets.push_back(&jet);
  }

  for (const auto& track : *tracks) {
    // Compute dR to nearest good jet — initialise to -1 as in legacy code.
    double dRMinJet = -1.0;
    for (const auto* jet : goodJets) {
      const double dR = reco::deltaR(track, *jet);
      if (dRMinJet < 0.0 || dR < dRMinJet) dRMinJet = dR;
    }

    // If no good jets exist (dRMinJet == -1) the track passes,
    // consistent with the legacy isProbeTrack check: fabs(dRMinJet) <= 0.5
    // which would be fabs(-1) = 1.0 > 0.5, so it passes.
    if (dRMinJet >= 0.0 && dRMinJet <= minDeltaR_) continue;

    hCutflow_->Fill(2, w);  // Passed
    return true;
  }

  return false;
}

// ─────────────────────────────────────────────────────────────────────────────
void TrackDeltaRJetFilter::fillDescriptions(
    edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;

  desc.add<edm::InputTag>("tracks", edm::InputTag("isolatedTracks"));
  desc.add<edm::InputTag>("jets",   edm::InputTag("slimmedJets"));

  desc.add<double>("minDeltaR",  0.5)
      ->setComment("Minimum dR between track and nearest good jet.");
  desc.add<double>("minJetPt",  30.0)
      ->setComment("Minimum jet pT in GeV.");
  desc.add<double>("maxJetEta",  4.5)
      ->setComment("Maximum |eta| for jets.");

  desc.add<std::string>("jetIdVersion", "RUN3CHSruns2022FGruns2023CD")
      ->setComment(
          "PFJetIDSelectionFunctor version string.  "
          "Quality is always TIGHTLEPVETO to match the legacy "
          "anatools::jetPassesTightLepVeto behaviour.");

  desc.addOptional<edm::InputTag>("generatorWeights", edm::InputTag("generator"))
      ->setComment("GenEventInfoProduct tag.  Omit for data (weight defaults to 1.0).");

  descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(TrackDeltaRJetFilter);


