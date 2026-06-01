#!/usr/bin/env python3
"""
Muon background estimate from DisappTrks_v2 flat ntuples.

This reproduces the muon section of
DisappTrks/BackgroundEstimation/test/bkgdEstimate_2023.py without OSUT3
histogram files.  The estimate is

    N_est = N_ctrl * P_veto * P_offlineMET * P_METtrig / trigger_eff

where N_ctrl and P_offlineMET are counted in SingleMuon-triggered v2 ntuples,
P_veto is counted from Z->mu+track tag-probe pairs, and P_METtrig is measured
from a MET-triggered ntuple divided by a SingleMuon denominator ntuple.

The v2 ntuplizer stores lepton trigger matching but not generic HLT decisions,
so this script expects separate ntuples produced with trigger=SingleMuon and
trigger=MET in ntuplizer_cfg.py.
"""

from __future__ import annotations

import argparse
import glob
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from helper_functions import print_cutflow, compute_cutflow

try:
    import awkward as ak
    import numpy as np
    import uproot
    import vector
except ModuleNotFoundError as exc:
    raise SystemExit(
        f"Missing Python dependency: {exc.name}. Run inside the CMSSW/python "
        "environment used for the v2 ntuple notebooks, or install uproot, "
        "awkward, numpy, and vector."
    ) from exc

vector.register_awkward()

MUON_MASS = 0.105658
Z_MASS = 91.1876


@dataclass
class Count:
    value: float = 0.0
    variance: float = 0.0

    @property
    def error(self) -> float:
        return math.sqrt(max(self.variance, 0.0))

    def add_poisson(self, n: float) -> None:
        self.value += float(n)
        self.variance += float(n)

    def __sub__(self, other: "Count") -> "Count":
        return Count(self.value - other.value, self.variance + other.variance)

    def __mul__(self, other: "Count | float") -> "Count":
        if isinstance(other, Count):
            value = self.value * other.value
            rel2 = _rel_var(self) + _rel_var(other)
            return Count(value, value * value * rel2)
        return Count(self.value * other, self.variance * other * other)

    def __truediv__(self, other: "Count | float") -> "Count":
        if isinstance(other, Count):
            if other.value == 0.0:
                return Count(0.0, 0.0)
            value = self.value / other.value
            rel2 = _rel_var(self) + _rel_var(other)
            return Count(value, value * value * rel2)
        if other == 0.0:
            return Count(0.0, 0.0)
        return Count(self.value / other, self.variance / (other * other))


@dataclass
class Totals:
    n_ctrl: Count
    p_veto_num_os: Count
    p_veto_num_ss: Count
    p_veto_den_os: Count
    p_veto_den_ss: Count
    p_offline_num: Count
    p_offline_den: Count
    met_trigger_den_hist: np.ndarray
    met_trigger_num_hist: np.ndarray
    met_offline_hist: np.ndarray
    met_weighted_num: Count
    met_weighted_den: Count


def _rel_var(x: Count) -> float:
    return x.variance / (x.value * x.value) if x.value != 0.0 else 0.0


def parse_inputs(items: Iterable[str]) -> list[str]:
    files: list[str] = []
    for item in items:
        if any(ch in item for ch in "*?["):
            files.extend(sorted(glob.glob(item)))
        else:
            files.append(item)
    return files

def delta_phi(phi1, phi2):
    return np.arctan2(np.sin(phi1 - phi2), np.cos(phi1 - phi2))

def trans_mass(arrays, prefix: str):
    dphi = delta_phi(arrays[f"{prefix}_phi"], arrays["metNoMu_phi"])
    return np.sqrt(
        2.0
        * arrays[f"{prefix}_pt"]
        * arrays["metNoMu_pt"]
        * (1.0 - np.cos(dphi))
    )
