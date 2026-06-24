#!/usr/bin/env python3

from __future__ import annotations

import argparse
import getpass
import glob
import json
import platform
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


JOB_COUNT_PATTERN = re.compile(
    r"^\s*(?:Jobs status:\s*)?([A-Za-z_]+)\s+.*\((\d+)/(\d+)\)",
    re.MULTILINE,
)
SERVER_STATUS_PATTERN = re.compile(r"Status on the CRAB server:\s+([A-Za-z_]+)", re.IGNORECASE)
TASK_STATUS_PATTERN = re.compile(r"Task status:\s+([A-Za-z_]+)", re.IGNORECASE)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(timezone.utc).astimezone()
    task_paths = _discover_tasks(args.task_globs)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    status = "ok"

    if shutil.which("crab") is None:
        status = "skipped"
        errors.append("crab is not available on PATH.")
    else:
        for task_path in task_paths:
            result = _run_command(["crab", "status", "-d", str(task_path)])
            record = _parse_task_status(task_path, result)
            records.append(record)
            if not result["ok"]:
                errors.append(str(result["error"]))
                if status == "ok":
                    status = "warning"

    summary = _summarize(records, len(task_paths))
    summary["errors"] = errors

    snapshot = {
        "metadata": {
            "source_type": "crab",
            "label": f"CRAB status {collected_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "collected_at": collected_at.isoformat(timespec="seconds"),
            "host": platform.node(),
            "username": getpass.getuser(),
            "status": status,
        },
        "summary": summary,
        "records": records,
    }

    output_path = output_dir / "crab_latest.json"
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect CRAB task status snapshots.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "snapshots",
    )
    parser.add_argument(
        "--task-glob",
        dest="task_globs",
        action="append",
        default=[],
        help="Glob used to discover CRAB project directories. May be repeated.",
    )
    return parser.parse_args()


def _discover_tasks(patterns: list[str]) -> list[Path]:
    paths: set[Path] = set()
    for pattern in patterns:
        for match in glob.glob(pattern):
            path = Path(match)
            if path.is_dir():
                paths.add(path.resolve())
    return sorted(paths)


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


def _parse_task_status(task_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    output = "\n".join(part for part in [str(result["stdout"]), str(result["stderr"])] if part)
    status_error = not bool(result["ok"]) or "CMSSW is missing" in output
    error = str(result["error"])
    if status_error and not error:
        error = output
    counts = {
        label.lower(): int(count)
        for label, count, _total in JOB_COUNT_PATTERN.findall(output)
    }
    totals = [int(total) for _label, _count, total in JOB_COUNT_PATTERN.findall(output)]
    server_status = _first_match(SERVER_STATUS_PATTERN, output)
    task_status = _first_match(TASK_STATUS_PATTERN, output)
    year, era = _year_and_era(task_path)
    failed_jobs = counts.get("failed", 0)
    finished_jobs = counts.get("finished", 0)
    total_jobs = max(totals, default=0)
    complete = (
        server_status.upper() == "COMPLETED"
        or task_status.upper() == "COMPLETED"
        or (total_jobs > 0 and finished_jobs == total_jobs)
    )

    return {
        "task_name": task_path.name.removeprefix("crab_"),
        "task_path": str(task_path),
        "year": year,
        "era": era,
        "server_status": server_status,
        "task_status": task_status,
        "finished_jobs": finished_jobs,
        "failed_jobs": failed_jobs,
        "running_jobs": counts.get("running", 0),
        "transferring_jobs": counts.get("transferring", 0),
        "cooloff_jobs": counts.get("cooloff", 0),
        "idle_jobs": counts.get("idle", 0),
        "held_jobs": counts.get("held", 0),
        "total_jobs": total_jobs,
        "complete": complete,
        "status_error": status_error,
        "error": error,
        "status_output": output[-6000:],
    }


def _summarize(records: list[dict[str, Any]], discovered_tasks: int) -> dict[str, Any]:
    return {
        "discovered_tasks": discovered_tasks,
        "checked_tasks": len(records),
        "completed_tasks": sum(bool(record["complete"]) for record in records),
        "tasks_with_failed_jobs": sum(int(record["failed_jobs"]) > 0 for record in records),
        "status_error_tasks": sum(bool(record["status_error"]) for record in records),
        "unfinished_tasks": sum(
            not bool(record["complete"]) and not bool(record["status_error"])
            for record in records
        ),
        "finished_jobs": sum(int(record["finished_jobs"]) for record in records),
        "failed_jobs": sum(int(record["failed_jobs"]) for record in records),
        "running_jobs": sum(int(record["running_jobs"]) for record in records),
    }


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1) if match else ""


def _year_and_era(task_path: Path) -> tuple[str, str]:
    parts = task_path.parts
    try:
        index = parts.index("crab_projects")
    except ValueError:
        return "", ""
    year = parts[index + 1] if len(parts) > index + 1 else ""
    era = parts[index + 2] if len(parts) > index + 2 else ""
    return year, era


if __name__ == "__main__":
    main()
