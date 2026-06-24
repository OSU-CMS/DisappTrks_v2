from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.config import SNAPSHOT_DIR
from dashboard.snapshots import read_snapshot_payload


CRAB_SNAPSHOT_PATH = SNAPSHOT_DIR / "crab_latest.json"


def render_crab_page() -> None:
    st.title("CRAB Monitoring")
    st.caption(f"Snapshot: {CRAB_SNAPSHOT_PATH}")

    payload = _load_snapshot(CRAB_SNAPSHOT_PATH)
    if payload is None:
        st.info("No CRAB snapshot found yet. Run the LPC snapshot sync to create crab_latest.json.")
        return

    metadata = payload.get("metadata", {})
    summary = payload.get("summary", {})
    records = payload.get("records", [])
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(records, list):
        records = []

    _render_header(metadata)
    _render_summary(summary)
    _render_errors(summary)

    if not records:
        st.info("No CRAB task records were collected.")
        return

    df = pd.DataFrame(record for record in records if isinstance(record, dict))
    filtered = _render_filters(df)
    st.caption(f"Showing {len(filtered)} of {len(df)} tasks.")
    st.dataframe(_display_columns(filtered), hide_index=True, use_container_width=True)

    selected_task = st.selectbox("Status Output", df["task_name"].astype(str).tolist())
    selected = df[df["task_name"].astype(str) == selected_task].iloc[0]
    st.code(str(selected.get("status_output") or "No status output recorded."), language="text")


def _load_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_snapshot_payload(path)
    except (json.JSONDecodeError, ValueError) as error:
        st.error(f"Could not read CRAB snapshot: {error}")
        return None


def _render_header(metadata: dict[str, Any]) -> None:
    cols = st.columns(4)
    cols[0].metric("Status", str(metadata.get("status") or "unknown"))
    cols[1].metric("Collected", str(metadata.get("collected_at") or "unknown"))
    cols[2].metric("Host", str(metadata.get("host") or "unknown"))
    cols[3].metric("User", str(metadata.get("username") or "unknown"))


def _render_summary(summary: dict[str, Any]) -> None:
    cols = st.columns(6)
    cols[0].metric("Tasks", int(summary.get("checked_tasks") or 0))
    cols[1].metric("Complete", int(summary.get("completed_tasks") or 0))
    cols[2].metric("Unfinished", int(summary.get("unfinished_tasks") or 0))
    cols[3].metric("Failed Tasks", int(summary.get("tasks_with_failed_jobs") or 0))
    cols[4].metric("Failed Jobs", int(summary.get("failed_jobs") or 0))
    cols[5].metric("Status Errors", int(summary.get("status_error_tasks") or 0))


def _render_errors(summary: dict[str, Any]) -> None:
    errors = summary.get("errors", [])
    if isinstance(errors, list) and errors:
        st.warning("\n".join(str(error) for error in errors))


def _render_filters(df: pd.DataFrame) -> pd.DataFrame:
    cols = st.columns(4)
    view = cols[0].selectbox("View", ["All", "Complete", "Failed Jobs", "Status Errors", "Unfinished"])
    years = cols[1].multiselect("Year", _unique_strings(df, "year"))
    eras = cols[2].multiselect("Era", _unique_strings(df, "era"))
    statuses = cols[3].multiselect("Task Status", _unique_strings(df, "task_status"))

    filtered = df
    if view == "Complete":
        filtered = filtered[filtered["complete"].fillna(False).astype(bool)]
    elif view == "Failed Jobs":
        filtered = filtered[pd.to_numeric(filtered["failed_jobs"], errors="coerce").fillna(0) > 0]
    elif view == "Status Errors":
        filtered = filtered[filtered["status_error"].fillna(False).astype(bool)]
    elif view == "Unfinished":
        filtered = filtered[
            ~filtered["complete"].fillna(False).astype(bool)
            & ~filtered["status_error"].fillna(False).astype(bool)
        ]

    if years:
        filtered = filtered[filtered["year"].isin(years)]
    if eras:
        filtered = filtered[filtered["era"].isin(eras)]
    if statuses:
        filtered = filtered[filtered["task_status"].isin(statuses)]
    return filtered


def _display_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "task_name",
        "year",
        "era",
        "server_status",
        "task_status",
        "finished_jobs",
        "failed_jobs",
        "running_jobs",
        "transferring_jobs",
        "cooloff_jobs",
        "idle_jobs",
        "total_jobs",
        "complete",
        "status_error",
    ]
    display = df.copy()
    for column in columns:
        if column not in display.columns:
            display[column] = ""
    return display[columns]


def _unique_strings(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    return sorted(str(value) for value in df[column].dropna().unique() if str(value))