#Calculates the deltaR between each track and the object specified by "prefix" having pT > obj_pt_min.
#It returns a mask that is requiring the deltaR be > max_dr, which is passed to this function.
def min_delta_r_mask(arrays, prefix: str, max_dr: float, obj_pt_min: float | None = None):
    tracks = ak.zip({"eta": arrays["trk_eta"], "phi": arrays["trk_phi"]})
    objs = ak.zip({
        "eta": arrays[f"{prefix}_eta"],
        "phi": arrays[f"{prefix}_phi"],
        "pt": arrays[f"{prefix}_pt"],
    })
    if obj_pt_min is not None:
        objs = objs[objs.pt > obj_pt_min]

    trk, obj = ak.unzip(ak.cartesian([tracks, objs], nested=True))
    dr = np.sqrt((trk.eta - obj.eta) ** 2 + delta_phi(trk.phi, obj.phi) ** 2)
    return ak.fill_none(ak.all(dr > max_dr, axis=2), True)


#Returns a mask for tracks that are matched with a muon.  That means deltaR(trk, muon) < max_dr.
#Applying this mask will give tracks that have been reconstructed as muons.
def matched_muon_mask(arrays, max_dr: float = 0.15):
    tracks = ak.zip({"eta": arrays["trk_eta"], "phi": arrays["trk_phi"]})
    muons = ak.zip({"eta": arrays["muon_eta"], "phi": arrays["muon_phi"]})
    trk, mu = ak.unzip(ak.cartesian([tracks, muons], nested=True))
    dr = np.sqrt((trk.eta - mu.eta) ** 2 + delta_phi(trk.phi, mu.phi) ** 2)
    return ak.fill_none(ak.any(dr < max_dr, axis=2), False)


def leading_jet_delta_phi(arrays):
    good = (arrays["jet_pt"] > 110.0) & (np.abs(arrays["jet_eta"]) < 2.4) & arrays["jet_isTightLepVeto"]
    jet_pt = arrays["jet_pt"][good]
    jet_phi = arrays["jet_phi"][good]
    order = ak.argsort(jet_pt, ascending=False)
    leading_phi = ak.firsts(jet_phi[order])
    return np.abs(delta_phi(arrays["metNoMu_phi"], leading_phi))


def dijet_delta_phi_ok(arrays):
    good = (arrays["jet_pt"] > 110.0) & (np.abs(arrays["jet_eta"]) < 2.4) & arrays["jet_isTightLepVeto"]
    phis = arrays["jet_phi"][good]
    a, b = ak.unzip(ak.combinations(phis, 2, axis=1))
    max_dphi = ak.fill_none(ak.max(np.abs(delta_phi(a, b)), axis=1), 0.0)
    return max_dphi < 2.5

#Used to select a muon as a tag for use in tag-and-probe.
#The pT cut for a muon should be passed to this function as pt_min.
#Need to add the transverse mass
def tag_muon_mask(arrays, pt_min: float):
    mt = trans_mass(arrays, "muon")
    return (
        arrays["muon_isTrigMatched"]
        & (arrays["muon_pt"] > pt_min)
        & (np.abs(arrays["muon_eta"]) < 2.1)
        & arrays["muon_isTight"]
        & (mt < 40.0)
#        & (arrays["muon_pfRelIso04_dBeta"] < 0.15)
    )


