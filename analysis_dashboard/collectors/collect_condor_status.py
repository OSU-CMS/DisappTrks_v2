#!/usr/bin/env python3

from __future__ import annotations

import argparse
import getpass
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


JOB_STATUS_NAMES = {
    1: "idle",
    2: "running",
    3: "removed",
    4: "completed",
    5: "held",
    6: "transferring_output",
    7: "suspended",
}


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(timezone.utc).astimezone()
    records: list[dict[str, Any]] = []
    status = "ok"
    errors: list[str] = []

    if shutil.which("condor_q") is None:
        status = "skipped"
        errors.append("condor_q is not available on PATH.")
    else:
        query = _run_json_command(["condor_q", "-json"])
        if query["ok"]:
            records.extend(_normalize_jobs(query["records"], source="queue"))
        else:
            status = "failed"
            errors.append(str(query["error"]))

    if args.include_history:
        if shutil.which("condor_history") is None:
            errors.append("condor_history is not available on PATH.")
            if status == "ok":
                status = "warning"
        else:
            history_args = ["condor_history", "-json", "-limit", str(args.history_limit)]
            history = _run_json_command(history_args)
            if history["ok"]:
                records.extend(_normalize_jobs(history["records"], source="history"))
            else:
                errors.append(str(history["error"]))
                if status == "ok":
                    status = "warning"

    summary = _summarize(records)
    summary["errors"] = errors

    snapshot = {
        "metadata": {
            "source_type": "condor",
            "label": f"condor status {collected_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "collected_at": collected_at.isoformat(timespec="seconds"),
            "host": platform.node(),
            "username": getpass.getuser(),
            "status": status,
        },
        "summary": summary,
        "records": records,
    }

    output_path = output_dir / "condor_latest.json"
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect HTCondor queue and optional history snapshots.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "snapshots",
        help="Directory where the JSON snapshot should be written.",
    )
    parser.add_argument(
        "--include-history",
        action="store_true",
        help="Also collect recent condor_history records.",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=200,
        help="Maximum number of condor_history records to collect.",
    )
    return parser.parse_args()


def _run_json_command(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as error:
        return {"ok": False, "records": [], "error": str(error)}

    if result.returncode != 0:
        stderr = result.stderr.strip()
        return {
            "ok": False,
            "records": [],
            "error": f"{' '.join(command)} exited with {result.returncode}: {stderr}",
        }

    if not result.stdout.strip():
        return {"ok": True, "records": [], "error": ""}

    try:
        records = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return {"ok": False, "records": [], "error": f"Could not parse JSON from {' '.join(command)}: {error}"}

    if not isinstance(records, list):
        return {"ok": False, "records": [], "error": f"{' '.join(command)} did not return a JSON list."}

    return {"ok": True, "records": records, "error": ""}


def _normalize_jobs(records: list[object], source: str) -> list[dict[str, Any]]:
    normalized = []
    for record in records:
        if not isinstance(record, dict):
            continue

        cluster_id = record.get("ClusterId")
        proc_id = record.get("ProcId")
        job_status = _as_int(record.get("JobStatus"))
        request_memory = _as_float(record.get("RequestMemory"))
        memory_usage = _as_float(record.get("MemoryUsage") or record.get("ResidentSetSize_RAW"))

        normalized.append(
            {
                "source": source,
                "cluster_id": cluster_id,
                "proc_id": proc_id,
                "job_id": _job_id(cluster_id, proc_id),
                "task_name": _task_name(record),
                "status": JOB_STATUS_NAMES.get(job_status, f"unknown_{job_status}" if job_status is not None else "unknown"),
                "status_code": job_status,
                "owner": record.get("Owner", ""),
                "runtime_sec": _runtime_seconds(record),
                "request_memory_mb": request_memory,
                "memory_usage_mb": memory_usage,
                "exit_code": record.get("ExitCode", ""),
                "hold_reason": record.get("HoldReason", ""),
                "submit_host": record.get("SubmitHost", ""),
            }
        )
    return normalized


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    failed = 0
    long_running = 0
    memory_issues = 0

    for record in records:
        status = str(record.get("status") or "unknown")
        source = str(record.get("source") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        source_counts[source] = source_counts.get(source, 0) + 1

        exit_code = record.get("exit_code")
        if exit_code not in ("", None, 0):
            failed += 1
        if _as_float(record.get("runtime_sec")) and float(record["runtime_sec"]) > 24 * 3600:
            long_running += 1
        if _memory_exceeds_request(record):
            memory_issues += 1

    return {
        "jobs": len(records),
        "status_counts": status_counts,
        "source_counts": source_counts,
        "failed_jobs": failed,
        "long_running_jobs": long_running,
        "memory_issues": memory_issues,
    }


def _task_name(record: dict[str, Any]) -> str:
    for key in ("JobBatchName", "Cmd", "Args", "Iwd"):
        value = record.get(key)
        if value:
            return str(value)
    return ""


def _runtime_seconds(record: dict[str, Any]) -> int | None:
    remote_wall_clock = _as_float(record.get("RemoteWallClockTime"))
    if remote_wall_clock is not None:
        return round(remote_wall_clock)

    entered_current_status = _as_float(record.get("EnteredCurrentStatus"))
    if entered_current_status is None:
        return None
    return max(0, round(datetime.now(timezone.utc).timestamp() - entered_current_status))


def _memory_exceeds_request(record: dict[str, Any]) -> bool:
    used = _as_float(record.get("memory_usage_mb"))
    requested = _as_float(record.get("request_memory_mb"))
    return used is not None and requested is not None and used > requested


def _job_id(cluster_id: object, proc_id: object) -> str:
    if cluster_id in ("", None):
        return ""
    if proc_id in ("", None):
        return str(cluster_id)
    return f"{cluster_id}.{proc_id}"


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
