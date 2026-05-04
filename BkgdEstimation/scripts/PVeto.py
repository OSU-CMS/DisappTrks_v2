"""
Script to calculate PVeto from the Ntuples
"""


import uproot
import math
import awkward as ak
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd
import awkward as ak
import ROOT
import vector
vector.register_awkward()

def print_cutflow(arrays, label):
    n_events = len(arrays["trk_pt"])
    n_tracks = ak.sum(ak.num(arrays["trk_pt"]))
    print(f"{label:50s}  events: {n_events:>8,}  tracks: {n_tracks:>8,}")

def dR_mask(arrays, obj_prefix, trk_prefix="trk", dr_cut=0.5, pt_cut=None, mode="all"):
    tracks = ak.zip({
        "eta": arrays[f"{trk_prefix}_eta"],
        "phi": arrays[f"{trk_prefix}_phi"]
    })
    objs = ak.zip({
        "eta": arrays[f"{obj_prefix}_eta"],
        "phi": arrays[f"{obj_prefix}_phi"],
        "pt":  arrays[f"{obj_prefix}_pt"],
    })

    if pt_cut is not None:
        objs = objs[objs.pt > pt_cut]

    t, o  = ak.unzip(ak.cartesian([tracks, objs], nested=True))
    dphi  = np.arctan2(np.sin(t.phi - o.phi), np.cos(t.phi - o.phi))
    dR    = np.sqrt((t.eta - o.eta)**2 + dphi**2)

    if mode == "all":
        return ak.all(dR > dr_cut, axis=2)  # far from ALL objects
    elif mode == "any":
        return ak.any(dR > dr_cut, axis=2)  # far from AT LEAST ONE object

NTUPLE_FILE = "root://cmseos.fnal.gov//store/user/delossan/DisappTrks_v2_Skims/DisappTrks_Skim_2024G_SingleMuonTrigger_partial.root"
TREE_NAME   = "ntuplizer/Events"   # adjust to match treeName + TFileService path
CHUNK_SIZE = 100_000

f    = uproot.open(NTUPLE_FILE, handler=uproot.source.xrootd.XRootDSource)
tree = f[TREE_NAME]
total_entries = tree.num_entries
print(f"Entries: {total_entries:,}\n")

branches = [
    "muon_pt", "muon_eta", "muon_phi", "muon_charge",
    "ele_pt", "ele_eta", "ele_phi",
    "tau_pt", "tau_eta", "tau_phi",
    "trk_pt", "trk_eta", "trk_phi", "trk_charge",
    "trk_missingInnerHits", "trk_missingMiddleHits", "trk_missingOuterHits",
    "trk_hitDrop_missingMiddleHits",
    "trk_relativePFIso", "trk_caloTotal", "trk_caloTotNoPU",
    "jet_pt", "jet_phi", "jet_eta",
]

total_tag_probe_pairs_SS    = 0
total_tag_probe_pairs_OS    = 0
total_tag_probe_veto_SS  = 0
total_tag_probe_veto_OS  = 0