def base_track_mask(arrays, pt_min: float, layer: str, require_d0_dz: bool = True):
    n_layers = arrays["trk_hp_trackerLayersWithMeasurement"]
    if layer == "NLayers4":
        layer_mask = n_layers == 4
    elif layer == "NLayers5":
        layer_mask = n_layers == 5
    elif layer == "NLayers6plus":
        layer_mask = n_layers >= 6
    elif layer == "combinedBins":
        layer_mask = n_layers >= 4
    else:
        raise ValueError(f"Unsupported layer bin: {layer}")

    mask = (
        (arrays["trk_pt"] > pt_min)
        & (np.abs(arrays["trk_eta"]) < 2.1)
        & ((np.abs(arrays["trk_eta"]) < 1.42) | (np.abs(arrays["trk_eta"]) > 1.65))
        & ((np.abs(arrays["trk_eta"]) < 0.15) | (np.abs(arrays["trk_eta"]) > 0.35))
        & ((np.abs(arrays["trk_eta"]) < 1.55) | (np.abs(arrays["trk_eta"]) > 1.85))
        & (arrays["trk_hp_numberOfValidPixelHits"] >= 4)
        & (arrays["trk_hp_numberOfValidHits"] >= 4)
        & (arrays["trk_missingInnerHits"] == 0)
        & (arrays["trk_hitDrop_missingMiddleHits"] == 0)
        & (arrays["trk_relativePFIso"] < 0.05)
        & (arrays["trk_caloTotNoPU"] < 10.0)
        & layer_mask
    )
    if require_d0_dz:
        mask = mask & (np.abs(arrays["trk_dxy"]) < 0.02) & (np.abs(arrays["trk_dz"]) < 0.5)
    return mask

def fiducial_track_mask(arrays):
    mask = (
        (np.abs(arrays["trk_eta"]) < 2.1)
        & ((np.abs(arrays["trk_eta"]) < 1.42) | (np.abs(arrays["trk_eta"]) > 1.65))
        & ((np.abs(arrays["trk_eta"]) < 0.15) | (np.abs(arrays["trk_eta"]) > 0.35))
        & ((np.abs(arrays["trk_eta"]) < 1.55) | (np.abs(arrays["trk_eta"]) > 1.85))
    )

    return mask
#Creates a mask to veto tracks within a certain deltaR of electrons, taus, and jets
def lepton_track_veto_mask(arrays):
    return (
        min_delta_r_mask(arrays, "ele", 0.15)
        #& min_delta_r_mask(arrays, "tau", 0.15). #No tau cuts/cleaning makes this kill everything
#        & min_delta_r_mask(arrays, "jet", 0.5). #Per analysis note, this is not used for tag and probe selection
    )


def selected_tag_pt55_events(arrays, layer: str):
    muon_ok = ak.any(tag_muon_mask(arrays, 35.0), axis=1)
    jet_ok = ak.any((arrays["jet_pt"] > 110.0) & (np.abs(arrays["jet_eta"]) < 2.4) & arrays["jet_isTightLepVeto"], axis=1)
    event_ok = muon_ok & jet_ok & dijet_delta_phi_ok(arrays)

    trk_ok = (
        base_track_mask(arrays, 55.0, layer)
        & lepton_track_veto_mask(arrays)
        & matched_muon_mask(arrays)
    )
    event_ok = event_ok & ak.any(trk_ok, axis=1)
    return event_ok

#This counts up the N_T&P for muons and tracks.
def tag_probe_pair_counts(arrays, layer: str):
    muon_ok = tag_muon_mask(arrays, 26.0)
    trk_ok = base_track_mask(arrays, 30.0, layer) & lepton_track_veto_mask(arrays)

    muons = ak.zip({
        "pt": arrays["muon_pt"][muon_ok],
        "eta": arrays["muon_eta"][muon_ok],
        "phi": arrays["muon_phi"][muon_ok],
        "mass": ak.ones_like(arrays["muon_pt"][muon_ok]) * MUON_MASS,
        "charge": arrays["muon_charge"][muon_ok],
    }, with_name="Momentum4D")
    tracks = ak.zip({
        "pt": arrays["trk_pt"][trk_ok],
        "eta": arrays["trk_eta"][trk_ok],
        "phi": arrays["trk_phi"][trk_ok],
        "mass": ak.ones_like(arrays["trk_pt"][trk_ok]) * MUON_MASS,
        "charge": arrays["trk_charge"][trk_ok],
        "missingOuterHits": arrays["trk_missingOuterHits"][trk_ok],
    }, with_name="Momentum4D")

    trk, mu = ak.unzip(ak.cartesian([tracks, muons], nested=True))
    mass = (trk + mu).mass
    z_window = (mass > Z_MASS - 10.0) & (mass < Z_MASS + 10.0)
    separated = np.sqrt((trk.eta - mu.eta) ** 2 + delta_phi(trk.phi, mu.phi) ** 2) > 0.15
    os_pair = trk.charge * mu.charge < 0
    ss_pair = trk.charge * mu.charge > 0
    passes_veto = trk.missingOuterHits >= 3

    den_os = ak.sum(z_window & separated & os_pair)
    den_ss = ak.sum(z_window & separated & ss_pair)
    num_os = ak.sum(z_window & separated & os_pair & passes_veto)
    num_ss = ak.sum(z_window & separated & ss_pair & passes_veto)
    return float(num_os), float(num_ss), float(den_os), float(den_ss)


