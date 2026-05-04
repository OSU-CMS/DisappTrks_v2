// -*- C++ -*-
//
// Package:    DisappTrks/ZtoProbeTrkTrackSelections
// Class:      ZtoProbeTrkTrackSelections
//
// Selects events containing at least one probe track passing the full
// disappearing-track pre-selection, and puts a filtered collection of
// those passing tracks into the event under the label "probeTracks".
//
// All downstream filters should consume:
//   cms.InputTag("ZtoProbeTrkTrackSelections", "probeTracks")
// instead of isolatedTracks, so that every subsequent cut acts on the
// same track objects that survived this selection.
//

#include <limits>
#include <memory>

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
#include "DataFormats/Math/interface/deltaR.h"
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "DataFormats/PatCandidates/interface/Jet.h"
#include "TH1D.h"
#include "DisappTrks_v2/BkgdEstimation/plugins/CutflowFlags.h"

const double PI_2 = 1.57079632679489661923;
namespace {
    // -------------------------------------------------------------------------
    // TightLepVeto jet ID for CMSSW >= 12.4.11 (Run 3, 13.6 TeV)
    // Mirrors anatools::jetPassesTightLepVeto for the CMSSW_VERSION_CODE
    // >= CMSSW_VERSION(12,4,11) branch exactly.
    // https://twiki.cern.ch/twiki/bin/view/CMS/JetID13p6TeV
    // -------------------------------------------------------------------------
    bool passesJetID(const pat::Jet& jet) {
        const double absEta = std::abs(jet.eta());
        if (absEta <= 2.6)
            return (jet.neutralHadronEnergyFraction() < 0.99 &&
                    jet.neutralEmEnergyFraction()     < 0.90 &&
                    (jet.chargedMultiplicity() + jet.neutralMultiplicity()) > 1 &&
                    jet.muonEnergyFraction()          < 0.8  &&
                    jet.chargedHadronEnergyFraction() > 0.01 &&
                    jet.chargedMultiplicity()         > 0    &&
                    jet.chargedEmEnergyFraction()     < 0.80);
        if (absEta <= 2.7)
            return (jet.neutralHadronEnergyFraction() < 0.90 &&
                    jet.neutralEmEnergyFraction()     < 0.99 &&
                    jet.muonEnergyFraction()          < 0.8  &&
                    jet.chargedMultiplicity()         > 0    &&
                    jet.chargedEmEnergyFraction()     < 0.80);
        if (absEta <= 3.0)
            return (jet.neutralHadronEnergyFraction() < 0.99 &&
                    jet.neutralEmEnergyFraction()     < 0.99 &&
                    jet.neutralMultiplicity()         > 1);
        // absEta <= 5.0
        return (jet.neutralEmEnergyFraction() < 0.40 &&
                jet.neutralMultiplicity()     > 10   &&
                absEta <= 5.0);
    }
} 

class ZtoProbeTrkTrackSelections : public edm::stream::EDFilter<> {
public:
    explicit ZtoProbeTrkTrackSelections(const edm::ParameterSet&);
    ~ZtoProbeTrkTrackSelections() override = default;
    static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
    void beginStream(edm::StreamID) override {}
    bool filter(edm::Event&, const edm::EventSetup&) override;
    void endStream() override {}

    edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;
    edm::EDGetTokenT<std::vector<pat::Muon>>          muonToken_;
    edm::EDGetTokenT<std::vector<pat::Electron>>      electronToken_;
    edm::EDGetTokenT<std::vector<pat::Jet>>           jetToken_;

    const double minPt_;
    const int    minLayers_;
    const bool   useExclusive_;
    const double minDeltaRJet_;
    const std::string instanceLabel_;

    TH1D* hDRMinJet_;
};

ZtoProbeTrkTrackSelections::ZtoProbeTrkTrackSelections(const edm::ParameterSet& iConfig)
    : trackToken_   (consumes<std::vector<pat::IsolatedTrack>>(iConfig.getParameter<edm::InputTag>("tracks"))),
      muonToken_    (consumes<std::vector<pat::Muon>>         (iConfig.getParameter<edm::InputTag>("muons"))),
      electronToken_(consumes<std::vector<pat::Electron>>     (iConfig.getParameter<edm::InputTag>("electrons"))),
      jetToken_     (consumes<std::vector<pat::Jet>>          (iConfig.getParameter<edm::InputTag>("jets"))),
      minPt_        (iConfig.getParameter<double>("minPt")),
      minLayers_    (iConfig.getParameter<int>("minLayers")),
      useExclusive_ (iConfig.getParameter<bool>("useExclusive")),
      minDeltaRJet_ (iConfig.getParameter<double>("minDeltaRJet")),
      instanceLabel_ (iConfig.getParameter<std::string>("instanceLabel"))

{
    produces<std::vector<pat::IsolatedTrack>>("probeTracks");
    produces<bool>(instanceLabel_+"trackPt");
    produces<bool>(instanceLabel_+"trackEta");
    produces<bool>(instanceLabel_+"trackECAL");
    produces<bool>(instanceLabel_+"trackEDT");
    produces<bool>(instanceLabel_+"trackCSC");
    produces<bool>(instanceLabel_+"trackTOB");
    produces<bool>(instanceLabel_+"trackPixelHits");
    produces<bool>(instanceLabel_+"trackValidHits");
    produces<bool>(instanceLabel_+"trackInnerHits");
    produces<bool>(instanceLabel_+"trackMiddleHits");
    produces<bool>(instanceLabel_+"trackIso");
    produces<bool>(instanceLabel_+"trackD0");
    produces<bool>(instanceLabel_+"trackDZ");
    produces<bool>(instanceLabel_+"trackDRJet");
    produces<bool>(instanceLabel_+"trackLayers");
}

