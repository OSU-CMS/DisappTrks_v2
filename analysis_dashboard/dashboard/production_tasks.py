from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dashboard.config import SNAPSHOT_DIR
from dashboard.db import get_connection


COMPLETENESS_SNAPSHOT_PATH = SNAPSHOT_DIR / "output_completeness_latest.json"


def sync_production_tasks(path: Path = COMPLETENESS_SNAPSHOT_PATH) -> dict[str, int]:
    if not path.exists():
        return {"inserted": 0, "updated": 0, "complete": 0, "total": 0}

    payload = json.loads(path.read_text())
    records = payload.get("records", []) if isinstance(payload, dict) else []
    inserted = 0
    updated = 0
    complete = 0

    with get_connection() as conn:
        for record in records:
            if not isinstance(record, dict) or not record.get("task_name"):
                continue

            name = f"Process {record['task_name']}"
            category = f"production:{record.get('source') or 'unknown'}"
            era = _task_era(record)
            status, progress = _task_state(record)
            complete += status == "complete"

            existing = conn.execute(
                "SELECT id FROM tasks WHERE name = ? AND category = ? LIMIT 1",
                (name, category),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE tasks
                    SET era = ?, status = ?, progress = ?
                    WHERE id = ?
                    """,
                    (era, status, progress, int(existing["id"])),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO tasks
                      (name, category, era, priority, status, progress)
                    VALUES (?, ?, ?, 'high', ?, ?)
                    """,
                    (name, category, era, status, progress),
                )
                inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "complete": complete,
        "total": inserted + updated,
    }


def _task_state(record: dict[str, Any]) -> tuple[str, int]:
    result = str(record.get("result") or "unknown")
    expected = _as_int(record.get("expected_jobs"))
    unique = _as_int(record.get("unique_outputs"))

    if result in {"complete", "extra_files"}:
        return "complete", 100
    if result == "incomplete" and expected > 0:
        return "in_progress", min(99, round(100 * unique / expected))
    if result == "error":
        return "blocked", 0
    if result == "not_created":
        return "not_started", 0
    return "waiting", 0


def _task_era(record: dict[str, Any]) -> str:
    group = str(record.get("group") or "")
    return group.split("_", 1)[0]


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
