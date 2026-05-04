#!/usr/bin/env python3
import ROOT
ROOT.gROOT.SetBatch(True)

from DataFormats.FWLite import Events, Handle

# ── Input file ──────────────────────────────────────────────────────────────
events = Events("electronFiducialFilter.root")

# ── Handles ─────────────────────────────────────────────────────────────────
h_fiducial = Handle("vector<pat::IsolatedTrack>")
h_tracks = Handle("vector<pat::IsolatedTrack>")

# Labels: (moduleLabel, instanceLabel, processLabel)
lbl_fiducial = ("TrackElectronFiducialFilter", "fiducialTracks", "ZtoEleProbeTrk")  # fill in your process name if needed
lbl_tracks = ("isolatedTracks", "" , "PAT")

# ── Histograms ───────────────────────────────────────────────────────────────
nEta, etaMin, etaMax = 50, -3.0,  3.0
nPhi, phiMin, phiMax = 64, -3.2,  3.2

def make2D(name, title):
    return ROOT.TH2F(name, f"{title};#eta;#phi",
                     nEta, etaMin, etaMax,
                     nPhi, phiMin, phiMax)

h2_fiducial = make2D("h2_fiducialTracks", "Fiducial tracks (#eta-#phi)")
h2_fiducial.SetStats(0)
h2_tracks     = make2D("h2_tracks",     "Isolated Tracks")
h2_tracks.SetStats(0)

h_fiducial_eta = ROOT.TH1F("h_fiducial_eta", "Fiducial track #eta;#eta;Events",         nEta, etaMin, etaMax)
h_fiducial_phi = ROOT.TH1F("h_fiducial_phi", "Fiducial track #phi;#phi;Events",         nPhi, phiMin, phiMax)
h_fiducial_pt  = ROOT.TH1F("h_fiducial_pt",  "Fiducial track p_{T};p_{T} [GeV];Events", 100, 0, 200)

# ── Count tracks in veto regions ─────────────────────────────────────────────
# Hot spots: (eta_center, phi_center, sigma)
hot_spots = [
    (-1.25, -1.15, 4.62087),
    (-1.25, -1.05, 2.50619),
    (-0.55, -0.95,  2.0621),
    ( 1.85, -1.35, 39.2679),
    ( 1.85, -1.25, 2.46258),
    ( 1.85,  2.35, 4.36014),
    ( 1.95, -1.35, 12.9072),
    ( 1.95, -1.25, 3.08742),
]

# Bin half-widths must match what the fiducial map histogram uses
# From veto list spacing: eta bins are 0.1 wide, phi bins are 0.1 wide
half_eta = 0.1 / 2.0
half_phi = 0.1 / 2.0

# Counters per hot spot
counts_all      = {hs: 0 for hs in hot_spots}
counts_fiducial = {hs: 0 for hs in hot_spots}

def in_hot_spot(eta, phi, hs_eta, hs_phi, he, hp):
    return abs(eta - hs_eta) < he and abs(phi - hs_phi) < hp


for i, event in enumerate(events):

    event.getByLabel("TrackElectronFiducialFilter", "fiducialTracks", "ZtoEleProbeTrk", h_fiducial)
    event.getByLabel("isolatedTracks", "", "PAT", h_tracks)

    if h_tracks.isValid():
        for track in h_tracks.product():
            h2_tracks.Fill(track.eta(), track.phi())
            for hs in hot_spots:
                if in_hot_spot(track.eta(), track.phi(), hs[0], hs[1], half_eta, half_phi):
                    counts_all[hs] += 1

    if h_fiducial.isValid():
        for trk in h_fiducial.product():
            h2_fiducial.Fill(trk.eta(), trk.phi())
            h_fiducial_eta.Fill(trk.eta())
            h_fiducial_phi.Fill(trk.phi())
            h_fiducial_pt.Fill(trk.pt())
            for hs in hot_spots:
                if in_hot_spot(trk.eta(), trk.phi(), hs[0], hs[1], half_eta, half_phi):
                    counts_fiducial[hs] += 1

    if i % 500 == 0:
        print(f"  processed {i} / {events.size()} events")

