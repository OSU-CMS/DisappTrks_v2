// ── Includes ─────────────────────────────────────────────────────────────────
#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ServiceRegistry/interface/Service.h"

// PAT objects
#include "DataFormats/PatCandidates/interface/Electron.h"
#include "DataFormats/PatCandidates/interface/IsolatedTrack.h"
#include "DataFormats/PatCandidates/interface/Jet.h"
#include "DataFormats/PatCandidates/interface/MET.h"
#include "DataFormats/PatCandidates/interface/Muon.h"
#include "DataFormats/PatCandidates/interface/Tau.h"
#include "DataFormats/VertexReco/interface/Vertex.h"
// Math utilities
#include "DataFormats/Math/interface/deltaPhi.h"
#include "DataFormats/Math/interface/deltaR.h"

// ROOT
#include "TTree.h"

#include <cmath>
#include <string>
#include <vector>

// ── Branch-group helpers
// ──────────────────────────────────────────────────────
namespace {

struct VertexBranches {
  std::vector<float> x, y, z;
  std::vector<float> xError, yError, zError;
  std::vector<float> chi2, normalizedChi2;
  std::vector<int>   ndof, nTracks;
  std::vector<bool>  isValid, isFake;

  void book(TTree *t, const std::string &pfx) {
    t->Branch((pfx + "_x").c_str(),             &x);
    t->Branch((pfx + "_y").c_str(),             &y);
    t->Branch((pfx + "_z").c_str(),             &z);
    t->Branch((pfx + "_xError").c_str(),        &xError);
    t->Branch((pfx + "_yError").c_str(),        &yError);
    t->Branch((pfx + "_zError").c_str(),        &zError);
    t->Branch((pfx + "_chi2").c_str(),          &chi2);
    t->Branch((pfx + "_normalizedChi2").c_str(),&normalizedChi2);
    t->Branch((pfx + "_ndof").c_str(),          &ndof);
    t->Branch((pfx + "_nTracks").c_str(),       &nTracks);
    t->Branch((pfx + "_isValid").c_str(),       &isValid);
    t->Branch((pfx + "_isFake").c_str(),        &isFake);
  }
  void clear() {
    x.clear(); y.clear(); z.clear();
    xError.clear(); yError.clear(); zError.clear();
    chi2.clear(); normalizedChi2.clear();
    ndof.clear(); nTracks.clear();
    isValid.clear(); isFake.clear();
  }
};

struct LepKin {
  std::vector<float> pt, eta, phi;
  std::vector<int> charge;

  void book(TTree *t, const std::string &pfx) {
    t->Branch((pfx + "_pt").c_str(), &pt);
    t->Branch((pfx + "_eta").c_str(), &eta);
    t->Branch((pfx + "_phi").c_str(), &phi);
    t->Branch((pfx + "_charge").c_str(), &charge);
  }
  void clear() {
    pt.clear();
    eta.clear();
    phi.clear();
    charge.clear();
  }
};

struct LepKinMinimal {
  std::vector<float> pt, eta, phi;
  std::vector<int> charge;

  void book(TTree *t, const std::string &pfx) {
    t->Branch((pfx + "_pt").c_str(), &pt);
    t->Branch((pfx + "_eta").c_str(), &eta);
    t->Branch((pfx + "_phi").c_str(), &phi);
    t->Branch((pfx + "_charge").c_str(), &charge);
  }
  void clear() {
    pt.clear();
    eta.clear();
    phi.clear();
    charge.clear();
  }
};

struct TrkBranches {
  // ── Kinematics & track parameters ────────────────────────────────────────
  std::vector<float> pt, eta, phi, dxy, dxyError, dz, dzError;
  std::vector<int> charge, fromPV;
  std::vector<float> deltaEta, deltaPhi;
  // ── Track quality flags ───────────────────────────────────────────────────
  std::vector<bool> isHighPurityTrack, isTightTrack, isLooseTrack;

  // ── dE/dx & calo ─────────────────────────────────────────────────────────
  std::vector<float> dEdxStrip, dEdxPixel;
  std::vector<float> caloEm, caloHad, caloTotal;
  std::vector<std::vector<uint16_t>> crossedEcalStatus;
  std::vector<std::vector<uint32_t>> crossedHcalStatus;

  // ── Isolation ─────────────────────────────────────────────────────────────
  std::vector<float> pfIso, relativePFIso;
  // DR03 PF isolation components
  std::vector<float> pfIso_chHad, pfIso_neutHad, pfIso_photon, pfIso_puChHad;
  // mini PF isolation components
  std::vector<float> miniIso_chHad, miniIso_neutHad, miniIso_photon,
      miniIso_puChHad;
  std::vector<float> miniIso_relative;

  // ── Derived ───────────────────────────────────────────────────────────────
  std::vector<float> dPhiMet, dPhiMetNoMu, ptOverMetNoMu;
  // ══ HitPattern ═══════════════════════════════════════════════════════════
  // ── All hits (TRACK_HITS category) ───────────────────────────────────────
  std::vector<int> hp_numberOfAllHits;
  std::vector<int> hp_numberOfAllTrackerHits;

  // ── Valid hit counts ──────────────────────────────────────────────────────
  std::vector<int> hp_numberOfValidHits;
  std::vector<int> hp_numberOfValidTrackerHits;
  std::vector<int> hp_numberOfValidPixelHits;
  std::vector<int> hp_numberOfValidPixelBarrelHits;
  std::vector<int> hp_numberOfValidPixelEndcapHits;
  std::vector<int> hp_numberOfValidStripHits;
  std::vector<int> hp_numberOfValidStripTIBHits;
  std::vector<int> hp_numberOfValidStripTIDHits;
  std::vector<int> hp_numberOfValidStripTOBHits;
  std::vector<int> hp_numberOfValidStripTECHits;

  // ── Lost/missing hit counts (3 categories each) ───────────────────────────
  // TRACK_HITS = hits missing on the track body itself
  // MISSING_INNER_HITS = expected hits before first valid hit
  // MISSING_OUTER_HITS = expected hits after last valid hit
  std::vector<int> hp_numberOfLostHits_TRACK;
  std::vector<int> hp_numberOfLostHits_INNER;
  std::vector<int> hp_numberOfLostHits_OUTER;

  std::vector<int> hp_numberOfLostTrackerHits_TRACK;
  std::vector<int> hp_numberOfLostTrackerHits_INNER;
  std::vector<int> hp_numberOfLostTrackerHits_OUTER;

  std::vector<int> hp_numberOfLostPixelHits_TRACK;
  std::vector<int> hp_numberOfLostPixelHits_INNER;
  std::vector<int> hp_numberOfLostPixelHits_OUTER;

  std::vector<int> hp_numberOfLostPixelBarrelHits_TRACK;
  std::vector<int> hp_numberOfLostPixelBarrelHits_INNER;
  std::vector<int> hp_numberOfLostPixelBarrelHits_OUTER;

  std::vector<int> hp_numberOfLostPixelEndcapHits_TRACK;
  std::vector<int> hp_numberOfLostPixelEndcapHits_INNER;
  std::vector<int> hp_numberOfLostPixelEndcapHits_OUTER;

  std::vector<int> hp_numberOfLostStripHits_TRACK;
  std::vector<int> hp_numberOfLostStripHits_INNER;
  std::vector<int> hp_numberOfLostStripHits_OUTER;

