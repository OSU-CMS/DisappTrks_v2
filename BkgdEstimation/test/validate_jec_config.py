#!/usr/bin/env python3
"""Validate configured JEC correction names against correctionlib payloads."""

from __future__ import annotations

import argparse
import difflib
import gzip
import json
import sys
from pathlib import Path
from typing import Iterable


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PACKAGE_ROOT / "data" / "JecConfigAK4.json"


def load_json(path: Path) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as source:
        return json.load(source)


def correction_names(payload_path: Path) -> set[str]:
    payload = load_json(payload_path)
    corrections = payload.get("corrections")
    if not isinstance(corrections, list):
        raise RuntimeError(
            f"{payload_path} does not contain a correctionlib 'corrections' list"
        )
    return {
        correction["name"]
        for correction in corrections
        if isinstance(correction, dict) and isinstance(correction.get("name"), str)
    }


def configured_tags(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = path + (key,)
            if key.startswith("tagName") and isinstance(value, str):
                yield ".".join(child_path), value
            else:
                yield from configured_tags(value, child_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from configured_tags(value, path + (str(index),))


def correction_suffix(name: str) -> str | None:
    for marker in ("_DATA_", "_MC_"):
        if marker in name:
            return name[name.index(marker):]
    return None


def suggestions(name: str, available: set[str], limit: int = 5) -> list[str]:
    suffix = correction_suffix(name)
    if suffix:
        same_kind = sorted(candidate for candidate in available if candidate.endswith(suffix))
        if same_kind:
            return same_kind[:limit]
    return difflib.get_close_matches(name, sorted(available), n=limit, cutoff=0.45)


def mode_section(year_config: dict, mode: str) -> dict:
    if mode == "data":
        return year_config.get("ApplyOnData", {})
    if mode == "mc":
        return year_config.get("ApplyOnMC", {})
    return year_config


def validate_jec_config(
    config_path: Path,
    years: Iterable[str] | None = None,
    mode: str = "data",
) -> list[str]:
    config_path = config_path.resolve()
    config = load_json(config_path)
    selected_years = list(dict.fromkeys(years or config.keys()))
    errors = []

    for year in selected_years:
        year_config = config.get(year)
        if not isinstance(year_config, dict):
            errors.append(f"[{year}] year key is missing from {config_path}")
            continue

        payload_value = year_config.get("jercJsonPath")
        if not isinstance(payload_value, str):
            errors.append(f"[{year}] jercJsonPath is missing")
            continue

        payload_path = Path(payload_value)
        if not payload_path.is_absolute():
            payload_path = config_path.parent / payload_path

        if not payload_path.is_file():
            errors.append(f"[{year}] correction payload is unavailable: {payload_path}")
            continue

        try:
            available = correction_names(payload_path)
        except Exception as error:
            errors.append(f"[{year}] could not read {payload_path}: {error}")
            continue

        tags = list(configured_tags(mode_section(year_config, mode)))
        if not tags:
            errors.append(f"[{year}] no configured {mode} correction tags were found")
            continue

        for location, name in tags:
            if name in available:
                continue
            message = [
                f"[{year}] missing correction: {name}",
                f"  config: {location}",
                f"  payload: {payload_path}",
            ]
            candidates = suggestions(name, available)
            if candidates:
                message.append("  suggested replacement(s):")
                message.extend(f"    {candidate}" for candidate in candidates)
            errors.append("\n".join(message))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check JEC config tag names against correctionlib payloads."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"JEC mapping JSON (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        help="JEC year keys to validate, for example 2023Pre 2024.",
    )
    parser.add_argument(
        "--mode",
        choices=("data", "mc", "all"),
        default="data",
        help="Correction section to validate.",
    )
    args = parser.parse_args()

    errors = validate_jec_config(args.config, args.years, args.mode)
    if errors:
        print("JEC preflight failed:", file=sys.stderr)
        for error in errors:
            print(f"\n{error}", file=sys.stderr)
        return 1

    years = ", ".join(args.years) if args.years else "all configured years"
    print(f"JEC preflight passed for {years} ({args.mode}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