bool ZtoProbeTrkTrackSelections::filter(edm::Event& iEvent, const edm::EventSetup& iSetup) {
    edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
    edm::Handle<std::vector<pat::Muon>>          muons;
    edm::Handle<std::vector<pat::Electron>>      electrons;
    edm::Handle<std::vector<pat::Jet>>           jets;

    iEvent.getByToken(trackToken_,    tracks);
    iEvent.getByToken(muonToken_,     muons);
    iEvent.getByToken(electronToken_, electrons);
    iEvent.getByToken(jetToken_,      jets);

    bool passedPt = false;
    bool passedEta = false;
    bool passedECAL = false;
    bool passedEDT = false;
    bool passedCSC = false;
    bool passedTOB = false;
    bool passedPixelHits = false;
    bool passedValidHits = false;
    bool passedInnerHits = false;
    bool passedMiddleHits = false;
    bool passedIso = false;
    bool passedD0 = false;
    bool passedDZ = false;
    bool passedDRJet = false;
    bool passedLayers = false;
    
    auto probeTracks = std::make_unique<std::vector<pat::IsolatedTrack>>();

    for (const auto& track : *tracks) {
        const double absEta = std::abs(track.eta());

        const bool inDTWheelGap          = (absEta >= 0.15 && absEta <= 0.35);
        const bool inECALCrack           = (absEta >= 1.42 && absEta <= 1.65);
        const bool inCSCTransitionRegion = (absEta >= 1.55 && absEta <= 1.85);
        const bool inTOBCrack            = (std::abs(track.dz()) < 0.5 && std::abs(PI_2 - track.theta()) < 1.0e-3);

        if (track.pt() <= minPt_) continue;
        passedPt = true;


        if (absEta >= 2.1) continue;
        passedEta = true;

        if (inECALCrack) continue;
        passedECAL = true;

        if (inDTWheelGap) continue;
        passedEDT = true;

        if (inCSCTransitionRegion) continue;
        passedCSC = true;

        if (inTOBCrack) continue;
        passedTOB = true;

        if (track.hitPattern().numberOfValidPixelHits() < 4) continue;
        passedPixelHits = true;

        if (track.hitPattern().numberOfValidHits() < 4) continue;
        passedValidHits = true;

        if (track.hitPattern().trackerLayersWithoutMeasurement(reco::HitPattern::MISSING_INNER_HITS) != 0) continue;
        passedInnerHits = true;

        if (track.hitPattern().trackerLayersWithoutMeasurement(reco::HitPattern::TRACK_HITS) != 0) continue;
        passedMiddleHits = true;

        if (track.pfIsolationDR03().chargedHadronIso() / track.pt() >= 0.05) continue;
        passedIso = true;

        if (std::abs(track.dxy()) >= 0.02) continue;
        passedD0 = true;

        if (std::abs(track.dz()) >= 0.5) continue;
        passedDZ = true;

        // Add in the filter loop after the dz cut and layer cut, before the jet DR cut:
        double minDRJet = std::numeric_limits<double>::max();
        for (const auto& jet : *jets) {
            if (jet.pt() <= 30.0 || std::abs(jet.eta()) >= 4.5) continue;
            if (!passesJetID(jet)) continue;
            minDRJet = std::min(minDRJet, reco::deltaR(track, jet));
        }
        if (minDRJet <= minDeltaRJet_) continue;
        passedDRJet = true;

        const int nLayers = track.hitPattern().trackerLayersWithMeasurement();
        const bool passesLayers = useExclusive_ ? (nLayers == minLayers_) : (nLayers >= minLayers_);
        if (!passesLayers) continue;
        passedLayers = true;

        probeTracks->push_back(track);
    }

    const bool pass = !probeTracks->empty();
    iEvent.put(std::move(probeTracks), "probeTracks");

    CutflowFlags flags;
    flags.set("trackPt", passedPt);
    flags.set("trackEta", passedEta);
    flags.set("trackECAL", passedECAL);
    flags.set("trackEDT", passedEDT);
    flags.set("trackCSC", passedCSC);
    flags.set("trackTOB", passedTOB);
    flags.set("trackPixelHits", passedPixelHits);
    flags.set("trackValidHits", passedValidHits);
    flags.set("trackInnerHits", passedInnerHits);
    flags.set("trackMiddleHits", passedMiddleHits);
    flags.set("trackIso", passedIso);
    flags.set("trackD0", passedD0);
    flags.set("trackDZ", passedDZ);
    flags.set("trackDRJet", passedDRJet);
    flags.set("trackLayers", passedLayers);
    flags.put(iEvent, instanceLabel_);
    return passedLayers;
}

void ZtoProbeTrkTrackSelections::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("tracks",       edm::InputTag("isolatedTracks"));
    desc.add<edm::InputTag>("muons",        edm::InputTag("slimmedMuons"));
    desc.add<edm::InputTag>("electrons",    edm::InputTag("slimmedElectrons"));
    desc.add<edm::InputTag>("jets",         edm::InputTag("slimmedJets"));
    desc.add<double>       ("minPt",        30.0);
    desc.add<int>          ("minLayers",    5);
    desc.add<bool>         ("useExclusive", true);
    desc.add<double>       ("minDeltaRJet", 0.5);
    desc.add<std::string>  ("instanceLabel", "ZtoProbeTrk");
    descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(ZtoProbeTrkTrackSelections);
