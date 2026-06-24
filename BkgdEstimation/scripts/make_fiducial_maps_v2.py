#!/usr/bin/env python3

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Iterable

from runtime_warnings import filter_known_runtime_warnings

filter_known_runtime_warnings()

import awkward as ak
import numpy as np
import uproot

from ElectronBackground_v2_table15_pveto_json_pairfix_taujet import (
    Z_MASS,
    build_electron_vectors,
    build_track_vectors as build_electron_probe_tracks,
    electron_tag_mask,
    probe_track_denominator_mask as electron_probe_track_denominator_mask,
)
from MuonBackground_v2_table16_pveto_json_pairfix_taujet import (
    build_track_vectors as build_muon_probe_tracks,
    muon_tag_mask,
    probe_track_denominator_mask as muon_probe_track_denominator_mask,
)
from fiducial_map_tools import load_fiducial_map


def parse_inputs(items: Iterable[str] | None) -> list[str]:
    files = []
    for item in items or []:
        if any(ch in item for ch in "*?["):
            files.extend(sorted(glob.glob(item)))
        else:
            files.append(item)
    return files


def histogram_axes(eta_bins, phi_bins, eta_min, eta_max, phi_min, phi_max):
    eta_edges = np.linspace(eta_min, eta_max, eta_bins + 1)
    phi_edges = np.linspace(phi_min, phi_max, phi_bins + 1)
    return eta_edges, phi_edges


def fill_histogram(eta, phi, eta_edges, phi_edges):
    eta_flat = ak.to_numpy(ak.flatten(eta, axis=None))
    phi_flat = ak.to_numpy(ak.flatten(phi, axis=None))
    values, _, _ = np.histogram2d(eta_flat, phi_flat, bins=(eta_edges, phi_edges))
    return values


def add_histograms(total, update):
    if total is None:
        return update
    total += update
    return total


def selected_electron_tracks(
    arrays,
    layer,
    jet_pt_min,
    jet_eta_max,
    apply_water_leak_veto,
):
    electrons = build_electron_vectors(arrays, electron_tag_mask(arrays))
    denominator = electron_probe_track_denominator_mask(
        arrays,
        layer,
        jet_pt_min,
        jet_eta_max,
        apply_water_leak_veto,
    )
    tracks = build_electron_probe_tracks(arrays, denominator)
    track_pairs, electron_pairs = ak.unzip(
        ak.cartesian([tracks, electrons], nested=True)
    )

    mass = (track_pairs + electron_pairs).mass
    pair_denominator = (
        (mass > Z_MASS - 10.0)
        & (mass < Z_MASS + 10.0)
        & (track_pairs.charge * electron_pairs.charge < 0)
    )

    before_eta = track_pairs.eta[pair_denominator]
    before_phi = track_pairs.phi[pair_denominator]

    # Match ElectronFiducialCalcAfter: the numerator differs from the
    # denominator only by the veto-electron DeltaR requirement.
    pair_numerator = pair_denominator & track_pairs.passesElectronDR
    after_eta = track_pairs.eta[pair_numerator]
    after_phi = track_pairs.phi[pair_numerator]

    return before_eta, before_phi, after_eta, after_phi


def selected_muon_tracks(arrays, layer):
    event_has_tag = ak.any(muon_tag_mask(arrays), axis=1)
    denominator = muon_probe_track_denominator_mask(arrays, layer)
    denominator = denominator & event_has_tag

    tracks = build_muon_probe_tracks(arrays, denominator)
    passes_veto = tracks.passesMuonVeto & (tracks.missingOuterHits >= 3)
    return denominator, passes_veto


