// -*- C++ -*-
//
// Package:    DisappTrks_v2/BkgdEstimation
// Class:      ElectronMETTransMassFilter
//
// Selects events where at least one tag-quality electron has
// transverse mass M_T(e, MET) < maxTransMass.
// This suppresses W+jets events where the electron has large M_T.
//
 
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/stream/EDFilter.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/Utilities/interface/StreamID.h"
 
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/MET.h"
#include "DataFormats/Math/interface/deltaPhi.h"
 
#include <cmath>

class ElectronMETTransMassFilter : public edm::stream::EDFilter<> {
public:
    explicit ElectronMETTransMassFilter(const edm::ParameterSet& iConfig)
        : electronToken_(consumes<std::vector<pat::Electron>>(iConfig.getParameter<edm::InputTag>("electrons"))),
          metToken_     (consumes<std::vector<pat::MET>>     (iConfig.getParameter<edm::InputTag>("mets"))),
          maxTransMass_ (iConfig.getParameter<double>("maxTransMass")) {}

    bool filter(edm::Event& iEvent, const edm::EventSetup&) override {
        edm::Handle<std::vector<pat::Electron>> electrons;
        edm::Handle<std::vector<pat::MET>>      mets;
        iEvent.getByToken(electronToken_, electrons);
        iEvent.getByToken(metToken_,      mets);

        const pat::MET &met = mets->at(0);
        for (const auto &electron : *electrons) {
            double dPhi = deltaPhi(electron.phi(), met.phi());
            double mt = sqrt(2.0 * electron.pt() * met.pt() * (1.0 - cos(dPhi)));
            if (mt < maxTransMass_) return true;
        }
        return false;
    }
private:
    edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;
    edm::EDGetTokenT<std::vector<pat::MET>>      metToken_;
    const double maxTransMass_;
};


DEFINE_FWK_MODULE(ElectronMETTransMassFilter);