  std::vector<int> hp_numberOfLostStripTIBHits_TRACK;
  std::vector<int> hp_numberOfLostStripTIDHits_TRACK;
  std::vector<int> hp_numberOfLostStripTOBHits_TRACK;
  std::vector<int> hp_numberOfLostStripTECHits_TRACK;

  // ── Inactive hit counts ───────────────────────────────────────────────────
  std::vector<int> hp_numberOfInactiveHits;
  std::vector<int> hp_numberOfInactiveTrackerHits;

  // ── Layers WITH measurement ───────────────────────────────────────────────
  std::vector<int> hp_trackerLayersWithMeasurement;
  std::vector<int> hp_pixelLayersWithMeasurement;
  std::vector<int> hp_stripLayersWithMeasurement;
  std::vector<int> hp_pixelBarrelLayersWithMeasurement;
  std::vector<int> hp_pixelEndcapLayersWithMeasurement;
  std::vector<int> hp_stripTIBLayersWithMeasurement;
  std::vector<int> hp_stripTIDLayersWithMeasurement;
  std::vector<int> hp_stripTOBLayersWithMeasurement;
  std::vector<int> hp_stripTECLayersWithMeasurement;

  // ── Layers WITHOUT measurement (3 categories each) ────────────────────────
  std::vector<int> hp_trackerLayersWithoutMeasurement_TRACK;
  std::vector<int> hp_trackerLayersWithoutMeasurement_INNER;
  std::vector<int> hp_trackerLayersWithoutMeasurement_OUTER;

  std::vector<int> hp_pixelLayersWithoutMeasurement_TRACK;
  std::vector<int> hp_pixelLayersWithoutMeasurement_INNER;
  std::vector<int> hp_pixelLayersWithoutMeasurement_OUTER;

  std::vector<int> hp_stripLayersWithoutMeasurement_TRACK;
  std::vector<int> hp_stripLayersWithoutMeasurement_INNER;
  std::vector<int> hp_stripLayersWithoutMeasurement_OUTER;

  std::vector<int> hp_pixelBarrelLayersWithoutMeasurement_TRACK;
  std::vector<int> hp_pixelEndcapLayersWithoutMeasurement_TRACK;
  std::vector<int> hp_stripTIBLayersWithoutMeasurement_TRACK;
  std::vector<int> hp_stripTIDLayersWithoutMeasurement_TRACK;
  std::vector<int> hp_stripTOBLayersWithoutMeasurement_TRACK;
  std::vector<int> hp_stripTECLayersWithoutMeasurement_TRACK;

  // ── Layers totally OFF or BAD ─────────────────────────────────────────────
  std::vector<int> hp_trackerLayersTotallyOffOrBad;
  std::vector<int> hp_pixelLayersTotallyOffOrBad;
  std::vector<int> hp_stripLayersTotallyOffOrBad;
  std::vector<int> hp_pixelBarrelLayersTotallyOffOrBad;
  std::vector<int> hp_pixelEndcapLayersTotallyOffOrBad;
  std::vector<int> hp_stripTIBLayersTotallyOffOrBad;
  std::vector<int> hp_stripTIDLayersTotallyOffOrBad;
  std::vector<int> hp_stripTOBLayersTotallyOffOrBad;
  std::vector<int> hp_stripTECLayersTotallyOffOrBad;

  // ── Layers NULL (track outside acceptance) ────────────────────────────────
  std::vector<int> hp_trackerLayersNull;
  std::vector<int> hp_pixelLayersNull;
  std::vector<int> hp_stripLayersNull;

  // ── Pixel layer validity ──────────────────────────────────────────────────
  std::vector<bool> hp_hasValidHitInPixelLayer; // PXB layer 1

  // ── Mono+stereo strip layers ──────────────────────────────────────────────
  std::vector<int> hp_numberOfValidStripLayersWithMonoAndStereo;
  std::vector<int> hp_numberOfValidTIBLayersWithMonoAndStereo;
  std::vector<int> hp_numberOfValidTIDLayersWithMonoAndStereo;
  std::vector<int> hp_numberOfValidTOBLayersWithMonoAndStereo;
  std::vector<int> hp_numberOfValidTECLayersWithMonoAndStereo;

