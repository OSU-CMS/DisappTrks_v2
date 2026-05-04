#include "FWCore/Framework/interface/stream/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "TH1F.h"
#include <vector>
#include <string>
#include <map>
#include <cassert>

class CutflowAnalyzer : public edm::stream::EDAnalyzer<> {
public:
  explicit CutflowAnalyzer(const edm::ParameterSet&);
  ~CutflowAnalyzer() override = default;
  static void fillDescriptions(edm::ConfigurationDescriptions& descriptions);

private:
  void analyze(const edm::Event&, const edm::EventSetup&) override;

  struct CutStep {
    std::string label;        // bin label in histogram  e.g. "trackPt"
    std::string productName;  // full instance name      e.g. "ZtoProbeTrkTrackSelectionstrackPt"
    edm::EDGetTokenT<bool> token;
  };

  std::vector<CutStep> cutSteps_;
  TH1F* h_cutflow_;
};


CutflowAnalyzer::CutflowAnalyzer(const edm::ParameterSet& iConfig) {
  auto instanceLabels = iConfig.getParameter<std::vector<std::string>>("instanceLabels");
  auto flagNames      = iConfig.getParameter<std::vector<std::string>>("flagNames");

  assert(instanceLabels.size() == flagNames.size());

  edm::Service<TFileService> fs;
  int nCuts = instanceLabels.size();
  h_cutflow_ = fs->make<TH1F>("cutflow", "Cutflow; ; Events", nCuts, 0, nCuts);

  for (int i = 0; i < nCuts; ++i) {
    // No underscore — concatenate directly
    std::string productName = instanceLabels[i] + flagNames[i];

    CutStep step;
    step.label       = flagNames[i];
    step.productName = productName;
    step.token       = consumes<bool>(edm::InputTag(
                           instanceLabels[i],  // module label — the C++ class label in the Path
                           productName));       // instance name — no underscore

    cutSteps_.push_back(step);
    h_cutflow_->GetXaxis()->SetBinLabel(i + 1, flagNames[i].c_str());
  }
}


void CutflowAnalyzer::analyze(const edm::Event& iEvent, const edm::EventSetup&) {
  // Walk the ordered cut list — stop filling as soon as one fails
  // to keep the histogram cumulative
  for (int i = 0; i < (int)cutSteps_.size(); ++i) {
    edm::Handle<bool> flag;
    iEvent.getByToken(cutSteps_[i].token, flag);

    if (!flag.isValid() || !(*flag)) return;

    h_cutflow_->Fill(i + 0.5);
  }
}


void CutflowAnalyzer::fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;
  desc.add<std::vector<std::string>>("instanceLabels");
  desc.add<std::vector<std::string>>("flagNames");
  descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(CutflowAnalyzer);
