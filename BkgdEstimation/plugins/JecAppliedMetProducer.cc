#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDMException.h"

#include "DataFormats/PatCandidates/interface/Jet.h"
#include "DataFormats/PatCandidates/interface/MET.h"
#include "DataFormats/Common/interface/Handle.h"
#include "DataFormats/Math/interface/LorentzVector.h"

#include <memory>
#include <optional>
#include <string>
#include <vector>
#include <iostream>
#include <cmath>

#include "JecConfigReader.h"
#include "JecApplication.h"

class JecAppliedMetProducer : public edm::stream::EDProducer<> {
public:
  explicit JecAppliedMetProducer(const edm::ParameterSet& iConfig);
  ~JecAppliedMetProducer() override = default;

  void produce(edm::Event& iEvent, const edm::EventSetup& iSetup) override;

private:
  // ---- Config (from python) ----
  edm::ParameterSet jetsPset_;
  edm::InputTag     srcJetsTag_;     // pat::JetCollection (AK4)
  edm::InputTag     rhoTag_;         // double
  edm::InputTag     srcMetPfTag_;    // pat::METCollection (PF)
  edm::InputTag     srcMetPuppiTag_; // pat::METCollection (PUPPI)

  std::string year_;
  bool        isData_;
  std::string era_;
  bool        isDebug_{false};

  // Optional: read muon subtraction factor from jet userFloat (0..1). Empty => disabled.
  std::string muonSubtrUserFloat_;

  // Systematics
  std::string systKind_;      // "Nominal" | "JES" | "JER"
  std::string jesSystName_;   // e.g. "AbsoluteStat" (empty => off)
  std::string jesSystVar_;    // "Up" | "Down"
  std::string jerVar_;        // "nom" | "up" | "down"
  bool        useJerRegion_{false};
  JecConfigReader::JerBin jerRegion_{};

  // ---- Tokens ----
  edm::EDGetTokenT<pat::JetCollection> jetsTok_;
  edm::EDGetTokenT<double>             rhoTok_;
  edm::EDGetTokenT<pat::METCollection> metPfTok_;
  edm::EDGetTokenT<pat::METCollection> metPuppiTok_;

  // ---- Config / corrections (AK4) ----
  edm::FileInPath jecConfigPath_;
  edm::FileInPath jerToolConfigPath_;
  JecConfigReader::JecConfig* jecCfg_{nullptr};

  // JES syst correction ref (MC only, cached once)
  std::optional<correction::Correction::Ref> jesSystRef_;

  // Helpers
  static inline double getRawPtFromMiniAOD(const pat::Jet& j) {
    return j.correctedP4("Uncorrected").pt();  // MiniAOD stores this
  }

  static inline double getMuonSubtrFraction(const pat::Jet& j, const std::string& name) {
    if (name.empty()) return 0.0;
    if (j.hasUserFloat(name)) {
      const double f = j.userFloat(name);
      if (std::isfinite(f)) return std::max(0.0, std::min(1.0, f));
    }
    return 0.0;
  }

  static inline double getMetRawPt(const pat::MET& met) {
    // Prefer uncorrected if available, else fall back with a warning.
    double v = met.uncorPt();
    if (!(v >= 0.0)) {
      std::cout << "[JecAppliedMetProducer] WARNING: met.uncorPt() invalid; using met.pt().\n";
      v = met.pt();
    }
    return v;
  }

  static inline double getMetRawPhi(const pat::MET& met) {
    double v = met.uncorPhi();
    if (!std::isfinite(v)) {
      std::cout << "[JecAppliedMetProducer] WARNING: met.uncorPhi() invalid; using met.phi().\n";
      v = met.phi();
    }
    return v;
  }

  static inline pat::MET makeCorrectedMetFrom(const pat::MET& src,
                                              const TLorentzVector& p4corr) {
    pat::MET out = src; // copy PAT object (keeps extras)
    // Replace p4 with corrected pT/phi, zero eta/mass (MET mass=0, eta unused)
    const auto corr = reco::Particle::LorentzVector(
        p4corr.Px(), p4corr.Py(), 0.0, p4corr.Pt() /* E≈|pT| for massless */);
    out.setP4(corr);
    // Bookkeeping helpers (raw pt/phi will be set by caller)
    out.addUserFloat("JERC:MET_corr_pt",  p4corr.Pt());
    out.addUserFloat("JERC:MET_corr_phi", p4corr.Phi());
    return out;
  }
};