  // ─────────────────────────────────────────────────────────────────────────
  void book(TTree *t, const std::string &pfx) {
    // kinematics
    t->Branch((pfx + "_pt").c_str(), &pt);
    t->Branch((pfx + "_eta").c_str(), &eta);
    t->Branch((pfx + "_phi").c_str(), &phi);
    t->Branch((pfx + "_dxy").c_str(), &dxy);
    t->Branch((pfx + "_dxyError").c_str(), &dxyError);
    t->Branch((pfx + "_dz").c_str(), &dz);
    t->Branch((pfx + "_dzError").c_str(), &dzError);
    t->Branch((pfx + "_charge").c_str(), &charge);
    t->Branch((pfx + "_fromPV").c_str(), &fromPV);
    t->Branch((pfx + "_deltaEta").c_str(), &deltaEta);
    t->Branch((pfx + "_deltaPhi").c_str(), &deltaPhi);
    // quality
    t->Branch((pfx + "_isHighPurityTrack").c_str(), &isHighPurityTrack);
    t->Branch((pfx + "_isTightTrack").c_str(), &isTightTrack);
    t->Branch((pfx + "_isLooseTrack").c_str(), &isLooseTrack);
    // dEdx & calo
    t->Branch((pfx + "_dEdxStrip").c_str(), &dEdxStrip);
    t->Branch((pfx + "_dEdxPixel").c_str(), &dEdxPixel);
    t->Branch((pfx + "_caloEm").c_str(), &caloEm);
    t->Branch((pfx + "_caloHad").c_str(), &caloHad);
    t->Branch((pfx + "_caloTotal").c_str(), &caloTotal);
    t->Branch((pfx + "_crossedEcalStatus").c_str(), &crossedEcalStatus);
    t->Branch((pfx + "_crossedHcalStatus").c_str(), &crossedHcalStatus);
    // DR03 PF isolation
    t->Branch((pfx + "_pfIso").c_str(), &pfIso);
    t->Branch((pfx + "_relativePFIso").c_str(), &relativePFIso);
    t->Branch((pfx + "_pfIso_chHad").c_str(), &pfIso_chHad);
    t->Branch((pfx + "_pfIso_neutHad").c_str(), &pfIso_neutHad);
    t->Branch((pfx + "_pfIso_photon").c_str(), &pfIso_photon);
    t->Branch((pfx + "_pfIso_puChHad").c_str(), &pfIso_puChHad);
    // mini PF isolation
    t->Branch((pfx + "_miniIso_chHad").c_str(), &miniIso_chHad);
    t->Branch((pfx + "_miniIso_neutHad").c_str(), &miniIso_neutHad);
    t->Branch((pfx + "_miniIso_photon").c_str(), &miniIso_photon);
    t->Branch((pfx + "_miniIso_puChHad").c_str(), &miniIso_puChHad);
    t->Branch((pfx + "_miniIso_relative").c_str(), &miniIso_relative);
    // derived
    t->Branch((pfx + "_dPhiMet").c_str(), &dPhiMet);
    t->Branch((pfx + "_dPhiMetNoMu").c_str(), &dPhiMetNoMu);
    t->Branch((pfx + "_ptOverMetNoMu").c_str(), &ptOverMetNoMu);

    // ── HitPattern ──────────────────────────────────────────────────────────
    t->Branch((pfx + "_hp_numberOfAllHits").c_str(), &hp_numberOfAllHits);
    t->Branch((pfx + "_hp_numberOfAllTrackerHits").c_str(),
              &hp_numberOfAllTrackerHits);

    t->Branch((pfx + "_hp_numberOfValidHits").c_str(), &hp_numberOfValidHits);
    t->Branch((pfx + "_hp_numberOfValidTrackerHits").c_str(),
              &hp_numberOfValidTrackerHits);
    t->Branch((pfx + "_hp_numberOfValidPixelHits").c_str(),
              &hp_numberOfValidPixelHits);
    t->Branch((pfx + "_hp_numberOfValidPixelBarrelHits").c_str(),
              &hp_numberOfValidPixelBarrelHits);
    t->Branch((pfx + "_hp_numberOfValidPixelEndcapHits").c_str(),
              &hp_numberOfValidPixelEndcapHits);
    t->Branch((pfx + "_hp_numberOfValidStripHits").c_str(),
              &hp_numberOfValidStripHits);
    t->Branch((pfx + "_hp_numberOfValidStripTIBHits").c_str(),
              &hp_numberOfValidStripTIBHits);
    t->Branch((pfx + "_hp_numberOfValidStripTIDHits").c_str(),
              &hp_numberOfValidStripTIDHits);
    t->Branch((pfx + "_hp_numberOfValidStripTOBHits").c_str(),
              &hp_numberOfValidStripTOBHits);
    t->Branch((pfx + "_hp_numberOfValidStripTECHits").c_str(),
              &hp_numberOfValidStripTECHits);

    t->Branch((pfx + "_hp_numberOfLostHits_TRACK").c_str(),
              &hp_numberOfLostHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostHits_INNER").c_str(),
              &hp_numberOfLostHits_INNER);
    t->Branch((pfx + "_hp_numberOfLostHits_OUTER").c_str(),
              &hp_numberOfLostHits_OUTER);

    t->Branch((pfx + "_hp_numberOfLostTrackerHits_TRACK").c_str(),
              &hp_numberOfLostTrackerHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostTrackerHits_INNER").c_str(),
              &hp_numberOfLostTrackerHits_INNER);
    t->Branch((pfx + "_hp_numberOfLostTrackerHits_OUTER").c_str(),
              &hp_numberOfLostTrackerHits_OUTER);

    t->Branch((pfx + "_hp_numberOfLostPixelHits_TRACK").c_str(),
              &hp_numberOfLostPixelHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostPixelHits_INNER").c_str(),
              &hp_numberOfLostPixelHits_INNER);
    t->Branch((pfx + "_hp_numberOfLostPixelHits_OUTER").c_str(),
              &hp_numberOfLostPixelHits_OUTER);

    t->Branch((pfx + "_hp_numberOfLostPixelBarrelHits_TRACK").c_str(),
              &hp_numberOfLostPixelBarrelHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostPixelBarrelHits_INNER").c_str(),
              &hp_numberOfLostPixelBarrelHits_INNER);
    t->Branch((pfx + "_hp_numberOfLostPixelBarrelHits_OUTER").c_str(),
              &hp_numberOfLostPixelBarrelHits_OUTER);

    t->Branch((pfx + "_hp_numberOfLostPixelEndcapHits_TRACK").c_str(),
              &hp_numberOfLostPixelEndcapHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostPixelEndcapHits_INNER").c_str(),
              &hp_numberOfLostPixelEndcapHits_INNER);
    t->Branch((pfx + "_hp_numberOfLostPixelEndcapHits_OUTER").c_str(),
              &hp_numberOfLostPixelEndcapHits_OUTER);

    t->Branch((pfx + "_hp_numberOfLostStripHits_TRACK").c_str(),
              &hp_numberOfLostStripHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostStripHits_INNER").c_str(),
              &hp_numberOfLostStripHits_INNER);
    t->Branch((pfx + "_hp_numberOfLostStripHits_OUTER").c_str(),
              &hp_numberOfLostStripHits_OUTER);

    t->Branch((pfx + "_hp_numberOfLostStripTIBHits_TRACK").c_str(),
              &hp_numberOfLostStripTIBHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostStripTIDHits_TRACK").c_str(),
              &hp_numberOfLostStripTIDHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostStripTOBHits_TRACK").c_str(),
              &hp_numberOfLostStripTOBHits_TRACK);
    t->Branch((pfx + "_hp_numberOfLostStripTECHits_TRACK").c_str(),
              &hp_numberOfLostStripTECHits_TRACK);

    t->Branch((pfx + "_hp_numberOfInactiveHits").c_str(),
              &hp_numberOfInactiveHits);
    t->Branch((pfx + "_hp_numberOfInactiveTrackerHits").c_str(),
              &hp_numberOfInactiveTrackerHits);

    t->Branch((pfx + "_hp_trackerLayersWithMeasurement").c_str(),
              &hp_trackerLayersWithMeasurement);
    t->Branch((pfx + "_hp_pixelLayersWithMeasurement").c_str(),
              &hp_pixelLayersWithMeasurement);
    t->Branch((pfx + "_hp_stripLayersWithMeasurement").c_str(),
              &hp_stripLayersWithMeasurement);
    t->Branch((pfx + "_hp_pixelBarrelLayersWithMeasurement").c_str(),
              &hp_pixelBarrelLayersWithMeasurement);
    t->Branch((pfx + "_hp_pixelEndcapLayersWithMeasurement").c_str(),
              &hp_pixelEndcapLayersWithMeasurement);
    t->Branch((pfx + "_hp_stripTIBLayersWithMeasurement").c_str(),
              &hp_stripTIBLayersWithMeasurement);
    t->Branch((pfx + "_hp_stripTIDLayersWithMeasurement").c_str(),
              &hp_stripTIDLayersWithMeasurement);
    t->Branch((pfx + "_hp_stripTOBLayersWithMeasurement").c_str(),
              &hp_stripTOBLayersWithMeasurement);
    t->Branch((pfx + "_hp_stripTECLayersWithMeasurement").c_str(),
              &hp_stripTECLayersWithMeasurement);

    t->Branch((pfx + "_hp_trackerLayersWithoutMeasurement_TRACK").c_str(),
              &hp_trackerLayersWithoutMeasurement_TRACK);
    t->Branch((pfx + "_hp_trackerLayersWithoutMeasurement_INNER").c_str(),
              &hp_trackerLayersWithoutMeasurement_INNER);
    t->Branch((pfx + "_hp_trackerLayersWithoutMeasurement_OUTER").c_str(),
              &hp_trackerLayersWithoutMeasurement_OUTER);

    t->Branch((pfx + "_hp_pixelLayersWithoutMeasurement_TRACK").c_str(),
              &hp_pixelLayersWithoutMeasurement_TRACK);
    t->Branch((pfx + "_hp_pixelLayersWithoutMeasurement_INNER").c_str(),
              &hp_pixelLayersWithoutMeasurement_INNER);
    t->Branch((pfx + "_hp_pixelLayersWithoutMeasurement_OUTER").c_str(),
              &hp_pixelLayersWithoutMeasurement_OUTER);

    t->Branch((pfx + "_hp_stripLayersWithoutMeasurement_TRACK").c_str(),
              &hp_stripLayersWithoutMeasurement_TRACK);
    t->Branch((pfx + "_hp_stripLayersWithoutMeasurement_INNER").c_str(),
              &hp_stripLayersWithoutMeasurement_INNER);
    t->Branch((pfx + "_hp_stripLayersWithoutMeasurement_OUTER").c_str(),
              &hp_stripLayersWithoutMeasurement_OUTER);

    t->Branch((pfx + "_hp_pixelBarrelLayersWithoutMeasurement_TRACK").c_str(),
              &hp_pixelBarrelLayersWithoutMeasurement_TRACK);
    t->Branch((pfx + "_hp_pixelEndcapLayersWithoutMeasurement_TRACK").c_str(),
              &hp_pixelEndcapLayersWithoutMeasurement_TRACK);
    t->Branch((pfx + "_hp_stripTIBLayersWithoutMeasurement_TRACK").c_str(),
              &hp_stripTIBLayersWithoutMeasurement_TRACK);
    t->Branch((pfx + "_hp_stripTIDLayersWithoutMeasurement_TRACK").c_str(),
              &hp_stripTIDLayersWithoutMeasurement_TRACK);
    t->Branch((pfx + "_hp_stripTOBLayersWithoutMeasurement_TRACK").c_str(),
              &hp_stripTOBLayersWithoutMeasurement_TRACK);
    t->Branch((pfx + "_hp_stripTECLayersWithoutMeasurement_TRACK").c_str(),
              &hp_stripTECLayersWithoutMeasurement_TRACK);

    t->Branch((pfx + "_hp_trackerLayersTotallyOffOrBad").c_str(),
              &hp_trackerLayersTotallyOffOrBad);
    t->Branch((pfx + "_hp_pixelLayersTotallyOffOrBad").c_str(),
              &hp_pixelLayersTotallyOffOrBad);
    t->Branch((pfx + "_hp_stripLayersTotallyOffOrBad").c_str(),
              &hp_stripLayersTotallyOffOrBad);
    t->Branch((pfx + "_hp_pixelBarrelLayersTotallyOffOrBad").c_str(),
              &hp_pixelBarrelLayersTotallyOffOrBad);
    t->Branch((pfx + "_hp_pixelEndcapLayersTotallyOffOrBad").c_str(),
              &hp_pixelEndcapLayersTotallyOffOrBad);
    t->Branch((pfx + "_hp_stripTIBLayersTotallyOffOrBad").c_str(),
              &hp_stripTIBLayersTotallyOffOrBad);
    t->Branch((pfx + "_hp_stripTIDLayersTotallyOffOrBad").c_str(),
              &hp_stripTIDLayersTotallyOffOrBad);
    t->Branch((pfx + "_hp_stripTOBLayersTotallyOffOrBad").c_str(),
              &hp_stripTOBLayersTotallyOffOrBad);
    t->Branch((pfx + "_hp_stripTECLayersTotallyOffOrBad").c_str(),
              &hp_stripTECLayersTotallyOffOrBad);

    t->Branch((pfx + "_hp_trackerLayersNull").c_str(), &hp_trackerLayersNull);
    t->Branch((pfx + "_hp_pixelLayersNull").c_str(), &hp_pixelLayersNull);
    t->Branch((pfx + "_hp_stripLayersNull").c_str(), &hp_stripLayersNull);

    t->Branch((pfx + "_hp_hasValidHitInPixelLayer").c_str(),
              &hp_hasValidHitInPixelLayer);

    t->Branch((pfx + "_hp_numberOfValidStripLayersWithMonoAndStereo").c_str(),
              &hp_numberOfValidStripLayersWithMonoAndStereo);
    t->Branch((pfx + "_hp_numberOfValidTIBLayersWithMonoAndStereo").c_str(),
              &hp_numberOfValidTIBLayersWithMonoAndStereo);
    t->Branch((pfx + "_hp_numberOfValidTIDLayersWithMonoAndStereo").c_str(),
              &hp_numberOfValidTIDLayersWithMonoAndStereo);
    t->Branch((pfx + "_hp_numberOfValidTOBLayersWithMonoAndStereo").c_str(),
              &hp_numberOfValidTOBLayersWithMonoAndStereo);
    t->Branch((pfx + "_hp_numberOfValidTECLayersWithMonoAndStereo").c_str(),
              &hp_numberOfValidTECLayersWithMonoAndStereo);
  }

