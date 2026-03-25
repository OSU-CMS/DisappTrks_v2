#!/usr/bin/env python3
import ROOT
ROOT.gROOT.SetBatch(True)
ROOT.gStyle.SetOptStat(0)

from DataFormats.FWLite import Handle, Events
import math

def delta_r(eta1, phi1, eta2, phi2):
    deta = eta1 - eta2
    dphi = abs(phi1 - phi2)
    if dphi > math.pi:
        dphi = 2 * math.pi - dphi
    return math.sqrt(deta**2 + dphi**2)
# ── Constants ─────────────────────────────────────────────────────────────────
Z_MASS       = 91.1876  # GeV
MASS_WINDOW  = 10.0     # GeV

# ── Input file ────────────────────────────────────────────────────────────────
events = Events('electronFiducialFilter.root')

electronHandle = Handle('std::vector<pat::Electron>')
trackHandle    = Handle('std::vector<pat::IsolatedTrack>')

electronLabel = ('QualityCut',              'qualityLeptons', 'ZtoEleProbeTrk')
trackLabel    = ('TrackTauDeltaRFilter',     'deltaRTracks',   'ZtoEleProbeTrk')

# ── Histograms ────────────────────────────────────────────────────────────────
hInvMass_all       = ROOT.TH1D('hInvMass_all',       'All pairs invariant mass;m_{e,trk} [GeV];Entries',          100, 50, 130)
hInvMass_Zpeak     = ROOT.TH1D('hInvMass_Zpeak',     'Z window pairs invariant mass;m_{e,trk} [GeV];Entries',     100, 50, 130)
hInvMass_OS        = ROOT.TH1D('hInvMass_OS',        'Opposite-sign pairs invariant mass;m_{e,trk} [GeV];Entries',100, 50, 130)
hInvMass_OS_Zpeak  = ROOT.TH1D('hInvMass_OS_Zpeak',  'OS + Z window;m_{e,trk} [GeV];Entries',                    100, 50, 130)

hTrackPt_selected  = ROOT.TH1D('hTrackPt_selected',  'Selected track p_{T};p_{T} [GeV];Entries', 100,  0, 500)
hElePt_selected    = ROOT.TH1D('hElePt_selected',    'Selected electron p_{T};p_{T} [GeV];Entries', 100, 0, 500)
hDeltaR_selected   = ROOT.TH1D('hDeltaR_selected',   'Selected pair #DeltaR;#DeltaR;Entries',    100,  0,   5)
hTrackPt_deltaR      = ROOT.TH1D('hTrackPt_deltaR',      'Track p_{T} (dR cut);p_{T} [GeV];Entries',           100, 0, 500)
hTrackPt_ecalo       = ROOT.TH1D('hTrackPt_ecalo',       'Track p_{T} (Ecalo cut);p_{T} [GeV];Entries',        100, 0, 500)
hTrackPt_missingHits = ROOT.TH1D('hTrackPt_missingHits', 'Track p_{T} (missing hits cut);p_{T} [GeV];Entries', 100, 0, 500)
hTrackPt_allCuts     = ROOT.TH1D('hTrackPt_allCuts',     'Track p_{T} (all cuts);p_{T} [GeV];Entries',         100, 0, 500)
hNPairs            = ROOT.TH1D('hNPairs',            'N OS Z-window pairs per event;N;Entries',   10,  0,  10)

n_total_events     = 0
n_events_with_pair = 0
n_pass_deltaR = 0
n_pass_ecalo = 0
n_pass_missingHits = 0
n_pass_all = 0

