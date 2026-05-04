#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/stream/EDFilter.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "FWCore/Utilities/interface/StreamID.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Tau.h"
#include "DataFormats/PatCandidates/interface/MET.h"
#include "DataFormats/PatCandidates/interface/TriggerObjectStandAlone.h"
#include "DataFormats/Common/interface/TriggerResults.h"
#include "DataFormats/Common/interface/View.h"
#include "DataFormats/Math/interface/deltaPhi.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "DataFormats/VertexReco/interface/Vertex.h"
#include "DataFormats/VertexReco/interface/VertexFwd.h"
#include "FWCore/Common/interface/TriggerNames.h"
#include "DisappTrks_v2/BkgdEstimation/plugins/CutflowFlags.h"

namespace {

    float transverseMass(float lepPt, float lepPhi, float metPt, float metPhi) {
        const float dPhi = reco::deltaPhi(lepPhi, metPhi);
        return std::sqrt(2.f * lepPt * metPt * (1.f - std::cos(dPhi)));
    }

    bool passesTightId(const reco::Candidate& cand,
                       const std::string& label,
                       const reco::Vertex& primaryVertex) {
        if (const auto* ele = dynamic_cast<const pat::Electron*>(&cand)) {
            if (ele->isElectronIDAvailable(label))
                return ele->electronID(label) > 0.5f;
            throw cms::Exception("Configuration")
                << "Electron ID '" << label << "' not available. "
                << "Check your tightIdLabel or re-run PAT with the correct VID setup.";
        }
        if (const auto* mu = dynamic_cast<const pat::Muon*>(&cand)) {
            return mu->isTightMuon(primaryVertex);
        }
        if (const auto* tau = dynamic_cast<const pat::Tau*>(&cand)) {
            if (tau->isTauIDAvailable(label))
                return tau->tauID(label) > 0.5f;
            throw cms::Exception("Configuration")
                << "Tau ID '" << label << "' not available. "
                << "Check your tightIdLabel or re-run PAT with the correct VID setup.";
        }
        throw cms::Exception("Configuration")
            << "Lepton is not a pat::Electron, pat::Muon, or pat::Tau.";
    }

    bool isMatchedToTriggerObject(const edm::Event& event,
                                   const edm::TriggerResults& triggers,
                                   const reco::Candidate& obj,
                                   const pat::TriggerObjectStandAloneCollection& trigObjs,
                                   const std::string& collection,
                                   const std::string& filter,
                                   const double dR = 0.3) {
        if (collection.empty()) return false;
        for (auto trigObj : trigObjs) {  // copy — unpackNamesAndLabels needs non-const
            trigObj.unpackNamesAndLabels(event, triggers);
            if (trigObj.collection() != collection) continue;
            if (!filter.empty()) {
                bool flag = false;
                for (const auto& filterLabel : trigObj.filterLabels())
                    if (filterLabel == filter) { flag = true; break; }
                if (!flag) continue;
            }
            if (reco::deltaR(obj, trigObj) > dR) continue;
            return true;
        }
        return false;
    }

} // namespace


// ── Forward declare the template ──────────────────────────────────────────────
template<typename LeptonType>
class QualityCut : public edm::stream::EDFilter<> {
public:
    explicit QualityCut(const edm::ParameterSet&);
    ~QualityCut() override = default;
    static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
    bool filter(edm::Event&, const edm::EventSetup&) override;

    const edm::EDGetTokenT<edm::View<reco::Candidate>>             leptonToken_;
    const edm::EDGetTokenT<std::vector<pat::MET>>                  metToken_;
    const edm::EDGetTokenT<std::vector<reco::Vertex>>              vertexToken_;
    const edm::EDGetTokenT<pat::TriggerObjectStandAloneCollection> trigObjToken_;
    const edm::EDGetTokenT<edm::TriggerResults>                    trigResultsToken_;

    const double      minPt_;
    const double      maxEta_;
    const std::string tightIdLabel_;
    const std::string instanceLabel_;
    const std::string triggerCollection_;
    const std::string triggerFilter_;
};

// ── Constructor ───────────────────────────────────────────────────────────────
template<typename LeptonType>
QualityCut<LeptonType>::QualityCut(const edm::ParameterSet& iConfig)
    : leptonToken_    (consumes<edm::View<reco::Candidate>>(
          iConfig.getParameter<edm::InputTag>("src"))),
      metToken_       (consumes<std::vector<pat::MET>>(
          iConfig.getParameter<edm::InputTag>("met"))),
      vertexToken_    (consumes<std::vector<reco::Vertex>>(
          iConfig.getParameter<edm::InputTag>("vertices"))),
      trigObjToken_   (consumes<pat::TriggerObjectStandAloneCollection>(
          iConfig.getParameter<edm::InputTag>("triggerObjects"))),
      trigResultsToken_(consumes<edm::TriggerResults>(
          iConfig.getParameter<edm::InputTag>("triggerResults"))),
      minPt_            (iConfig.getParameter<double>("minPt")),
      maxEta_           (iConfig.getParameter<double>("maxEta")),
      tightIdLabel_     (iConfig.getParameter<std::string>("tightIdLabel")),
      instanceLabel_    (iConfig.getParameter<std::string>("instanceLabel")),
      triggerCollection_(iConfig.getParameter<std::string>("triggerCollection")),
      triggerFilter_    (iConfig.getParameter<std::string>("triggerFilter"))
{
    produces<bool>("leptonPt");
    produces<bool>("leptonTriggerMatch");
    produces<bool>("leptonEta");
    produces<bool>("tightID");
    produces<bool>("leptonMETTransverseMass");
    produces<bool>("leptonD0");
    produces<bool>("leptonDZ");
    produces<std::vector<LeptonType>>("qualityLeptons");  // ← templated output
}

