#!/usr/bin/env python3

from __future__ import annotations

import argparse
import glob
import json
import math
from collections import OrderedDict
from pathlib import Path

LAYERS = ["NLayers4", "NLayers5", "NLayers6plus", "combinedBins"]

DISPLAY_LAYER = {
    "NLayers4": r"$N_{\mathrm{layers}}=4$",
    "NLayers5": r"$N_{\mathrm{layers}}=5$",
    "NLayers6plus": r"$N_{\mathrm{layers}}\geq 6$",
    "combinedBins": r"combined",
}

# Force the cutflow table to follow the order in which cuts are applied.
# Rows that are absent in a particular JSON are skipped.
CUTFLOW_ORDER = [
    "event passes SingleMuon triggers",
    ">= 1 muons pT > 26 GeV",
    ">= 1 muons |eta| < 2.1",
    ">= 1 muons passing tight muon ID",
    ">= 1 muons MT(pTmiss, muon) < 40 GeV",
    "exactly one passing muon chosen randomly",
    ">= 1 tracks pT > 30 GeV",
    ">= 1 tracks |eta| < 2.1",
    ">= 1 tracks |eta| < 0.15 OR |eta| > 0.35",
    ">= 1 tracks |eta| < 1.42 OR |eta| > 1.65",
    ">= 1 tracks |eta| < 1.55 OR |eta| > 1.85",
    ">= 1 tracks number of pixel hits >= 4",
    ">= 1 tracks missing inner hits = 0",
    ">= 1 tracks missing middle hits = 0",
    ">= 1 tracks rel. PF-based iso. < 0.05",
    ">= 1 tracks |dxy| < 0.02 cm",
    ">= 1 tracks |dz| < 0.5 cm",
    ">= 1 track-jet pairs DeltaRtrack,jet > 0.5",
    ">= 1 track-muon pairs Mtrack,muon > 10 GeV",
    ">= 1 tracks min DeltaRtrack,electron > 0.15",
    ">= 1 tracks min DeltaRtrack,had. tau > 0.15",
    ">= 1 tracks Ecalo < 10 GeV",
    "exactly one passing track chosen randomly",
    "= 1 track-muon pairs |Mtrack,muon - MZ| < 10 GeV",
    "= 1 track-muon pairs qtrack * qmuon < 0",
    # Layer row is handled by prefix match below because the exact name contains the layer.
]

LATEX_LABELS = {
    "event passes SingleMuon triggers":
        r"Event passes SingleMuon triggers",
    ">= 1 muons pT > 26 GeV":
        r"$\geq 1$ muon with $p_{\mathrm{T}}>26~\mathrm{GeV}$",
    ">= 1 muons |eta| < 2.1":
        r"$\geq 1$ muon with $|\eta|<2.1$",
    ">= 1 muons passing tight muon ID":
        r"$\geq 1$ muon passing tight muon ID",
    ">= 1 muons MT(pTmiss, muon) < 40 GeV":
        r"$\geq 1$ muon with $M_{\mathrm{T}}(p_{\mathrm{T}}^{\mathrm{miss}},\mu)<40~\mathrm{GeV}$",
    "exactly one passing muon chosen randomly":
        r"Exactly one passing muon chosen randomly",
    ">= 1 tracks pT > 30 GeV":
        r"$\geq 1$ track with $p_{\mathrm{T}}>30~\mathrm{GeV}$",
    ">= 1 tracks |eta| < 2.1":
        r"$\geq 1$ track with $|\eta|<2.1$",
    ">= 1 tracks |eta| < 0.15 OR |eta| > 0.35":
        r"$\geq 1$ track with $|\eta|<0.15$ or $|\eta|>0.35$",
    ">= 1 tracks |eta| < 1.42 OR |eta| > 1.65":
        r"$\geq 1$ track with $|\eta|<1.42$ or $|\eta|>1.65$",
    ">= 1 tracks |eta| < 1.55 OR |eta| > 1.85":
        r"$\geq 1$ track with $|\eta|<1.55$ or $|\eta|>1.85$",
    ">= 1 tracks number of pixel hits >= 4":
        r"$\geq 1$ track with $\geq 4$ pixel hits",
    ">= 1 tracks missing inner hits = 0":
        r"$\geq 1$ track with missing inner hits $=0$",
    ">= 1 tracks missing middle hits = 0":
        r"$\geq 1$ track with missing middle hits $=0$",
    ">= 1 tracks rel. PF-based iso. < 0.05":
        r"$\geq 1$ track with relative PF-based isolation $<0.05$",
    ">= 1 tracks |dxy| < 0.02 cm":
        r"$\geq 1$ track with $|d_{xy}|<0.02~\mathrm{cm}$",
    ">= 1 tracks |dz| < 0.5 cm":
        r"$\geq 1$ track with $|d_{z}|<0.5~\mathrm{cm}$",
    ">= 1 track-jet pairs DeltaRtrack,jet > 0.5":
        r"$\geq 1$ track--jet pair with $\Delta R(\mathrm{track},\mathrm{jet})>0.5$",
    ">= 1 track-muon pairs Mtrack,muon > 10 GeV":
        r"$\geq 1$ track--muon pair with $M_{\mathrm{track},\mu}>10~\mathrm{GeV}$",
    ">= 1 tracks min DeltaRtrack,electron > 0.15":
        r"$\geq 1$ track with $\min\Delta R(\mathrm{track},e)>0.15$",
    ">= 1 tracks min DeltaRtrack,had. tau > 0.15":
        r"$\geq 1$ track with $\min\Delta R(\mathrm{track},\tau_{\mathrm{h}})>0.15$",
    ">= 1 tracks Ecalo < 10 GeV":
        r"$\geq 1$ track with $E_{\mathrm{calo}}<10~\mathrm{GeV}$",
    "exactly one passing track chosen randomly":
        r"Exactly one passing track chosen randomly",
    "= 1 track-muon pairs |Mtrack,muon - MZ| < 10 GeV":
        r"$\geq 1$ track--muon pair with $|M_{\mathrm{track},\mu}-M_{Z}|<10~\mathrm{GeV}$",
    "= 1 track-muon pairs qtrack * qmuon < 0":
        r"$\geq 1$ track--muon pair with $q_{\mathrm{track}}q_{\mu}<0$",
}


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def latex_cut_label(cut: str) -> str:
    if cut.startswith(">= 1 track nlayers >= 4"):
        return r"$\geq 1$ track with $N_{\mathrm{layers}}\geq 4$"
    return LATEX_LABELS.get(cut, latex_escape(cut))


