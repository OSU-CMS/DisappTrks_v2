#!/usr/bin/env python3
"""
ntuple_cutflow.py — reproduce the DisappTrks/OSUT3Analysis Z→ℓ probe-track
cutflow from a DisappTrks_v2 TTree ntuple, for direct 1-to-1 comparison.

Mirrors the old-framework cut ordering in MuonTagProbeSelections.py /
ElectronTagProbeSelections.py + EventSelections.py (isoTrkCuts).

Cuts already pre-applied by CMSSW producers (100% efficient in ntuple):
  • HLT path filter (hltFilter)
  • Track fiducial: electron map, muon map, ECAL dead channels
  • Track: pT>20, ≥4 pixel hits, 0 miss-inner, 0 miss-mid,
           relIso<0.05, |dxy|<0.02, |dz|<0.5  (QualityTrackProducer)
  • Tag lepton: pT>20, |η|<2.1, tight ID  (LeptonCollectionsProducer)

Cuts applied here (not pre-applied):
  • Tag signal pT threshold (default 26 muon / 35 electron)
  • Tag trigger match  (muon_isTrigMatched / ele_isTrigMatched)
  • [GAP] Tag tight PF iso — not yet in ntuple, shown as placeholder
  • Probe signal pT threshold (default 55 GeV)
  • Probe |η| < 2.1 (pre-applied but verified)
  • Probe ECAL gap veto  |η| ∉ (1.42, 1.65)
  • Probe muon-ineff region 1  |η| ∉ (0.15, 0.35)
  • Probe muon-ineff region 2  |η| ∉ (1.55, 1.85)
  • Probe ≥4 total valid hits  (NOT in QualityTrackProducer)
  • Probe dRMinJet > 0.5
  • Z mass 80–100 GeV, opposite-sign

Requires: pip install uproot awkward numpy

Usage:
    python ntuple_cutflow.py ntuple.root
    python ntuple_cutflow.py ntuple.root --channel electron --tag-pt 35
    python ntuple_cutflow.py ntuple.root --probe-pt 30 --zmass-lo 76 --zmass-hi 106
"""

import argparse
import math
import sys
import uproot
import numpy as np

MUON_MASS = 0.10566   # GeV
ELEC_MASS = 5.11e-4   # GeV


# ── Physics helpers ───────────────────────────────────────────────────────────

def inv_mass(pt1, eta1, phi1, m1, pt2, eta2, phi2, m2):
    E1  = math.sqrt((pt1 * math.cosh(eta1))**2 + m1**2)
    E2  = math.sqrt((pt2 * math.cosh(eta2))**2 + m2**2)
    px  = pt1 * math.cos(phi1) + pt2 * math.cos(phi2)
    py  = pt1 * math.sin(phi1) + pt2 * math.sin(phi2)
    pz  = pt1 * math.sinh(eta1) + pt2 * math.sinh(eta2)
    return math.sqrt(max((E1 + E2)**2 - px**2 - py**2 - pz**2, 0.0))


def delta_r(eta1, phi1, eta2, phi2):
    dphi = abs(phi1 - phi2)
    if dphi > math.pi:
        dphi = 2 * math.pi - dphi
    return math.sqrt((eta1 - eta2)**2 + dphi**2)


def dr_to_closest_jet(trk_eta, trk_phi, jet_etas, jet_phis, jet_pts, min_jet_pt):
    best = 999.0
    for jeta, jphi, jpt in zip(jet_etas, jet_phis, jet_pts):
        if jpt < min_jet_pt:
            continue
        best = min(best, delta_r(trk_eta, trk_phi, jeta, jphi))
    return best


# ── Cutflow table ─────────────────────────────────────────────────────────────

