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


def min_delta_r_mask(arrays, prefix, min_dr, obj_mask=None):
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

    if obj_mask is not None:
        objs = objs[obj_mask]

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
    mask = arrays["muon_isTrigMatched"]
    mask = mask & (arrays["muon_pt"] > 26)
    mask = mask & (np.abs(arrays["muon_eta"]) < 2.1)
    mask = mask & arrays["muon_isTight"]
    mask = mask & (arrays["muon_pfRelIso04_dBeta"] < 0.15)
    return mask


def probe_track_denominator_mask(arrays, layer):
    """
    Strict V1 ZtoMuProbeTrk probe-track denominator.

    The event-level trigger, MET filters, TrackEcalDeadChannelFilter, and
    JvmAppliedEventFilter are applied while making the ntuple.  This function
    applies the per-track rows that remain in ZtoMuProbeTrk after V1 removes
    arbitration, M(track,muon)>10, Z-window, and OS cuts from the selection.
    """
    mask = arrays["trk_pt"] > 30
    mask = mask & (np.abs(arrays["trk_eta"]) < 2.1)
    mask = mask & fiducial_eta_mask(arrays)
    mask = mask & (~arrays["trk_inTOBCrack"])
    mask = mask & arrays["trk_isFiducialElectronTrack"]
    mask = mask & arrays["trk_isFiducialMuonTrack"]
    mask = mask & arrays["trk_isFiducialECALTrack"]
    mask = mask & (arrays["trk_hp_numberOfValidPixelHits"] >= 4)
    mask = mask & (arrays["trk_hp_numberOfValidHits"] >= 4)
    mask = mask & (arrays["trk_missingInnerHits"] == 0)
    mask = mask & (arrays["trk_hitDrop_missingMiddleHits"] == 0)
    mask = mask & (arrays["trk_relativePFIso"] < 0.05)
    mask = mask & (np.abs(arrays["trk_dxy"]) < 0.02)
    mask = mask & (np.abs(arrays["trk_dz"]) < 0.5)
    mask = mask & (arrays["trk_dRMinJet"] > 0.5)

    # cutVetoJetMap2022 is event-level and is applied upstream by
    # process.JvmAppliedEventFilter before the ntuplizer writes an event.

    mask = mask & (arrays["trk_deltaRToClosestElectron"] > 0.15)
    mask = mask & (arrays["trk_deltaRToClosestTauHad"] > 0.15)
    mask = mask & (arrays["trk_caloTotNoPU"] < 10)
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
    return ak.zip({
        "pt": arrays["trk_pt"][mask],
        "eta": arrays["trk_eta"][mask],
        "phi": arrays["trk_phi"][mask],
        "mass": ak.ones_like(arrays["trk_pt"][mask]) * MUON_MASS,
        "charge": arrays["trk_charge"][mask],
        "deltaRToClosestMuon": arrays["trk_deltaRToClosestMuon"][mask],
        "hitDropMissingOuterHits": arrays["trk_hitDrop_missingOuterHits"][mask],
    }, with_name="Momentum4D")


