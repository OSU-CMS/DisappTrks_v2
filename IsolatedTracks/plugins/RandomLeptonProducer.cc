#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Tau.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include <algorithm>
#include <random>

template <class T>
class RandomLeptonProducer : public edm::stream::EDProducer<> {
public:
  explicit RandomLeptonProducer(const edm::ParameterSet &iConfig)
      : leptonToken_(consumes<std::vector<T>>(
            iConfig.getParameter<edm::InputTag>("src"))) {
    produces<std::vector<T>>();
  }

  void produce(edm::Event &iEvent, const edm::EventSetup &iSetup) override {
    edm::Handle<std::vector<T>> leptons;
    iEvent.getByToken(leptonToken_, leptons);

    auto output = std::make_unique<std::vector<T>>(*leptons);

    std::shuffle(output->begin(), output->end(),
                 std::mt19937{std::random_device{}()});

    if (output->size() > 1)
      output->erase(output->begin() + 1, output->end());

    iEvent.put(std::move(output));
  }

private:
  const edm::EDGetTokenT<std::vector<T>> leptonToken_;
};

typedef RandomLeptonProducer<pat::Electron> RandomElectronProducer;
typedef RandomLeptonProducer<pat::Muon> RandomMuonProducer;
typedef RandomLeptonProducer<pat::Tau> RandomTauProducer;

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(RandomElectronProducer);
DEFINE_FWK_MODULE(RandomMuonProducer);
DEFINE_FWK_MODULE(RandomTauProducer);