def add_count(total: dict, key: str, value: float, variance: float | None = None) -> None:
    total.setdefault(key, {"value": 0.0, "variance": 0.0})
    total[key]["value"] += float(value)
    total[key]["variance"] += float(value if variance is None else variance)


def pveto_with_asymmetric_uncertainty(num_os: dict, num_ss: dict, den_os: dict, den_ss: dict):
    """
    Table-24-style Pveto convention.

    P_veto = (N_veto_OS - N_veto_SS)/(N_OS - N_SS)

    If the numerator is negative, set the central value to zero and quote only
    the upward one-sigma uncertainty from the signed numerator uncertainty.
    """
    n_os = float(num_os.get("value", 0.0))
    n_ss = float(num_ss.get("value", 0.0))
    d_os = float(den_os.get("value", 0.0))
    d_ss = float(den_ss.get("value", 0.0))

    n_var = float(num_os.get("variance", n_os)) + float(num_ss.get("variance", n_ss))
    d_var = float(den_os.get("variance", d_os)) + float(den_ss.get("variance", d_ss))

    num = n_os - n_ss
    den = d_os - d_ss

    if den <= 0:
        return 0.0, 0.0, 0.0, num, den

    sigma_num = math.sqrt(max(n_var, 0.0))
    sigma_den = math.sqrt(max(d_var, 0.0))

    if num < 0:
        central = 0.0
        err_down = 0.0
        err_up = sigma_num / den
        return central, err_down, err_up, num, den

    central = num / den
    rel2 = 0.0
    if num > 0:
        rel2 += (sigma_num / num) ** 2
    if den > 0:
        rel2 += (sigma_den / den) ** 2
    err = abs(central) * math.sqrt(rel2)
    return central, err, err, num, den