// ── filter() ─────────────────────────────────────────────────────────────────
template<typename LeptonType>
bool QualityCut<LeptonType>::filter(edm::Event& iEvent, const edm::EventSetup&) {

    auto qualityLeptons = std::make_unique<std::vector<LeptonType>>();  // ← templated

    bool passedPt        = false;
    bool passedTrigMatch = false;
    bool passedEta       = false;
    bool passedId        = false;
    bool passedMT        = false;
    bool passedD0        = false;
    bool passedDz        = false;

    auto putAll = [&]() {
        iEvent.put(std::make_unique<bool>(passedPt),        "leptonPt");
        iEvent.put(std::make_unique<bool>(passedTrigMatch), "leptonTriggerMatch");
        iEvent.put(std::make_unique<bool>(passedEta),       "leptonEta");
        iEvent.put(std::make_unique<bool>(passedId),        "tightID");
        iEvent.put(std::make_unique<bool>(passedMT),        "leptonMETTransverseMass");
        iEvent.put(std::make_unique<bool>(passedD0),        "leptonD0");
        iEvent.put(std::make_unique<bool>(passedDz),        "leptonDZ");
        iEvent.put(std::move(qualityLeptons),               "qualityLeptons");
    };

    edm::Handle<std::vector<pat::MET>> mets;
    iEvent.getByToken(metToken_, mets);
    if (mets->empty()) { putAll(); return false; }
    const pat::MET& met = mets->front();

    edm::Handle<std::vector<reco::Vertex>> vertices;
    iEvent.getByToken(vertexToken_, vertices);
    if (vertices->empty()) { putAll(); return false; }
    const reco::Vertex& pv = vertices->front();

    edm::Handle<pat::TriggerObjectStandAloneCollection> trigObjs;
    edm::Handle<edm::TriggerResults>                    trigResults;
    iEvent.getByToken(trigObjToken_,     trigObjs);
    iEvent.getByToken(trigResultsToken_, trigResults);

    edm::Handle<edm::View<reco::Candidate>> leptons;
    iEvent.getByToken(leptonToken_, leptons);

    for (const auto& lep : *leptons) {

        if (lep.pt() <= minPt_) continue;
        passedPt = true;

        if (!isMatchedToTriggerObject(iEvent, *trigResults, lep, *trigObjs,
                                      triggerCollection_, triggerFilter_)) continue;
        passedTrigMatch = true;

        if (std::abs(lep.eta()) >= maxEta_) continue;
        passedEta = true;

        if (!passesTightId(lep, tightIdLabel_, pv)) continue;
        passedId = true;

        if (transverseMass(lep.pt(), lep.phi(), met.pt(), met.phi()) >= 40.f) continue;
        passedMT = true;

        // ── Type-specific d0/dz cuts ──────────────────────────────────────────
        const auto* typedLep = dynamic_cast<const LeptonType*>(&lep);
        if (!typedLep) continue;

        if constexpr (std::is_same_v<LeptonType, pat::Electron>) {
            const bool  inEB  = std::abs(lep.eta()) < 1.479;
            const float maxD0 = inEB ? 0.05f : 0.10f;
            const float maxDz = inEB ? 0.10f : 0.20f;
            if (std::abs(typedLep->gsfTrack()->dxy(pv.position())) >= maxD0) continue;
            passedD0 = true;
            if (std::abs(typedLep->gsfTrack()->dz(pv.position()))  >= maxDz) continue;
            passedDz = true;
        } else if constexpr (std::is_same_v<LeptonType, pat::Muon>) {
            if (std::abs(typedLep->muonBestTrack()->dxy(pv.position())) >= 0.02f) continue;
            passedD0 = true;
            if (std::abs(typedLep->muonBestTrack()->dz(pv.position()))  >= 0.10f) continue;
            passedDz = true;
        }

        qualityLeptons->push_back(*typedLep);
    }

    const bool pass = !qualityLeptons->empty();
    putAll();
    return pass;
}

// ── fillDescriptions ──────────────────────────────────────────────────────────
template<typename LeptonType>
void QualityCut<LeptonType>::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("src",               edm::InputTag("slimmedElectrons"));
    desc.add<edm::InputTag>("met",               edm::InputTag("slimmedMETs"));
    desc.add<edm::InputTag>("vertices",          edm::InputTag("offlineSlimmedPrimaryVertices"));
    desc.add<edm::InputTag>("triggerObjects",    edm::InputTag("slimmedPatTrigger"));
    desc.add<edm::InputTag>("triggerResults",    edm::InputTag("TriggerResults", "", "HLT"));
    desc.add<double>       ("minPt",             32.0);
    desc.add<double>       ("maxEta",            2.1);
    desc.add<std::string>  ("tightIdLabel",      "cutBasedElectronID-RunIIIWinter22-V1-tight");
    desc.add<std::string>  ("instanceLabel",     "QualityCut");
    desc.add<std::string>  ("triggerCollection", "hltEgammaCandidates::HLT");
    desc.add<std::string>  ("triggerFilter",     "hltEle32WPTightGsfTrackIsoFilter");
    descriptions.addWithDefaultLabel(desc);
}

// ── Register both instantiations as separate named plugins ────────────────────
typedef QualityCut<pat::Electron> ElectronQualityCut;
typedef QualityCut<pat::Muon>     MuonQualityCut;

DEFINE_FWK_MODULE(ElectronQualityCut);
DEFINE_FWK_MODULE(MuonQualityCut);
