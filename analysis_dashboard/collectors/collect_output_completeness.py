#!/usr/bin/env python3

from __future__ import annotations

import argparse
import getpass
import json
import platform
import re
import runpy
import shlex
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


JOB_FILE_PATTERN = re.compile(r"^.+_(\d+)\.root$")
TERMINAL_VERSION_PATTERN = re.compile(r"^(?P<base>.+)_v(?P<version>\d+)$")
ATTEMPT_TIMESTAMP_PATTERN = re.compile(r"^\d{6}_\d{6}$")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    collected_at = datetime.now(timezone.utc).astimezone()
    crab_records = _load_crab_records(args.crab_snapshot)
    mappings = _load_mappings(args.mapping_scripts)
    mappings.extend(_derive_mappings(crab_records, args.derived_prefixes))
    mappings = _latest_mappings(mappings)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    status = "ok"

    if shutil.which("xrdfs") is None:
        status = "skipped"
        errors.append("xrdfs is not available on PATH.")
    else:
        for mapping in mappings:
            record = _collect_mapping(args.endpoint, mapping, crab_records)
            records.append(record)
            if record["result"] == "error":
                errors.append(str(record["error"]))
                if status == "ok":
                    status = "warning"

    summary = _summarize(records)
    summary["errors"] = errors

    snapshot = {
        "metadata": {
            "source_type": "output_completeness",
            "label": f"CRAB output completeness {collected_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "collected_at": collected_at.isoformat(timespec="seconds"),
            "host": platform.node(),
            "username": getpass.getuser(),
            "status": status,
        },
        "summary": summary,
        "records": records,
    }

    output_path = output_dir / "output_completeness_latest.json"
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare CRAB job counts with exact EOS output directories.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "snapshots",
    )
    parser.add_argument(
        "--crab-snapshot",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "snapshots" / "crab_latest.json",
    )
    parser.add_argument(
        "--mapping-script",
        dest="mapping_scripts",
        type=Path,
        action="append",
        default=[],
        help="File-list script containing DATASETS and BASE definitions. May be repeated.",
    )
    parser.add_argument(
        "--endpoint",
        default="root://cmseosmgm01.fnal.gov",
        help="XRootD endpoint passed to xrdfs.",
    )
    parser.add_argument(
        "--derived-prefix",
        dest="derived_prefixes",
        action="append",
        default=[],
        help=(
            "Derive mappings as TASK_PREFIX[:EOS_PARENT_PREFIX]=/eos/base "
            "from CRAB task names. May be repeated."
        ),
    )
    return parser.parse_args()


def _load_crab_records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return {
        str(record.get("task_name")): record
        for record in records
        if isinstance(record, dict) and record.get("task_name")
    }


def _load_mappings(paths: list[Path]) -> list[dict[str, str]]:
    mappings: list[dict[str, str]] = []
    for path in paths:
        namespace = runpy.run_path(str(path))
        datasets = namespace.get("DATASETS")
        base = str(namespace.get("BASE") or "").rstrip("/")
        if not isinstance(datasets, dict) or not base:
            raise ValueError(f"{path} must define DATASETS and BASE.")

        source = _mapping_source(path)
        for group, values in datasets.items():
            if not isinstance(values, list):
                continue
            for value in values:
                dataset_path = str(value).strip("/")
                mappings.append(
                    {
                        "source": source,
                        "group": str(group),
                        "task_name": PurePosixPath(dataset_path).name,
                        "eos_dir": f"{base}/{dataset_path}",
                    }
                )
    return sorted(mappings, key=lambda item: (item["source"], item["group"], item["task_name"]))


def _derive_mappings(
    crab_records: dict[str, dict[str, Any]],
    specifications: list[str],
) -> list[dict[str, str]]:
    mappings: list[dict[str, str]] = []
    for specification in specifications:
        prefix_spec, separator, base = specification.partition("=")
        if not separator or not prefix_spec or not base:
            raise ValueError(
                f"Invalid derived prefix {specification!r}; "
                "expected TASK_PREFIX[:EOS_PARENT_PREFIX]=/eos/base."
            )
        task_prefix, parent_separator, eos_parent_prefix = prefix_spec.partition(":")
        if not parent_separator:
            eos_parent_prefix = task_prefix

        for task_name in crab_records:
            parts = task_name.split("_")
            task_dataset = next((part for part in parts if part.startswith(task_prefix)), "")
            if not task_dataset:
                continue
            suffix = task_dataset[len(task_prefix):]
            eos_parent = f"{eos_parent_prefix}{suffix}"
            group = "_".join(parts[:2]) if len(parts) >= 2 else ""
            mappings.append(
                {
                    "source": task_prefix.lower(),
                    "group": group,
                    "task_name": task_name,
                    "eos_dir": f"{base.rstrip('/')}/{eos_parent}/{task_name}",
                }
            )
    return mappings


def _latest_mappings(mappings: list[dict[str, str]]) -> list[dict[str, str]]:
    latest: dict[tuple[str, str], tuple[int, dict[str, str]]] = {}
    for mapping in mappings:
        task_name = mapping["task_name"]
        match = TERMINAL_VERSION_PATTERN.fullmatch(task_name)
        family = match.group("base") if match else task_name
        version = int(match.group("version")) if match else -1
        key = (mapping["source"], family)
        current = latest.get(key)
        if current is None or version > current[0]:
            latest[key] = (version, mapping)
    return sorted(
        (mapping for _version, mapping in latest.values()),
        key=lambda item: (item["source"], item["group"], item["task_name"]),
    )


