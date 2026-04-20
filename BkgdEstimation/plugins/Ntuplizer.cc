// ── Includes ─────────────────────────────────────────────────────────────────
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"

// PAT objects
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "DataFormats/PatCandidates/interface/Jet.h"
#include "DataFormats/PatCandidates/interface/MET.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Tau.h"

// Math utilities
#include "DataFormats/Math/interface/deltaPhi.h"
#include "DataFormats/Math/interface/deltaR.h"

// ROOT
#include "TTree.h"

#include <cmath>
#include <string>
#include <vector>

// ── Branch-group helpers
// ──────────────────────────────────────────────────────
namespace {

struct LepKin {
  std::vector<float> pt, eta, phi;
  std::vector<int> charge;

  void book(TTree *t, const std::string &pfx) {
    t->Branch((pfx + "_pt").c_str(), &pt);
    t->Branch((pfx + "_eta").c_str(), &eta);
    t->Branch((pfx + "_phi").c_str(), &phi);
    t->Branch((pfx + "_charge").c_str(), &charge);
  }
  void clear() {
    pt.clear();
    eta.clear();
    phi.clear();
    charge.clear();
  }
};

struct LepKinMinimal {
  std::vector<float> pt, eta, phi;
  std::vector<int> charge;

  void book(TTree *t, const std::string &pfx) {
    t->Branch((pfx + "_pt").c_str(), &pt);
    t->Branch((pfx + "_eta").c_str(), &eta);
    t->Branch((pfx + "_phi").c_str(), &phi);
    t->Branch((pfx + "_charge").c_str(), &charge);
  }
  void clear() {
    pt.clear();
    eta.clear();
    phi.clear();
    charge.clear();
  }
};

struct TrkBranches {
  // kinematics
  std::vector<float> pt, eta, phi, dxy, dz;
  std::vector<int> charge;
  // hit pattern
  std::vector<int> nHits, nPixelHits, missingOuterHits, missingMiddleHits,
      missingInnerHits;
  // isolation
  std::vector<float> pfIso, relativePFIso;
  // calo
  std::vector<float> caloEm, caloHad, caloTotal;
  // derived
  std::vector<float> dPhiMet, dPhiMetNoMu, ptOverMetNoMu;

  void book(TTree *t, const std::string &pfx) {
    t->Branch((pfx + "_pt").c_str(), &pt);
    t->Branch((pfx + "_eta").c_str(), &eta);
    t->Branch((pfx + "_phi").c_str(), &phi);
    t->Branch((pfx + "_dxy").c_str(), &dxy);
    t->Branch((pfx + "_dz").c_str(), &dz);
    t->Branch((pfx + "_charge").c_str(), &charge);
    t->Branch((pfx + "_nHits").c_str(), &nHits);
    t->Branch((pfx + "_nPixelHits").c_str(), &nPixelHits);
    t->Branch((pfx + "_missingOuterHits").c_str(), &missingOuterHits);
    t->Branch((pfx + "_missingMiddleHits").c_str(), &missingMiddleHits);
    t->Branch((pfx + "_missingInnerHits").c_str(), &missingInnerHits);
    t->Branch((pfx + "_pfIso").c_str(), &pfIso);
    t->Branch((pfx + "_relativePFIso").c_str(), &relativePFIso);
    t->Branch((pfx + "_caloEm").c_str(), &caloEm);
    t->Branch((pfx + "_caloHad").c_str(), &caloHad);
    t->Branch((pfx + "_caloTotal").c_str(), &caloTotal);
    t->Branch((pfx + "_dPhiMet").c_str(), &dPhiMet);
    t->Branch((pfx + "_dPhiMetNoMu").c_str(), &dPhiMetNoMu);
    t->Branch((pfx + "_ptOverMetNoMu").c_str(), &ptOverMetNoMu);
  }
  void clear() {
    pt.clear();
    eta.clear();
    phi.clear();
    dxy.clear();
    dz.clear();
    charge.clear();
    nHits.clear();
    nPixelHits.clear();
    missingOuterHits.clear();
    missingMiddleHits.clear();
    missingInnerHits.clear();
    pfIso.clear();
    relativePFIso.clear();
    caloEm.clear();
    caloHad.clear();
    caloTotal.clear();
    dPhiMet.clear();
    dPhiMetNoMu.clear();
    ptOverMetNoMu.clear();
  }
};

struct JetBranches {
  std::vector<float> pt, eta, phi, energy;

  void book(TTree *t, const std::string &pfx) {
    t->Branch((pfx + "_pt").c_str(), &pt);
    t->Branch((pfx + "_eta").c_str(), &eta);
    t->Branch((pfx + "_phi").c_str(), &phi);
    t->Branch((pfx + "_energy").c_str(), &energy);
  }
  void clear() {
    pt.clear();
    eta.clear();
    phi.clear();
    energy.clear();
  }
};

} // namespace

