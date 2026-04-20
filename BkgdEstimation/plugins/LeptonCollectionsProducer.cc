#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Tau.h"
#include "DataFormats/VertexReco/interface/Vertex.h"
#include "DataFormats/VertexReco/interface/VertexFwd.h"
#include "DataFormats/Common/interface/View.h"

// Produces three separate PAT lepton collections (qualityElectrons, qualityMuons,
// qualityTaus) requiring pT > minPt, |eta| < maxEta, and tight ID.
class LeptonCollectionsProducer : public edm::stream::EDProducer<> {
public:
    explicit LeptonCollectionsProducer(const edm::ParameterSet&);
    ~LeptonCollectionsProducer() override = default;
    static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
    void produce(edm::Event&, const edm::EventSetup&) override;

    const edm::EDGetTokenT<edm::View<pat::Electron>>  electronToken_;
    const edm::EDGetTokenT<edm::View<pat::Muon>>      muonToken_;
    const edm::EDGetTokenT<edm::View<pat::Tau>>       tauToken_;
    const edm::EDGetTokenT<std::vector<reco::Vertex>> vertexToken_;

    const double      minPt_;
    const double      maxEta_;
    const std::string electronIdLabel_;
    const std::string tauVsJetLabel_;
    const std::string tauVsEleLabel_;
    const std::string tauVsMuLabel_;

    bool passesTauId(const pat::Tau&) const;
};

LeptonCollectionsProducer::LeptonCollectionsProducer(const edm::ParameterSet& iConfig)
    : electronToken_(consumes<edm::View<pat::Electron>>(
          iConfig.getParameter<edm::InputTag>("electrons"))),
      muonToken_    (consumes<edm::View<pat::Muon>>(
          iConfig.getParameter<edm::InputTag>("muons"))),
      tauToken_     (consumes<edm::View<pat::Tau>>(
          iConfig.getParameter<edm::InputTag>("taus"))),
      vertexToken_  (consumes<std::vector<reco::Vertex>>(
          iConfig.getParameter<edm::InputTag>("vertices"))),
      minPt_         (iConfig.getParameter<double>("minPt")),
      maxEta_        (iConfig.getParameter<double>("maxEta")),
      electronIdLabel_(iConfig.getParameter<std::string>("electronIdLabel")),
      tauVsJetLabel_ (iConfig.getParameter<std::string>("tauVsJetLabel")),
      tauVsEleLabel_ (iConfig.getParameter<std::string>("tauVsEleLabel")),
      tauVsMuLabel_  (iConfig.getParameter<std::string>("tauVsMuLabel"))
{
    produces<std::vector<pat::Electron>>("qualityElectrons");
    produces<std::vector<pat::Muon>>    ("qualityMuons");
    produces<std::vector<pat::Tau>>     ("qualityTaus");
}

void LeptonCollectionsProducer::produce(edm::Event& iEvent, const edm::EventSetup&) {
    auto qualityElectrons = std::make_unique<std::vector<pat::Electron>>();
    auto qualityMuons     = std::make_unique<std::vector<pat::Muon>>();
    auto qualityTaus      = std::make_unique<std::vector<pat::Tau>>();

    edm::Handle<std::vector<reco::Vertex>> vertices;
    iEvent.getByToken(vertexToken_, vertices);
    const reco::Vertex* pv = vertices->empty() ? nullptr : &vertices->front();

    edm::Handle<edm::View<pat::Electron>> electrons;
    iEvent.getByToken(electronToken_, electrons);
    for (const auto& ele : *electrons) {
        if (ele.pt() <= minPt_) continue;
        if (std::abs(ele.eta()) >= maxEta_) continue;
        if (!ele.isElectronIDAvailable(electronIdLabel_)) continue;
        if (ele.electronID(electronIdLabel_) <= 0.5f) continue;
        qualityElectrons->push_back(ele);
    }

    edm::Handle<edm::View<pat::Muon>> muons;
    iEvent.getByToken(muonToken_, muons);
    for (const auto& mu : *muons) {
        if (mu.pt() <= minPt_) continue;
        if (std::abs(mu.eta()) >= maxEta_) continue;
        if (!pv || !mu.isTightMuon(*pv)) continue;
        qualityMuons->push_back(mu);
    }

    edm::Handle<edm::View<pat::Tau>> taus;
    iEvent.getByToken(tauToken_, taus);
    for (const auto& tau : *taus) {
        if (tau.pt() <= minPt_) continue;
        if (std::abs(tau.eta()) >= maxEta_) continue;
        if (!passesTauId(tau)) continue;
        qualityTaus->push_back(tau);
    }

    iEvent.put(std::move(qualityElectrons), "qualityElectrons");
    iEvent.put(std::move(qualityMuons),     "qualityMuons");
    iEvent.put(std::move(qualityTaus),      "qualityTaus");
}

bool LeptonCollectionsProducer::passesTauId(const pat::Tau& tau) const {
    auto check = [&tau](const std::string& label) -> bool {
        if (label.empty()) return true;
        if (!tau.isTauIDAvailable(label)) return false;
        return tau.tauID(label) > 0.5f;
    };
    return check(tauVsJetLabel_) && check(tauVsEleLabel_) && check(tauVsMuLabel_);
}

void LeptonCollectionsProducer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("electrons", edm::InputTag("slimmedElectrons"));
    desc.add<edm::InputTag>("muons",     edm::InputTag("slimmedMuons"));
    desc.add<edm::InputTag>("taus",      edm::InputTag("slimmedTaus"));
    desc.add<edm::InputTag>("vertices",  edm::InputTag("offlineSlimmedPrimaryVertices"));
    desc.add<double>       ("minPt",     20.0);
    desc.add<double>       ("maxEta",    2.1);
    desc.add<std::string>  ("electronIdLabel", "cutBasedElectronID-RunIIIWinter22-V1-tight");
    desc.add<std::string>  ("tauVsJetLabel",   "");
    desc.add<std::string>  ("tauVsEleLabel",   "byTightDeepTau2018v2p5VSe");
    desc.add<std::string>  ("tauVsMuLabel",    "byTightDeepTau2018v2p5VSmu");
    descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(LeptonCollectionsProducer);
