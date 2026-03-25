#!/usr/bin/env python3

#!/usr/bin/env python3
import ROOT
ROOT.gROOT.SetBatch(True)
ROOT.gStyle.SetOptStat(0)

# ── FWLite setup ──────────────────────────────────────────────────────────────
from DataFormats.FWLite import Handle, Events

# ── Input file ────────────────────────────────────────────────────────────────
events = Events('root://cmseos.fnal.gov//eos/uscms/store/user/lpclonglived/DisappTrks/EGamma0/ElectronTagSkim_2024G_v1_EGamma0/260303_183737/0001/skim_ElectronTagSkim_2026_03_03_12h35m53s_1037.root')

handle = Handle('std::vector<pat::IsolatedTrack>')
label  = ('isolatedTracks', '', '')

# ── Histograms ────────────────────────────────────────────────────────────────
hEta     = ROOT.TH1D('hEta',    'IsoTrack #eta;#eta;Entries',          100, -3.0, 3.0)
hPhi     = ROOT.TH1D('hPhi',    'IsoTrack #phi;#phi;Entries',          128, -3.2, 3.2)
hEtaPhi  = ROOT.TH2D('hEtaPhi', 'IsoTrack #eta vs #phi;#eta;#phi',     100, -3.0, 3.0, 128, -3.2, 3.2)
hPt      = ROOT.TH1D('hPt',     'IsoTrack p_{T};p_{T} [GeV];Entries',  100,  0.0, 200.0)
hNTracks = ROOT.TH1D('hNTracks','N IsoTracks per event;N;Entries',       50,  0.0,  50.0)

# ── Event loop ────────────────────────────────────────────────────────────────
for i, event in enumerate(events):
    event.getByLabel(label, handle)
    tracks = handle.product()

    hNTracks.Fill(tracks.size())
    for trk in tracks:
        hEta   .Fill(trk.eta())
        hPhi   .Fill(trk.phi())
        hEtaPhi.Fill(trk.eta(), trk.phi())
        hPt    .Fill(trk.pt())

    if i % 1000 == 0:
        print(f"Processed {i} events...")

print(f"Done. Total tracks: {int(hEta.GetEntries())}")

# ── Save histograms ───────────────────────────────────────────────────────────
fout = ROOT.TFile('isotrack_etaphi.root', 'RECREATE')
hEta   .Write()
hPhi   .Write()
hEtaPhi.Write()
hPt    .Write()
hNTracks.Write()
fout.Close()

# ── Plot ──────────────────────────────────────────────────────────────────────
c1 = ROOT.TCanvas('c1', '', 1200, 800)
c1.Divide(2, 2)

c1.cd(1); hEta.Draw()
c1.cd(2); hPhi.Draw()
c1.cd(3); ROOT.gPad.SetRightMargin(0.15); hEtaPhi.Draw('COLZ')
c1.cd(4); hPt.Draw()

c1.SaveAs('isotrack_etaphi.png')
