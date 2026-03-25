#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDMException.h"
#include "DataFormats/PatCandidates/interface/Jet.h"
#include "DataFormats/Math/interface/LorentzVector.h"
#include "DataFormats/Common/interface/Handle.h"

#include <memory>
#include <string>
#include <optional>
#include <vector>
#include <iostream>

#include "JecConfigReader.h"
#include "JecApplication.h"

class JecAppliedJetProducer : public edm::stream::EDProducer<> {
public:
  explicit JecAppliedJetProducer(const edm::ParameterSet& iConfig);
  ~JecAppliedJetProducer() override = default;

  void produce(edm::Event& iEvent, const edm::EventSetup& iSetup) override;

private:
  // --- Config (from python)
  edm::ParameterSet jetsPset_;
  edm::InputTag     srcJetsTag_;
  edm::InputTag     rhoTag_;

  std::string year_;
  bool        isData_;
  std::string era_;                // required for data, optional/ignored for MC

  // Systematics mode
  std::string systKind_;           // "Nominal" | "JES" | "JER"
  std::string jesSystName_;        // e.g. "AbsoluteStat" (empty => off)
  std::string jesSystVar_;         // "Up" | "Down"
  std::string jerVar_;             // "nom" | "up" | "down"

  // Optional JER region gate
  bool                       useJerRegion_{false};
  JecConfigReader::JerBin    jerRegion_{};

  bool        isDebug_{false};

  // --- Tokens
  edm::EDGetTokenT<pat::JetCollection> jetsTok_;
  edm::EDGetTokenT<double>             rhoTok_;

  // --- Config / correction backends
  edm::FileInPath jecConfigPath_;
  edm::FileInPath jerToolConfigPath_;

  // Pointer to the global JEC config singleton
  JecConfigReader::JecConfig* jecCfg_{nullptr};

  // JES syst correction ref (MC only, cached once)
  std::optional<correction::Correction::Ref> jesSystRef_;

  // Helpers
  static double computeRawFactorFromMiniAOD(const pat::Jet& j) {
    const double ptCorr = j.pt();
    const double ptRaw  = j.correctedP4("Uncorrected").pt(); // MiniAOD stored
    if (ptCorr <= 0.0) return 0.0;
    const double rf = 1.0 - (ptRaw / ptCorr);
    // clamp to sane range
    return std::min(std::max(rf, 0.0), 1.0);
  }

  static inline void setP4Scaled(pat::Jet& j, double scale) {
    // Scale full p4 (JEC/JER are p4 scalings)
    const auto p4 = j.p4();
    const auto p4Scaled = reco::Particle::LorentzVector(
        p4.px() * scale, p4.py() * scale, p4.pz() * scale, p4.energy() * scale);
    j.setP4(p4Scaled);
  }

  static inline void addUserFloats(pat::Jet& j,
                                   double jes,
                                   double jesSyst,
                                   double jer,
                                   double total) {
    j.addUserFloat("JERC:jesFactor",      jes);
    j.addUserFloat("JERC:jesSystFactor",  jesSyst);
    j.addUserFloat("JERC:jerFactor",      jer);
    j.addUserFloat("JERC:totalFactor",    total);
  }
};

JecAppliedJetProducer::JecAppliedJetProducer(const edm::ParameterSet& iConfig)
  : jetsPset_ ( iConfig.getParameter<edm::ParameterSet>("Jets") ),
    srcJetsTag_( jetsPset_.getParameter<edm::InputTag>("srcAK4") ),
    rhoTag_   ( jetsPset_.getParameter<edm::InputTag>("rho") ),
    year_     ( jetsPset_.getParameter<std::string>("Year") ),
    isData_   ( jetsPset_.getParameter<bool>("IsData") ),
    systKind_ ( jetsPset_.getParameter<std::string>("SystKind") ),
    jesSystName_( jetsPset_.getParameter<std::string>("JesSystName") ),
    jesSystVar_ ( jetsPset_.getParameter<std::string>("JesSystVar") ),
    jerVar_     ( jetsPset_.getParameter<std::string>("JerVar") ),
    isDebug_ ( iConfig.existsAs<bool>("isDebug") ? iConfig.getParameter<bool>("isDebug") : false ),
    jetsTok_( consumes<pat::JetCollection>(srcJetsTag_) ),
    rhoTok_ ( consumes<double>(rhoTag_) )
{
  // Era (needed for data path)
  if (jetsPset_.existsAs<std::string>("Era")) {
    era_ = jetsPset_.getParameter<std::string>("Era");
  }
  if (isData_ && era_.empty()) {
    throw edm::Exception(edm::errors::Configuration)
      << "JecAppliedJetProducer: For data (IsData=true) you must provide a non-empty 'Era' in the Jets PSet.";
  }

  // Use the resolved filesystem path from edm::FileInPath and configure
  // the singleton defaults *before* first construction.
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
    // AK4, MC, JES uncertainty sets
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
      std::cout << "[JecAppliedJetProducer] Warning: JES syst name '"
                << jesSystName_ << "' not found in any uncertainty set for year "
                << year_ << " (AK4). JES systematics will be ignored.\n";
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

  produces<pat::JetCollection>("CorrectedAK4");
}

