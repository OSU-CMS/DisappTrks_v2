#!/usr/bin/env python3
"""Export merged P_veto cutflows to ROOT histograms and optional LaTeX tables.

Each output ROOT file contains three TH1F objects (NLayers4, NLayers5,
NLayers6plus). The x-axis bin labels are the cut names; y is the event count
after each cut.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ROOT

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from MergePvetoJsonAndMakeTables_v2 import (  # noqa: E402
    ordered_cut_names,
    write_cutflow_latex,
)

CUTFLOW_LAYERS = ["NLayers4", "NLayers5", "NLayers6plus"]


def load_merged(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def cutflow_rows(cutflow: dict) -> list[tuple[str, int, float, float]]:
    """Return (cut_name, events, eff_prev, eff_total) in analysis order."""
    names = ordered_cut_names(cutflow)
    rows: list[tuple[str, int, float, float]] = []
    first = None
    prev = None
    for cut in names:
        value = int(cutflow[cut])
        if first is None:
            first = value
        eff_prev = value / prev if prev else 1.0
        eff_total = value / first if first else 0.0
        rows.append((cut, value, eff_prev, eff_total))
        prev = value
    return rows


def axis_cut_label(cut: str) -> str:
    """ROOT x-axis bin label (TLatex-style # tokens where helpful)."""
    if cut.startswith(">= 1 track nlayers >= 4"):
        # e.g. ">= 1 track nlayers >= 4 (NLayers4)"
        suffix = cut.split("(", 1)[-1].rstrip(")") if "(" in cut else cut
        return f"#geq 1 track N_{{layers}}#geq 4 ({suffix})"

    replacements = (
        (">=", "#geq"),
        ("<=", "#leq"),
        ("|eta|", "|#eta|"),
        ("pT", "p_{T}"),
        ("pTmiss", "p_{T}^{miss}"),
        ("DeltaR", "#DeltaR"),
    )
    label = cut
    for old, new in replacements:
        label = label.replace(old, new)
    return label


def make_cutflow_hist(
    rows: list[tuple[str, int, float, float]], name: str, title: str
) -> ROOT.TH1F:
    n = len(rows)
    hist = ROOT.TH1F(name, title, n, 0, n)
    hist.SetStats(0)
    hist.SetDirectory(ROOT.nullptr)

    for i, (cut, events, _, _) in enumerate(rows):
        hist.SetBinContent(i + 1, events)
        hist.GetXaxis().SetBinLabel(i + 1, axis_cut_label(cut))

    hist.GetXaxis().SetTitle("")
    hist.GetYaxis().SetTitle("Events")
    hist.GetXaxis().LabelsOption("v")
    hist.GetXaxis().SetLabelSize(0.03)
    hist.SetTitle(title)
    return hist


def write_cutflow_root(merged: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    root_file = ROOT.TFile.Open(str(output_path), "RECREATE")
    if not root_file or root_file.IsZombie():
        raise OSError(f"Could not create ROOT file: {output_path}")

    for layer in CUTFLOW_LAYERS:
        cutflow = merged.get(layer, {}).get("cutflow", {})
        if not cutflow:
            raise KeyError(f"Missing cutflow for layer {layer!r} in merged JSON")

        rows = cutflow_rows(cutflow)
        hist_name = f"cutflow_{layer}"
        hist_title = f"P_veto cutflow ({layer}); ;Events"
        hist = make_cutflow_hist(rows, hist_name, hist_title)
        hist.Write(hist_name)

    root_file.Close()


def write_all_cutflow_latex(merged: dict, out_dir: Path, table_env: bool) -> None:
    for layer in CUTFLOW_LAYERS:
        tex_path = out_dir / f"cutflow_table_{layer}.tex"
        write_cutflow_latex(merged, tex_path, layer, table_env)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write P_veto cutflow histograms (3 layers) and optional LaTeX tables."
    )
    parser.add_argument(
        "merged_json",
        type=Path,
        help="Path to merged_pveto_cutflow.json (per era or merged).",
    )
    parser.add_argument(
        "-o",
        "--output-root",
        type=Path,
        default=None,
        help="Output ROOT file (default: same directory as JSON, pveto_cutflow.root).",
    )
    parser.add_argument(
        "--latex-dir",
        type=Path,
        default=None,
        help="If set, write cutflow_table_<layer>.tex for each NLayers bin.",
    )
    parser.add_argument(
        "--table-env",
        action="store_true",
        help="Wrap LaTeX tabulars in table/caption environments.",
    )
    args = parser.parse_args()

    merged_json = args.merged_json.resolve()
    merged = load_merged(merged_json)

    output_root = args.output_root
    if output_root is None:
        output_root = merged_json.parent / "pveto_cutflow.root"
    else:
        output_root = output_root.resolve()

    ROOT.gROOT.SetBatch(True)
    write_cutflow_root(merged, output_root)
    print(f"Wrote {output_root}")
    for layer in CUTFLOW_LAYERS:
        n_cuts = len(cutflow_rows(merged[layer]["cutflow"]))
        print(f"  {layer}: {n_cuts} cuts -> cutflow_{layer} (TH1F, cut names on x-axis)")

    if args.latex_dir is not None:
        latex_dir = args.latex_dir.resolve()
        latex_dir.mkdir(parents=True, exist_ok=True)
        write_all_cutflow_latex(merged, latex_dir, args.table_env)
        for layer in CUTFLOW_LAYERS:
            print(f"Wrote {latex_dir / f'cutflow_table_{layer}.tex'}")


if __name__ == "__main__":
    main()
