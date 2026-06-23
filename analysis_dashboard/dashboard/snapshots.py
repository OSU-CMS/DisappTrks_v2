from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dashboard.config import SNAPSHOT_DIR
from dashboard.db import execute, fetch_all


@dataclass(frozen=True)
class SnapshotMetadata:
    path: Path
    source_type: str
    label: str
    collected_at: str
    host: str
    username: str
    status: str
    summary: dict[str, Any]
    error: str = ""


def discover_snapshot_files() -> list[Path]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(SNAPSHOT_DIR.glob("*.json"))


def read_snapshot_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("Snapshot JSON must contain an object at the top level.")
    return payload


def read_snapshot_metadata(path: Path) -> SnapshotMetadata:
    try:
        payload = read_snapshot_payload(path)
    except (json.JSONDecodeError, ValueError) as error:
        return _invalid_metadata(path, f"Invalid JSON: {error}")

    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    source_type = str(metadata.get("source_type") or payload.get("source_type") or "unknown")
    label = str(metadata.get("label") or payload.get("label") or path.stem)
    collected_at = str(metadata.get("collected_at") or payload.get("collected_at") or "")
    host = str(metadata.get("host") or payload.get("host") or "")
    username = str(metadata.get("username") or payload.get("username") or "")
    status = str(metadata.get("status") or payload.get("status") or "available")

    return SnapshotMetadata(
        path=path,
        source_type=source_type,
        label=label,
        collected_at=collected_at,
        host=host,
        username=username,
        status=status,
        summary=summary,
    )


def import_snapshot_metadata(snapshot: SnapshotMetadata) -> None:
    execute(
        """
        INSERT INTO snapshot_sources
          (source_type, label, path, collected_at, host, username, status, summary_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
          source_type = excluded.source_type,
          label = excluded.label,
          collected_at = excluded.collected_at,
          imported_at = CURRENT_TIMESTAMP,
          host = excluded.host,
          username = excluded.username,
          status = excluded.status,
          summary_json = excluded.summary_json
        """,
        (
            snapshot.source_type,
            snapshot.label,
            str(snapshot.path),
            snapshot.collected_at,
            snapshot.host,
            snapshot.username,
            snapshot.status,
            json.dumps(snapshot.summary, sort_keys=True),
        ),
    )


def imported_snapshots() -> list[dict[str, object]]:
    rows = fetch_all(
        """
        SELECT source_type, label, path, collected_at, imported_at, host, username, status, summary_json
        FROM snapshot_sources
        ORDER BY imported_at DESC, source_type, label
        """
    )
    return [dict(row) for row in rows]


def _invalid_metadata(path: Path, error: str) -> SnapshotMetadata:
    return SnapshotMetadata(
        path=path,
        source_type="invalid",
        label=path.stem,
        collected_at="",
        host="",
        username="",
        status="failed",
        summary={},
        error=error,
    )
