#!/usr/bin/env python3

from __future__ import annotations

import argparse
import getpass
import json
import platform
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import PurePosixPath, Path
from typing import Any


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(timezone.utc).astimezone()
    root_records: list[dict[str, Any]] = []
    file_records: list[dict[str, Any]] = []
    errors: list[str] = []
    status = "ok"

    if shutil.which("xrdfs") is None:
        status = "skipped"
        errors.append("xrdfs is not available on PATH.")
    else:
        for root in args.roots:
            root_record, files = _collect_root(args.endpoint, root)
            root_records.append(root_record)
            file_records.extend(files)
            if root_record["status"] == "failed":
                errors.append(str(root_record["error"]))
                if status == "ok":
                    status = "warning"

    summary = {
        "configured_roots": len(args.roots),
        "available_roots": sum(record["status"] == "available" for record in root_records),
        "not_created_roots": sum(record["status"] == "not_created" for record in root_records),
        "failed_roots": sum(record["status"] == "failed" for record in root_records),
        "root_files": len(file_records),
        "errors": errors,
    }

    snapshot = {
        "metadata": {
            "source_type": "eos",
            "label": f"EOS outputs {collected_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "collected_at": collected_at.isoformat(timespec="seconds"),
            "host": platform.node(),
            "username": getpass.getuser(),
            "status": status,
        },
        "summary": summary,
        "roots": root_records,
        "records": file_records,
    }

    output_path = output_dir / "eos_latest.json"
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory ROOT outputs under EOS directories.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "snapshots",
    )
    parser.add_argument(
        "--endpoint",
        default="root://cmseosmgm01.fnal.gov",
        help="XRootD endpoint passed to xrdfs.",
    )
    parser.add_argument(
        "--root",
        dest="roots",
        action="append",
        default=[],
        help="EOS directory to inventory. May be repeated.",
    )
    return parser.parse_args()


def _collect_root(endpoint: str, root: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stat_result = _run_command(["xrdfs", endpoint, "stat", root])
    if not stat_result["ok"]:
        detail = f"{stat_result['stdout']}\n{stat_result['stderr']}".lower()
        if "no such file" in detail or "not found" in detail:
            return _root_record(root, "not_created", 0, ""), []
        error = str(stat_result["error"])
        return _root_record(root, "failed", 0, error), []

    list_result = _run_command(["xrdfs", endpoint, "ls", "-R", root])
    if not list_result["ok"]:
        error = str(list_result["error"])
        return _root_record(root, "failed", 0, error), []

    files = []
    for line in str(list_result["stdout"]).splitlines():
        path = line.strip()
        if not path.endswith(".root"):
            continue
        files.append(
            {
                "root": root,
                "path": path,
                "relative_path": _relative_path(path, root),
                "top_level": _top_level(path, root),
                "url": f"{endpoint.rstrip('/')}/{path.lstrip('/')}",
            }
        )
    return _root_record(root, "available", len(files), ""), files


def _run_command(command: list[str]) -> dict[str, Any]:
    command_text = " ".join(shlex.quote(part) for part in command)
    try:
        result = subprocess.run(
            ["bash", "-lc", command_text],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return {"ok": False, "stdout": "", "stderr": "", "error": str(error)}

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        detail = stderr or stdout or "no diagnostic output"
        return {
            "ok": False,
            "stdout": stdout,
            "stderr": stderr,
            "error": f"{command_text} exited with {result.returncode}: {detail}",
        }
    return {"ok": True, "stdout": stdout, "stderr": stderr, "error": ""}


def _root_record(root: str, status: str, root_files: int, error: str) -> dict[str, Any]:
    return {
        "root": root,
        "status": status,
        "root_files": root_files,
        "error": error,
    }


def _relative_path(path: str, root: str) -> str:
    prefix = root.rstrip("/") + "/"
    return path[len(prefix):] if path.startswith(prefix) else path


def _top_level(path: str, root: str) -> str:
    relative = _relative_path(path, root)
    parts = PurePosixPath(relative).parts
    return parts[0] if parts else ""


if __name__ == "__main__":
    main()