class Cutflow:
    COL = 58

    def __init__(self):
        self.rows = []

    def add(self, label, n, note=""):
        self.rows.append((label, n, note))

    def print(self):
        header = (f"{'Cut':<{self.COL}} {'N events':>10}  "
                  f"{'Abs.eff':>8}  {'Rel.eff':>8}")
        bar = "=" * len(header)
        print(f"\n{bar}\n{header}\n{'-' * len(header)}")
        n_total = self.rows[0][1] if self.rows else 0
        prev = n_total
        for label, n, note in self.rows:
            abs_eff = 100.0 * n / n_total if n_total else 0.0
            rel_eff = 100.0 * n / prev    if prev    else 0.0
            suffix  = f"  [{note}]" if note else ""
            print(f"{label:<{self.COL}} {n:>10}  "
                  f"{abs_eff:>7.2f}%  {rel_eff:>7.2f}%{suffix}")
            prev = n
        print(f"{bar}\n")


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ntuple",               help="DisappTrks_v2 ntuple ROOT file")
    p.add_argument("--tree",    default="Events",
                   help="TTree name (default: Events)")
    p.add_argument("--channel", choices=["muon", "electron"], default="muon")
    p.add_argument("--tag-pt",  type=float, default=None,
                   help="Signal pT threshold on tag lepton "
                        "(default: 26 GeV muon, 35 GeV electron)")
    p.add_argument("--probe-pt",  type=float, default=55.0,
                   help="Signal pT threshold on probe track (default: 55 GeV)")
    p.add_argument("--min-jet-pt",type=float, default=30.0,
                   help="Minimum jet pT for dRMinJet calculation (default: 30 GeV)")
    p.add_argument("--zmass-lo",  type=float, default=80.0)
    p.add_argument("--zmass-hi",  type=float, default=100.0)
    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if args.tag_pt is None:
        args.tag_pt = 26.0 if args.channel == "muon" else 35.0

    tag_mass = MUON_MASS if args.channel == "muon" else ELEC_MASS
    tag_pfx  = "muon"   if args.channel == "muon" else "ele"

    print(f"\nChannel  : {args.channel}")
    print(f"Tag pT   : > {args.tag_pt} GeV")
    print(f"Probe pT : > {args.probe_pt} GeV")
    print(f"Z mass   : {args.zmass_lo}–{args.zmass_hi} GeV")

    if args.channel == "muon":
        print("\nNOTE: tag tight PF isolation is NOT yet stored in the ntuple "
              "(LeptonCollectionsProducer gap). That row is a placeholder showing "
              "the same count as the trigger-match row. Add PF iso to "
              "LeptonCollectionsProducer to fill this gap.")

    # ── Load arrays ───────────────────────────────────────────────────────────
    branches_needed = [
        f"{tag_pfx}_pt", f"{tag_pfx}_eta", f"{tag_pfx}_phi",
        f"{tag_pfx}_charge", f"{tag_pfx}_isTrigMatched",
        "trk_pt", "trk_eta", "trk_phi", "trk_charge",
        "trk_hp_numberOfValidHits",
        "jet_pt", "jet_eta", "jet_phi",
    ]

    print(f"\nOpening {args.ntuple}:{args.tree} ...")
    try:
        with uproot.open(f"{args.ntuple}:{args.tree}") as tree:
            ev = tree.arrays(branches_needed, library="ak")
    except Exception as exc:
        sys.exit(f"ERROR reading ntuple: {exc}")

    n_events = len(ev[f"{tag_pfx}_pt"])
    print(f"Loaded {n_events} events.\n")

    # ── Per-event loop ────────────────────────────────────────────────────────
    # At each step we track whether the event has ≥1 surviving (tag, probe) pair.
    # Steps follow the old-framework ObjectSelector cut ordering.

    # 13 counting buckets (indices 0..12)
    counts = [0] * 13

    for iev in range(n_events):

        # Unpack per-event collections to plain Python lists for clarity
        tpt   = ev[f"{tag_pfx}_pt"][iev].to_list()
        teta  = ev[f"{tag_pfx}_eta"][iev].to_list()
        tphi  = ev[f"{tag_pfx}_phi"][iev].to_list()
        tch   = ev[f"{tag_pfx}_charge"][iev].to_list()
        ttrig = ev[f"{tag_pfx}_isTrigMatched"][iev].to_list()

        ppt   = ev["trk_pt"][iev].to_list()
        peta  = ev["trk_eta"][iev].to_list()
        pphi  = ev["trk_phi"][iev].to_list()
        pch   = ev["trk_charge"][iev].to_list()
        pnh   = ev["trk_hp_numberOfValidHits"][iev].to_list()

        jpt   = ev["jet_pt"][iev].to_list()
        jeta  = ev["jet_eta"][iev].to_list()
        jphi  = ev["jet_phi"][iev].to_list()

        n_trk = len(ppt)

        # ── TAG CUTS ──────────────────────────────────────────────────────────
        # All tags start as indices into the tag-lepton collection.
        # pT>20, |η|<2.1, tight ID already pre-applied in LeptonCollectionsProducer.

        # [0] Signal-level pT threshold
        tags = [i for i in range(len(tpt)) if tpt[i] > args.tag_pt]
        if tags:
            counts[0] += 1

        # [1] Trigger match
        tags = [i for i in tags if ttrig[i]]
        if tags:
            counts[1] += 1

        # [2] Tight PF isolation  — GAP: placeholder, same count as step 1
        tags_iso = tags  # unchanged until iso branch exists in ntuple
        if tags_iso:
            counts[2] += 1

        # ── PROBE CUTS ────────────────────────────────────────────────────────
        # pT>20, ≥4 pixel hits, 0 miss-inner, 0 miss-mid,
        # relIso<0.05, |dxy|<0.02, |dz|<0.5 already pre-applied in QualityTrackProducer.
        # Fiducial maps pre-applied by TrackFiducialFilter modules.
        # Cuts below narrow down the probe candidates further.

        # [3] Signal-level pT threshold
        probes = [i for i in range(n_trk) if ppt[i] > args.probe_pt]
        if tags_iso and probes:
            counts[3] += 1

        # [4] |η| < 2.1  (pre-applied, but verified here)
        probes = [i for i in probes if abs(peta[i]) < 2.1]
        if tags_iso and probes:
            counts[4] += 1

        # [5] ECAL gap veto
        probes = [i for i in probes
                  if abs(peta[i]) < 1.42 or abs(peta[i]) > 1.65]
        if tags_iso and probes:
            counts[5] += 1

        # [6] Muon-inefficiency region 1
        probes = [i for i in probes
                  if abs(peta[i]) < 0.15 or abs(peta[i]) > 0.35]
        if tags_iso and probes:
            counts[6] += 1

        # [7] Muon-inefficiency region 2
        probes = [i for i in probes
                  if abs(peta[i]) < 1.55 or abs(peta[i]) > 1.85]
        if tags_iso and probes:
            counts[7] += 1

        # [8] ≥4 total valid hits  (NOT in QualityTrackProducer)
        probes = [i for i in probes if pnh[i] >= 4]
        if tags_iso and probes:
            counts[8] += 1

        # [9] dRMinJet > 0.5
        probes = [i for i in probes
                  if dr_to_closest_jet(peta[i], pphi[i],
                                       jeta, jphi, jpt,
                                       args.min_jet_pt) > 0.5]
        if tags_iso and probes:
            counts[9] += 1

        # ── PAIR CUTS ─────────────────────────────────────────────────────────

        # [10] ≥1 (tag, probe) pair exists
        if tags_iso and probes:
            counts[10] += 1

        # [11] Z mass window
        zmass_pairs = []
        for ti in tags_iso:
            for pi in probes:
                m = inv_mass(tpt[ti], teta[ti], tphi[ti], tag_mass,
                             ppt[pi], peta[pi], pphi[pi], tag_mass)
                if args.zmass_lo < m < args.zmass_hi:
                    zmass_pairs.append((ti, pi))
        if zmass_pairs:
            counts[11] += 1

        # [12] Opposite sign
        os_pairs = [(ti, pi) for ti, pi in zmass_pairs
                    if tch[ti] * pch[pi] < 0]
        if os_pairs:
            counts[12] += 1

    # ── Build and print cutflow table ─────────────────────────────────────────
    iso_note = ("GAP: tight PF iso not yet in ntuple — "
                "add to LeptonCollectionsProducer; count = step above")

    cf = Cutflow()
    cf.add("All ntuple events  (after HLT filter)", n_events,
           "pre-applied")
    cf.add(f"  ≥1 tag {args.channel}  pT > {args.tag_pt:.0f} GeV",
           counts[0],
           f"pT>20/|η|<2.1/tight ID pre-applied")
    cf.add(f"    + trigger match",
           counts[1],
           f"{tag_pfx}_isTrigMatched")
    cf.add(f"    + tight PF isolation  [GAP]",
           counts[2],
           iso_note)
    cf.add(f"  ≥1 probe track  pT > {args.probe_pt:.0f} GeV",
           counts[3],
           "iso/hits/dxy/dz/fiducial pre-applied")
    cf.add(f"    + |η| < 2.1",
           counts[4],
           "pre-applied; verified")
    cf.add(f"    + ECAL gap veto  |η| ∉ (1.42, 1.65)",
           counts[5])
    cf.add(f"    + muon-ineff region 1  |η| ∉ (0.15, 0.35)",
           counts[6])
    cf.add(f"    + muon-ineff region 2  |η| ∉ (1.55, 1.85)",
           counts[7])
    cf.add(f"    + ≥4 total valid hits",
           counts[8],
           "NOT pre-applied in QualityTrackProducer")
    cf.add(f"    + dRMinJet > 0.5  (jets pT > {args.min_jet_pt:.0f} GeV)",
           counts[9])
    cf.add(f"  ≥1 (tag, probe) pair",
           counts[10])
    cf.add(f"    + Z mass {args.zmass_lo:.0f}–{args.zmass_hi:.0f} GeV",
           counts[11])
    cf.add(f"    + opposite sign",
           counts[12])

    cf.print()

    print("Compare 'All ntuple events' against the TrigReport event count from")
    print("wantSummary=True in ntuplizer_cfg.py, and the final OS-pair row")
    print("against the old framework's ZtoMuProbeTrkWithZCuts event count.\n")


if __name__ == "__main__":
    main()