# ── Event loop ────────────────────────────────────────────────────────────────
for i, event in enumerate(events):
    event.getByLabel(electronLabel, electronHandle)
    event.getByLabel(trackLabel,    trackHandle)

    # Skip events where downstream filters didn't run
    if not electronHandle.isValid() or not trackHandle.isValid():
        continue

    electrons = electronHandle.product()
    tracks    = trackHandle.product()

    if i % 1000 == 0:
        print(f"Processing event {i}...")

    n_total_events += 1
    n_selected_pairs = 0

    for ele in electrons:
        eleP4 = ROOT.TLorentzVector()
        eleP4.SetPtEtaPhiM(ele.pt(), ele.eta(), ele.phi(), ele.mass())

        for trk in tracks:
            trkP4 = ROOT.TLorentzVector()
            trkP4.SetPtEtaPhiM(trk.pt(), trk.eta(), trk.phi(), 0.000511)  # electron mass

            invMass = (eleP4 + trkP4).M()
            hInvMass_all.Fill(invMass)

            # ── Opposite charge ───────────────────────────────────────────────
            oppositeCharge = (ele.charge() * trk.charge() < 0)
            if oppositeCharge:
                hInvMass_OS.Fill(invMass)

            # ── Z mass window ─────────────────────────────────────────────────
            inZwindow = abs(invMass - Z_MASS) < MASS_WINDOW
            if inZwindow:
                hInvMass_Zpeak.Fill(invMass)

            # ── Both cuts ─────────────────────────────────────────────────────
            if oppositeCharge and inZwindow:
                hInvMass_OS_Zpeak.Fill(invMass)
                hTrackPt_selected.Fill(trk.pt())
                hElePt_selected.Fill(ele.pt())
                hDeltaR_selected.Fill(delta_r(ele.eta(), ele.phi(),
                                                   trk.eta(), trk.phi()))
                n_selected_pairs += 1

                # ── Probe cuts ────────────────────────────────────────────────────
                dr              = delta_r(ele.eta(), ele.phi(), trk.eta(), trk.phi())
                ecalo = trk.matchedCaloJetEmEnergy() + trk.matchedCaloJetHadEnergy()
                missingHits     = trk.hitPattern().numberOfLostHits(
                                    ROOT.reco.HitPattern.MISSING_OUTER_HITS)

                passDeltaR      = dr          > 0.15
                passEcalo       = ecalo       < 10.0
                passMissingHits = missingHits >= 3

                # ── Fill per-cut histograms ────────────────────────────────────────
                if passDeltaR:
                    hTrackPt_deltaR.Fill(trk.pt())
                    n_pass_deltaR += 1

                if passEcalo:
                    hTrackPt_ecalo.Fill(trk.pt())
                    n_pass_ecalo += 1

                if passMissingHits:
                    hTrackPt_missingHits.Fill(trk.pt())
                    n_pass_missingHits += 1

                if passDeltaR and passEcalo and passMissingHits:
                    hTrackPt_allCuts.Fill(trk.pt())
                    n_pass_all += 1

    if n_selected_pairs > 0:
        n_events_with_pair += 1
    hNPairs.Fill(n_selected_pairs)

# ── Summary ───────────────────────────────────────────────────────────────────
#
print(f"\n{'='*50}")
print(f"Total events processed:          {n_total_events}")
print(f"Events with >=1 OS Z-pair:       {n_events_with_pair}")
print(f"Total OS Z-window pairs:         {int(hInvMass_OS_Zpeak.GetEntries())}")
print(f"\n{'='*50}")
print(f"{'='*50}\n")
print(f"Tracks passing dR > 0.15:              {n_pass_deltaR}")
print(f"Tracks passing Ecalo < 10 GeV:         {n_pass_ecalo}")
print(f"Tracks passing missing outer hits >= 3:{n_pass_missingHits}")
print(f"Tracks passing all probe cuts:         {n_pass_all}")
print(f"{'='*50}\n")

# ── Save ──────────────────────────────────────────────────────────────────────
fout = ROOT.TFile('Zpeak_analysis.root', 'RECREATE')
hInvMass_all     .Write()
hInvMass_Zpeak   .Write()
hInvMass_OS      .Write()
hInvMass_OS_Zpeak.Write()
hTrackPt_selected.Write()
hElePt_selected  .Write()
hDeltaR_selected .Write()
hNPairs          .Write()
fout.Close()

# ── Plot ──────────────────────────────────────────────────────────────────────
c1 = ROOT.TCanvas('c1', '', 1200, 800)
c1.Divide(2, 2)

c1.cd(1)
hInvMass_all.SetLineColor(ROOT.kBlue)
hInvMass_OS.SetLineColor(ROOT.kRed)
hInvMass_OS_Zpeak.SetLineColor(ROOT.kGreen+2)
hInvMass_all.Draw()
hInvMass_OS.Draw("SAME")
hInvMass_OS_Zpeak.Draw("SAME")
leg = ROOT.TLegend(0.15, 0.65, 0.55, 0.88)
leg.AddEntry(hInvMass_all,      'All pairs',       'l')
leg.AddEntry(hInvMass_OS,       'Opposite sign',   'l')
leg.AddEntry(hInvMass_OS_Zpeak, 'OS + Z window',   'l')
leg.Draw()

# Draw Z mass window lines
line_lo = ROOT.TLine(Z_MASS - MASS_WINDOW, 0, Z_MASS - MASS_WINDOW, hInvMass_all.GetMaximum())
line_hi = ROOT.TLine(Z_MASS + MASS_WINDOW, 0, Z_MASS + MASS_WINDOW, hInvMass_all.GetMaximum())
for line in [line_lo, line_hi]:
    line.SetLineStyle(2)
    line.SetLineColor(ROOT.kGray+2)
    line.Draw()

c1.cd(2)
hTrackPt_selected.Draw()

c1.cd(3)
hElePt_selected.Draw()

c1.cd(4)
hDeltaR_selected.Draw()

c1.SaveAs('Zpeak_analysis.png')