JecAppliedMetProducer::JecAppliedMetProducer(const edm::ParameterSet& iConfig)
  : jetsPset_        ( iConfig.getParameter<edm::ParameterSet>("Jets") )
  , srcJetsTag_      ( jetsPset_.getParameter<edm::InputTag>("srcAK4") )
  , rhoTag_          ( jetsPset_.getParameter<edm::InputTag>("rho") )
  , srcMetPfTag_     ( iConfig.getParameter<edm::InputTag>("srcMET_PF") )
  , srcMetPuppiTag_  ( iConfig.getParameter<edm::InputTag>("srcMET_PUPPI") )
  , year_            ( jetsPset_.getParameter<std::string>("Year") )
  , isData_          ( jetsPset_.getParameter<bool>("IsData") )
  , isDebug_         ( iConfig.existsAs<bool>("isDebug") ? iConfig.getParameter<bool>("isDebug") : false )
  , muonSubtrUserFloat_(
        jetsPset_.existsAs<std::string>("MuonSubtrUserFloat")
          ? jetsPset_.getParameter<std::string>("MuonSubtrUserFloat")
          : std::string{} )
  , systKind_        ( jetsPset_.getParameter<std::string>("SystKind") )
  , jesSystName_     ( jetsPset_.getParameter<std::string>("JesSystName") )
  , jesSystVar_      ( jetsPset_.getParameter<std::string>("JesSystVar") )
  , jerVar_          ( jetsPset_.getParameter<std::string>("JerVar") )
  , jetsTok_         ( consumes<pat::JetCollection>(srcJetsTag_) )
  , rhoTok_          ( consumes<double>(rhoTag_) )
  , metPfTok_        ( consumes<pat::METCollection>(srcMetPfTag_) )
  , metPuppiTok_     ( consumes<pat::METCollection>(srcMetPuppiTag_) )
{
  // Era (needed for data path)
  if (jetsPset_.existsAs<std::string>("Era")) {
    era_ = jetsPset_.getParameter<std::string>("Era");
  }
  if (isData_ && era_.empty()) {
    throw edm::Exception(edm::errors::Configuration)
      << "JecAppliedMetProducer: For data (IsData=true) you must provide a non-empty 'Era' in the Jets PSet.";
  }

  // Use the resolved filesystem path from edm::FileInPath and configure
  // the JEC singleton defaults *before* first construction.
  jecConfigPath_     = jetsPset_.getParameter<edm::FileInPath>("JecConfig");
  jerToolConfigPath_ = jetsPset_.getParameter<edm::FileInPath>("JerToolConfig");

  JecConfigReader::ConfigPaths paths;
  paths.ak4 = jecConfigPath_.fullPath();
  // ak8 left at default for this producer (AK4 only)

  JecConfigReader::JecConfig::setDefaultPaths(paths);
  JecConfigReader::JecConfig::setDefaultJerSmearPath(jerToolConfigPath_.fullPath());

  // Get the singleton instance
  jecCfg_ = &JecConfigReader::JecConfig::defaultInstance();

  // Pre-compute JES syst ref for MC, if requested
  if (!isData_ && systKind_ == "JES" && !jesSystName_.empty()) {
    const auto jesUncSets = jecCfg_->getJesUncSetsMcAK4Ref(year_);

    auto findRef = [&](const std::map<std::string, correction::Correction::Ref>& m)
      -> std::optional<correction::Correction::Ref>
    {
      auto it = m.find(jesSystName_);
      if (it != m.end()) return it->second;
      return std::nullopt;
    };

    // Try "total" first, then "reduced", then "full"
    jesSystRef_ = findRef(jesUncSets.total);
    if (!jesSystRef_) jesSystRef_ = findRef(jesUncSets.reduced);
    if (!jesSystRef_) jesSystRef_ = findRef(jesUncSets.full);

    if (!jesSystRef_) {
      std::cout << "[JecAppliedMetProducer] Warning: JES syst name '"
                << jesSystName_ << "' not found in any uncertainty set for year "
                << year_ << " (AK4). JES systematics will be ignored for MET.\n";
    }
  }

  // Optional JER region
  if (jetsPset_.existsAs<edm::ParameterSet>("JerRegion")) {
    const auto& p = jetsPset_.getParameter<edm::ParameterSet>("JerRegion");
    jerRegion_.etaMin = p.getParameter<double>("etaMin");
    jerRegion_.etaMax = p.getParameter<double>("etaMax");
    jerRegion_.ptMin  = p.getParameter<double>("ptMin");
    jerRegion_.ptMax  = p.getParameter<double>("ptMax");
    useJerRegion_ = true;
  }

  produces<pat::METCollection>("CorrectedMet");
}

