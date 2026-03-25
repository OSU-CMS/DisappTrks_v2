#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/one/EDFilter.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "DataFormats/PatCandidates/interface/Jet.h"

#include <memory>
#include <iostream>

#include "JvmConfigReader.h"
#include "JvmApplication.h"

class JvmAppliedEventFilter : public edm::one::EDFilter<edm::one::SharedResources> {
public:
  explicit JvmAppliedEventFilter(const edm::ParameterSet& iConfig);
  ~JvmAppliedEventFilter();

private:
  edm::ParameterSet                    configParamsJets_;
  edm::InputTag                        edmTagJetAK4_;
  std::string                          year_;
  edm::EDGetTokenT<pat::JetCollection> edmTokenJetAK4_;
  edm::FileInPath                      jvmConfigPath_;
  JvmApplication::VetoChecker          jvmChecker_;

  bool filter(edm::Event&, const edm::EventSetup&) override;
};

JvmAppliedEventFilter::JvmAppliedEventFilter(const edm::ParameterSet& iConfig)
  : configParamsJets_(iConfig.getParameter<edm::ParameterSet>("Jets")),
    edmTagJetAK4_(configParamsJets_.getParameter<edm::InputTag>("SourcesAK4")),
    year_(configParamsJets_.getParameter<std::string>("Year")),
    jvmConfigPath_(configParamsJets_.getParameter<edm::FileInPath>("JvmConfig")),
    jvmChecker_() {

    // Configure the JVM config singleton with the path from edm::FileInPath
    auto& jvmCfg = JvmConfigReader::JvmConfig::defaultInstance();
    jvmCfg.setConfigPath(jvmConfigPath_.fullPath(), /*reload=*/true);

    // Get the JVM for this year from the JSON config
    JvmConfigReader::Jvm jvm = jvmCfg.getJvmForYear(year_);
    if (jvm.use) {
        jvmChecker_.setJvm(jvm.ref, jvm.key);
    } else {
        std::cout << "[JvmAppliedEventFilter] No JVM entry for year \"" << year_
                  << "\" in config \"" << jvmConfigPath_.fullPath()
                  << "\". Filter will not veto any events.\n";
    }

    // Declare consumes using the EDFilter base API
    edmTokenJetAK4_ = consumes<pat::JetCollection>(edmTagJetAK4_);
}

JvmAppliedEventFilter::~JvmAppliedEventFilter() {}

bool JvmAppliedEventFilter::filter(edm::Event& iEvent, const edm::EventSetup& iSetup) {

    bool passEvent = true;
    try {
        edm::Handle<pat::JetCollection> iJets;
        iEvent.getByToken(edmTokenJetAK4_, iJets);

        if (iJets.isValid()) {
            for (const auto& jIt : *iJets) {
                if (jvmChecker_.checkJetInVetoRegion(
                        jIt.eta(),
                        jIt.phi(),
                        jIt.pt(),
                        /* jetId: NanoAOD TightLepVeto not always available in MiniAOD */
                        6,
                        jIt.chargedEmEnergyFraction(),
                        jIt.neutralEmEnergyFraction())) {

                    passEvent = false;
                    break; // No need to loop over the remaining jets.
                }
            }
        }
    } catch (std::exception const& e) {
        std::cout << "[JvmAppliedEventFilter] exception in filter -> "
                  << e.what() << std::endl;
        // Be conservative on exception: do not veto the event.
        return true;
    }
    return passEvent;
}

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(JvmAppliedEventFilter);

