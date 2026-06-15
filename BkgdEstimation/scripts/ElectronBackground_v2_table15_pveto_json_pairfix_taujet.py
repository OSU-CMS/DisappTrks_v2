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

ELECTRON_MASS = 0.000511
TRACK_MASS_FOR_ELECTRON_TP = ELECTRON_MASS
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


def min_delta_r_mask(arrays, prefix, min_dr, obj_mask=None):
    """
    Per-track mask requiring min DeltaR(track, object) > min_dr.

    Returns an event-by-track mask. If an event has no objects of the requested
    type after optional cleaning, the veto passes for all tracks in that event.
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

    return ak.fill_none(ak.all(dr > min_dr, axis=2), True)


def any_pair_per_event(pair_mask):
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


def water_leak_mask(arrays):
    """
    Additional 2022 E/F/G ECAL water-leak veto from Table 15.

    This must not be applied to other eras.
    """
    return (
        (arrays["trk_eta"] < 0.0)
        | (arrays["trk_eta"] > 1.42)
        | (arrays["trk_phi"] < 2.7)
    )


def good_jet_mask(arrays, jet_pt_min, jet_eta_max):
    mask = (arrays["jet_pt"] > jet_pt_min) & (np.abs(arrays["jet_eta"]) < jet_eta_max)
    if "jet_isTightLepVeto" in arrays.fields:
        mask = mask & arrays["jet_isTightLepVeto"]
    return mask


def good_tau_mask(arrays):
    """
    Restrict the tau veto to selected hadronic taus.

    The ntuplizer's tau_isTight branch is the available summary of the configured
    decay-mode and DeepTau working points. It is preferable to vetoing against
    every reconstructed tau candidate.
    """
    return arrays["tau_isTight"]


def electron_tag_mask(arrays):
    """
    Electron tag selection from the AN electron tag-and-probe table:
      - SingleElectron/EGamma trigger match
      - pT > 35 GeV
      - |eta| < 2.1
      - tight electron ID

    The input ntuple is assumed to have been produced from the SingleElectron/EGamma
    triggered dataset.
    """
    mask = arrays["ele_isTrigMatched"]
    mask = mask & (arrays["ele_pt"] > 35.0)
    mask = mask & (np.abs(arrays["ele_eta"]) < 2.1)
    mask = mask & arrays["ele_isTight"]
    return mask


def probe_track_denominator_mask(
    arrays,
    layer,
    jet_pt_min,
    jet_eta_max,
    apply_water_leak_veto,
):
    """
    Probe-track denominator selection for the electron Pveto measurement.

    This is the Table-15-style probe-track selection with the electron veto
    removed. The electron veto is applied only in the numerator via Table 21:
      - min DeltaR(track, electron) > 0.15
      - Ecalo < 10 GeV
      - missing outer hits >= 3

    Therefore, unlike the muon Pveto script, Ecalo is deliberately NOT applied
    in this denominator.
    """
    mask = arrays["trk_pt"] > 30
    mask = mask & (np.abs(arrays["trk_eta"]) < 2.1)
    mask = mask & fiducial_eta_mask(arrays)
    if apply_water_leak_veto:
        mask = mask & water_leak_mask(arrays)

    mask = mask & (
        (np.abs(arrays["trk_dz"]) > 0.5)
        | (np.abs((np.pi / 2.0) - arrays["trk_theta"]) > 1.0e-3)
    )

    mask = mask & (arrays["trk_hp_numberOfValidPixelHits"] >= 4)
    mask = mask & (arrays["trk_missingInnerHits"] == 0)
    mask = mask & (arrays["trk_hitDrop_missingMiddleHits"] == 0)
    mask = mask & (arrays["trk_relativePFIso"] < 0.05)
    mask = mask & (np.abs(arrays["trk_dxy"]) < 0.02)
    mask = mask & (np.abs(arrays["trk_dz"]) < 0.5)

    mask = mask & min_delta_r_mask(
        arrays,
        "jet",
        0.5,
        obj_mask=good_jet_mask(arrays, jet_pt_min, jet_eta_max),
    )

    # Keep non-electron lepton veto rows in the denominator.
    mask = mask & min_delta_r_mask(arrays, "muon", 0.15)

    mask = mask & min_delta_r_mask(
        arrays,
        "tau",
        0.15,
        obj_mask=good_tau_mask(arrays),
    )

    mask = mask & layer_mask(arrays, layer)

    return mask


def build_electron_vectors(arrays, mask):
    return ak.zip({
        "pt": arrays["ele_pt"][mask],
        "eta": arrays["ele_eta"][mask],
        "phi": arrays["ele_phi"][mask],
        "mass": ak.ones_like(arrays["ele_pt"][mask]) * ELECTRON_MASS,
        "charge": arrays["ele_charge"][mask],
    }, with_name="Momentum4D")


def build_track_vectors(arrays, mask):
    electron_veto = min_delta_r_mask(arrays, "ele", 0.15)

    return ak.zip({
        "pt": arrays["trk_pt"][mask],
        "eta": arrays["trk_eta"][mask],
        "phi": arrays["trk_phi"][mask],
        "mass": ak.ones_like(arrays["trk_pt"][mask]) * TRACK_MASS_FOR_ELECTRON_TP,
        "charge": arrays["trk_charge"][mask],
        "missingOuterHits": arrays["trk_missingOuterHits"][mask],
        "calo": arrays["trk_caloTotNoPU"][mask],
        "passesElectronDR": electron_veto[mask],
    }, with_name="Momentum4D")


def make_tp_cutflow(
    arrays,
    layer,
    jet_pt_min,
    jet_eta_max,
    apply_water_leak_veto,
):
    cutflow = OrderedDict()
    event_mask = ak.ones_like(arrays["metNoMu_pt"], dtype=bool)

    def add(label, mask):
        nonlocal event_mask
        event_mask = event_mask & mask
        cutflow[label] = int(ak.sum(event_mask))

    add("event passes SingleElectron/EGamma triggers", ak.ones_like(arrays["metNoMu_pt"], dtype=bool))

    ele = arrays["ele_isTrigMatched"]

    ele = ele & (arrays["ele_pt"] > 35.0)
    add(">= 1 electrons pT > 35 GeV", ak.any(ele, axis=1))

    ele = ele & (np.abs(arrays["ele_eta"]) < 2.1)
    add(">= 1 electrons |eta| < 2.1", ak.any(ele, axis=1))

    ele = ele & arrays["ele_isTight"]
    add(">= 1 electrons passing tight electron ID", ak.any(ele, axis=1))

    add("exactly one passing electron chosen randomly", ak.any(ele, axis=1))

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

    if apply_water_leak_veto:
        trk = trk & water_leak_mask(arrays)
        add(
            ">= 1 tracks eta < 0 OR eta > 1.42 OR phi < 2.7",
            ak.any(trk, axis=1),
        )

    trk = trk & (
        (np.abs(arrays["trk_dz"]) > 0.5)
        | (np.abs((np.pi / 2.0) - arrays["trk_theta"]) > 1.0e-3)
    )
    add(">= 1 tracks |dz| > 0.5 cm OR |lambda| > 1e-3", ak.any(trk, axis=1))

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

    trk = trk & min_delta_r_mask(
        arrays,
        "jet",
        0.5,
        obj_mask=good_jet_mask(arrays, jet_pt_min, jet_eta_max),
    )
    add(">= 1 track-jet pairs DeltaRtrack,jet > 0.5", ak.any(trk, axis=1))

    # Build pre-electron-veto tag-probe pairs for the Table 15 M(track,electron) row.
    electrons = build_electron_vectors(arrays, ele)
    tracks_pre_veto = build_track_vectors(arrays, trk)
    trk_obj, ele_obj = ak.unzip(ak.cartesian([tracks_pre_veto, electrons], nested=True))

    mass = (trk_obj + ele_obj).mass
    pair_mass_gt_10 = mass > 10
    add(">= 1 track-electron pairs Mtrack,electron > 10 GeV", any_pair_per_event(pair_mass_gt_10))

    trk = trk & min_delta_r_mask(arrays, "muon", 0.15)
    add(">= 1 tracks min DeltaRtrack,muon > 0.15", ak.any(trk, axis=1))

    trk = trk & min_delta_r_mask(
        arrays,
        "tau",
        0.15,
        obj_mask=good_tau_mask(arrays),
    )
    add(">= 1 tracks min DeltaRtrack,had. tau > 0.15", ak.any(trk, axis=1))

    add("exactly one passing track chosen randomly", ak.any(trk, axis=1))

    trk = trk & layer_mask(arrays, layer)

    electrons = build_electron_vectors(arrays, ele)
    tracks = build_track_vectors(arrays, trk)
    trk_obj, ele_obj = ak.unzip(ak.cartesian([tracks, electrons], nested=True))
    mass = (trk_obj + ele_obj).mass

    z_window = (mass > Z_MASS - 10) & (mass < Z_MASS + 10)
    add("= 1 track-electron pairs |Mtrack,electron - MZ| < 10 GeV", any_pair_per_event(z_window))

    os_pair = z_window & (trk_obj.charge * ele_obj.charge < 0)
    add("= 1 track-electron pairs qtrack * qelectron < 0", any_pair_per_event(os_pair))

    add(f">= 1 track nlayers >= 4 ({layer})", any_pair_per_event(os_pair))

    return cutflow


def count_pveto_pairs(
    arrays,
    layer,
    jet_pt_min,
    jet_eta_max,
    apply_water_leak_veto,
):
    ele = electron_tag_mask(arrays)
    trk = probe_track_denominator_mask(
        arrays,
        layer,
        jet_pt_min,
        jet_eta_max,
        apply_water_leak_veto,
    )

    electrons = build_electron_vectors(arrays, ele)
    tracks = build_track_vectors(arrays, trk)

    trk_obj, ele_obj = ak.unzip(ak.cartesian([tracks, electrons], nested=True))

    mass = (trk_obj + ele_obj).mass
    mass_gt_10 = mass > 10.0
    z_window = mass_gt_10 & (mass > Z_MASS - 10) & (mass < Z_MASS + 10)

    os_pair = trk_obj.charge * ele_obj.charge < 0
    ss_pair = trk_obj.charge * ele_obj.charge > 0

    # Electron Pveto numerator from Table 21:
    #   min DeltaR(track, electron) > 0.15
    #   Ecalo < 10 GeV
    #   missing outer hits >= 3
    passes_electron_dr = trk_obj.passesElectronDR
    passes_ecalo = trk_obj.calo < 10.0
    passes_missing_outer = trk_obj.missingOuterHits >= 3
    passes_veto = passes_electron_dr & passes_ecalo & passes_missing_outer

    return {
        "p_veto_den_os": float(ak.sum(z_window & os_pair)),
        "p_veto_den_ss": float(ak.sum(z_window & ss_pair)),
        "p_veto_num_os": float(ak.sum(z_window & os_pair & passes_veto)),
        "p_veto_num_ss": float(ak.sum(z_window & ss_pair & passes_veto)),
    }


def process_file_set(
    files,
    tree_name,
    layer,
    chunk_size,
    jet_pt_min,
    jet_eta_max,
    apply_water_leak_veto,
):
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
        "muon_eta",
        "muon_phi",
        "ele_pt",
        "ele_eta",
        "ele_phi",
        "ele_charge",
        "ele_isTrigMatched",
        "ele_isTight",
        "tau_eta",
        "tau_phi",
        "tau_isTight",
        "jet_eta",
        "jet_phi",
        "jet_pt",
        "jet_isTightLepVeto",
        "trk_pt",
        "trk_eta",
        "trk_phi",
        "trk_theta",
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
            cutflow = make_tp_cutflow(
                arrays,
                layer,
                jet_pt_min,
                jet_eta_max,
                apply_water_leak_veto,
            )

            for name, val in cutflow.items():
                cutflow_totals[name] = cutflow_totals.get(name, 0) + val

            pveto = count_pveto_pairs(
                arrays,
                layer,
                jet_pt_min,
                jet_eta_max,
                apply_water_leak_veto,
            )

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
    files = parse_inputs(args.single_electron)

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
            args.jet_pt_min,
            args.jet_eta_max,
            args.apply_2022_efg_water_leak_veto,
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
            "configuration": {
                "jet_pt_min": args.jet_pt_min,
                "jet_eta_max": args.jet_eta_max,
                "apply_2022_efg_water_leak_veto":
                    args.apply_2022_efg_water_leak_veto,
            },
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
        output_path.parent.mkdir(parents=True, exist_ok=True)

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
        description="Electron Pveto cutflow and count producer from DisappTrks_v2 ntuples."
    )

    parser.add_argument(
        "--single-electron",
        nargs="+",
        required=True,
        help="SingleElectron/EGamma-triggered ntuple files or globs.",
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
        "--jet-pt-min",
        type=float,
        default=30.0,
        help="Minimum jet pT used for the DeltaR(track,jet) cleaning.",
    )

    parser.add_argument(
        "--jet-eta-max",
        type=float,
        default=4.5,
        help="Maximum |eta| for jets used in the DeltaR(track,jet) cleaning.",
    )

    parser.add_argument(
        "--apply-2022-efg-water-leak-veto",
        action="store_true",
        help=(
            "Apply the Table 15 eta/phi veto for the 2022 E, F, and G eras. "
            "Do not use this option for other eras."
        ),
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