def hist_counts(values, bins):
    vals = ak.to_numpy(ak.flatten(values, axis=None))
    return np.histogram(vals, bins=bins)[0].astype(float)


def process_file_set(files, tree_name, layer, bins, chunk_size, need_pairs=True):
    from collections import OrderedDict
    cutflow_totals = OrderedDict()
    out = {
        "n_ctrl": Count(),
        "p_veto_num_os": Count(),
        "p_veto_num_ss": Count(),
        "p_veto_den_os": Count(),
        "p_veto_den_ss": Count(),
        "p_offline_num": Count(),
        "p_offline_den": Count(),
        "met_den_hist": np.zeros(len(bins) - 1, dtype=float),
        "met_num_hist": np.zeros(len(bins) - 1, dtype=float),
    }
    branches = [
        "metNoMu_pt", "metNoMu_phi",
        "muon_pt", "muon_eta", "muon_phi", "muon_charge", "muon_isTrigMatched",
        "muon_isTight", "muon_pfRelIso04_dBeta",
        "ele_pt", "ele_eta", "ele_phi",
        "tau_pt", "tau_eta", "tau_phi",
        "jet_pt", "jet_eta", "jet_phi", "jet_isTightLepVeto",
        "trk_pt", "trk_eta", "trk_phi", "trk_charge", "trk_dxy", "trk_dz",
        "trk_missingInnerHits", "trk_missingMiddleHits", "trk_missingOuterHits",
        "trk_hitDrop_missingMiddleHits", "trk_relativePFIso", "trk_caloTotNoPU",
        "trk_hp_numberOfValidPixelHits", "trk_hp_numberOfValidHits",
        "trk_hp_trackerLayersWithMeasurement",
    ]

    for filename in files:
        tree_path = f"{filename}:{tree_name}"
        for arrays in uproot.iterate(tree_path, branches, step_size=chunk_size, library="ak"):
            # Build cuts (same as before)
           # print(f'jet debug {ak.sum(arrays["jet_eta"] < 4.5)}')
            
            muon_cuts = {
                "muon: isTrigMatched": arrays["muon_isTrigMatched"],
                "muon: pt > 26": arrays["muon_pt"] > 26.0,
                "muon: |eta| < 2.1": abs(arrays["muon_eta"]) < 2.1,
                "muon: tight": arrays["muon_isTight"],
                "muon: iso < 0.15": arrays["muon_pfRelIso04_dBeta"] < 0.15,
                #"muon: mT < 40": trans_mass(arrays, "muon") < 40.0,
            }
            #trk = base_track_mask(arrays, 30.0, layer) & lepton_track_veto_mask(arrays)
            trk = arrays
            track_cuts = {
                "trk: pt > 30": trk["trk_pt"] > 30.0,
            }
            track_cuts["trk: passing fiducial selections"] = fiducial_track_mask(arrays)
            track_cuts["trk: number of pixel hits >= 4"] = arrays["trk_hp_numberOfValidPixelHits"] >= 4
            track_cuts["trk: missing inner hits == 0"] = arrays["trk_missingInnerHits"] == 0
            track_cuts["trk: missing middle hits ==0"] = arrays["trk_hitDrop_missingMiddleHits"] == 0
            track_cuts["trk: rel PF-based iso"] = arrays["trk_relativePFIso"] < 0.05
        #& (arrays["trk_hp_numberOfValidHits"] >= 4)
            track_cuts["trk: lepton veto"] = lepton_track_veto_mask(arrays)
            #track_cuts["trk: matched muon"] = matched_muon_mask(arrays)
            track_cuts["trk: Ecalo < 10GeV"] = arrays["trk_caloTotNoPU"] < 10

            # Event cuts
            event_cuts = {}

            #muon_mask = tag_muon_mask(arrays, 26.0)
            #event_cuts[">=1 tag muon"] = ak.any(muon_mask, axis=1)

            #jet_mask = (
            #    (arrays["jet_pt"] > 110.0) #changed from 110.0
            #    & (abs(arrays["jet_eta"]) < 2.4) #changed from 2.4
            #    & arrays["jet_isTightLepVeto"]
            #)
            #event_cuts[">=1 jet"] = ak.any(jet_mask, axis=1)
            
            #event_cuts["dijet dphi"] = dijet_delta_phi_ok(arrays)

            dphi = leading_jet_delta_phi(arrays)
            #event_cuts["MET > 120"] = arrays["metNoMu_pt"] >= 120.0
            #event_cuts["Δφ(jet,MET) > 0.5"] = dphi >= 0.5
            # ---------------------------------------------------------
            # Build cumulative muon object mask
            # ---------------------------------------------------------

            cumulative_muon_mask = None

            for cut in muon_cuts.values():

                cumulative_muon_mask = (
                    cut if cumulative_muon_mask is None
                    else cumulative_muon_mask & cut
                )

            # Event passes if >=1 muon survives
            muon_event_selection = ak.any(cumulative_muon_mask, axis=1)

            # ---------------------------------------------------------
            # Build cumulative track object mask
            # ---------------------------------------------------------

            cumulative_track_mask = None

            for cut in track_cuts.values():

                cumulative_track_mask = (
                    cut if cumulative_track_mask is None
                    else cumulative_track_mask & cut
                )

            # Event passes if >=1 track survives
            track_event_selection = ak.any(cumulative_track_mask, axis=1)

            # =========================================================
            # Full cumulative event selection
            # =========================================================

            event_selection = (
                muon_event_selection
                & track_event_selection
            )

            for cut in event_cuts.values():
                event_selection = event_selection & cut

            print("events after full selection:", ak.sum(event_selection))

            # =========================================================
            # Apply selection
            # =========================================================

            selected_arrays = arrays[event_selection]

            # =========================================================
            # Cutflow
            # =========================================================

            results = compute_cutflow(
                object_cuts=[
                    {"label": "Muon", "cuts": muon_cuts},
                    {"label": "Track", "cuts": track_cuts},
                ],
                event_cuts=event_cuts,
            )

            for name, val in results:
                cutflow_totals[name] = cutflow_totals.get(name, 0) + val

            selected = selected_tag_pt55_events(arrays, layer)
            n_selected = float(ak.sum(selected))
            out["n_ctrl"].add_poisson(n_selected)
            out["p_offline_den"].add_poisson(n_selected)

            dphi = leading_jet_delta_phi(arrays)
            offline = selected & (arrays["metNoMu_pt"] >= 120.0) & (dphi >= 0.5)
            out["p_offline_num"].add_poisson(float(ak.sum(offline)))
            out["met_den_hist"] += hist_counts(arrays["metNoMu_pt"][selected], bins)
            out["met_num_hist"] += hist_counts(arrays["metNoMu_pt"][offline], bins)

            if need_pairs:
                num_os, num_ss, den_os, den_ss = tag_probe_pair_counts(selected_arrays, layer)
                out["p_veto_num_os"].add_poisson(num_os)
                out["p_veto_num_ss"].add_poisson(num_ss)
                out["p_veto_den_os"].add_poisson(den_os)
                out["p_veto_den_ss"].add_poisson(den_ss)
    return out, cutflow_totals


