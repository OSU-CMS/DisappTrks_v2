// ─────────────────────────────────────────────────────────────────────────────
// TrackFiducialFilter.cc  —  EDFilter + Producer
//
// Accepts events with at least one isolated track that does NOT point into any
// fiducial veto region derived from a set of TH2D histograms on disk, and
// puts a filtered collection of those passing tracks into the event under the
// instance label "fiducialTracks".
//
// Downstream filters should consume:
//   cms.InputTag("<moduleLabel>", "fiducialTracks")
// so that every subsequent cut acts on the same track objects that survived
// this veto.
//
// The veto-region algorithm is identical to
// OSUGenericTrackProducer::extractFiducialMap:
//
//   1. Compute mean inefficiency across all non-empty (eta,phi) bins:
//        meanIneff = sum(afterVeto) / sum(beforeVeto)
//
//   2. Divide afterVeto by beforeVeto bin-by-bin to get per-bin efficiency.
//      Compute the standard deviation of those values.
//
//   3. Any bin whose efficiency exceeds
//        meanIneff + thresholdForVeto * stdDevIneff
//      is a hot spot.  Its (eta, phi) bin centre is added to the veto list.
//
//   4. The veto radius is the diagonal half-width of a bin:
//        minDeltaR = hypot(binWidthEta/2, binWidthPhi/2)
//
//   5. A track is vetoed if dR(track, hotSpot) < minDeltaR for any hot spot.
//
// Intended usage
// ──────────────
// Run two instances in the path, each consuming the output of the previous:
//
//   process.TrackElectronFiducialFilter = cms.EDFilter("TrackFiducialFilter",
//       tracks = cms.InputTag("TagAndProbe", "probeTracks"), ...)
//
//   process.TrackMuonFiducialFilter = cms.EDFilter("TrackFiducialFilter",
//       tracks = cms.InputTag("TrackElectronFiducialFilter", "fiducialTracks"), ...)
//
// Configuration
// ─────────────
//   tracks                  — InputTag for pat::IsolatedTrack collection
//   fiducialMaps            — VPSet, each entry:
//       histFile              FileInPath to ROOT file
//       era                   string appended to hist names when useEraByEra=true
//       beforeVetoHistName    TH2D name before the veto
//       afterVetoHistName     TH2D name after the veto
//       thresholdForVeto      sigma above mean to declare a hot spot
//   useEraByEraFiducialMaps — bool, whether to append era to histogram names
//   generatorWeights        — optional GenEventInfoProduct tag (MC only)
// ─────────────────────────────────────────────────────────────────────────────

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "TFile.h"
#include "TH2D.h"

#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "DataFormats/Math/interface/deltaR.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDFilter.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/FileInPath.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/ServiceRegistry/interface/Service.h"
#include "SimDataFormats/GeneratorProducts/interface/GenEventInfoProduct.h"
#include "TH1D.h"

namespace {

struct EtaPhi {
    double eta, phi, sigma;
    double halfBinEta, halfBinPhi;
    EtaPhi(double e, double p, double s, double hbe, double hbp)
        : eta(e), phi(p), sigma(s), halfBinEta(hbe), halfBinPhi(hbp) {}
};

  struct EtaPhiList : public std::vector<EtaPhi> {
    double minDeltaR = 0.0;
  };

