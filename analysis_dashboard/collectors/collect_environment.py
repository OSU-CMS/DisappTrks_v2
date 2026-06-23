#!/usr/bin/env python3

from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(timezone.utc).astimezone()
    snapshot = {
        "metadata": {
            "source_type": "environment",
            "label": f"environment {collected_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "collected_at": collected_at.isoformat(timespec="seconds"),
            "host": platform.node(),
            "username": getpass.getuser(),
            "status": "ok",
        },
        "summary": {
            "cwd": str(Path.cwd()),
            "python": platform.python_version(),
            "has_crab": _has_command("crab"),
            "has_condor_q": _has_command("condor_q"),
            "has_xrdfs": _has_command("xrdfs"),
            "has_voms_proxy_info": _has_command("voms-proxy-info"),
            "cmssw_base": os.environ.get("CMSSW_BASE", ""),
        },
        "records": [],
    }

    output_path = output_dir / "environment_latest.json"
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect basic runtime environment metadata.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "snapshots",
        help="Directory where the JSON snapshot should be written.",
    )
    return parser.parse_args()


def _has_command(command: str) -> bool:
    return shutil.which(command) is not None


if __name__ == "__main__":
    main()