def weighted_trigger_probability(den_offline_hist, den_hist, num_hist):
    eff = np.divide(num_hist, den_hist, out=np.zeros_like(num_hist), where=den_hist > 0.0)
    weighted = den_offline_hist * eff
    num = Count(float(np.sum(weighted)), float(np.sum(weighted)))
    den = Count(float(np.sum(den_offline_hist)), float(np.sum(den_offline_hist)))
    return num / den if den.value > 0.0 else Count(), num, den


def merge_totals(den, met_num):
    return Totals(
        n_ctrl=den["n_ctrl"],
        p_veto_num_os=den["p_veto_num_os"],
        p_veto_num_ss=den["p_veto_num_ss"],
        p_veto_den_os=den["p_veto_den_os"],
        p_veto_den_ss=den["p_veto_den_ss"],
        p_offline_num=den["p_offline_num"],
        p_offline_den=den["p_offline_den"],
        met_trigger_den_hist=den["met_den_hist"],
        met_trigger_num_hist=met_num["met_den_hist"],
        met_offline_hist=den["met_num_hist"],
        met_weighted_num=Count(),
        met_weighted_den=Count(),
    )


def format_count(label, count):
    return f"{label:28s} {count.value:12.6g} +/- {count.error:.6g}"


def run(args):
    single_muon_files = parse_inputs(args.single_muon)
    met_files = parse_inputs(args.met)
    if not single_muon_files:
        print("WARNING: no single-muon files")
    if not met_files:
        print("WARNING: no MET files")
    #if not single_muon_files:   
        #raise RuntimeError("No SingleMuon denominator ntuples matched --single-muon.")
    #if not met_files:
        #raise RuntimeError("No MET-trigger numerator ntuples matched --met.")

    bins = np.asarray(args.met_bins, dtype=float)
    layers_to_run = (
        ["NLayers4", "NLayers5", "NLayers6plus", "combinedBins"]
        if args.layers == "all"
        else [args.layers]
    )

    all_results = {}
    for layer in layers_to_run:

        print(f"\nRunning layer: {layer}")

        den, cutflow_den = process_file_set(
            single_muon_files,
            args.tree,
            layer,
            bins,
            args.chunk_size,
            True,
        )

        met, cutflow_met = process_file_set(
            met_files,
            args.tree,
            layer,
            bins,
            args.chunk_size,
            False,
        )

        totals = merge_totals(den, met)

        all_results[layer] = {
            "totals": totals,
            "cutflow_den": cutflow_den,
            "cutflow_met": cutflow_met,
        }
    #den, cutflow_den = process_file_set(single_muon_files, args.tree, args.layers, bins, args.chunk_size, True)
    #met, cutflow_met = process_file_set(met_files, args.tree, args.layers, bins, args.chunk_size, False)
    #totals = merge_totals(den, met)
    
    from collections import OrderedDict

    cutflow_totals = OrderedDict()

    for d in [cutflow_den, cutflow_met]:
        for k, v in d.items():
            cutflow_totals[k] = cutflow_totals.get(k, 0) + v

    for layer, result in all_results.items():

        totals = result["totals"]

        print("\n" + "="*80)
        print(f"Layer bin: {layer}")
        print("="*80)

        p_veto_num = totals.p_veto_num_os - totals.p_veto_num_ss
        p_veto_den = totals.p_veto_den_os - totals.p_veto_den_ss
        p_veto = p_veto_num / p_veto_den

        p_offline = totals.p_offline_num / totals.p_offline_den

        p_mettrig, weighted_num, weighted_den = weighted_trigger_probability(
            totals.met_offline_hist,
            totals.met_trigger_den_hist,
            totals.met_trigger_num_hist,
        )

        n_ctrl = totals.n_ctrl * args.prescale

        alpha = p_veto * p_offline * p_mettrig / args.trigger_eff

        n_est = n_ctrl * alpha

        print(format_count("N_ctrl raw", totals.n_ctrl))
        print(format_count("P_veto", p_veto))
        print(format_count("P_offlineMET", p_offline))
        print(format_count("P_METtrig", p_mettrig))
        print(format_count("alpha", alpha))
        print(format_count("N_est", n_est))

    if args.output:
        path = Path(args.output)
        with uproot.recreate(path) as fout:
            #fout["met_trigger_counts"] = {
            #    "bin_low": bins[:-1],
            #    "bin_high": bins[1:],
            #    "den": totals.met_trigger_den_hist,
            #    "num": totals.met_trigger_num_hist,
            #    "offline_shape": totals.met_offline_hist,
            #}
            for layer, result in all_results.items():
                totals = result["totals"]
                fout[f"{layer}/p_veto_num_os"] = np.histogram(
                    [0.5],
                    bins=1,
                    range=(0, 1),
                    weights=[totals.p_veto_num_os.value],
                )

                fout[f"{layer}/p_veto_num_ss"] = np.histogram(
                    [0.5],
                    bins=1,
                    range=(0, 1),
                    weights=[totals.p_veto_num_ss.value],
                )

                fout[f"{layer}/p_veto_den_os"] = np.histogram(
                    [0.5],
                    bins=1,
                    range=(0, 1),
                    weights=[totals.p_veto_den_os.value],
                )

                fout[f"{layer}/p_veto_den_ss"] = np.histogram(
                    [0.5],
                    bins=1,
                    range=(0, 1),
                    weights=[totals.p_veto_den_ss.value],
                )
      
    print(f"\nWrote {path}")
    print("\nFinal Cutflow (combined over all chunks):")
    print(f"{'Cut':40s} {'Events':>12s} {'eff(prev)':>12s} {'eff(total)':>12s}")

    first = None
    prev = None

    for name, val in cutflow_totals.items():
        if first is None:
            first = val

        eff_prev = val / prev if prev else 1.0
        eff_total = val / first if first else 0.0

        print(f"{name:40s} {val:12d} {eff_prev:12.4f} {eff_total:12.4f}")

        prev = val

    import json

    if args.partial_output:
        Path(args.partial_output).parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "cutflow": dict(cutflow_totals),
            "n_ctrl": totals.n_ctrl.value,
            "n_ctrl_var": totals.n_ctrl.variance,
        }

        with open(args.partial_output, "w") as f:
            json.dump(payload, f)