  // ── extractFiducialMap ─────────────────────────────────────────────────────
  void extractFiducialMap(const edm::ParameterSet& cfg,
                           bool useEraByEra,
                           EtaPhiList& vetoList,
                           std::stringstream& ss) {
    const edm::FileInPath& histFile   = cfg.getParameter<edm::FileInPath>("histFile");
    const std::string&     era        = cfg.getParameter<std::string>("era");
    const std::string      beforeName = cfg.getParameter<std::string>("beforeVetoHistName")
                                        + (useEraByEra ? era : "");
    const std::string      afterName  = cfg.getParameter<std::string>("afterVetoHistName")
                                        + (useEraByEra ? era : "");
    const double           threshold  = cfg.getParameter<double>("thresholdForVeto");

    ss << "================================================================================\n"
       << "extracting histograms from \"" << histFile.relativePath() << "\"\n"
       << "  before: " << beforeName << "\n"
       << "  after:  " << afterName  << "\n"
       << "--------------------------------------------------------------------------------\n";

    TFile* fin = TFile::Open(histFile.fullPath().c_str());
    if (!fin || fin->IsZombie()) {
      edm::LogWarning("TrackFiducialFilter")
          << "Cannot open \"" << histFile.fullPath() << "\". Skipping map.";
      return;
    }

    TH2D* beforeHist = dynamic_cast<TH2D*>(fin->Get(beforeName.c_str()));
    TH2D* afterHist  = dynamic_cast<TH2D*>(fin->Get(afterName.c_str()));

    if (!beforeHist) {
      edm::LogWarning("TrackFiducialFilter")
          << "Histogram \"" << beforeName << "\" not found. Skipping map.";
      fin->Close(); delete fin; return;
    }
    if (!afterHist) {
      edm::LogWarning("TrackFiducialFilter")
          << "Histogram \"" << afterName << "\" not found. Skipping map.";
      fin->Close(); delete fin; return;
    }

    beforeHist->SetDirectory(nullptr);
    afterHist->SetDirectory(nullptr);
    fin->Close();
    delete fin;

    const int nX = beforeHist->GetXaxis()->GetNbins();
    const int nY = beforeHist->GetYaxis()->GetNbins();

    double totalBefore = 0.0, totalAfter = 0.0;
    int    nBinsWithTags = 0;

    std::cout << "X Bin Width: " << beforeHist->GetXaxis()->GetBinWidth(0) << std::endl;
    std::cout << "Y Bin Width: " << beforeHist->GetYaxis()->GetBinWidth(0) << std::endl;
    for (int i = 1; i <= nX; ++i) {
      for (int j = 1; j <= nY; ++j) {
        const double binRadius = std::hypot(
            0.5 * beforeHist->GetXaxis()->GetBinWidth(i),
            0.5 * beforeHist->GetYaxis()->GetBinWidth(j));
        if (vetoList.minDeltaR < binRadius) vetoList.minDeltaR = binRadius;

        const double contentBefore = beforeHist->GetBinContent(i, j);
        if (contentBefore == 0.0) continue;

        ++nBinsWithTags;
        totalBefore += contentBefore;
        totalAfter  += afterHist->GetBinContent(i, j);
      }
    }

    if (totalBefore == 0.0) {
      edm::LogWarning("TrackFiducialFilter") << "beforeVeto histogram is empty. Skipping map.";
      delete beforeHist; delete afterHist;
      return;
    }
    const double meanIneff = totalAfter / totalBefore;

    afterHist->Divide(beforeHist);

    double stdDevIneff = 0.0;
    for (int i = 1; i <= nX; ++i) {
      for (int j = 1; j <= nY; ++j) {
        if (beforeHist->GetBinContent(i, j) == 0.0) continue;
        const double diff = afterHist->GetBinContent(i, j) - meanIneff;
        stdDevIneff += diff * diff;
      }
    }
    if (nBinsWithTags < 2) stdDevIneff = 0.0;
    else {
      stdDevIneff /= (nBinsWithTags - 1);
      stdDevIneff  = std::sqrt(stdDevIneff);
    }

    for (int i = 1; i <= nX; ++i) {
      for (int j = 1; j <= nY; ++j) {
        const double content = afterHist->GetBinContent(i, j);
        if (!content) continue;

        const double eta   = afterHist->GetXaxis()->GetBinCenter(i);
        const double phi   = afterHist->GetYaxis()->GetBinCenter(j);
        const double sigma = (stdDevIneff > 0.0)
            ? (content - meanIneff) / stdDevIneff : 0.0;

        ss << "(" << std::setw(10) << eta
           << ", " << std::setw(10) << phi
           << "): " << std::setw(10) << sigma
           << " sigma above mean of " << std::setw(10) << meanIneff;

        if ((content - meanIneff) > threshold * stdDevIneff) {
            const double halfBinEta = 0.5 * afterHist->GetXaxis()->GetBinWidth(i);
            const double halfBinPhi = 0.5 * afterHist->GetYaxis()->GetBinWidth(j);
            vetoList.emplace_back(eta, phi, sigma, halfBinEta, halfBinPhi);
            ss << "  * HOT SPOT *";
        }
        ss << "\n";
      }
    }

    delete beforeHist;
    delete afterHist;
  }

bool isVetoed(double eta, double phi, const EtaPhiList& vetoList, double minDeltaR) {
    const double minDR = std::max(minDeltaR, vetoList.minDeltaR);
    for (const auto& hotSpot : vetoList) {
      if (deltaR (eta, phi, hotSpot.eta, hotSpot.phi) < minDR) return true;
    }
    return false ;
}

}  // namespace

// ─────────────────────────────────────────────────────────────────────────────
class TrackFiducialFilter
    : public edm::one::EDFilter<edm::one::SharedResources> {
public:
  explicit TrackFiducialFilter(const edm::ParameterSet&);
  static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
  bool filter(edm::Event&, const edm::EventSetup&) override;

  const edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> tracksToken_;
  edm::EDGetTokenT<GenEventInfoProduct>                   genWeightToken_;
  const bool                                              useGenWeights_;

  EtaPhiList vetoList_;
  const double minDeltaR_;

  TH1D* hCutflow_{nullptr};
};