def process_flavor(
    files,
    tree_name,
    flavor,
    layer,
    chunk_size,
    eta_edges,
    phi_edges,
    jet_pt_min,
    jet_eta_max,
    apply_water_leak_veto,
):
    before_total = None
    after_total = None

    common_branches = [
        "metNoMu_pt",
        "metNoMu_phi",
        "muon_pt",
        "muon_eta",
        "muon_phi",
        "muon_charge",
        "muon_isTrigMatched",
        "muon_isTight",
        "ele_pt",
        "ele_eta",
        "ele_phi",
        "ele_charge",
        "ele_isTrigMatched",
        "ele_isTight",
        "tau_eta",
        "tau_phi",
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
    if flavor == "electron":
        common_branches.append("tau_isTight")

    for filename in files:
        tree_path = f"{filename}:{tree_name}"
        for arrays in uproot.iterate(
            tree_path,
            common_branches,
            step_size=chunk_size,
            library="ak",
        ):
            if flavor == "electron":
                before_eta, before_phi, after_eta, after_phi = selected_electron_tracks(
                    arrays,
                    layer,
                    jet_pt_min,
                    jet_eta_max,
                    apply_water_leak_veto,
                )
            else:
                denominator, after_mask = selected_muon_tracks(arrays, layer)
                before_eta = arrays["trk_eta"][denominator]
                before_phi = arrays["trk_phi"][denominator]
                after_eta = before_eta[after_mask]
                after_phi = before_phi[after_mask]

            before_total = add_histograms(
                before_total,
                fill_histogram(before_eta, before_phi, eta_edges, phi_edges),
            )
            after_total = add_histograms(
                after_total,
                fill_histogram(after_eta, after_phi, eta_edges, phi_edges),
            )

    if before_total is None:
        before_total = np.zeros((len(eta_edges) - 1, len(phi_edges) - 1))
        after_total = np.zeros_like(before_total)

    return before_total, after_total


def write_map(path, before, after, eta_edges, phi_edges):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with uproot.recreate(path) as fout:
        fout["beforeVeto"] = before, eta_edges, phi_edges
        fout["afterVeto"] = after, eta_edges, phi_edges


def write_summary(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fout:
        json.dump(payload, fout, indent=2, sort_keys=True)


def read_map(path):
    with uproot.open(path) as fin:
        before, eta_edges, phi_edges = fin["beforeVeto"].to_numpy()
        after, after_eta_edges, after_phi_edges = fin["afterVeto"].to_numpy()

    if not np.allclose(eta_edges, after_eta_edges) or not np.allclose(phi_edges, after_phi_edges):
        raise ValueError(f"{path}: beforeVeto and afterVeto have different binning")

    return before.astype(float), after.astype(float), eta_edges.astype(float), phi_edges.astype(float)


def merge_maps(files):
    before_total = None
    after_total = None
    eta_edges = None
    phi_edges = None

    for path in files:
        before, after, this_eta_edges, this_phi_edges = read_map(path)

        if before_total is None:
            before_total = before
            after_total = after
            eta_edges = this_eta_edges
            phi_edges = this_phi_edges
            continue

        if not np.allclose(eta_edges, this_eta_edges) or not np.allclose(phi_edges, this_phi_edges):
            raise ValueError(f"{path}: map binning does not match previous inputs")

        before_total += before
        after_total += after

    if before_total is None:
        raise RuntimeError("No fiducial-map inputs found to merge")

    return before_total, after_total, eta_edges, phi_edges


def inefficiency_and_sigma(before, after):
    occupied = before > 0.0
    if not np.any(occupied):
        raise ValueError("beforeVeto has no occupied bins")

    mean = float(np.sum(after[occupied]) / np.sum(before[occupied]))

    inefficiency = np.zeros_like(after, dtype=float)
    inefficiency[occupied] = after[occupied] / before[occupied]

    n_occupied = int(np.count_nonzero(occupied))
    if n_occupied < 2:
        stddev = 0.0
    else:
        stddev = float(np.sqrt(np.sum((inefficiency[occupied] - mean) ** 2) / (n_occupied - 1)))

    sigma = np.zeros_like(inefficiency, dtype=float)
    if stddev > 0.0:
        sigma[occupied] = (inefficiency[occupied] - mean) / stddev

    sigma_positive = sigma.copy()
    sigma_positive[sigma_positive < 0.0] = 0.0

    return inefficiency, sigma, sigma_positive, mean, stddev


def plot_eta_phi(
    values,
    eta_edges,
    phi_edges,
    output_path,
    colorbar_label,
    hot_spots=(),
    z_range=None,
    cms_label="CMS Preliminary",
    lumi_label="13.6 TeV",
    hot_spot_radius=0.06,
):
    try:
        plot_eta_phi_root(
            values,
            eta_edges,
            phi_edges,
            output_path,
            colorbar_label,
            hot_spots,
            z_range,
            cms_label,
            lumi_label,
            hot_spot_radius,
        )
        return
    except ImportError:
        pass

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    fig, ax = plt.subplots(figsize=(8, 7))
    mesh = ax.pcolormesh(
        eta_edges,
        phi_edges,
        values.T,
        shading="auto",
        vmin=None if z_range is None else z_range[0],
        vmax=None if z_range is None else z_range[1],
    )
    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label(colorbar_label)

    for spot in hot_spots:
        ax.add_patch(
            Circle(
                (spot.eta, spot.phi),
                spot.radius,
                edgecolor="limegreen",
                facecolor="none",
                linewidth=1.5,
            )
        )

    ax.set_xlabel(r"track $\eta$")
    ax.set_ylabel(r"track $\phi$")
    ax.set_xlim(float(eta_edges[0]), float(eta_edges[-1]))
    ax.set_ylim(float(phi_edges[0]), float(phi_edges[-1]))
    ax.text(0.02, 1.02, cms_label, transform=ax.transAxes, ha="left", va="bottom", fontweight="bold")
    ax.text(0.98, 1.02, lumi_label, transform=ax.transAxes, ha="right", va="bottom")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_raw_sigma(sigma, before, output_path):
    try:
        plot_raw_sigma_root(sigma, before, output_path)
        return
    except ImportError:
        pass

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    values = sigma[before > 0.0]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(values, bins=40, range=(-20, 20), histtype="step", linewidth=1.5)
    ax.set_xlabel(r"$(\epsilon_{\mathrm{bin}} - \langle\epsilon\rangle) / \sigma_{\epsilon}$")
    ax.set_ylabel("bins")
    ax.text(0.02, 1.02, "CMS Preliminary", transform=ax.transAxes, ha="left", va="bottom", fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_eta_phi_root(
    values,
    eta_edges,
    phi_edges,
    output_path,
    colorbar_label,
    hot_spots=(),
    z_range=None,
    cms_label="CMS Preliminary",
    lumi_label="13.6 TeV",
    hot_spot_radius=0.06,
):
    from array import array

    from ROOT import TCanvas, TEllipse, TH2D, TLatex, gROOT, gStyle

    gROOT.SetBatch(True)
    gStyle.SetOptStat(0)
    gStyle.SetOptTitle(0)
    gStyle.SetPalette(56)
    gStyle.SetNumberContours(255)

    output_path = Path(output_path)
    hist_name = output_path.stem.replace("-", "_")
    hist = TH2D(
        hist_name,
        f";track #eta;track #phi;{colorbar_label}",
        len(eta_edges) - 1,
        array("d", eta_edges.astype(float).tolist()),
        len(phi_edges) - 1,
        array("d", phi_edges.astype(float).tolist()),
    )
    hist.SetDirectory(0)
    hist.GetXaxis().SetTitleSize(0.045)
    hist.GetYaxis().SetTitleSize(0.045)
    hist.GetZaxis().SetTitleSize(0.04)
    hist.GetXaxis().SetLabelSize(0.04)
    hist.GetYaxis().SetLabelSize(0.04)
    hist.GetZaxis().SetLabelSize(0.025)
    hist.GetXaxis().SetTitleOffset(1.05)
    hist.GetYaxis().SetTitleOffset(1.25)
    hist.GetZaxis().SetTitleOffset(1.3)

    for ix in range(values.shape[0]):
        for iy in range(values.shape[1]):
            hist.SetBinContent(ix + 1, iy + 1, float(values[ix, iy]))

    if z_range is not None:
        hist.GetZaxis().SetRangeUser(float(z_range[0]), float(z_range[1]))

    canvas = TCanvas(f"c_{hist_name}", f"c_{hist_name}", 800, 800)
    canvas.SetLeftMargin(0.12)
    canvas.SetRightMargin(0.16)
    canvas.SetTopMargin(0.10)
    canvas.SetBottomMargin(0.12)
    canvas.SetLogz(False)
    hist.Draw("colz")

    circles = []
    for spot in hot_spots:
        radius = float(hot_spot_radius) if hot_spot_radius is not None else float(spot.radius)
        circle = TEllipse(float(spot.eta), float(spot.phi), radius)
        circle.SetLineColor(820)
        circle.SetLineWidth(1)
        circle.SetFillStyle(0)
        circle.Draw("same")
        circles.append(circle)

    label = TLatex()
    label.SetNDC()
    label.SetTextAngle(0)
    label.SetTextFont(62)
    label.SetTextAlign(12)
    label.SetTextSize(0.04)
    label.DrawLatex(0.12, 0.925, cms_label)

    lumi = TLatex()
    lumi.SetNDC()
    lumi.SetTextAngle(0)
    lumi.SetTextFont(42)
    lumi.SetTextAlign(32)
    lumi.SetTextSize(0.04)
    lumi.DrawLatex(0.96, 0.93, lumi_label)

    canvas.SaveAs(str(output_path))


def plot_raw_sigma_root(sigma, before, output_path):
    from ROOT import TCanvas, TH1D, TLatex, gROOT, gStyle

    gROOT.SetBatch(True)
    gStyle.SetOptStat(0)
    gStyle.SetOptTitle(0)

    output_path = Path(output_path)
    hist = TH1D(output_path.stem, ";(#epsilon_{bin} - <#epsilon>) / #sigma_{#epsilon};bins", 40, -20, 20)
    hist.SetDirectory(0)
    for value in sigma[before > 0.0]:
        hist.Fill(float(value))

    canvas = TCanvas(f"c_{output_path.stem}", f"c_{output_path.stem}", 700, 500)
    canvas.SetLeftMargin(0.12)
    canvas.SetRightMargin(0.05)
    canvas.SetTopMargin(0.10)
    canvas.SetBottomMargin(0.12)
    hist.Draw("hist")

    label = TLatex()
    label.SetNDC()
    label.SetTextAngle(0)
    label.SetTextFont(62)
    label.SetTextAlign(12)
    label.SetTextSize(0.04)
    label.DrawLatex(0.12, 0.925, "CMS Preliminary")

    canvas.SaveAs(str(output_path))


def make_fiducial_map_plots(
    map_path,
    flavor,
    tag,
    plot_dir,
    threshold,
    cms_label="CMS Preliminary",
    lumi_label="13.6 TeV",
    hot_spot_radius=0.06,
):
    plot_dir = Path(plot_dir)
    plot_dir.mkdir(parents=True, exist_ok=True)

    before, after, eta_edges, phi_edges = read_map(map_path)
    inefficiency, raw_sigma, sigma_positive, _, _ = inefficiency_and_sigma(before, after)
    fmap = load_fiducial_map(map_path, threshold=threshold)

    prefix = f"fiducialMapCalc_{flavor}_{tag}"
    efficiency_range = (0.0, 0.5) if flavor == "electron" else (0.0, 0.05)
    sigma_range = (0.0, 12.0) if flavor == "electron" else (0.0, 23.0)

    plot_eta_phi(
        before,
        eta_edges,
        phi_edges,
        plot_dir / f"{prefix}_beforeVeto.pdf",
        "tracks before veto",
        cms_label=cms_label,
        lumi_label=lumi_label,
    )
    plot_eta_phi(
        after,
        eta_edges,
        phi_edges,
        plot_dir / f"{prefix}_afterVeto.pdf",
        "tracks after veto",
        cms_label=cms_label,
        lumi_label=lumi_label,
    )
    plot_eta_phi(
        inefficiency,
        eta_edges,
        phi_edges,
        plot_dir / f"{prefix}_efficiency.pdf",
        "inefficiency",
        hot_spots=fmap.hot_spots,
        z_range=efficiency_range,
        cms_label=cms_label,
        lumi_label=lumi_label,
        hot_spot_radius=hot_spot_radius,
    )
    plot_eta_phi(
        sigma_positive,
        eta_edges,
        phi_edges,
        plot_dir / f"{prefix}_efficiencyInSigma.pdf",
        "sigma above mean inefficiency",
        hot_spots=fmap.hot_spots,
        z_range=sigma_range,
        cms_label=cms_label,
        lumi_label=lumi_label,
        hot_spot_radius=hot_spot_radius,
    )
    plot_raw_sigma(raw_sigma, before, plot_dir / f"{prefix}_rawSigma.pdf")

    print(f"Wrote fiducial-map plots to {plot_dir}")


def summarize_map(path, threshold):
    fmap = load_fiducial_map(path, threshold=threshold)
    return {
        "path": fmap.path,
        "mean_inefficiency": fmap.mean_inefficiency,
        "stddev_inefficiency": fmap.stddev_inefficiency,
        "threshold": fmap.threshold,
        "n_hot_spots": len(fmap.hot_spots),
        "hot_spots": [
            {
                "eta": spot.eta,
                "phi": spot.phi,
                "radius": spot.radius,
                "sigma": spot.sigma,
            }
            for spot in fmap.hot_spots
        ],
    }


def run(args):
    eta_edges, phi_edges = histogram_axes(
        args.eta_bins,
        args.phi_bins,
        args.eta_min,
        args.eta_max,
        args.phi_min,
        args.phi_max,
    )
    outputs = {}

    electron_files = parse_inputs(args.single_electron)
    muon_files = parse_inputs(args.single_muon)
    merge_inputs = parse_inputs(args.merge_inputs)

    if merge_inputs:
        if args.flavor == "both":
            raise RuntimeError("--merge-inputs requires --flavor electron or --flavor muon")

        before, after, eta_edges, phi_edges = merge_maps(merge_inputs)
        path = Path(args.output_dir) / f"{args.flavor}FiducialMap_{args.tag}.root"
        write_map(path, before, after, eta_edges, phi_edges)
        outputs[args.flavor] = summarize_map(path, args.threshold)
        print(f"Wrote {path}")
        if args.plot_dir:
            make_fiducial_map_plots(
                path,
                args.flavor,
                args.tag,
                args.plot_dir,
                args.threshold,
                args.cms_label,
                args.lumi_label,
                args.hot_spot_radius,
            )

        if args.json_output:
            write_summary(
                args.json_output,
                {
                    "configuration": {
                        "merge_inputs": merge_inputs,
                        "threshold": args.threshold,
                        "plot_dir": args.plot_dir,
                        "cms_label": args.cms_label,
                        "lumi_label": args.lumi_label,
                        "hot_spot_radius": args.hot_spot_radius,
                    },
                    "maps": outputs,
                },
            )
            print(f"Wrote {args.json_output}")
        return

    if args.flavor in ("electron", "both"):
        if not electron_files:
            raise RuntimeError("--single-electron is required when making the electron fiducial map")
        before, after = process_flavor(
            electron_files,
            args.tree,
            "electron",
            args.layers,
            args.chunk_size,
            eta_edges,
            phi_edges,
            args.jet_pt_min,
            args.jet_eta_max,
            args.apply_2022_efg_water_leak_veto,
        )
        path = Path(args.output_dir) / f"electronFiducialMap_{args.tag}.root"
        write_map(path, before, after, eta_edges, phi_edges)
        outputs["electron"] = summarize_map(path, args.threshold)
        print(f"Wrote {path}")
        if args.plot_dir:
            make_fiducial_map_plots(
                path,
                "electron",
                args.tag,
                args.plot_dir,
                args.threshold,
                args.cms_label,
                args.lumi_label,
                args.hot_spot_radius,
            )

    if args.flavor in ("muon", "both"):
        if not muon_files:
            raise RuntimeError("--single-muon is required when making the muon fiducial map")
        before, after = process_flavor(
            muon_files,
            args.tree,
            "muon",
            args.layers,
            args.chunk_size,
            eta_edges,
            phi_edges,
            args.jet_pt_min,
            args.jet_eta_max,
            args.apply_2022_efg_water_leak_veto,
        )
        path = Path(args.output_dir) / f"muonFiducialMap_{args.tag}.root"
        write_map(path, before, after, eta_edges, phi_edges)
        outputs["muon"] = summarize_map(path, args.threshold)
        print(f"Wrote {path}")
        if args.plot_dir:
            make_fiducial_map_plots(
                path,
                "muon",
                args.tag,
                args.plot_dir,
                args.threshold,
                args.cms_label,
                args.lumi_label,
                args.hot_spot_radius,
            )

    if args.json_output:
        write_summary(
            args.json_output,
            {
                "configuration": {
                    "tree": args.tree,
                    "layers": args.layers,
                    "eta_bins": args.eta_bins,
                    "phi_bins": args.phi_bins,
                    "eta_range": [args.eta_min, args.eta_max],
                    "phi_range": [args.phi_min, args.phi_max],
                    "threshold": args.threshold,
                    "jet_pt_min": args.jet_pt_min,
                    "jet_eta_max": args.jet_eta_max,
                    "plot_dir": args.plot_dir,
                    "cms_label": args.cms_label,
                    "lumi_label": args.lumi_label,
                    "hot_spot_radius": args.hot_spot_radius,
                    "apply_2022_efg_water_leak_veto": args.apply_2022_efg_water_leak_veto,
                },
                "input_files": {
                    "electron": electron_files,
                    "muon": muon_files,
                },
                "maps": outputs,
            },
        )
        print(f"Wrote {args.json_output}")


def main():
    parser = argparse.ArgumentParser(
        description="Create electron and muon fiducial-map payloads from DisappTrks_v2 ntuples."
    )
    parser.add_argument("--single-electron", nargs="+", help="SingleElectron/EGamma ntuple files or globs.")
    parser.add_argument("--single-muon", nargs="+", help="SingleMuon ntuple files or globs.")
    parser.add_argument("--tree", default="ntuplizer/Events", help="TTree path inside each ROOT file.")
    parser.add_argument("--flavor", choices=["electron", "muon", "both"], default="both")
    parser.add_argument("--merge-inputs", nargs="+", help="Partial fiducial-map ROOT files or globs to merge.")
    parser.add_argument("--layers", default="combinedBins", choices=["NLayers4", "NLayers5", "NLayers6plus", "combinedBins"])
    parser.add_argument("--chunk-size", default="100 MB", help="uproot iterate step_size.")
    parser.add_argument("--output-dir", default=".", help="Directory for fiducial-map ROOT payloads.")
    parser.add_argument("--tag", required=True, help="Output tag, e.g. 2024G_data.")
    parser.add_argument(
        "--eta-bins",
        type=int,
        default=60,
        help="Number of eta bins. Default reproduces the legacy 0.1-wide binning.",
    )
    parser.add_argument(
        "--phi-bins",
        type=int,
        default=64,
        help="Number of phi bins. Default reproduces the legacy 0.1-wide binning.",
    )
    parser.add_argument("--eta-min", type=float, default=-3.0)
    parser.add_argument("--eta-max", type=float, default=3.0)
    parser.add_argument("--phi-min", type=float, default=-3.2)
    parser.add_argument("--phi-max", type=float, default=3.2)
    parser.add_argument("--threshold", type=float, default=2.0, help="Hot-spot threshold in sigma for the JSON summary.")
    parser.add_argument("--jet-pt-min", type=float, default=30.0)
    parser.add_argument("--jet-eta-max", type=float, default=4.5)
    parser.add_argument("--apply-2022-efg-water-leak-veto", action="store_true")
    parser.add_argument("--plot-dir", help="Optional directory for before/after, inefficiency, and hot-spot plots.")
    parser.add_argument("--cms-label", default="CMS Preliminary", help="CMS label drawn at the upper left of fiducial-map plots.")
    parser.add_argument("--lumi-label", default="13.6 TeV", help="Luminosity/energy label drawn at the upper right of fiducial-map plots.")
    parser.add_argument(
        "--hot-spot-radius",
        type=float,
        default=None,
        help="Radius of hot-spot circles in eta-phi plots. Default uses the bin half-diagonal from the AN.",
    )
    parser.add_argument("--json-output", help="Optional JSON summary of the calculated maps.")

    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