void JecAppliedJetProducer::produce(edm::Event& iEvent, const edm::EventSetup& iSetup) {

  // Inputs
  edm::Handle<pat::JetCollection> hJets;
  iEvent.getByToken(jetsTok_, hJets);

  edm::Handle<double> hRho;
  iEvent.getByToken(rhoTok_, hRho);
  const double rho = hRho.isValid() ? *hRho : 0.0;

  auto out = std::make_unique<pat::JetCollection>();
  out->reserve(hJets->size());

  // Build systematics payload
  JecApplication::SystematicOptions systOpts{};
  if (systKind_ == "JES") {
    if (jesSystRef_) {
      systOpts.jesSystRef = jesSystRef_;
      systOpts.jesSystVar = jesSystVar_; // "Up" | "Down"
    }
  } else if (systKind_ == "JER") {
    systOpts.jerVar = jerVar_;           // "nom" | "up" | "down"
    if (useJerRegion_) systOpts.jerRegion = jerRegion_;
  }

  // Per-event Applier (handles JEC/JER handles and run-based residual logic)
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

  // Loop jets
  for (const auto& jet : *hJets) {
    pat::Jet outJet = jet; // copy

    // --- Build JES inputs from MiniAOD ---
    const double rawFactor = computeRawFactorFromMiniAOD(jet);

    JecApplication::JesInputs jesIn{
      /*pt=*/        jet.pt(),
      /*eta=*/       jet.eta(),
      /*phi=*/       jet.phi(),
      /*area=*/      jet.jetArea(),
      /*rho=*/       rho,
      /*rawFactor=*/ rawFactor
    };

    // --- JES nominal factor (via Applier) ---
    const double jesFactor = applier.jesFactorNominal(jesIn);

    // Apply JES nominal
    setP4Scaled(outJet, jesFactor);

    // --- JES syst (MC only and if requested) ---
    double jesSystFactor = 1.0;
    if (!isData_ && systKind_ == "JES" && jesSystRef_) {
      const double ptAfterJes = jesIn.pt * jesFactor;
      jesSystFactor = JecApplication::Applier::jesComponentSyst(
          *jesSystRef_, jesSystVar_, jesIn.eta, ptAfterJes, isDebug_);
      setP4Scaled(outJet, jesSystFactor);
    }

    // --- JER (MC only) ---
    double jerFactor = 1.0;
    if (!isData_) {
      // State after JES (and optional JES syst)
      JecApplication::JesInputs jAfter{
        /*pt=*/        outJet.pt(),
        /*eta=*/       outJet.eta(),
        /*phi=*/       outJet.phi(),
        /*area=*/      jet.jetArea(),
        /*rho=*/       rho,
        /*rawFactor=*/ 0.0
      };

      // Gen-matching if available
      JecApplication::JerInputs jerIn{};
      jerIn.event = iEvent.id().event();
      jerIn.rho   = rho;

      if (const auto* gj = jet.genJet()) {
        jerIn.hasGen = true;
        jerIn.genPt  = gj->pt();
        jerIn.genEta = gj->eta();
        jerIn.genPhi = gj->phi();
        jerIn.maxDr  = 0.2; // AK4
      }

      jerFactor = applier.jerFactor(jAfter, jerIn, systOpts);
      setP4Scaled(outJet, jerFactor);
    }

    // Attach userFloats for downstream bookkeeping
    const double total = jesFactor * jesSystFactor * jerFactor;
    addUserFloats(outJet, jesFactor, jesSystFactor, jerFactor, total);

    out->push_back(std::move(outJet));
  }

  iEvent.put(std::move(out), "CorrectedAK4");
}

// Register
#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(JecAppliedJetProducer);

