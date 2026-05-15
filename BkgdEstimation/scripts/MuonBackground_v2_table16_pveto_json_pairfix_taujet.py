#!/usr/bin/env python3

from __future__ import annotations

import argparse
import glob
import json
import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import awkward as ak
import numpy as np
import uproot
import vector

vector.register_awkward()

MUON_MASS = 0.105658
Z_MASS = 91.1876


@dataclass
class Count:
    value: float = 0.0
    variance: float = 0.0

    @property
    def error(self):
        return math.sqrt(max(self.variance, 0.0))

    def add_poisson(self, n):
        self.value += float(n)
        self.variance += float(n)


def parse_inputs(items: Iterable[str]) -> list[str]:
    files = []
    for item in items:
        if any(ch in item for ch in "*?["):
            files.extend(sorted(glob.glob(item)))
        else:
            files.append(item)
    return files


def delta_phi(phi1, phi2):
    return np.arctan2(np.sin(phi1 - phi2), np.cos(phi1 - phi2))


def trans_mass(arrays, prefix):
    dphi = delta_phi(arrays[f"{prefix}_phi"], arrays["metNoMu_phi"])
    return np.sqrt(
        2.0
        * arrays[f"{prefix}_pt"]
        * arrays["metNoMu_pt"]
        * (1.0 - np.cos(dphi))
    )


def min_delta_r_mask(arrays, prefix, min_dr):
    """
    Per-track mask requiring min DeltaR(track, object) > min_dr.

    This uses ALL reconstructed objects of the requested prefix in the event.
    For prefix='muon', this is the muon-veto requirement from Table 21:
        min DeltaR(track, muon) > 0.15
    """
    tracks = ak.zip({
        "eta": arrays["trk_eta"],
        "phi": arrays["trk_phi"],
    })

    objs = ak.zip({
        "eta": arrays[f"{prefix}_eta"],
        "phi": arrays[f"{prefix}_phi"],
    })

    trk, obj = ak.unzip(ak.cartesian([tracks, objs], nested=True))

    dr = np.sqrt(
        (trk.eta - obj.eta) ** 2
        + delta_phi(trk.phi, obj.phi) ** 2
    )

    # True if the track is farther than min_dr from every object.
    # If there are no such objects in the event, the veto passes.
    return ak.fill_none(ak.all(dr > min_dr, axis=2), True)


def any_pair_per_event(pair_mask):
    """
    Reduce an event -> track -> muon pair mask to one boolean per event.

    Pair masks made from ak.cartesian([tracks, muons], nested=True) have
    two jagged pair axes.  The cutflow add(...) function needs a flat
    event-level boolean mask, so first collapse the track/muon pair axes
    and then ask whether any pair passed in each event.
    """
    return ak.any(ak.flatten(pair_mask, axis=2), axis=1)


def layer_mask(arrays, layer):
    n_layers = arrays["trk_hp_trackerLayersWithMeasurement"]

    if layer == "NLayers4":
        return n_layers == 4
    if layer == "NLayers5":
        return n_layers == 5
    if layer == "NLayers6plus":
        return n_layers >= 6
    if layer == "combinedBins":
        return n_layers >= 4

    raise ValueError(f"Unknown layer bin: {layer}")


def fiducial_eta_mask(arrays):
    return (
        ((np.abs(arrays["trk_eta"]) < 0.15) | (np.abs(arrays["trk_eta"]) > 0.35))
        & ((np.abs(arrays["trk_eta"]) < 1.42) | (np.abs(arrays["trk_eta"]) > 1.65))
        & ((np.abs(arrays["trk_eta"]) < 1.55) | (np.abs(arrays["trk_eta"]) > 1.85))
    )