def make_tp_cutflow(arrays, layer):
    cutflow = OrderedDict()

    event_mask = ak.ones_like(arrays["metNoMu_pt"], dtype=bool)

    def add(label, mask):
        nonlocal event_mask
        event_mask = event_mask & mask
        cutflow[label] = int(ak.sum(event_mask))

    add(
        "event written by ntuplizer trigger/MET/JVM path",
        ak.ones_like(arrays["metNoMu_pt"], dtype=bool),
    )

    mu = arrays["muon_isTrigMatched"]
    mu = mu & (arrays["muon_pt"] > 26)
    add(">= 1 muons pT > 26 GeV", ak.any(mu, axis=1))

    mu = mu & (np.abs(arrays["muon_eta"]) < 2.1)
    add(">= 1 muons |eta| < 2.1", ak.any(mu, axis=1))

    mu = mu & arrays["muon_isTight"]
    add(">= 1 muons passing tight muon ID", ak.any(mu, axis=1))

    mu = mu & (arrays["muon_pfRelIso04_dBeta"] < 0.15)
    add(">= 1 muons rel. PF iso. < 0.15", ak.any(mu, axis=1))

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

    trk = trk & (~arrays["trk_inTOBCrack"])
    add(">= 1 tracks not in TOB crack", ak.any(trk, axis=1))

    trk = trk & arrays["trk_isFiducialElectronTrack"]
    add(">= 1 tracks passing electron fiducial map", ak.any(trk, axis=1))

    trk = trk & arrays["trk_isFiducialMuonTrack"]
    add(">= 1 tracks passing muon fiducial map", ak.any(trk, axis=1))

    trk = trk & arrays["trk_isFiducialECALTrack"]
    add(">= 1 tracks passing ECAL dead-channel fiducial veto", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_hp_numberOfValidPixelHits"] >= 4)
    add(">= 1 tracks number of pixel hits >= 4", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_hp_numberOfValidHits"] >= 4)
    add(">= 1 tracks number of valid hits >= 4", ak.any(trk, axis=1))

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

    trk = trk & (arrays["trk_dRMinJet"] > 0.5)
    add(">= 1 tracks dRMinJet > 0.5", ak.any(trk, axis=1))

    add("event passed jet veto map upstream", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_deltaRToClosestElectron"] > 0.15)
    add(">= 1 tracks min DeltaRtrack,electron > 0.15", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_deltaRToClosestTauHad"] > 0.15)
    add(">= 1 tracks min DeltaRtrack,had. tau > 0.15", ak.any(trk, axis=1))

    trk = trk & (arrays["trk_caloTotNoPU"] < 10)
    add(">= 1 tracks Ecalo < 10 GeV", ak.any(trk, axis=1))

    add("exactly one passing track chosen randomly", ak.any(trk, axis=1))

    trk = trk & layer_mask(arrays, layer)
    add(f">= 1 track nlayers selection ({layer})", ak.any(trk, axis=1))

    muons = build_muon_vectors(arrays, mu)
    tracks = build_track_vectors(arrays, trk)
    trk_obj, mu_obj = ak.unzip(ak.cartesian([tracks, muons], nested=True))
    mass = (trk_obj + mu_obj).mass

    z_window = (mass > Z_MASS - 10) & (mass < Z_MASS + 10)
    add(">= 1 track-muon pairs |Mtrack,muon - MZ| < 10 GeV", any_pair_per_event(z_window))

    os_pair = z_window & (trk_obj.charge * mu_obj.charge < 0)
    add(">= 1 track-muon pairs qtrack * qmuon < 0", any_pair_per_event(os_pair))

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

    passes_veto = (
        (trk_obj.deltaRToClosestMuon > 0.15)
        & (trk_obj.hitDropMissingOuterHits >= 3)
    )

    return {
        "p_veto_den_os": float(ak.sum(z_window & os_pair)),
        "p_veto_den_ss": float(ak.sum(z_window & ss_pair)),
        "p_veto_num_os": float(ak.sum(z_window & os_pair & passes_veto)),
        "p_veto_num_ss": float(ak.sum(z_window & ss_pair & passes_veto)),
    }



def validate_branches(filename, tree_name, branches):
    with uproot.open(filename) as fin:
        if tree_name not in fin:
            raise RuntimeError(f"{filename} does not contain tree {tree_name!r}")
        available = set(fin[tree_name].keys())
    missing = [branch for branch in branches if branch not in available]
    if missing:
        raise RuntimeError(
            "Input is not a strict Matt/V1-compatible ntuple. "
            f"{filename}:{tree_name} is missing branches: "
            + ", ".join(missing)
        )


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
        "muon_pfRelIso04_dBeta",
        "trk_pt",
        "trk_eta",
        "trk_phi",
        "trk_charge",
        "trk_dxy",
        "trk_dz",
        "trk_inTOBCrack",
        "trk_isFiducialElectronTrack",
        "trk_isFiducialMuonTrack",
        "trk_isFiducialECALTrack",
        "trk_missingInnerHits",
        "trk_hitDrop_missingMiddleHits",
        "trk_hitDrop_missingOuterHits",
        "trk_relativePFIso",
        "trk_caloTotNoPU",
        "trk_dRMinJet",
        "trk_deltaRToClosestElectron",
        "trk_deltaRToClosestMuon",
        "trk_deltaRToClosestTauHad",
        "trk_hp_numberOfValidHits",
        "trk_hp_numberOfValidPixelHits",
        "trk_hp_trackerLayersWithMeasurement",
    ]

    for filename in files:
        tree_path = f"{filename}:{tree_name}"

        validate_branches(filename, tree_name, branches)

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
