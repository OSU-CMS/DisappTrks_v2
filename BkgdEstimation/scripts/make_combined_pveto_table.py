#!/usr/bin/env python3
r"""
Combine per-era Pveto LaTeX tables into one Table-24-style LaTeX table.

Expected input files are the per-era tables produced by MergePvetoJsonAndMakeTables_v2.py,
with rows like:

    $N_{\mathrm{layers}}=4$ & 141 & 75 & 66 & 61 & $0.1867^{+0.16}_{-0.16}$ \\

Usage examples:

    python3 make_combined_pveto_table.py \
        --inputs 2023C=pveto_2023C_muon_v2.tex \
                 2023D=pveto_2023D_muon_v2.tex \
                 2024=pveto_2024_muon_v2.tex \
                 2025=pveto_2025_muon_v2.tex \
        --output pveto_muon_run3_table.tex

or, if labels can be inferred from filenames:

    python3 make_combined_pveto_table.py \
        --inputs pveto_2023C_muon_v2.tex pveto_2023D_muon_v2.tex \
                 pveto_2024_muon_v2.tex pveto_2025_muon_v2.tex \
        --output pveto_muon_run3_table.tex
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

LAYER_ORDER = ["4", "5", r"\geq 6"]
LAYER_OUTPUT = {
    "4": "4",
    "5": "5",
    r"\geq 6": r"$\geq 6$",
}

ROW_RE = re.compile(
    r"^\s*(?P<layer>\$N_\{\\mathrm\{layers\}\}\s*(?P<op>=|\\geq)\s*(?P<n>\d+)\$|combined)\s*&\s*"
    r"(?P<ntp>[^&]+?)\s*&\s*"
    r"(?P<nveto>[^&]+?)\s*&\s*"
    r"(?P<nss>[^&]+?)\s*&\s*"
    r"(?P<nssveto>[^&]+?)\s*&\s*"
    r"(?P<pveto>.+?)\s*\\\\\s*$"
)


def infer_label(path: Path) -> str:
    name = path.stem
    match = re.search(r"(2023C|2023D|2023_C|2023_D|2024|2025)", name)
    if not match:
        raise ValueError(
            f"Could not infer run-period label from {path}. "
            "Pass inputs as LABEL=FILE, e.g. 2023C=pveto_2023C_muon_v2.tex."
        )
    return match.group(1).replace("_", "")


def parse_input_spec(spec: str) -> Tuple[str, Path]:
    if "=" in spec:
        label, filename = spec.split("=", 1)
        return label.strip().replace("_", ""), Path(filename)
    path = Path(spec)
    return infer_label(path), path


def _format_sig(x: float, ndigits: int = 3) -> str:
    if x == 0:
        return "0.0"
    return f"{x:.{ndigits}g}"


def format_pveto(pveto: str, convert_scientific: bool = False) -> str:
    """Optionally convert e-notation Pveto values to AN-style ×10^n notation."""
    if not convert_scientific or "e" not in pveto.lower():
        return pveto

    raw = pveto.strip()
    if raw.startswith("$") and raw.endswith("$"):
        raw = raw[1:-1]

    m = re.match(
        r"(?P<c>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)"
        r"\^\{\+(?P<u>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\}"
        r"_\{-(?P<d>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\}$",
        raw,
        flags=re.IGNORECASE,
    )
    if not m:
        return pveto

    central = float(m.group("c"))
    up = float(m.group("u"))
    down = float(m.group("d"))

    reference = abs(central) if central != 0 else abs(up)
    if reference == 0:
        return pveto

    exponent = int(np.floor(np.log10(reference)))
    scale = 10.0 ** exponent

    return (
        rf"$({_format_sig(central / scale)}^{{+{_format_sig(up / scale)}}}_{{-{_format_sig(down / scale)}}}) "
        rf"\times 10^{{{exponent}}}$"
    )


def canonical_layer(op: str, n: str) -> str:
    if op == "=":
        return n
    if op == r"\geq" and n == "6":
        return r"\geq 6"
    return f"{op} {n}"


def parse_pveto_tex(path: Path) -> Dict[str, Dict[str, str]]:
    rows: Dict[str, Dict[str, str]] = {}

    for line in path.read_text().splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue

        if m.group("layer") == "combined":
            layer = "combined"
        else:
            layer = canonical_layer(m.group("op"), m.group("n"))

        rows[layer] = {
            "ntp": m.group("ntp").strip(),
            "nveto": m.group("nveto").strip(),
            "nss": m.group("nss").strip(),
            "nssveto": m.group("nssveto").strip(),
            "pveto": m.group("pveto").strip(),
        }

    missing = [layer for layer in LAYER_ORDER if layer not in rows]
    if missing:
        raise ValueError(f"Missing layer rows {missing} in {path}")

    return rows


def write_table(
    all_rows: List[Tuple[str, Dict[str, Dict[str, str]]]],
    output: Path,
    flavor: str = "muon",
    caption: str | None = None,
    label: str | None = None,
    include_combined: bool = False,
    convert_scientific: bool = False,
) -> None:
    layers = LAYER_ORDER + (["combined"] if include_combined else [])

    lines: List[str] = []

    if caption or label:
        lines.append(r"\begin{table}[htbp]")
        lines.append(r"\centering")
        if caption:
            lines.append(rf"\caption{{{caption}}}")
        if label:
            lines.append(rf"\label{{{label}}}")

    lines.append(r"\begin{tabular}{llcrrrrc}")
    lines.append(r"\hline")
    lines.append(
        r"run period & flavor & $n_{\mathrm{layers}}$ & "
        r"$N_{T\&P}$ & $N^{\mathrm{veto}}_{T\&P}$ & "
        r"$N_{SS,T\&P}$ & $N^{\mathrm{veto}}_{SS,T\&P}$ & "
        r"$P_{\mathrm{veto}}$ \\" 
    )
    lines.append(r"\hline")

    for i, (period, rows) in enumerate(all_rows):
        for j, layer in enumerate(layers):
            row = rows[layer]
            run_cell = period if j == 0 else ""
            flavor_cell = flavor if j == 0 else ""
            layer_cell = LAYER_OUTPUT.get(layer, layer)
            pveto = format_pveto(row["pveto"], convert_scientific)
            lines.append(
                f"{run_cell} & {flavor_cell} & {layer_cell} & "
                f"{row['ntp']} & {row['nveto']} & {row['nss']} & {row['nssveto']} & {pveto} "
                r"\\"
            )
        if i != len(all_rows) - 1:
            lines.append(r"\hline")

    lines.append(r"\hline")
    lines.append(r"\end{tabular}")

    if caption or label:
        lines.append(r"\end{table}")

    output.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Combine per-era Pveto LaTeX tables into a Table-24-style table."
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input tex files, either FILE or LABEL=FILE. Example: 2023C=pveto_2023C_muon_v2.tex",
    )
    parser.add_argument("--output", required=True, help="Output combined LaTeX table.")
    parser.add_argument("--flavor", default="muon", help="Flavor label for the table. Default: muon")
    parser.add_argument(
        "--include-combined",
        action="store_true",
        help="Also include the combined layer row from each input table.",
    )
    parser.add_argument(
        "--convert-scientific",
        action="store_true",
        help="Convert e-notation Pveto entries to AN-style ×10^{n} notation.",
    )
    parser.add_argument(
        "--caption",
        default=None,
        help="Optional caption. If supplied, wraps the tabular in a table environment.",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional LaTeX label. If supplied, wraps the tabular in a table environment.",
    )

    args = parser.parse_args()

    parsed: List[Tuple[str, Dict[str, Dict[str, str]]]] = []
    for spec in args.inputs:
        period, path = parse_input_spec(spec)
        parsed.append((period, parse_pveto_tex(path)))

    write_table(
        parsed,
        Path(args.output),
        flavor=args.flavor,
        caption=args.caption,
        label=args.label,
        include_combined=args.include_combined,
        convert_scientific=args.convert_scientific,
    )

    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