def muon_tag_mask(arrays):
    # Input ntuple is assumed to already be SingleMuon-triggered.
    mask = arrays["muon_isTrigMatched"]
    mask = mask & (arrays["muon_pt"] > 26)
    mask = mask & (np.abs(arrays["muon_eta"]) < 2.1)
    mask = mask & arrays["muon_isTight"]

    # Section 5.1 adds this cut for charged-lepton T&P samples to reduce W+jets.
    mask = mask & (trans_mass(arrays, "muon") < 40)
    return mask


def probe_track_denominator_mask(arrays, layer):
    """
    Probe-track denominator selection for the muon Pveto measurement.

    This is the Table 16-style probe track selection with the muon veto removed.
    The muon veto is applied only in the numerator via:
        min DeltaR(track, muon) > 0.15
        missing outer hits >= 3
    """
    mask = arrays["trk_pt"] > 30
    mask = mask & (np.abs(arrays["trk_eta"]) < 2.1)
    mask = mask & fiducial_eta_mask(arrays)

    # The following Table 16 cuts need branches/maps not present in this flat ntuple
    # or are applied upstream in the ntuplizer/preselection:
    #   min DeltaR(track, noisy/dead ECAL channel) > 0.05  [applied upstream]
    #   |dz| > 0.5 cm OR |lambda| > 1e-3                [not available here]

    mask = mask & (arrays["trk_hp_numberOfValidPixelHits"] >= 4)
    mask = mask & (arrays["trk_missingInnerHits"] == 0)
    mask = mask & (arrays["trk_hitDrop_missingMiddleHits"] == 0)
    mask = mask & (arrays["trk_relativePFIso"] < 0.05)
    mask = mask & (np.abs(arrays["trk_dxy"]) < 0.02)
    mask = mask & (np.abs(arrays["trk_dz"]) < 0.5)

    # Table 16 track-jet and lepton-veto rows.
    # Keep the muon veto OUT of the denominator; it is the Pveto numerator split.
    #mask = mask & min_delta_r_mask(arrays, "jet", 0.5)
    mask = mask & min_delta_r_mask(arrays, "ele", 0.15)
    #mask = mask & min_delta_r_mask(arrays, "tau", 0.15)

    # Table 16 Ecalo row.
    mask = mask & (arrays["trk_caloTotNoPU"] < 10)

    # Final signal-region layer bin.
    mask = mask & layer_mask(arrays, layer)

    return mask


def build_muon_vectors(arrays, mask):
    return ak.zip({
        "pt": arrays["muon_pt"][mask],
        "eta": arrays["muon_eta"][mask],
        "phi": arrays["muon_phi"][mask],
        "mass": ak.ones_like(arrays["muon_pt"][mask]) * MUON_MASS,
        "charge": arrays["muon_charge"][mask],
    }, with_name="Momentum4D")


def build_track_vectors(arrays, mask):
    muon_veto = min_delta_r_mask(arrays, "muon", 0.15)

    return ak.zip({
        "pt": arrays["trk_pt"][mask],
        "eta": arrays["trk_eta"][mask],
        "phi": arrays["trk_phi"][mask],
        "mass": ak.ones_like(arrays["trk_pt"][mask]) * MUON_MASS,
        "charge": arrays["trk_charge"][mask],
        "missingOuterHits": arrays["trk_missingOuterHits"][mask],
        "passesMuonVeto": muon_veto[mask],
    }, with_name="Momentum4D")


