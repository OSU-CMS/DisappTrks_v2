#!/usr/bin/env python3
"""Build CMS-style P_veto summary tables from merged_pveto_cutflow.json files."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

LAYERS = [
    ("NLayers4", "4"),
    ("NLayers5", "5"),
    ("NLayers6plus", r"$\geq 6$"),
]

COUNT_KEYS = (
    "p_veto_den_os",
    "p_veto_num_os",
    "p_veto_den_ss",
    "p_veto_num_ss",
)

DEFAULT_PERIODS = {
    "2022 CD": ["2022_C", "2022_D"],
    "2022 EFG": ["2022_E", "2022_F", "2022_G"],
}


def load_merged(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def add_count(total: dict, key: str, value: float, variance: float) -> None:
    total.setdefault(key, {"value": 0.0, "variance": 0.0})
    total[key]["value"] += float(value)
    total[key]["variance"] += float(variance)


def merge_period(datasets: list[str], base_dir: Path) -> dict:
    merged = {layer: {"counts": {}} for layer, _ in LAYERS}

    for dataset in datasets:
        path = base_dir / dataset / "merged_pveto_cutflow.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing merged file: {path}")

        payload = load_merged(path)
        for layer, _ in LAYERS:
            counts = payload.get(layer, {}).get("counts", {})
            for key in COUNT_KEYS:
                item = counts.get(key, {"value": 0.0, "variance": 0.0})
                add_count(
                    merged[layer]["counts"],
                    key,
                    item.get("value", 0.0),
                    item.get("variance", item.get("value", 0.0)),
                )

    return merged


def pveto_central(counts: dict) -> float:
    """Central P_veto only: (N_veto_OS - N_veto_SS) / (N_OS - N_SS)."""
    n_os = float(counts.get("p_veto_num_os", {}).get("value", 0.0))
    n_ss = float(counts.get("p_veto_num_ss", {}).get("value", 0.0))
    d_os = float(counts.get("p_veto_den_os", {}).get("value", 0.0))
    d_ss = float(counts.get("p_veto_den_ss", {}).get("value", 0.0))

    num = n_os - n_ss
    den = d_os - d_ss
    if den == 0 :
        return 0.0
    return num / den


def format_count(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{round(value):d}"
    return f"{value:.3g}"


def format_pveto(value: float) -> str:
    if value == 0.0:
        return "$0.0$"
    if abs(value) >= 0.01:
        return f"${value:.2f}$"
    exp = int(math.floor(math.log10(abs(value))))
    mantissa = value / (10**exp)
    if abs(mantissa - round(mantissa)) < 1e-6:
        mantissa = int(round(mantissa))
    else:
        mantissa = round(mantissa, 2)
    return rf"${mantissa} \times 10^{{{exp}}}$"


def build_rows(periods: dict[str, list[str]], base_dir: Path, flavors: list[str]) -> list[dict]:
    rows = []
    for period_label, datasets in periods.items():
        merged = merge_period(datasets, base_dir)
        for flavor in flavors:
            for layer_key, layer_label in LAYERS:
                counts = merged[layer_key]["counts"]
                rows.append(
                    {
                        "period": period_label,
                        "flavor": flavor,
                        "nlayers": layer_label,
                        "n_tp": format_count(counts.get("p_veto_den_os", {}).get("value", 0.0)),
                        "n_veto_tp": format_count(counts.get("p_veto_num_os", {}).get("value", 0.0)),
                        "n_ss_tp": format_count(counts.get("p_veto_den_ss", {}).get("value", 0.0)),
                        "n_veto_ss_tp": format_count(counts.get("p_veto_num_ss", {}).get("value", 0.0)),
                        "pveto": format_pveto(pveto_central(counts)),
                    }
                )
    return rows


def write_latex(rows: list[dict], path: Path, include_table_env: bool = True) -> None:
    period_blocks: dict[str, dict[str, list[dict]]] = {}
    for row in rows:
        period_blocks.setdefault(row["period"], {}).setdefault(row["flavor"], []).append(row)

    lines = []
    if include_table_env:
        lines.extend(
            [
                r"\begin{table}[htbp]",
                r"\centering",
                r"\caption{Muon veto probabilities in tag-and-probe samples.}",
                r"\label{tab:pveto_summary}",
            ]
        )

    lines.extend(
        [
            r"\begin{tabular}{llcrrrrr}",
            r"\hline",
            r"run period & flavor & $n_{\mathrm{layers}}$ & "
            r"$N_{T\&P}$ & $N^{\mathrm{veto}}_{T\&P}$ & "
            r"$N_{\mathrm{SS},T\&P}$ & $N^{\mathrm{veto}}_{\mathrm{SS},T\&P}$ & "
            r"$P_{\mathrm{veto}}$ \\",
            r"\hline",
        ]
    )

    period_names = list(period_blocks.keys())
    for period_idx, (period_label, flavor_rows) in enumerate(period_blocks.items()):
        n_period_rows = sum(len(v) for v in flavor_rows.values())
        period_written = False

        flavor_names = list(flavor_rows.keys())
        for flavor_idx, (flavor, layer_rows) in enumerate(flavor_rows.items()):
            n_flavor_rows = len(layer_rows)

            for layer_idx, layer_row in enumerate(layer_rows):
                if not period_written:
                    period_cell = rf"\multirow{{{n_period_rows}}}{{*}}{{{period_label}}}"
                    period_written = True
                else:
                    period_cell = ""

                if layer_idx == 0:
                    flavor_cell = rf"\multirow{{{n_flavor_rows}}}{{*}}{{{flavor}}}"
                else:
                    flavor_cell = ""

                lines.append(
                    f"{period_cell} & {flavor_cell} & {layer_row['nlayers']} & "
                    f"{layer_row['n_tp']} & {layer_row['n_veto_tp']} & "
                    f"{layer_row['n_ss_tp']} & {layer_row['n_veto_ss_tp']} & "
                    f"{layer_row['pveto']} \\\\"
                )

        if period_idx != len(period_names) - 1:
            lines.append(r"\hline")

    lines.extend([r"\hline", r"\end{tabular}"])
    if include_table_env:
        lines.append(r"\end{table}")

    path.write_text("\n".join(lines) + "\n")


def write_csv(rows: list[dict], path: Path) -> None:
    header = [
        "run_period",
        "flavor",
        "n_layers",
        "N_TP",
        "N_veto_TP",
        "N_SS_TP",
        "N_veto_SS_TP",
        "P_veto",
    ]
    lines = [",".join(header)]
    for row in rows:
        nlayers = row["nlayers"].replace("$", "").replace(r"\geq", ">=")
        pveto = row["pveto"].replace("$", "")
        lines.append(
            ",".join(
                [
                    row["period"],
                    row["flavor"],
                    nlayers,
                    row["n_tp"],
                    row["n_veto_tp"],
                    row["n_ss_tp"],
                    row["n_veto_ss_tp"],
                    pveto,
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Build CMS-style P_veto summary tables from merged JSON files."
    )
    parser.add_argument(
        "--base-dir",
        default="analysis_output",
        help="Directory containing per-era merged_pveto_cutflow.json files.",
    )
    parser.add_argument(
        "--output-tex",
        default="analysis_output/pveto_summary_table.tex",
    )
    parser.add_argument(
        "--output-csv",
        default="analysis_output/pveto_summary_table.csv",
    )
    parser.add_argument(
        "--flavor",
        action="append",
        default=["muon"],
        help="Flavor label(s) to include (repeat for multiple). Default: muon only.",
    )
    parser.add_argument(
        "--no-table-env",
        action="store_true",
        help="Write only the tabular environment.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    rows = build_rows(DEFAULT_PERIODS, base_dir, args.flavor)

    tex_path = Path(args.output_tex)
    csv_path = Path(args.output_csv)
    tex_path.parent.mkdir(parents=True, exist_ok=True)

    write_latex(rows, tex_path, include_table_env=not args.no_table_env)
    write_csv(rows, csv_path)

    print(f"Wrote {tex_path}")
    print(f"Wrote {csv_path}")
    for period, datasets in DEFAULT_PERIODS.items():
        print(f"  {period}: merged {', '.join(datasets)}")


if __name__ == "__main__":
    main()