// ── Class declaration
// ─────────────────────────────────────────────────────────
class Ntuplizer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit Ntuplizer(const edm::ParameterSet &);
  void analyze(const edm::Event &, const edm::EventSetup &) override;

private:
  edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;
  edm::EDGetTokenT<std::vector<pat::MET>> metToken_;
  edm::EDGetTokenT<std::vector<pat::Muon>> muonToken_;
  edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;
  edm::EDGetTokenT<std::vector<pat::Jet>> jetToken_;
  edm::EDGetTokenT<std::vector<pat::Tau>> tauToken_;
  edm::EDGetTokenT<std::vector<pat::Muon>> allMuonToken_;
  edm::EDGetTokenT<std::vector<pat::Electron>> allElectronToken_;
  edm::EDGetTokenT<std::vector<pat::Tau>> allTauToken_;

  TTree *tree_;

  unsigned int run_, lumi_;
  unsigned long long eventNum_;
  float met_pt_, met_phi_, metNoMu_pt_, metNoMu_phi_;

  TrkBranches trk_;
  LepKin muon_, ele_, tau_;
  LepKinMinimal allMuon_, allEle_, allTau_;
  JetBranches jet_;
};

// ── Constructor
// ───────────────────────────────────────────────────────────────
Ntuplizer::Ntuplizer(const edm::ParameterSet &iConfig)
    : trackToken_(consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      metToken_(consumes<std::vector<pat::MET>>(
          iConfig.getParameter<edm::InputTag>("met"))),
      muonToken_(consumes<std::vector<pat::Muon>>(
          iConfig.getParameter<edm::InputTag>("muons"))),
      electronToken_(consumes<std::vector<pat::Electron>>(
          iConfig.getParameter<edm::InputTag>("electrons"))),
      jetToken_(consumes<std::vector<pat::Jet>>(
          iConfig.getParameter<edm::InputTag>("jets"))),
      tauToken_(consumes<std::vector<pat::Tau>>(
          iConfig.getParameter<edm::InputTag>("taus"))),
      allMuonToken_(consumes<std::vector<pat::Muon>>(
          iConfig.getParameter<edm::InputTag>("allMuons"))),
      allElectronToken_(consumes<std::vector<pat::Electron>>(
          iConfig.getParameter<edm::InputTag>("allElectrons"))),
      allTauToken_(consumes<std::vector<pat::Tau>>(
          iConfig.getParameter<edm::InputTag>("allTaus"))) {
  usesResource(TFileService::kSharedResource);
  edm::Service<TFileService> fs;
  tree_ = fs->make<TTree>(iConfig.getParameter<std::string>("treeName").c_str(),
                          "Tag and Probe Ntuple");

  tree_->Branch("run", &run_);
  tree_->Branch("lumi", &lumi_);
  tree_->Branch("eventNum", &eventNum_);
  tree_->Branch("met_pt", &met_pt_);
  tree_->Branch("met_phi", &met_phi_);
  tree_->Branch("metNoMu_pt", &metNoMu_pt_);
  tree_->Branch("metNoMu_phi", &metNoMu_phi_);

  trk_.book(tree_, "trk");
  muon_.book(tree_, "muon");
  ele_.book(tree_, "ele");
  jet_.book(tree_, "jet");
  tau_.book(tree_, "tau");
  allMuon_.book(tree_, "allMuon");
  allEle_.book(tree_, "allEle");
  allTau_.book(tree_, "allTau");
}

// ── analyze
// ───────────────────────────────────────────────────────────────────
void Ntuplizer::analyze(const edm::Event &iEvent, const edm::EventSetup &) {
  run_ = iEvent.run();
  lumi_ = iEvent.luminosityBlock();
  eventNum_ = iEvent.id().event();

  edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
  edm::Handle<std::vector<pat::MET>> mets;
  edm::Handle<std::vector<pat::Muon>> muons;
  edm::Handle<std::vector<pat::Electron>> electrons;
  edm::Handle<std::vector<pat::Jet>> jets;
  edm::Handle<std::vector<pat::Tau>> taus;
  edm::Handle<std::vector<pat::Muon>> allMuons;
  edm::Handle<std::vector<pat::Electron>> allElectrons;
  edm::Handle<std::vector<pat::Tau>> allTaus;

  iEvent.getByToken(trackToken_, tracks);
  iEvent.getByToken(metToken_, mets);
  iEvent.getByToken(muonToken_, muons);
  iEvent.getByToken(electronToken_, electrons);
  iEvent.getByToken(jetToken_, jets);
  iEvent.getByToken(tauToken_, taus);
  iEvent.getByToken(allMuonToken_, allMuons);
  iEvent.getByToken(allElectronToken_, allElectrons);
  iEvent.getByToken(allTauToken_, allTaus);

  // ── MET and MET^{no mu} ───────────────────────────────────────────────────
  const pat::MET &met = mets->at(0);
  met_pt_ = met.pt();
  met_phi_ = met.phi();

  float metX = met.pt() * std::cos(met.phi());
  float metY = met.pt() * std::sin(met.phi());
  for (const auto &mu : *muons) {
    metX += mu.pt() * std::cos(mu.phi());
    metY += mu.pt() * std::sin(mu.phi());
  }
  metNoMu_pt_ = std::hypot(metX, metY);
  metNoMu_phi_ = std::atan2(metY, metX);

  // ── Clear all branch vectors ──────────────────────────────────────────────
  trk_.clear();
  muon_.clear();
  ele_.clear();
  tau_.clear();
  allMuon_.clear();
  allEle_.clear();
  allTau_.clear();
  jet_.clear();

  // ── Fill muons ────────────────────────────────────────────────────────────
  for (const auto &mu : *muons) {
    muon_.pt.push_back(mu.pt());
    muon_.eta.push_back(mu.eta());
    muon_.phi.push_back(mu.phi());
    muon_.charge.push_back(mu.charge());
  }

  // ── Fill electrons ────────────────────────────────────────────────────────
  for (const auto &el : *electrons) {
    ele_.pt.push_back(el.pt());
    ele_.eta.push_back(el.eta());
    ele_.phi.push_back(el.phi());
    ele_.charge.push_back(el.charge());
  }

  // ── Fill taus ─────────────────────────────────────────────────────────────
  for (const auto &tau : *taus) {
    tau_.pt.push_back(tau.pt());
    tau_.eta.push_back(tau.eta());
    tau_.phi.push_back(tau.phi());
    tau_.charge.push_back(tau.charge());
  }

  // ── Fill all miniAOD leptons (for dR calculations) ───────────────────────
  for (const auto &mu : *allMuons) {
    allMuon_.pt.push_back(mu.pt());
    allMuon_.eta.push_back(mu.eta());
    allMuon_.phi.push_back(mu.phi());
    allMuon_.charge.push_back(mu.charge());
  }
  for (const auto &el : *allElectrons) {
    allEle_.pt.push_back(el.pt());
    allEle_.eta.push_back(el.eta());
    allEle_.phi.push_back(el.phi());
    allEle_.charge.push_back(el.charge());
  }
  for (const auto &tau : *allTaus) {
    allTau_.pt.push_back(tau.pt());
    allTau_.eta.push_back(tau.eta());
    allTau_.phi.push_back(tau.phi());
    allTau_.charge.push_back(tau.charge());
  }

  // ── Fill tracks ───────────────────────────────────────────────────────────
  for (const auto &trk : *tracks) {
    trk_.pt.push_back(trk.pt());
    trk_.eta.push_back(trk.eta());
    trk_.phi.push_back(trk.phi());
    trk_.dxy.push_back(trk.dxy());
    trk_.dz.push_back(trk.dz());
    trk_.charge.push_back(trk.charge());

    trk_.nHits.push_back(trk.hitPattern().numberOfValidHits());
    trk_.nPixelHits.push_back(trk.hitPattern().numberOfValidPixelHits());
    trk_.missingOuterHits.push_back(trk.hitPattern().numberOfLostHits(
        reco::HitPattern::MISSING_OUTER_HITS));
    trk_.missingMiddleHits.push_back(
        trk.hitPattern().trackerLayersWithoutMeasurement(
            reco::HitPattern::TRACK_HITS));
    trk_.missingInnerHits.push_back(
        trk.hitPattern().trackerLayersWithoutMeasurement(
            reco::HitPattern::MISSING_INNER_HITS));

    const float absIso = trk.pfIsolationDR03().chargedHadronIso();
    trk_.pfIso.push_back(absIso);
    trk_.relativePFIso.push_back(absIso / trk.pt());

    const float caloEm = trk.matchedCaloJetEmEnergy();
    const float caloHad = trk.matchedCaloJetHadEnergy();
    trk_.caloEm.push_back(caloEm);
    trk_.caloHad.push_back(caloHad);
    trk_.caloTotal.push_back(caloEm + caloHad);

    trk_.dPhiMet.push_back(reco::deltaPhi(trk.phi(), met.phi()));
    trk_.dPhiMetNoMu.push_back(reco::deltaPhi(trk.phi(), metNoMu_phi_));
    trk_.ptOverMetNoMu.push_back(metNoMu_pt_ > 0.f ? trk.pt() / metNoMu_pt_
                                                   : -1.f);
  }
  // ── Fill jets
  // ─────────────────────────────────────────────────────────────
  for (const auto &jet : *jets) {
    jet_.pt.push_back(jet.pt());
    jet_.eta.push_back(jet.eta());
    jet_.phi.push_back(jet.phi());
    jet_.energy.push_back(jet.energy());
  }

  tree_->Fill();
}

DEFINE_FWK_MODULE(Ntuplizer);