def make_tp_cutflow(arrays, layer):
    """
    Cutflow with labels matched to Table 16 as closely as possible.

    Rows that require unavailable flat-ntuple branches/maps are omitted:
      - min DeltaR(track, noisy/dead ECAL channel) > 0.05  [applied upstream]
      - |dz| > 0.5 cm OR |lambda| > 1e-3                [not available here]

    The track-jet DeltaR, electron veto, and tau veto rows are applied here.
    The muon veto is NOT applied to the denominator; it is used only to split
    the Pveto numerator according to Table 21.
    """
    cutflow = OrderedDict()

    event_mask = ak.ones_like(arrays["metNoMu_pt"], dtype=bool)

    def add(label, mask):
        nonlocal event_mask
        event_mask = event_mask & mask
        cutflow[label] = int(ak.sum(event_mask))

    # The ntuple is assumed to be made from the SingleMuon-triggered dataset.
    add("event passes SingleMuon triggers", ak.ones_like(arrays["metNoMu_pt"], dtype=bool))

    mu = arrays["muon_isTrigMatched"]

    mu = mu & (arrays["muon_pt"] > 26)
    add(">= 1 muons pT > 26 GeV", ak.any(mu, axis=1))

    mu = mu & (np.abs(arrays["muon_eta"]) < 2.1)
    add(">= 1 muons |eta| < 2.1", ak.any(mu, axis=1))

    mu = mu & arrays["muon_isTight"]
    add(">= 1 muons passing tight muon ID", ak.any(mu, axis=1))

    mu = mu & (trans_mass(arrays, "muon") < 40)
    add(">= 1 muons MT(pTmiss, muon) < 40 GeV", ak.any(mu, axis=1))

    # For the Pveto calculation in Section 5.1, all unique passing pairs are used.
    # Keep this Table 16-style row as a bookkeeping row without reducing the sample.
    add("exactly one passing muon chosen randomly", ak.any(mu, axis=1))

    trk = arrays["trk_pt"] > 30
    add(">= 1 tracks pT > 30 GeV", ak.any(trk, axis=1))

    trk = trk & (np.abs(arrays["trk_eta"]) < 2.1)
    add(">= 1 tracks |eta| < 2.1", ak.any(trk, axis=1))

    trk = trk & ((np.abs(arrays["trk_eta"]) < 0.15) | (np.abs(arrays["trk_eta"]) > 0.35))
    add(">= 1 tracks |eta| < 0.15 OR |eta| > 0.35", ak.any(trk, axis=1))

    trk = trk & ((np.abs(arrays["trk_eta"]) < 1.42) | (np.abs(arrays["trk_eta"]) > 1.65))
    add(">= 1 tracks |eta| < 1.42 OR |eta| > 1.65", ak.any(trk, axis=1))

    trk = trk & ((np.abs(arrays["trk_eta"]) < 1.55) | (np.abs(arrays["trk_eta"]) > 1.85))
    add(">= 1 tracks |eta| < 1.55 OR |eta| > 1.85", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_hp_numberOfValidPixelHits"] >= 4)
    add(">= 1 tracks number of pixel hits >= 4", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_missingInnerHits"] == 0)
    add(">= 1 tracks missing inner hits = 0", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_hitDrop_missingMiddleHits"] == 0)
    add(">= 1 tracks missing middle hits = 0", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_relativePFIso"] < 0.05)
    add(">= 1 tracks rel. PF-based iso. < 0.05", ak.any(trk, axis=1))

    trk = trk & (np.abs(arrays["trk_dxy"]) < 0.02)
    add(">= 1 tracks |dxy| < 0.02 cm", ak.any(trk, axis=1))

    trk = trk & (np.abs(arrays["trk_dz"]) < 0.5)
    add(">= 1 tracks |dz| < 0.5 cm", ak.any(trk, axis=1))

    #trk = trk & min_delta_r_mask(arrays, "jet", 0.5)
    #add(">= 1 track-jet pairs DeltaRtrack,jet > 0.5", ak.any(trk, axis=1))

    # Build pre-veto tag-probe pairs for the Table 16 M(track,muon) row.
    muons = build_muon_vectors(arrays, mu)
    tracks_pre_veto = build_track_vectors(arrays, trk)
    trk_obj, mu_obj = ak.unzip(ak.cartesian([tracks_pre_veto, muons], nested=True))

    mass = (trk_obj + mu_obj).mass
    pair_mass_gt_10 = mass > 10
    add(">= 1 track-muon pairs Mtrack,muon > 10 GeV", any_pair_per_event(pair_mass_gt_10))

    trk = trk & min_delta_r_mask(arrays, "ele", 0.15)
    add(">= 1 tracks min DeltaRtrack,electron > 0.15", ak.any(trk, axis=1))

    #trk = trk & min_delta_r_mask(arrays, "tau", 0.15)
    #add(">= 1 tracks min DeltaRtrack,had. tau > 0.15", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_caloTotNoPU"] < 10)
    add(">= 1 tracks Ecalo < 10 GeV", ak.any(trk, axis=1))

    # For the Pveto calculation in Section 5.1, all unique passing pairs are used.
    # Keep this Table 16-style row as a bookkeeping row without reducing the sample.
    add("exactly one passing track chosen randomly", ak.any(trk, axis=1))

    trk = trk & layer_mask(arrays, layer)

    muons = build_muon_vectors(arrays, mu)
    tracks = build_track_vectors(arrays, trk)
    trk_obj, mu_obj = ak.unzip(ak.cartesian([tracks, muons], nested=True))
    mass = (trk_obj + mu_obj).mass

    z_window = (mass > Z_MASS - 10) & (mass < Z_MASS + 10)
    add("= 1 track-muon pairs |Mtrack,muon - MZ| < 10 GeV", any_pair_per_event(z_window))

    os_pair = z_window & (trk_obj.charge * mu_obj.charge < 0)
    add("= 1 track-muon pairs qtrack * qmuon < 0", any_pair_per_event(os_pair))

    add(f">= 1 track nlayers >= 4 ({layer})", any_pair_per_event(os_pair))

    return cutflow


def count_pveto_pairs(arrays, layer):
    mu = muon_tag_mask(arrays)
    trk = probe_track_denominator_mask(arrays, layer)

    muons = build_muon_vectors(arrays, mu)
    tracks = build_track_vectors(arrays, trk)

    trk_obj, mu_obj = ak.unzip(ak.cartesian([tracks, muons], nested=True))

    mass = (trk_obj + mu_obj).mass
    z_window = (mass > Z_MASS - 10) & (mass < Z_MASS + 10)

    os_pair = trk_obj.charge * mu_obj.charge < 0
    ss_pair = trk_obj.charge * mu_obj.charge > 0

    # Muon Pveto numerator from Table 21:
    #   min DeltaR(track, muon) > 0.15
    #   missing outer hits >= 3
    # This is deliberately NOT part of the denominator.
    passes_muon_veto = trk_obj.passesMuonVeto
    passes_missing_outer = trk_obj.missingOuterHits >= 3
    passes_veto = passes_muon_veto & passes_missing_outer

    return {
        "p_veto_den_os": float(ak.sum(z_window & os_pair)),
        "p_veto_den_ss": float(ak.sum(z_window & ss_pair)),
        "p_veto_num_os": float(ak.sum(z_window & os_pair & passes_veto)),
        "p_veto_num_ss": float(ak.sum(z_window & ss_pair & passes_veto)),
    }


def process_file_set(files, tree_name, layer, chunk_size):
    cutflow_totals = OrderedDict()

    counts = {
        "p_veto_num_os": Count(),
        "p_veto_num_ss": Count(),
        "p_veto_den_os": Count(),
        "p_veto_den_ss": Count(),
    }

    branches = [
        "metNoMu_pt",
        "metNoMu_phi",
        "muon_pt",
        "muon_eta",
        "muon_phi",
        "muon_charge",
        "muon_isTrigMatched",
        "muon_isTight",
        "ele_eta",
        "ele_phi",
        "tau_eta",
        "tau_phi",
        "jet_eta",
        "jet_phi",
        "trk_pt",
        "trk_eta",
        "trk_phi",
        "trk_charge",
        "trk_dxy",
        "trk_dz",
        "trk_missingInnerHits",
        "trk_hitDrop_missingMiddleHits",
        "trk_missingOuterHits",
        "trk_relativePFIso",
        "trk_caloTotNoPU",
        "trk_hp_numberOfValidPixelHits",
        "trk_hp_trackerLayersWithMeasurement",
    ]

    for filename in files:
        tree_path = f"{filename}:{tree_name}"

        for arrays in uproot.iterate(
            tree_path,
            branches,
            step_size=chunk_size,
            library="ak",
        ):
            cutflow = make_tp_cutflow(arrays, layer)

            for name, val in cutflow.items():
                cutflow_totals[name] = cutflow_totals.get(name, 0) + val

            pveto = count_pveto_pairs(arrays, layer)

            for key, value in pveto.items():
                counts[key].add_poisson(value)

    return cutflow_totals, counts


def print_cutflow(cutflow):
    header = (
        f"{'Cut':65s} "
        f"{'Events':>12s} "
        f"{'Eff(prev)':>12s} "
        f"{'Eff(total)':>12s}"
    )

    print(header)
    print("-" * len(header))

    first = None
    prev = None

    for name, val in cutflow.items():
        if first is None:
            first = val

        eff_prev = val / prev if prev and prev > 0 else 1.0
        eff_total = val / first if first and first > 0 else 0.0

        print(
            f"{name:65s} "
            f"{val:12d} "
            f"{eff_prev:12.4f} "
            f"{eff_total:12.4f}"
        )

        prev = val


def run(args):
    files = parse_inputs(args.single_muon)

    if not files:
        raise RuntimeError("No input files found.")

    layers = (
        ["NLayers4", "NLayers5", "NLayers6plus", "combinedBins"]
        if args.layers == "all"
        else [args.layers]
    )

    all_results = {}

    for layer in layers:
        print()
        print("=" * 100)
        print(layer)
        print("=" * 100)

        cutflow, counts = process_file_set(
            files,
            args.tree,
            layer,
            args.chunk_size,
        )

        all_results[layer] = {
            "cutflow": cutflow,
            "counts": counts,
        }

        print()
        print_cutflow(cutflow)

        print("\nPveto counts")
        for name, count in counts.items():
            print(f"{name:20s} {count.value:12.6g} +/- {count.error:.6g}")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "input_files": files,
            "tree": args.tree,
            "layers": {},
        }

        for layer, result in all_results.items():
            payload["layers"][layer] = {
                "cutflow": dict(result["cutflow"]),
                "counts": {
                    name: {
                        "value": count.value,
                        "variance": count.variance,
                        "error": count.error,
                    }
                    for name, count in result["counts"].items()
                },
            }

        with open(json_path, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=True)

        print(f"\nWrote {json_path}")

    if args.output:
        output_path = Path(args.output)

        with uproot.recreate(output_path) as fout:
            for layer, result in all_results.items():
                counts = result["counts"]

                for name, count in counts.items():
                    fout[f"{layer}/{name}"] = np.histogram(
                        [0.5],
                        bins=1,
                        range=(0, 1),
                        weights=[count.value],
                    )

        print(f"\nWrote {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Muon Pveto cutflow and count producer from DisappTrks_v2 ntuples."
    )

    parser.add_argument(
        "--single-muon",
        nargs="+",
        required=True,
        help="SingleMuon-triggered ntuple files or globs.",
    )

    parser.add_argument(
        "--tree",
        default="ntuplizer/Events",
        help="TTree path inside each ROOT file.",
    )

    parser.add_argument(
        "--layers",
        default="all",
        choices=[
            "NLayers4",
            "NLayers5",
            "NLayers6plus",
            "combinedBins",
            "all",
        ],
    )

    parser.add_argument(
        "--chunk-size",
        default="100 MB",
        help="uproot iterate step_size.",
    )

    parser.add_argument(
        "--output",
        help="Output ROOT file with Pveto count histograms.",
    )

    parser.add_argument(
        "--json-output",
        help="Optional per-job JSON output with cutflow and Pveto counts.",
    )

    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