  void clear() {
    pt.clear();
    eta.clear();
    phi.clear();
    dxy.clear();
    dxyError.clear();
    dz.clear();
    dzError.clear();
    charge.clear();
    fromPV.clear();
    deltaEta.clear();
    deltaPhi.clear();
    isHighPurityTrack.clear();
    isTightTrack.clear();
    isLooseTrack.clear();
    dEdxStrip.clear();
    dEdxPixel.clear();
    caloEm.clear();
    caloHad.clear();
    caloTotal.clear();
    crossedEcalStatus.clear();
    crossedHcalStatus.clear();
    pfIso.clear();
    relativePFIso.clear();
    dPhiMet.clear();
    dPhiMetNoMu.clear();
    ptOverMetNoMu.clear();

    hp_numberOfAllHits.clear();
    hp_numberOfAllTrackerHits.clear();
    hp_numberOfValidHits.clear();
    hp_numberOfValidTrackerHits.clear();
    hp_numberOfValidPixelHits.clear();
    hp_numberOfValidPixelBarrelHits.clear();
    hp_numberOfValidPixelEndcapHits.clear();
    hp_numberOfValidStripHits.clear();
    hp_numberOfValidStripTIBHits.clear();
    hp_numberOfValidStripTIDHits.clear();
    hp_numberOfValidStripTOBHits.clear();
    hp_numberOfValidStripTECHits.clear();

    hp_numberOfLostHits_TRACK.clear();
    hp_numberOfLostHits_INNER.clear();
    hp_numberOfLostHits_OUTER.clear();
    hp_numberOfLostTrackerHits_TRACK.clear();
    hp_numberOfLostTrackerHits_INNER.clear();
    hp_numberOfLostTrackerHits_OUTER.clear();
    hp_numberOfLostPixelHits_TRACK.clear();
    hp_numberOfLostPixelHits_INNER.clear();
    hp_numberOfLostPixelHits_OUTER.clear();
    hp_numberOfLostPixelBarrelHits_TRACK.clear();
    hp_numberOfLostPixelBarrelHits_INNER.clear();
    hp_numberOfLostPixelBarrelHits_OUTER.clear();
    hp_numberOfLostPixelEndcapHits_TRACK.clear();
    hp_numberOfLostPixelEndcapHits_INNER.clear();
    hp_numberOfLostPixelEndcapHits_OUTER.clear();
    hp_numberOfLostStripHits_TRACK.clear();
    hp_numberOfLostStripHits_INNER.clear();
    hp_numberOfLostStripHits_OUTER.clear();
    hp_numberOfLostStripTIBHits_TRACK.clear();
    hp_numberOfLostStripTIDHits_TRACK.clear();
    hp_numberOfLostStripTOBHits_TRACK.clear();
    hp_numberOfLostStripTECHits_TRACK.clear();

    hp_numberOfInactiveHits.clear();
    hp_numberOfInactiveTrackerHits.clear();

    hp_trackerLayersWithMeasurement.clear();
    hp_pixelLayersWithMeasurement.clear();
    hp_stripLayersWithMeasurement.clear();
    hp_pixelBarrelLayersWithMeasurement.clear();
    hp_pixelEndcapLayersWithMeasurement.clear();
    hp_stripTIBLayersWithMeasurement.clear();
    hp_stripTIDLayersWithMeasurement.clear();
    hp_stripTOBLayersWithMeasurement.clear();
    hp_stripTECLayersWithMeasurement.clear();

    hp_trackerLayersWithoutMeasurement_TRACK.clear();
    hp_trackerLayersWithoutMeasurement_INNER.clear();
    hp_trackerLayersWithoutMeasurement_OUTER.clear();
    hp_pixelLayersWithoutMeasurement_TRACK.clear();
    hp_pixelLayersWithoutMeasurement_INNER.clear();
    hp_pixelLayersWithoutMeasurement_OUTER.clear();
    hp_stripLayersWithoutMeasurement_TRACK.clear();
    hp_stripLayersWithoutMeasurement_INNER.clear();
    hp_stripLayersWithoutMeasurement_OUTER.clear();
    hp_pixelBarrelLayersWithoutMeasurement_TRACK.clear();
    hp_pixelEndcapLayersWithoutMeasurement_TRACK.clear();
    hp_stripTIBLayersWithoutMeasurement_TRACK.clear();
    hp_stripTIDLayersWithoutMeasurement_TRACK.clear();
    hp_stripTOBLayersWithoutMeasurement_TRACK.clear();
    hp_stripTECLayersWithoutMeasurement_TRACK.clear();

    hp_trackerLayersTotallyOffOrBad.clear();
    hp_pixelLayersTotallyOffOrBad.clear();
    hp_stripLayersTotallyOffOrBad.clear();
    hp_pixelBarrelLayersTotallyOffOrBad.clear();
    hp_pixelEndcapLayersTotallyOffOrBad.clear();
    hp_stripTIBLayersTotallyOffOrBad.clear();
    hp_stripTIDLayersTotallyOffOrBad.clear();
    hp_stripTOBLayersTotallyOffOrBad.clear();
    hp_stripTECLayersTotallyOffOrBad.clear();

    hp_trackerLayersNull.clear();
    hp_pixelLayersNull.clear();
    hp_stripLayersNull.clear();
    hp_hasValidHitInPixelLayer.clear();
    hp_numberOfValidStripLayersWithMonoAndStereo.clear();
    hp_numberOfValidTIBLayersWithMonoAndStereo.clear();
    hp_numberOfValidTIDLayersWithMonoAndStereo.clear();
    hp_numberOfValidTOBLayersWithMonoAndStereo.clear();
    hp_numberOfValidTECLayersWithMonoAndStereo.clear();
    pfIso.clear();
    relativePFIso.clear();
    pfIso_chHad.clear();
    pfIso_neutHad.clear();
    pfIso_photon.clear();
    pfIso_puChHad.clear();
    miniIso_chHad.clear();
    miniIso_neutHad.clear();
    miniIso_photon.clear();
    miniIso_puChHad.clear();
    miniIso_relative.clear();
  }
};

struct JetBranches {
  std::vector<float> pt, eta, phi, energy;