print("\n{:<8} {:<8} {:<10} {:<12} {:<16} {:<12}".format(
    "eta", "phi", "sigma", "all tracks", "fiducial tracks", "removed"))
print("-" * 70)
for hs in hot_spots:
    n_all = counts_all[hs]
    n_fid = counts_fiducial[hs]
    print("{:<8} {:<8} {:<10.4f} {:<12} {:<16} {:<12}".format(
        hs[0], hs[1], hs[2], n_all, n_fid, n_all - n_fid))
# ── Draw & save ──────────────────────────────────────────────────────────────
canvas = ROOT.TCanvas("c", "c", 800, 700)
canvas.SetRightMargin(0.13)

plots2D = [
    (h2_fiducial, "fiducialTracks_etaPhi.png"),
    (h2_tracks,     "tracks_etaPhi.png"),
]

for hist, fname in plots2D:
    hist.Draw("COLZ")
    canvas.SaveAs(fname)
    print(f"Saved {fname}  (entries = {hist.GetEntries():.0f})")

canvas.SetRightMargin(0.05)
for hist, fname in [
    (h_fiducial_eta, "fiducialTracks_eta.png"),
    (h_fiducial_phi, "fiducialTracks_phi.png"),
    (h_fiducial_pt,  "fiducialTracks_pt.png"),
]:
    hist.Draw("HIST")
    canvas.SaveAs(fname)
    print(f"Saved {fname}")

# Persist everything
out = ROOT.TFile("etaPhi_plots.root", "RECREATE")
for obj in [h2_fiducial, h2_tracks,
            h_fiducial_eta, h_fiducial_phi, h_fiducial_pt]:
    obj.Write()
out.Close()

# ── Comparison canvas ────────────────────────────────────────────────────────
c_compare = ROOT.TCanvas("c_compare", "Eta-Phi Comparison", 1600, 700)
c_compare.Divide(2, 1)

# Set a common z-axis range so the colour scales are comparable
zmax = max(h2_tracks.GetMaximum(), h2_fiducial.GetMaximum())
h2_tracks.SetMaximum(zmax)
h2_fiducial.SetMaximum(zmax)
h2_tracks.SetMinimum(0)
h2_fiducial.SetMinimum(0)

c_compare.cd(1)
ROOT.gPad.SetRightMargin(0.15)
h2_tracks.SetTitle("Isolated Tracks;#eta;#phi")
h2_tracks.Draw("COLZ")

c_compare.cd(2)
ROOT.gPad.SetRightMargin(0.15)
h2_fiducial.SetTitle("Fiducial Tracks;#eta;#phi")
h2_fiducial.Draw("COLZ")

c_compare.SaveAs("tracks_fiducial_comparison_etaPhi.png")
print(f"Saved tracks_fiducial_comparison_etaPhi.png")

# ── Ratio plot ───────────────────────────────────────────────────────────────
h2_ratio = h2_fiducial.Clone("h2_ratio")
h2_ratio.Divide(h2_tracks)
h2_ratio.SetTitle("Fiducial / All Isolated Tracks;#eta;#phi")
h2_ratio.SetMinimum(0)
h2_ratio.SetMaximum(1)

c_ratio = ROOT.TCanvas("c_ratio", "Ratio", 800, 700)
c_ratio.SetRightMargin(0.15)
h2_ratio.Draw("COLZ")
c_ratio.SaveAs("tracks_fiducial_ratio_etaPhi.png")
print("Saved tracks_fiducial_ratio_etaPhi.png")

# Write new histograms to ROOT file
out = ROOT.TFile("etaPhi_plots.root", "RECREATE")
for obj in [h2_fiducial, h2_tracks, h2_ratio,
            h_fiducial_eta, h_fiducial_phi, h_fiducial_pt]:
    obj.Write()
out.Close()