// ─────────────────────────────────────────────────────────────────────────────
TrackFiducialFilter::TrackFiducialFilter(const edm::ParameterSet& iConfig)
    : tracksToken_(consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      useGenWeights_(iConfig.exists("generatorWeights")),
      minDeltaR_(iConfig.getParameter<double>("minDeltaR"))
{
  usesResource("TFileService");

  // Declare the output collection under the instance label "fiducialTracks".
  // Downstream filters consume cms.InputTag("<moduleLabel>", "fiducialTracks").
  produces<std::vector<pat::IsolatedTrack>>("fiducialTracks");

  if (useGenWeights_)
    genWeightToken_ = consumes<GenEventInfoProduct>(
        iConfig.getParameter<edm::InputTag>("generatorWeights"));

  const bool useEraByEra =
      iConfig.getParameter<bool>("useEraByEraFiducialMaps");

  std::stringstream ss;
  const auto& maps =
      iConfig.getParameter<std::vector<edm::ParameterSet>>("fiducialMaps");
  for (const auto& mapCfg : maps)
    extractFiducialMap(mapCfg, useEraByEra, vetoList_, ss);

  std::sort(vetoList_.begin(), vetoList_.end(),
            [](const EtaPhi& a, const EtaPhi& b) {
              return a.eta < b.eta || (a.eta == b.eta && a.phi < b.phi);
            });

  ss << "================================================================================\n"
     << "veto regions (eta, phi, sigma)\n"
     << "--------------------------------------------------------------------------------\n";
  for (const auto& v : vetoList_)
    ss << "  (" << std::setw(10) << v.eta
       << ", " << std::setw(10) << v.phi
       << ", " << std::setw(10) << v.sigma << " sigma)\n";
  ss << "================================================================================";
  edm::LogPrint("TrackFiducialFilter") << ss.str();

  const std::string label =
      iConfig.getParameter<std::string>("@module_label");
  edm::Service<TFileService> fs;
  hCutflow_ = fs->make<TH1D>(
      ("cutflow_" + label).c_str(),
      (label + ";Cut;Events").c_str(),
      2, 0.5, 2.5);
  hCutflow_->Sumw2();
  hCutflow_->GetXaxis()->SetBinLabel(1, "Reached");
  hCutflow_->GetXaxis()->SetBinLabel(2, "Passed");
}

// ─────────────────────────────────────────────────────────────────────────────
bool TrackFiducialFilter::filter(edm::Event& iEvent,
                                  const edm::EventSetup&) {
  double w = 1.0;
  if (useGenWeights_) {
    edm::Handle<GenEventInfoProduct> genInfo;
    iEvent.getByToken(genWeightToken_, genInfo);
    if (genInfo.isValid()) w = genInfo->weight();
  }

  edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
  iEvent.getByToken(tracksToken_, tracks);

  hCutflow_->Fill(1, w);  // Reached

  auto fiducialTracks = std::make_unique<std::vector<pat::IsolatedTrack>>();
  // Assume the bin width is constant:
  for (const auto& track : *tracks) {
    if (isVetoed(track.eta(), track.phi(), vetoList_, minDeltaR_ )) continue;
    fiducialTracks->push_back(track);
  }

  const bool pass = !fiducialTracks->empty();
  if (pass) hCutflow_->Fill(2, w);  // Passed

  // Always put the collection so downstream modules can consume unconditionally.
  iEvent.put(std::move(fiducialTracks), "fiducialTracks");

  return true;
}

// ─────────────────────────────────────────────────────────────────────────────
void TrackFiducialFilter::fillDescriptions(
    edm::ConfigurationDescriptions& descriptions) {
  edm::ParameterSetDescription desc;

  desc.add<edm::InputTag>("tracks", edm::InputTag("isolatedTracks"));
  desc.add<bool>("useEraByEraFiducialMaps", false);
  desc.add<double>("minDeltaR", 0.05);

  edm::ParameterSetDescription mapDesc;
  mapDesc.add<edm::FileInPath>("histFile");
  mapDesc.add<std::string>("era", "");
  mapDesc.add<std::string>("beforeVetoHistName");
  mapDesc.add<std::string>("afterVetoHistName");
  mapDesc.add<double>("thresholdForVeto", 2.0);

  desc.addVPSet("fiducialMaps", mapDesc, std::vector<edm::ParameterSet>{});
  desc.addOptional<edm::InputTag>("generatorWeights", edm::InputTag("generator"));

  descriptions.addWithDefaultLabel(desc);
}

DEFINE_FWK_MODULE(TrackFiducialFilter);