def main():
    parser = argparse.ArgumentParser(
        description="Reproduce the bkgdEstimate_2023.py muon estimate using DisappTrks_v2 ntuples."
    )
    parser.add_argument("--single-muon", nargs="+", required=True, help="SingleMuon-triggered ntuple files or globs.")
    parser.add_argument("--met", nargs="+", required=True, help="MET-triggered ntuple files or globs.")
    parser.add_argument("--tree", default="ntuplizer/Events", help="TTree path inside each ROOT file.")
    parser.add_argument("--layers", default="all", choices=["NLayers4", "NLayers5", "NLayers6plus", "combinedBins", "all"])
    parser.add_argument("--prescale", type=float, default=1.0, help="Old-script lumi(MET)/lumi(Muon) factor.")
    parser.add_argument("--trigger-eff", type=float, default=0.940, help="External single-muon trigger efficiency divisor.")
    parser.add_argument("--chunk-size", default="100 MB", help="uproot iterate step_size.")
    parser.add_argument("--output", help="Optional ROOT output with MET trigger numerator/denominator histograms.")
    parser.add_argument("--partial-output", help="Write per-job JSON output")
    parser.add_argument(
        "--met-bins",
        nargs="+",
        type=float,
        default=[0, 50, 75, 100, 120, 140, 160, 180, 200, 250, 300, 400, 600, 1000],
        help="MET bin edges for P_METtrig.",
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
