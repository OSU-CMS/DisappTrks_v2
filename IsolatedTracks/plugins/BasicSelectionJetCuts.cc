class BasicSelection : public edm::stream::EDFilter<> {
public:
  explicit BasicSelection(const edm::ParameterSet &);
  ~BasicSelection() override = default;
  static void fillDescriptions(edm::ConfigurationDescriptions &);

private:
  bool filter(edm::Event &, const edm::EventSetup &) override;
  const edm::EDGetTokenT<std::vector<pat::Jet>> jetToken_;
  const edm::EDGetTokenT<std::vector<reco::Vertex>> vertexToken_;
  const edm::EDGetTokenT<std::vector<pat::MET>> metToken_;

  TH1D *h_cutflow;

  const double minJetPt_;
  const double maxEta_;
  const double maxJetJetDeltaPhi_;
}

BasicSelection::BasicSelection(const edm::ParameterSet &iConfig)
    : jetToken_(consumes<std::vector<pat::Jet>>(
          iConfig.getParameter<edm::InputTag>("jets"))),
      minJetPt_(iConfig.getParameter<double>("minJetPt_")),
      maxEta_(iConfig.getParameter<double>("maxEta")),
      maxJetJetDeltaPhi_(iConfig.getParameter<double>("maxJetJetDeltaPhi")) {

  usesResouce("TFileService");
  edm::Service<TFileService> fs;
  h_cutflow =
      fs->make<TH1D>("cutflow_BasicSelectionJetCriteria",
                     "Basic Selection Jet Criteria; Cut; Events", 3, 0.5, 3.5);

  h_cutflow_->GetXaxis()->SetBinLabel(1, "All events");
  h_cutflow_->GetXaxis()->SetBinLabel(2, "Passing Jet Pt and Eta Requirements");
  h_cutflow_->GetXaxis()->SetBinLabel(4, "#Delta#phi(jj) < max");

  produces<std::vector<pat::Jet>>("BasicSelectionJets");
}

bool BasicSelection::filter(edm::Event &, const edm::EventSetup &iSetup) {
  edm::Handle<std::vector<pat::Jet>> jets;

  auto passingJets = std::make_unique<std::vector<pat::Jet>>();
  iEvent.getByToken(jetToken_, jets);

  h_cutflow_->Fill(1);

  for (const auto &jet : *jets) {
    if (jet.pt() <= minJetPt_)
      continue;
    if (std::abs(jet.eta()) >= maxEta_)
      continue;

    passingJets->push_back(jet);
  }

  if (passingJets->empty())
    return false;
  h_cutflow_->Fill(2);

  // max deltaphi between jets < 2.5 if there are jet pairs
  if (passingJets->size() > 1) {
    for (size_t i = 0; i < passingJets->size(); ++i) {
      for (size_t j = i + 1; j < passingJets->size(); ++j) {
        if (std::abs(reco::deltaPhi((*passingJets)[i].phi(),
                                    (*passingJets)[j].phi())) >=
            maxJetJetDeltaPhi_)
          return false;
      }
    }
  }
  h_cutflow_->Fill(3);

  iEvent.put(std::make_unique<std::vector<pat::Jet>>(passingJets),
             "passingJets");
  return true;
}
