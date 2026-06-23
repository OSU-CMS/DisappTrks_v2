from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.config import SNAPSHOT_DIR
from dashboard.snapshots import read_snapshot_payload


CONDOR_SNAPSHOT_PATH = SNAPSHOT_DIR / "condor_latest.json"


def render_condor_page() -> None:
    st.title("HTCondor Monitoring")
    st.caption(f"Snapshot: {CONDOR_SNAPSHOT_PATH}")

    payload = _load_condor_snapshot(CONDOR_SNAPSHOT_PATH)
    if payload is None:
        st.info("No Condor snapshot found yet. Run the LPC snapshot sync to create condor_latest.json.")
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

    _render_snapshot_header(metadata)
    _render_summary(summary)

    if errors := summary.get("errors"):
        if isinstance(errors, list) and errors:
            st.warning("\n".join(str(error) for error in errors))

    st.subheader("Jobs")
    if not records:
        st.info("No Condor jobs were recorded in this snapshot.")
        return

    df = pd.DataFrame([record for record in records if isinstance(record, dict)])
    if df.empty:
        st.info("No displayable Condor job records were found.")
        return

    filtered_df = _render_filters(df)
    st.dataframe(_display_columns(filtered_df), hide_index=True, use_container_width=True)

    st.subheader("Status Counts")
    status_counts = summary.get("status_counts", {})
    if isinstance(status_counts, dict) and status_counts:
        st.bar_chart(pd.DataFrame(status_counts.items(), columns=["status", "jobs"]).set_index("status"))
    else:
        st.info("No status counts available.")


def _load_condor_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_snapshot_payload(path)
    except (json.JSONDecodeError, ValueError) as error:
        st.error(f"Could not read Condor snapshot: {error}")
        return None


def _render_snapshot_header(metadata: dict[str, Any]) -> None:
    cols = st.columns(4)
    cols[0].metric("Status", str(metadata.get("status") or "unknown"))
    cols[1].metric("Collected", str(metadata.get("collected_at") or "unknown"))
    cols[2].metric("Host", str(metadata.get("host") or "unknown"))
    cols[3].metric("User", str(metadata.get("username") or "unknown"))


def _render_summary(summary: dict[str, Any]) -> None:
    cols = st.columns(5)
    cols[0].metric("Jobs", int(summary.get("jobs") or 0))
    cols[1].metric("Failed", int(summary.get("failed_jobs") or 0))
    cols[2].metric("Long Running", int(summary.get("long_running_jobs") or 0))
    cols[3].metric("Memory Issues", int(summary.get("memory_issues") or 0))
    cols[4].metric("Queue Records", _source_count(summary, "queue"))


def _render_filters(df: pd.DataFrame) -> pd.DataFrame:
    filter_cols = st.columns(4)
    sources = filter_cols[0].multiselect("Source", sorted(_unique_strings(df, "source")))
    statuses = filter_cols[1].multiselect("Status", sorted(_unique_strings(df, "status")))
    owners = filter_cols[2].multiselect("Owner", sorted(_unique_strings(df, "owner")))
    failed_only = filter_cols[3].checkbox("Failed only")

    filtered = df
    if sources:
        filtered = filtered[filtered["source"].isin(sources)]
    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]
    if owners:
        filtered = filtered[filtered["owner"].isin(owners)]
    if failed_only and "exit_code" in filtered.columns:
        filtered = filtered[~filtered["exit_code"].isin(["", None, 0])]

    return filtered


def _display_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "source",
        "job_id",
        "task_name",
        "status",
        "owner",
        "runtime_sec",
        "request_memory_mb",
        "memory_usage_mb",
        "exit_code",
        "hold_reason",
    ]
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df[columns]


def _source_count(summary: dict[str, Any], source: str) -> int:
    source_counts = summary.get("source_counts", {})
    if not isinstance(source_counts, dict):
        return 0
    return int(source_counts.get(source) or 0)


def _unique_strings(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    return [str(value) for value in df[column].dropna().unique() if str(value)]