  void book(TTree *t, const std::string &pfx) {
    t->Branch((pfx + "_pt").c_str(), &pt);
    t->Branch((pfx + "_eta").c_str(), &eta);
    t->Branch((pfx + "_phi").c_str(), &phi);
    t->Branch((pfx + "_energy").c_str(), &energy);
  }
  void clear() {
    pt.clear();
    eta.clear();
    phi.clear();
    energy.clear();
  }
};

} // namespace

// ── Class declaration
// ─────────────────────────────────────────────────────────
class Ntuplizer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit Ntuplizer(const edm::ParameterSet &);
  void analyze(const edm::Event &, const edm::EventSetup &) override;

private:
  edm::EDGetTokenT<std::vector<pat::IsolatedTrack>> trackToken_;
  edm::EDGetTokenT<std::vector<pat::MET>> metToken_;
  edm::EDGetTokenT<std::vector<pat::Muon>> muonToken_;
  edm::EDGetTokenT<std::vector<pat::Electron>> electronToken_;
  edm::EDGetTokenT<std::vector<pat::Jet>> jetToken_;
  edm::EDGetTokenT<std::vector<pat::Jet>> tightJetToken_;
  edm::EDGetTokenT<std::vector<pat::Tau>> tauToken_;
  edm::EDGetTokenT<std::vector<reco::Vertex>> vertexToken_;
  edm::EDGetTokenT<std::vector<pat::Muon>> allMuonToken_;
  edm::EDGetTokenT<std::vector<pat::Electron>> allElectronToken_;
  edm::EDGetTokenT<std::vector<pat::Tau>> allTauToken_;

  TTree *tree_;

  unsigned int run_, lumi_;
  unsigned long long eventNum_;
  float met_pt_, met_phi_, metNoMu_pt_, metNoMu_phi_;

  TrkBranches trk_;
  LepKin muon_, ele_, tau_;
  LepKinMinimal allMuon_, allEle_, allTau_;
  JetBranches jet_, tightJet_;
  VertexBranches vtx_;
};

// ── Constructor
// ───────────────────────────────────────────────────────────────
Ntuplizer::Ntuplizer(const edm::ParameterSet &iConfig)
    : trackToken_(consumes<std::vector<pat::IsolatedTrack>>(
          iConfig.getParameter<edm::InputTag>("tracks"))),
      metToken_(consumes<std::vector<pat::MET>>(
          iConfig.getParameter<edm::InputTag>("met"))),
      muonToken_(consumes<std::vector<pat::Muon>>(
          iConfig.getParameter<edm::InputTag>("muons"))),
      electronToken_(consumes<std::vector<pat::Electron>>(
          iConfig.getParameter<edm::InputTag>("electrons"))),
      jetToken_(consumes<std::vector<pat::Jet>>(
          iConfig.getParameter<edm::InputTag>("jets"))),
      tightJetToken_(consumes<std::vector<pat::Jet>>(
          iConfig.getParameter<edm::InputTag>("tightJets"))),
      tauToken_(consumes<std::vector<pat::Tau>>(
          iConfig.getParameter<edm::InputTag>("taus"))),
      vertexToken_(consumes<std::vector<reco::Vertex>>(
          iConfig.getParameter<edm::InputTag>("vertices"))),
      allMuonToken_(consumes<std::vector<pat::Muon>>(
          iConfig.getParameter<edm::InputTag>("allMuons"))),
      allElectronToken_(consumes<std::vector<pat::Electron>>(
          iConfig.getParameter<edm::InputTag>("allElectrons"))),
      allTauToken_(consumes<std::vector<pat::Tau>>(
          iConfig.getParameter<edm::InputTag>("allTaus"))) {
  usesResource(TFileService::kSharedResource);
  edm::Service<TFileService> fs;
  tree_ = fs->make<TTree>(iConfig.getParameter<std::string>("treeName").c_str(),
                          "Tag and Probe Ntuple");

  tree_->Branch("run", &run_);
  tree_->Branch("lumi", &lumi_);
  tree_->Branch("eventNum", &eventNum_);
  tree_->Branch("met_pt", &met_pt_);
  tree_->Branch("met_phi", &met_phi_);
  tree_->Branch("metNoMu_pt", &metNoMu_pt_);
  tree_->Branch("metNoMu_phi", &metNoMu_phi_);

  trk_.book(tree_, "trk");
  muon_.book(tree_, "muon");
  ele_.book(tree_, "ele");
  jet_.book(tree_, "jet");
  tightJet_.book(tree_, "tightJet");
  tau_.book(tree_, "tau");
  vtx_.book(tree_, "vtx");
  allMuon_.book(tree_, "allMuon");
  allEle_.book(tree_, "allEle");
  allTau_.book(tree_, "allTau");
}