def format_count(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return f"{round(x):d}"
    return f"{x:.3g}"


def format_pveto_latex(central: float, err_down: float, err_up: float) -> str:
    return rf"${central:.4g}^{{+{err_up:.2g}}}_{{-{err_down:.2g}}}$"


def load_json_files(patterns: list[str]) -> list[dict]:
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        paths.extend(matches if matches else [pattern])

    if not paths:
        raise RuntimeError("No JSON files matched the input patterns.")

    payloads = []
    for path in paths:
        with open(path) as f:
            payloads.append(json.load(f))
    return payloads


def merge_payloads(payloads: list[dict]):
    merged = {layer: {"cutflow": OrderedDict(), "counts": {}} for layer in LAYERS}

    for payload in payloads:
        for layer, layer_data in payload.get("layers", {}).items():
            if layer not in merged:
                merged[layer] = {"cutflow": OrderedDict(), "counts": {}}

            for cut, value in layer_data.get("cutflow", {}).items():
                if cut not in merged[layer]["cutflow"]:
                    merged[layer]["cutflow"][cut] = 0
                merged[layer]["cutflow"][cut] += int(value)

            for key, count in layer_data.get("counts", {}).items():
                add_count(
                    merged[layer]["counts"],
                    key,
                    count.get("value", 0.0),
                    count.get("variance", count.get("value", 0.0)),
                )

    return merged


def ordered_cut_names(cutflow: OrderedDict) -> list[str]:
    names: list[str] = []
    seen = set()

    for cut in CUTFLOW_ORDER:
        if cut in cutflow and cut not in seen:
            names.append(cut)
            seen.add(cut)

    layer_rows = [cut for cut in cutflow if cut.startswith(">= 1 track nlayers >= 4")]
    for cut in layer_rows:
        if cut not in seen:
            names.append(cut)
            seen.add(cut)

    # Append any future/new rows in the JSON's insertion order rather than dropping them.
    for cut in cutflow:
        if cut not in seen:
            names.append(cut)
            seen.add(cut)

    return names


def write_cutflow_latex(merged: dict, path: Path, layer: str, include_table_env: bool = False):
    cutflow = merged[layer]["cutflow"]
    names = ordered_cut_names(cutflow)

    with open(path, "w") as out:
        if include_table_env:
            out.write(r"\begin{table}[htbp]" + "\n")
            out.write(r"\centering" + "\n")
            out.write(r"\caption{Muon tag-and-probe cutflow.}" + "\n")
            out.write(r"\label{tab:muon_tp_cutflow}" + "\n")

        out.write(r"\begin{tabular}{lrrr}" + "\n")
        out.write(r"\hline" + "\n")
        out.write(r"Cut & Events & $\epsilon_{\mathrm{prev}}$ & $\epsilon_{\mathrm{total}}$ \\" + "\n")
        out.write(r"\hline" + "\n")

        first = None
        prev = None
        for cut in names:
            value = int(cutflow[cut])
            if first is None:
                first = value
            eff_prev = value / prev if prev else 1.0
            eff_total = value / first if first else 0.0
            out.write(
                f"{latex_cut_label(cut)} & {value:d} & {eff_prev:.4f} & {eff_total:.4f} \\\\\n"
            )
            prev = value

        out.write(r"\hline" + "\n")
        out.write(r"\end{tabular}" + "\n")
        if include_table_env:
            out.write(r"\end{table}" + "\n")


def write_pveto_latex(merged: dict, path: Path, include_table_env: bool = False):
    with open(path, "w") as out:
        if include_table_env:
            out.write(r"\begin{table}[htbp]" + "\n")
            out.write(r"\centering" + "\n")
            out.write(r"\caption{Muon veto probabilities.}" + "\n")
            out.write(r"\label{tab:muon_pveto}" + "\n")

        out.write(r"\begin{tabular}{lrrrrr}" + "\n")
        out.write(r"\hline" + "\n")
        out.write(
            r"Layer & $N_{T\&P}$ & $N^{\mathrm{veto}}_{T\&P}$ & "
            r"$N_{SS,T\&P}$ & $N^{\mathrm{veto}}_{SS,T\&P}$ & "
            r"$P_{\mathrm{veto}}$ \\" + "\n"
        )
        out.write(r"\hline" + "\n")

        for layer in LAYERS:
            counts = merged[layer]["counts"]
            den_os = counts.get("p_veto_den_os", {"value": 0.0, "variance": 0.0})
            num_os = counts.get("p_veto_num_os", {"value": 0.0, "variance": 0.0})
            den_ss = counts.get("p_veto_den_ss", {"value": 0.0, "variance": 0.0})
            num_ss = counts.get("p_veto_num_ss", {"value": 0.0, "variance": 0.0})

            central, err_down, err_up, raw_num, raw_den = pveto_with_asymmetric_uncertainty(
                num_os=num_os,
                num_ss=num_ss,
                den_os=den_os,
                den_ss=den_ss,
            )

            out.write(
                f"{DISPLAY_LAYER.get(layer, latex_escape(layer))} & "
                f"{format_count(den_os['value'])} & {format_count(num_os['value'])} & "
                f"{format_count(den_ss['value'])} & {format_count(num_ss['value'])} & "
                f"{format_pveto_latex(central, err_down, err_up)} \\\\\n"
            )

        out.write(r"\hline" + "\n")
        out.write(r"\end{tabular}" + "\n")
        if include_table_env:
            out.write(r"\end{table}" + "\n")


def write_merged_json(merged: dict, path: Path):
    serializable = {
        layer: {
            "cutflow": dict(data["cutflow"]),
            "counts": data["counts"],
        }
        for layer, data in merged.items()
    }
    with open(path, "w") as out:
        json.dump(serializable, out, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Merge per-job muon Pveto JSON outputs and make LaTeX tables."
    )
    parser.add_argument("json_files", nargs="+", help="Per-job JSON files or glob patterns.")
    parser.add_argument("--cutflow-tex", default="cutflow_table.tex")
    parser.add_argument("--pveto-tex", default="pveto_table.tex")
    parser.add_argument("--cutflow-layer", default="combinedBins", choices=LAYERS)
    parser.add_argument("--merged-json", default="merged_pveto_cutflow.json")
    parser.add_argument(
        "--table-env",
        action="store_true",
        help="Wrap output tabulars in table/centering/caption/label environments. Default writes only tabulars for easy \\input{}.",
    )
    args = parser.parse_args()

    payloads = load_json_files(args.json_files)
    merged = merge_payloads(payloads)

    write_merged_json(merged, Path(args.merged_json))
    write_cutflow_latex(merged, Path(args.cutflow_tex), args.cutflow_layer, args.table_env)
    write_pveto_latex(merged, Path(args.pveto_tex), args.table_env)

    print(f"Merged {len(payloads)} JSON files")
    print(f"Wrote {args.merged_json}")
    print(f"Wrote {args.cutflow_tex}")
    print(f"Wrote {args.pveto_tex}")


if __name__ == "__main__":
    main()