def _collect_mapping(
    endpoint: str,
    mapping: dict[str, str],
    crab_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    task_name = mapping["task_name"]
    crab = crab_records.get(task_name, {})
    expected_jobs = _as_int(crab.get("total_jobs")) or 0
    list_result = _run_command(["xrdfs", endpoint, "ls", "-R", mapping["eos_dir"]])

    if not list_result["ok"]:
        detail = f"{list_result['stdout']}\n{list_result['stderr']}".lower()
        result = "not_created" if "no such file" in detail or "not found" in detail else "error"
        return _build_record(
            mapping,
            crab,
            expected_jobs,
            result=result,
            error="" if result == "not_created" else str(list_result["error"]),
        )

    root_paths = [
        line.strip()
        for line in str(list_result["stdout"]).splitlines()
        if line.strip().endswith(".root")
    ]
    root_paths, selected_attempt, ignored_attempts = _latest_attempt_paths(
        root_paths,
        mapping["eos_dir"],
    )
    job_ids: list[int] = []
    unparsed_files: list[str] = []
    for path in root_paths:
        match = JOB_FILE_PATTERN.match(PurePosixPath(path).name)
        if match:
            job_ids.append(int(match.group(1)))
        else:
            unparsed_files.append(path)

    counts = Counter(job_ids)
    unique_ids = set(counts)
    expected_ids = set(range(1, expected_jobs + 1)) if expected_jobs else set()
    missing_ids = sorted(expected_ids - unique_ids)
    unexpected_ids = sorted(unique_ids - expected_ids) if expected_ids else []
    duplicate_ids = sorted(job_id for job_id, count in counts.items() if count > 1)
    result = _completion_result(expected_jobs, missing_ids, unexpected_ids)

    return _build_record(
        mapping,
        crab,
        expected_jobs,
        result=result,
        observed_files=len(root_paths),
        unique_outputs=len(unique_ids),
        missing_job_ids=missing_ids,
        unexpected_job_ids=unexpected_ids,
        duplicate_job_ids=duplicate_ids,
        duplicate_files=sum(count - 1 for count in counts.values() if count > 1),
        unparsed_files=unparsed_files,
        attempts=[selected_attempt] if selected_attempt else [],
        ignored_attempts=ignored_attempts,
    )


def _build_record(
    mapping: dict[str, str],
    crab: dict[str, Any],
    expected_jobs: int,
    *,
    result: str,
    observed_files: int = 0,
    unique_outputs: int = 0,
    missing_job_ids: list[int] | None = None,
    unexpected_job_ids: list[int] | None = None,
    duplicate_job_ids: list[int] | None = None,
    duplicate_files: int = 0,
    unparsed_files: list[str] | None = None,
    attempts: list[str] | None = None,
    ignored_attempts: list[str] | None = None,
    error: str = "",
) -> dict[str, Any]:
    return {
        **mapping,
        "expected_jobs": expected_jobs,
        "observed_files": observed_files,
        "unique_outputs": unique_outputs,
        "missing_count": len(missing_job_ids or []),
        "missing_job_ids": missing_job_ids or [],
        "unexpected_count": len(unexpected_job_ids or []),
        "unexpected_job_ids": unexpected_job_ids or [],
        "duplicate_files": duplicate_files,
        "duplicate_job_ids": duplicate_job_ids or [],
        "unparsed_count": len(unparsed_files or []),
        "unparsed_files": unparsed_files or [],
        "attempts": attempts or [],
        "ignored_attempts": ignored_attempts or [],
        "crab_failed_jobs": _as_int(crab.get("failed_jobs")) or 0,
        "crab_complete": bool(crab.get("complete")),
        "crab_status_error": bool(crab.get("status_error")),
        "result": result,
        "error": error,
    }


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


def _attempt_from_path(path: str, eos_dir: str) -> str:
    prefix = eos_dir.rstrip("/") + "/"
    relative = path[len(prefix):] if path.startswith(prefix) else ""
    parts = PurePosixPath(relative).parts
    return parts[0] if len(parts) > 1 else ""


def _latest_attempt_paths(paths: list[str], eos_dir: str) -> tuple[list[str], str, list[str]]:
    timestamped: dict[str, list[str]] = {}
    unversioned: list[str] = []

    for path in paths:
        attempt = _attempt_from_path(path, eos_dir)
        if ATTEMPT_TIMESTAMP_PATTERN.fullmatch(attempt):
            timestamped.setdefault(attempt, []).append(path)
        else:
            unversioned.append(path)

    if not timestamped:
        return paths, "", []

    selected = max(timestamped)
    ignored = sorted(attempt for attempt in timestamped if attempt != selected)
    return timestamped[selected] + unversioned, selected, ignored


def _completion_result(expected_jobs: int, missing_ids: list[int], unexpected_ids: list[int]) -> str:
    if expected_jobs <= 0:
        return "unknown"
    if missing_ids:
        return "incomplete"
    if unexpected_ids:
        return "extra_files"
    return "complete"


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    result_counts = Counter(str(record["result"]) for record in records)
    return {
        "mapped_tasks": len(records),
        "complete_tasks": result_counts["complete"],
        "incomplete_tasks": result_counts["incomplete"],
        "extra_file_tasks": result_counts["extra_files"],
        "unknown_tasks": result_counts["unknown"],
        "not_created_tasks": result_counts["not_created"],
        "error_tasks": result_counts["error"],
        "expected_jobs": sum(int(record["expected_jobs"]) for record in records),
        "unique_outputs": sum(int(record["unique_outputs"]) for record in records),
        "missing_outputs": sum(int(record["missing_count"]) for record in records),
        "duplicate_files": sum(int(record["duplicate_files"]) for record in records),
    }


def _mapping_source(path: Path) -> str:
    name = path.name.lower()
    if "muon" in name:
        return "muon"
    if "electron" in name:
        return "electron"
    return path.stem


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