// ── analyze
// ───────────────────────────────────────────────────────────────────
void Ntuplizer::analyze(const edm::Event &iEvent, const edm::EventSetup &) {
  run_ = iEvent.run();
  lumi_ = iEvent.luminosityBlock();
  eventNum_ = iEvent.id().event();

  edm::Handle<std::vector<pat::IsolatedTrack>> tracks;
  edm::Handle<std::vector<pat::MET>> mets;
  edm::Handle<std::vector<pat::Muon>> muons;
  edm::Handle<std::vector<pat::Electron>> electrons;
  edm::Handle<std::vector<pat::Jet>> jets;
  edm::Handle<std::vector<pat::Jet>> tightJets;
  edm::Handle<std::vector<pat::Tau>> taus;
  edm::Handle<std::vector<reco::Vertex>> vertices;
  edm::Handle<std::vector<pat::Muon>> allMuons;
  edm::Handle<std::vector<pat::Electron>> allElectrons;
  edm::Handle<std::vector<pat::Tau>> allTaus;

  iEvent.getByToken(trackToken_, tracks);
  iEvent.getByToken(metToken_, mets);
  iEvent.getByToken(muonToken_, muons);
  iEvent.getByToken(electronToken_, electrons);
  iEvent.getByToken(jetToken_, jets);
  iEvent.getByToken(tightJetToken_, tightJets);
  iEvent.getByToken(tauToken_, taus);
  iEvent.getByToken(vertexToken_, vertices);
  iEvent.getByToken(allMuonToken_, allMuons);
  iEvent.getByToken(allElectronToken_, allElectrons);
  iEvent.getByToken(allTauToken_, allTaus);

  // ── MET and MET^{no mu} ───────────────────────────────────────────────────
  const pat::MET &met = mets->at(0);
  met_pt_ = met.pt();
  met_phi_ = met.phi();

  float metX = met.pt() * std::cos(met.phi());
  float metY = met.pt() * std::sin(met.phi());
  for (const auto &mu : *muons) {
    metX += mu.pt() * std::cos(mu.phi());
    metY += mu.pt() * std::sin(mu.phi());
  }
  metNoMu_pt_ = std::hypot(metX, metY);
  metNoMu_phi_ = std::atan2(metY, metX);

  // ── Clear all branch vectors ──────────────────────────────────────────────
  trk_.clear();
  muon_.clear();
  ele_.clear();
  tau_.clear();
  vtx_.clear();
  allMuon_.clear();
  allEle_.clear();
  allTau_.clear();
  jet_.clear();
  tightJet_.clear();

  // ── Fill muons ────────────────────────────────────────────────────────────
  for (const auto &mu : *muons) {
    muon_.pt.push_back(mu.pt());
    muon_.eta.push_back(mu.eta());
    muon_.phi.push_back(mu.phi());
    muon_.charge.push_back(mu.charge());
  }

  // ── Fill electrons ────────────────────────────────────────────────────────
  for (const auto &el : *electrons) {
    ele_.pt.push_back(el.pt());
    ele_.eta.push_back(el.eta());
    ele_.phi.push_back(el.phi());
    ele_.charge.push_back(el.charge());
  }

  // ── Fill taus ─────────────────────────────────────────────────────────────
  for (const auto &tau : *taus) {
    tau_.pt.push_back(tau.pt());
    tau_.eta.push_back(tau.eta());
    tau_.phi.push_back(tau.phi());
    tau_.charge.push_back(tau.charge());
  }

  // ── Fill all miniAOD leptons (for dR calculations) ───────────────────────
  for (const auto &mu : *allMuons) {
    allMuon_.pt.push_back(mu.pt());
    allMuon_.eta.push_back(mu.eta());
    allMuon_.phi.push_back(mu.phi());
    allMuon_.charge.push_back(mu.charge());
  }
  for (const auto &el : *allElectrons) {
    allEle_.pt.push_back(el.pt());
    allEle_.eta.push_back(el.eta());
    allEle_.phi.push_back(el.phi());
    allEle_.charge.push_back(el.charge());
  }
  for (const auto &tau : *allTaus) {
    allTau_.pt.push_back(tau.pt());
    allTau_.eta.push_back(tau.eta());
    allTau_.phi.push_back(tau.phi());
    allTau_.charge.push_back(tau.charge());
  }

  // ── Fill tracks ───────────────────────────────────────────────────────────
  for (const auto &trk : *tracks) {
    // ── Kinematics ───────────────────────────────────────────────────────────
    trk_.pt.push_back(trk.pt());
    trk_.eta.push_back(trk.eta());
    trk_.phi.push_back(trk.phi());
    trk_.dxy.push_back(trk.dxy());
    trk_.dxyError.push_back(trk.dxyError());
    trk_.dz.push_back(trk.dz());
    trk_.dzError.push_back(trk.dzError());
    trk_.charge.push_back(trk.charge());
    trk_.fromPV.push_back(trk.fromPV());
    trk_.deltaEta.push_back(trk.deltaEta());
    trk_.deltaPhi.push_back(trk.deltaPhi());
    // ── Track quality (decoded from trackQuality bitmask) ────────────────────
    trk_.isHighPurityTrack.push_back(trk.isHighPurityTrack());
    trk_.isTightTrack.push_back(trk.isTightTrack());
    trk_.isLooseTrack.push_back(trk.isLooseTrack());

    // ── dE/dx & calo ─────────────────────────────────────────────────────────
    trk_.dEdxStrip.push_back(trk.dEdxStrip());
    trk_.dEdxPixel.push_back(trk.dEdxPixel());
    const float caloEm = trk.matchedCaloJetEmEnergy();
    const float caloHad = trk.matchedCaloJetHadEnergy();
    trk_.caloEm.push_back(caloEm);
    trk_.caloHad.push_back(caloHad);
    trk_.caloTotal.push_back(caloEm + caloHad);
    trk_.crossedEcalStatus.push_back(trk.crossedEcalStatus());
    trk_.crossedHcalStatus.push_back(trk.crossedHcalStatus());

    // ── DR03 PF isolation ─────────────────────────────────────────────────
    const pat::PFIsolation &dr03 = trk.pfIsolationDR03();
    const float absIso = dr03.chargedHadronIso();
    trk_.pfIso.push_back(absIso);
    trk_.relativePFIso.push_back(trk.pt() > 0.f ? absIso / trk.pt() : -1.f);
    trk_.pfIso_chHad.push_back(dr03.chargedHadronIso());
    trk_.pfIso_neutHad.push_back(dr03.neutralHadronIso());
    trk_.pfIso_photon.push_back(dr03.photonIso());
    trk_.pfIso_puChHad.push_back(dr03.puChargedHadronIso());

    // ── Mini PF isolation ─────────────────────────────────────────────────
    const pat::PFIsolation &mini = trk.miniPFIsolation();
    const float miniChHad = mini.chargedHadronIso();
    trk_.miniIso_chHad.push_back(miniChHad);
    trk_.miniIso_neutHad.push_back(mini.neutralHadronIso());
    trk_.miniIso_photon.push_back(mini.photonIso());
    trk_.miniIso_puChHad.push_back(mini.puChargedHadronIso());
    trk_.miniIso_relative.push_back(trk.pt() > 0.f ? miniChHad / trk.pt()
                                                   : -1.f);
    // ── Derived
    // ───────────────────────────────────────────────────────────────
    trk_.dPhiMet.push_back(reco::deltaPhi(trk.phi(), met.phi()));
    trk_.dPhiMetNoMu.push_back(reco::deltaPhi(trk.phi(), metNoMu_phi_));
    trk_.ptOverMetNoMu.push_back(metNoMu_pt_ > 0.f ? trk.pt() / metNoMu_pt_
                                                   : -1.f);

    // ── HitPattern
    // ────────────────────────────────────────────────────────────
    const reco::HitPattern &hp = trk.hitPattern();
    using HP = reco::HitPattern;

    trk_.hp_numberOfAllHits.push_back(hp.numberOfAllHits(HP::TRACK_HITS));
    trk_.hp_numberOfAllTrackerHits.push_back(
        hp.numberOfAllTrackerHits(HP::TRACK_HITS));

    trk_.hp_numberOfValidHits.push_back(hp.numberOfValidHits());
    trk_.hp_numberOfValidTrackerHits.push_back(hp.numberOfValidTrackerHits());
    trk_.hp_numberOfValidPixelHits.push_back(hp.numberOfValidPixelHits());
    trk_.hp_numberOfValidPixelBarrelHits.push_back(
        hp.numberOfValidPixelBarrelHits());
    trk_.hp_numberOfValidPixelEndcapHits.push_back(
        hp.numberOfValidPixelEndcapHits());
    trk_.hp_numberOfValidStripHits.push_back(hp.numberOfValidStripHits());
    trk_.hp_numberOfValidStripTIBHits.push_back(hp.numberOfValidStripTIBHits());
    trk_.hp_numberOfValidStripTIDHits.push_back(hp.numberOfValidStripTIDHits());
    trk_.hp_numberOfValidStripTOBHits.push_back(hp.numberOfValidStripTOBHits());
    trk_.hp_numberOfValidStripTECHits.push_back(hp.numberOfValidStripTECHits());

    trk_.hp_numberOfLostHits_TRACK.push_back(
        hp.numberOfLostHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostHits_INNER.push_back(
        hp.numberOfLostHits(HP::MISSING_INNER_HITS));
    trk_.hp_numberOfLostHits_OUTER.push_back(
        hp.numberOfLostHits(HP::MISSING_OUTER_HITS));

    trk_.hp_numberOfLostTrackerHits_TRACK.push_back(
        hp.numberOfLostTrackerHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostTrackerHits_INNER.push_back(
        hp.numberOfLostTrackerHits(HP::MISSING_INNER_HITS));
    trk_.hp_numberOfLostTrackerHits_OUTER.push_back(
        hp.numberOfLostTrackerHits(HP::MISSING_OUTER_HITS));

    trk_.hp_numberOfLostPixelHits_TRACK.push_back(
        hp.numberOfLostPixelHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostPixelHits_INNER.push_back(
        hp.numberOfLostPixelHits(HP::MISSING_INNER_HITS));
    trk_.hp_numberOfLostPixelHits_OUTER.push_back(
        hp.numberOfLostPixelHits(HP::MISSING_OUTER_HITS));

    trk_.hp_numberOfLostPixelBarrelHits_TRACK.push_back(
        hp.numberOfLostPixelBarrelHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostPixelBarrelHits_INNER.push_back(
        hp.numberOfLostPixelBarrelHits(HP::MISSING_INNER_HITS));
    trk_.hp_numberOfLostPixelBarrelHits_OUTER.push_back(
        hp.numberOfLostPixelBarrelHits(HP::MISSING_OUTER_HITS));

    trk_.hp_numberOfLostPixelEndcapHits_TRACK.push_back(
        hp.numberOfLostPixelEndcapHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostPixelEndcapHits_INNER.push_back(
        hp.numberOfLostPixelEndcapHits(HP::MISSING_INNER_HITS));
    trk_.hp_numberOfLostPixelEndcapHits_OUTER.push_back(
        hp.numberOfLostPixelEndcapHits(HP::MISSING_OUTER_HITS));

    trk_.hp_numberOfLostStripHits_TRACK.push_back(
        hp.numberOfLostStripHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostStripHits_INNER.push_back(
        hp.numberOfLostStripHits(HP::MISSING_INNER_HITS));
    trk_.hp_numberOfLostStripHits_OUTER.push_back(
        hp.numberOfLostStripHits(HP::MISSING_OUTER_HITS));

    trk_.hp_numberOfLostStripTIBHits_TRACK.push_back(
        hp.numberOfLostStripTIBHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostStripTIDHits_TRACK.push_back(
        hp.numberOfLostStripTIDHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostStripTOBHits_TRACK.push_back(
        hp.numberOfLostStripTOBHits(HP::TRACK_HITS));
    trk_.hp_numberOfLostStripTECHits_TRACK.push_back(
        hp.numberOfLostStripTECHits(HP::TRACK_HITS));

    trk_.hp_numberOfInactiveHits.push_back(hp.numberOfInactiveHits());
    trk_.hp_numberOfInactiveTrackerHits.push_back(
        hp.numberOfInactiveTrackerHits());

    trk_.hp_trackerLayersWithMeasurement.push_back(
        hp.trackerLayersWithMeasurement());
    trk_.hp_pixelLayersWithMeasurement.push_back(
        hp.pixelLayersWithMeasurement());
    trk_.hp_stripLayersWithMeasurement.push_back(
        hp.stripLayersWithMeasurement());
    trk_.hp_pixelBarrelLayersWithMeasurement.push_back(
        hp.pixelBarrelLayersWithMeasurement());
    trk_.hp_pixelEndcapLayersWithMeasurement.push_back(
        hp.pixelEndcapLayersWithMeasurement());
    trk_.hp_stripTIBLayersWithMeasurement.push_back(
        hp.stripTIBLayersWithMeasurement());
    trk_.hp_stripTIDLayersWithMeasurement.push_back(
        hp.stripTIDLayersWithMeasurement());
    trk_.hp_stripTOBLayersWithMeasurement.push_back(
        hp.stripTOBLayersWithMeasurement());
    trk_.hp_stripTECLayersWithMeasurement.push_back(
        hp.stripTECLayersWithMeasurement());

    trk_.hp_trackerLayersWithoutMeasurement_TRACK.push_back(
        hp.trackerLayersWithoutMeasurement(HP::TRACK_HITS));
    trk_.hp_trackerLayersWithoutMeasurement_INNER.push_back(
        hp.trackerLayersWithoutMeasurement(HP::MISSING_INNER_HITS));
    trk_.hp_trackerLayersWithoutMeasurement_OUTER.push_back(
        hp.trackerLayersWithoutMeasurement(HP::MISSING_OUTER_HITS));

    trk_.hp_pixelLayersWithoutMeasurement_TRACK.push_back(
        hp.pixelLayersWithoutMeasurement(HP::TRACK_HITS));
    trk_.hp_pixelLayersWithoutMeasurement_INNER.push_back(
        hp.pixelLayersWithoutMeasurement(HP::MISSING_INNER_HITS));
    trk_.hp_pixelLayersWithoutMeasurement_OUTER.push_back(
        hp.pixelLayersWithoutMeasurement(HP::MISSING_OUTER_HITS));

    trk_.hp_stripLayersWithoutMeasurement_TRACK.push_back(
        hp.stripLayersWithoutMeasurement(HP::TRACK_HITS));
    trk_.hp_stripLayersWithoutMeasurement_INNER.push_back(
        hp.stripLayersWithoutMeasurement(HP::MISSING_INNER_HITS));
    trk_.hp_stripLayersWithoutMeasurement_OUTER.push_back(
        hp.stripLayersWithoutMeasurement(HP::MISSING_OUTER_HITS));

    trk_.hp_pixelBarrelLayersWithoutMeasurement_TRACK.push_back(
        hp.pixelBarrelLayersWithoutMeasurement(HP::TRACK_HITS));
    trk_.hp_pixelEndcapLayersWithoutMeasurement_TRACK.push_back(
        hp.pixelEndcapLayersWithoutMeasurement(HP::TRACK_HITS));
    trk_.hp_stripTIBLayersWithoutMeasurement_TRACK.push_back(
        hp.stripTIBLayersWithoutMeasurement(HP::TRACK_HITS));
    trk_.hp_stripTIDLayersWithoutMeasurement_TRACK.push_back(
        hp.stripTIDLayersWithoutMeasurement(HP::TRACK_HITS));
    trk_.hp_stripTOBLayersWithoutMeasurement_TRACK.push_back(
        hp.stripTOBLayersWithoutMeasurement(HP::TRACK_HITS));
    trk_.hp_stripTECLayersWithoutMeasurement_TRACK.push_back(
        hp.stripTECLayersWithoutMeasurement(HP::TRACK_HITS));

    trk_.hp_trackerLayersTotallyOffOrBad.push_back(
        hp.trackerLayersTotallyOffOrBad());
    trk_.hp_pixelLayersTotallyOffOrBad.push_back(
        hp.pixelLayersTotallyOffOrBad());
    trk_.hp_stripLayersTotallyOffOrBad.push_back(
        hp.stripLayersTotallyOffOrBad());
    trk_.hp_pixelBarrelLayersTotallyOffOrBad.push_back(
        hp.pixelBarrelLayersTotallyOffOrBad());
    trk_.hp_pixelEndcapLayersTotallyOffOrBad.push_back(
        hp.pixelEndcapLayersTotallyOffOrBad());
    trk_.hp_stripTIBLayersTotallyOffOrBad.push_back(
        hp.stripTIBLayersTotallyOffOrBad());
    trk_.hp_stripTIDLayersTotallyOffOrBad.push_back(
        hp.stripTIDLayersTotallyOffOrBad());
    trk_.hp_stripTOBLayersTotallyOffOrBad.push_back(
        hp.stripTOBLayersTotallyOffOrBad());
    trk_.hp_stripTECLayersTotallyOffOrBad.push_back(
        hp.stripTECLayersTotallyOffOrBad());

    trk_.hp_trackerLayersNull.push_back(hp.trackerLayersNull());
    trk_.hp_pixelLayersNull.push_back(hp.pixelLayersNull());
    trk_.hp_stripLayersNull.push_back(hp.stripLayersNull());

    // PXB layer 1 — most commonly used for disappearing track searches
    trk_.hp_hasValidHitInPixelLayer.push_back(
        hp.hasValidHitInPixelLayer(PixelSubdetector::PixelBarrel, 1));

    trk_.hp_numberOfValidStripLayersWithMonoAndStereo.push_back(
        hp.numberOfValidStripLayersWithMonoAndStereo());
    trk_.hp_numberOfValidTIBLayersWithMonoAndStereo.push_back(
        hp.numberOfValidTIBLayersWithMonoAndStereo());
    trk_.hp_numberOfValidTIDLayersWithMonoAndStereo.push_back(
        hp.numberOfValidTIDLayersWithMonoAndStereo());
    trk_.hp_numberOfValidTOBLayersWithMonoAndStereo.push_back(
        hp.numberOfValidTOBLayersWithMonoAndStereo());
    trk_.hp_numberOfValidTECLayersWithMonoAndStereo.push_back(
        hp.numberOfValidTECLayersWithMonoAndStereo());
  }
  // ── Fill jets
  for (const auto &jet : *jets) {
    jet_.pt.push_back(jet.pt());
    jet_.eta.push_back(jet.eta());
    jet_.phi.push_back(jet.phi());
    jet_.energy.push_back(jet.energy());

    // Tight Lep Veto ID applied inline
    const float absEta = std::abs(jet.eta());
    bool passesTightLepVeto = false;

    if (absEta <= 2.6)
      passesTightLepVeto = jet.neutralHadronEnergyFraction() < 0.99
        && jet.neutralEmEnergyFraction() < 0.9
        && jet.numberOfDaughters() > 1
        && jet.muonEnergyFraction() < 0.8
        && jet.chargedHadronEnergyFraction() > 0.01
        && jet.chargedMultiplicity() > 0
        && jet.chargedEmEnergyFraction() < 0.8;
    else if (absEta <= 2.7)
      passesTightLepVeto = jet.neutralHadronEnergyFraction() < 0.9
        && jet.neutralEmEnergyFraction() < 0.99
        && jet.muonEnergyFraction() < 0.8
        && jet.chargedEmEnergyFraction() < 0.8;
    else if (absEta <= 3.0)
      passesTightLepVeto = jet.neutralHadronEnergyFraction() < 0.99;
    else
      passesTightLepVeto = jet.neutralEmEnergyFraction() < 0.4
        && jet.neutralMultiplicity() >= 2;

    tightJet_.pt.push_back(passesTightLepVeto     ? jet.pt()     : -1.f);
    tightJet_.eta.push_back(passesTightLepVeto    ? jet.eta()    : -99.f);
    tightJet_.phi.push_back(passesTightLepVeto    ? jet.phi()    : -99.f);
    tightJet_.energy.push_back(passesTightLepVeto ? jet.energy() : -1.f);
  }

  // ── Fill primary vertices ─────────────────────────────────────────────────
  for (const auto &pv : *vertices) {
    vtx_.x.push_back(pv.x());
    vtx_.y.push_back(pv.y());
    vtx_.z.push_back(pv.z());
    vtx_.xError.push_back(pv.xError());
    vtx_.yError.push_back(pv.yError());
    vtx_.zError.push_back(pv.zError());
    vtx_.chi2.push_back(pv.chi2());
    vtx_.normalizedChi2.push_back(pv.normalizedChi2());
    vtx_.ndof.push_back(pv.ndof());
    vtx_.nTracks.push_back(pv.nTracks());
    vtx_.isValid.push_back(pv.isValid());
    vtx_.isFake.push_back(pv.isFake());
  }
  tree_->Fill();
}

DEFINE_FWK_MODULE(Ntuplizer);