void JecAppliedMetProducer::produce(edm::Event& iEvent, const edm::EventSetup& iSetup) {
  // Inputs
  edm::Handle<pat::JetCollection> hJets;
  iEvent.getByToken(jetsTok_, hJets);

  edm::Handle<double> hRho;
  iEvent.getByToken(rhoTok_, hRho);
  const double rho = hRho.isValid() ? *hRho : 0.0;

  const bool usePuppi = JecApplication::usesPuppiMet(year_);

  edm::Handle<pat::METCollection> hMet;
  if (usePuppi) {
    iEvent.getByToken(metPuppiTok_, hMet);
  } else {
    iEvent.getByToken(metPfTok_, hMet);
  }
  if (!hMet.isValid() || hMet->empty()) {
    throw edm::Exception(edm::errors::ProductNotFound)
        << "JecAppliedMetProducer: MET collection is invalid or empty ("
        << (usePuppi ? srcMetPuppiTag_.encode() : srcMetPfTag_.encode()) << ").";
  }
  const pat::MET& metIn = hMet->front();

  const double metRawPt  = getMetRawPt(metIn);
  const double metRawPhi = getMetRawPhi(metIn);

  // Build jetsForMet (RAW AK4 BEFORE any modifications)
  std::vector<JecApplication::JetForMet> jetsForMet;
  std::vector<JecApplication::JerInputs> jersForMet;
  jetsForMet.reserve(hJets->size());
  jersForMet.reserve(hJets->size());

  for (const auto& j : *hJets) {
    JecApplication::JetForMet v;
    v.phi             = j.phi();
    v.eta             = j.eta();
    v.area            = j.jetArea();
    v.rawPt           = getRawPtFromMiniAOD(j);
    v.muonSubtrFactor = getMuonSubtrFraction(j, muonSubtrUserFloat_);
    v.chEmEf          = j.chargedEmEnergyFraction();
    v.neEmEf          = j.neutralEmEnergyFraction();
    jetsForMet.push_back(v);

    JecApplication::JerInputs jerIn;
    jerIn.event = iEvent.id().event();
    jerIn.rho   = rho;
    if (const auto* gj = j.genJet()) {
      jerIn.hasGen = true;
      jerIn.genPt  = gj->pt();
      jerIn.genEta = gj->eta();
      jerIn.genPhi = gj->phi();
      jerIn.maxDr  = 0.2; // AK4
    }
    jersForMet.push_back(jerIn);
  }

  // Per-event Applier (same pattern as jet producer)
  JecApplication::Applier applier =
    [&]() -> JecApplication::Applier {
      if (isData_) {
        std::optional<double> runNumber;
        if (JecApplication::requiresRunBasedResidual(year_)) {
          runNumber = static_cast<double>(iEvent.id().run());
        }
        return JecApplication::Applier::DataAK4(*jecCfg_, year_, era_, isDebug_, runNumber);
      } else {
        return JecApplication::Applier::McAK4(*jecCfg_, year_, isDebug_);
      }
    }();

  // Systematics payload
  JecApplication::SystematicOptions systOpts{};
  if (systKind_ == "JES") {
    if (jesSystRef_) {
      systOpts.jesSystRef = jesSystRef_;
      systOpts.jesSystVar = jesSystVar_;    // "Up" | "Down"
    }
  } else if (systKind_ == "JER") {
    systOpts.jerVar = jerVar_;              // "nom" | "up" | "down"
    if (useJerRegion_) systOpts.jerRegion = jerRegion_;
  }

  // Call the shared Type-1 MET routine through Applier
  JecApplication::MetInputs metInputs{metRawPt, metRawPhi};
  const TLorentzVector p4CorrectedMET =
      applier.correctedMet(metInputs, jetsForMet, jersForMet, rho, systOpts);

  // Build and put output (copy original PAT MET; replace p4)
  auto out = std::make_unique<pat::METCollection>();
  pat::MET metOut = makeCorrectedMetFrom(metIn, p4CorrectedMET);
  // record which raw was used
  metOut.addUserFloat("JERC:MET_raw_pt_used",  metRawPt);
  metOut.addUserFloat("JERC:MET_raw_phi_used", metRawPhi);
  out->push_back(std::move(metOut));

  iEvent.put(std::move(out), "CorrectedMet");
}

// Register module
#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(JecAppliedMetProducer);