for start in range(0, total_entries, CHUNK_SIZE):
    stop   = min(start + CHUNK_SIZE, total_entries)

    print(f"Processing events from {start} to {stop}")
    arrays = tree.arrays(branches, entry_start=start, entry_stop=stop, library="ak")
    # ── 1. Muon event filter ─────────────────────────────────────────────────
    muon_pt_cut  = arrays["muon_pt"] > 26
    muon_eta_cut = np.abs(arrays["muon_eta"]) < 2.1
    good_muons   = muon_pt_cut & muon_eta_cut
    arrays       = arrays[ak.any(good_muons, axis=1)]
    good_muons = good_muons[ak.any(good_muons, axis=1)]  # keep in sync
    # then filter muon branches to only keep good muons
    arrays["muon_pt"]     = arrays["muon_pt"][good_muons]
    arrays["muon_eta"]    = arrays["muon_eta"][good_muons]
    arrays["muon_phi"]    = arrays["muon_phi"][good_muons]
    arrays["muon_charge"] = arrays["muon_charge"][good_muons]

    # ── 2. Track pT , ecalo, and eta cuts ─────────────────────────────────────────────
    track_pt_cut    = arrays["trk_pt"] > 30
    track_eta_cut   = np.abs(arrays["trk_eta"]) < 2.1
    track_eta_cut_1 = (np.abs(arrays["trk_eta"]) < 0.15) | (np.abs(arrays["trk_eta"]) > 0.35)
    track_eta_cut_2 = (np.abs(arrays["trk_eta"]) < 1.42) | (np.abs(arrays["trk_eta"]) > 1.65)
    track_eta_cut_3 = (np.abs(arrays["trk_eta"]) < 1.55) | (np.abs(arrays["trk_eta"]) > 1.85)
    track_ecalo_cut = arrays["trk_caloTotNoPU"] < 10
    track_mask      = track_pt_cut & track_eta_cut & track_eta_cut_1 & track_eta_cut_2 & track_eta_cut_3 & track_ecalo_cut

    # drop events with no passing tracks
    event_filter = ak.any(track_mask, axis=1)
    arrays       = arrays[event_filter]
    track_mask   = track_mask[event_filter]

    # filter all trk_ branches to only keep good tracks
    for field in arrays.fields:
        if field.startswith("trk_"):
            arrays = ak.with_field(arrays, arrays[field][track_mask], field)

    # get per-track boolean - DON'T slice arrays with this directly
    jet_veto = dR_mask(arrays, "jet", dr_cut=0.5, pt_cut=None, mode="any")

    # only drop events at the event level
    event_filter = ak.any(track_mask, axis=1)
    arrays       = arrays[event_filter]
    jet_veto   = jet_veto[event_filter]
    for field in arrays.fields:
        if field.startswith("trk_"):
            arrays = ak.with_field(arrays, arrays[field][jet_veto], field)

    tracks = ak.zip({
        "pt":  arrays["trk_pt"],
        "eta": arrays["trk_eta"],
        "phi": arrays["trk_phi"],
    })
    electrons = ak.zip({
        "pt": arrays["ele_pt"],
        "eta": arrays["ele_eta"],
        "phi": arrays["ele_phi"]
    })
    # cross join
    tracks_paired, electrons_paired = ak.unzip(
        ak.cartesian([tracks, electrons], nested=True)
    )
    # compute dR
    deta = tracks_paired.eta - electrons_paired.eta
    dphi = np.arctan2(
        np.sin(tracks_paired.phi - electrons_paired.phi),
        np.cos(tracks_paired.phi - electrons_paired.phi)
    )
    dR = np.sqrt(deta**2 + dphi**2)

    # mask: track must be dR > 0.15 from ALL electrons
    electron_veto_mask = ak.all(dR > 0.15, axis=2)


    # drop events with no passing tracks
    event_filter = ak.any(electron_veto_mask, axis=1)
    arrays       = arrays[event_filter]
    electron_veto_mask   = electron_veto_mask[event_filter]  # sync the mask!


    # filter all trk_ branches to only keep good tracks
    for field in arrays.fields:
        if field.startswith("trk_"):
            arrays = ak.with_field(arrays, arrays[field][electron_veto_mask], field)

    tracks = ak.zip({
        "pt":  arrays["trk_pt"],
        "eta": arrays["trk_eta"],
        "phi": arrays["trk_phi"],
    })
    taus = ak.zip({
        "pt": arrays["tau_pt"],
        "eta": arrays["tau_eta"],
        "phi": arrays["tau_phi"]
    })
    # cross join
    tracks_paired, taus_paired = ak.unzip(
        ak.cartesian([tracks, taus], nested=True)
    )
    # compute dR
    deta = tracks_paired.eta - taus_paired.eta
    dphi = np.arctan2(
        np.sin(tracks_paired.phi - taus_paired.phi),
        np.cos(tracks_paired.phi - taus_paired.phi)
    )
    dR = np.sqrt(deta**2 + dphi**2)

    # mask: track must be dR > 0.15 from ALL electrons
    tau_veto_mask = ak.all(dR > 0.15, axis=2)


    # drop events with no passing tracks
    event_filter = ak.any(tau_veto_mask, axis=1)
    arrays       = arrays[event_filter]
    tau_veto_mask   = tau_veto_mask[event_filter]  # sync the mask!


    # filter all trk_ branches to only keep good tracks
    for field in arrays.fields:
        if field.startswith("trk_"):
            arrays = ak.with_field(arrays, arrays[field][tau_veto_mask], field)

    # build 4-vector records
    tracks = ak.zip({
        "pt":     arrays["trk_pt"],
        "eta":    arrays["trk_eta"],
        "phi":    arrays["trk_phi"],
        "mass":   ak.ones_like(arrays["trk_pt"]) * 0.106,
        "charge": arrays["trk_charge"],
        "missingOuterHits": arrays["trk_missingOuterHits"],

    }, with_name="Momentum4D")

    muons = ak.zip({
        "pt":     arrays["muon_pt"],
        "eta":    arrays["muon_eta"],
        "phi":    arrays["muon_phi"],
        "mass":   ak.ones_like(arrays["muon_pt"]) * 0.106,
        "charge": arrays["muon_charge"],
    }, with_name="Momentum4D")

    # pair each track with each muon
    tracks_paired, muons_paired = ak.unzip(
        ak.cartesian([tracks, muons], nested=True)
    )

    # compute invariant mass
    pairs    = tracks_paired + muons_paired
    inv_mass = pairs.mass  # shape: [event, track, muon]

    # compute dR for all pairs (reuse for both counts)
    dphi = np.arctan2(
        np.sin(tracks_paired.phi - muons_paired.phi),
        np.cos(tracks_paired.phi - muons_paired.phi)
    )
    dR            = np.sqrt((tracks_paired.eta - muons_paired.eta)**2 + dphi**2)
    opposite_sign = tracks_paired.charge * muons_paired.charge == -1

    # define Z window and opposite sign
    z_window      = (inv_mass > 81.2) & (inv_mass < 101.2)  # 91.2 +/- 10 GeV
    opposite_sign = tracks_paired.charge * muons_paired.charge <= -1
    same_sign = tracks_paired.charge * muons_paired.charge >= 1


    # count pairs passing both criteria
    z_pairs_OS       = z_window & opposite_sign                 # shape: [event, track, muon]
    z_pairs_SS    = z_window & same_sign
    n_z_pairs_OS     = ak.sum(ak.sum(z_pairs_OS, axis=2), axis=1) # sum over muons then tracks -> per event
    n_z_pairs_SS     = ak.sum(ak.sum(z_pairs_SS, axis=2), axis=1) # sum over muons then tracks -> per event

    total_z_pairs_OS = ak.sum(n_z_pairs_OS)                        # total across all events
    total_z_pairs_SS = ak.sum(n_z_pairs_SS)                        # total across all events

    print(f"Total track-muon pairs within 10 GeV of Z mass with opposite charge: {total_z_pairs_OS:,}")
    print(f"Total track-muon pairs within 10 GeV of Z mass with same charge: {total_z_pairs_SS:,}")

    dr_cut            = dR > 0.15
    missing_outer_cut = tracks_paired.missingOuterHits >= 3
    tag_probe_pairs   = dr_cut & missing_outer_cut & opposite_sign & z_window
    n_tag_probe       = ak.sum(ak.sum(tag_probe_pairs, axis=2), axis=1)
    tag_probe_veto_OS   = ak.sum(n_tag_probe)
    print(f"Total tag and probe pairs (dR>0.15, missingOuterHits>=3, OS): {total_tag_probe_veto_OS:,}")
    print(f"Events containing at least one such pair: {ak.sum(n_tag_probe > 0):,}")

    # Opposite Sign
    tag_probe_pairs_SS = dr_cut & same_sign & z_window & missing_outer_cut
    n_tag_probe_SS = ak.sum(ak.sum(tag_probe_pairs_SS, axis=2), axis=1)
    tag_probe_veto_SS = ak.sum(n_tag_probe_SS)
    print(f"Total tag and probe pairs (dR>0.15, missingOuterHits>=3, SS): {total_tag_probe_veto_SS:,}")

    total_tag_probe_pairs_SS    += total_z_pairs_SS
    total_tag_probe_pairs_OS    += total_z_pairs_OS
    total_tag_probe_veto_SS  += tag_probe_veto_SS
    total_tag_probe_veto_OS  += tag_probe_veto_OS

PVeto = (total_tag_probe_veto_OS - total_tag_probe_veto_SS) / (total_tag_probe_pairs_OS - total_tag_probe_pairs_SS)


print(f"\n{'─'*60}")
print(f"Total Z pairs OS:          {total_tag_probe_pairs_OS:>10,} ± {math.sqrt(total_tag_probe_pairs_OS):.1f}")
print(f"Total Z pairs SS:          {total_tag_probe_pairs_SS:>10,} ± {math.sqrt(total_tag_probe_pairs_SS):.1f}")
print(f"Total tag+probe pairs OS:  {total_tag_probe_veto_OS:>10,} ± {math.sqrt(total_tag_probe_veto_OS):.1f}")
print(f"Total tag+probe pairs SS:  {total_tag_probe_veto_SS:>10,} ± {math.sqrt(total_tag_probe_veto_SS):.1f}")

print(f"Value for PVeto: ", PVeto)
