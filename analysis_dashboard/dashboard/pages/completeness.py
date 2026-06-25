from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.config import SNAPSHOT_DIR
from dashboard.snapshots import read_snapshot_payload


COMPLETENESS_SNAPSHOT_PATH = SNAPSHOT_DIR / "output_completeness_latest.json"


def render_completeness_page() -> None:
    st.title("Output Completeness")
    st.caption(f"Snapshot: {COMPLETENESS_SNAPSHOT_PATH}")

    payload = _load_snapshot(COMPLETENESS_SNAPSHOT_PATH)
    if payload is None:
        st.info("No completeness snapshot found yet. Run the LPC snapshot sync.")
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
        st.info("No mapped output tasks were collected.")
        return

    df = pd.DataFrame(record for record in records if isinstance(record, dict))
    _render_era_progress(df)

    st.subheader("Mapped Tasks")
    filtered = _render_filters(df)
    st.caption(f"Showing {len(filtered)} of {len(df)} mapped tasks.")
    st.dataframe(_display_columns(filtered), hide_index=True, use_container_width=True)

    selected_task = st.selectbox("Task Details", df["task_name"].astype(str).tolist())
    selected = df[df["task_name"].astype(str) == selected_task].iloc[0]
    detail_cols = st.columns(3)
    detail_cols[0].metric("Missing IDs", int(selected.get("missing_count") or 0))
    detail_cols[1].metric("Duplicate Files", int(selected.get("duplicate_files") or 0))
    detail_cols[2].metric("Attempts", len(selected.get("attempts") or []))
    st.json(
        {
            "eos_dir": selected.get("eos_dir"),
            "missing_job_ids": selected.get("missing_job_ids") or [],
            "unexpected_job_ids": selected.get("unexpected_job_ids") or [],
            "duplicate_job_ids": selected.get("duplicate_job_ids") or [],
            "attempts": selected.get("attempts") or [],
            "ignored_attempts": selected.get("ignored_attempts") or [],
            "unparsed_files": selected.get("unparsed_files") or [],
            "error": selected.get("error") or "",
        }
    )


def _load_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_snapshot_payload(path)
    except (json.JSONDecodeError, ValueError) as error:
        st.error(f"Could not read output completeness snapshot: {error}")
        return None


def _render_header(metadata: dict[str, Any]) -> None:
    cols = st.columns(4)
    cols[0].metric("Status", str(metadata.get("status") or "unknown"))
    cols[1].metric("Collected", str(metadata.get("collected_at") or "unknown"))
    cols[2].metric("Host", str(metadata.get("host") or "unknown"))
    cols[3].metric("User", str(metadata.get("username") or "unknown"))


def _render_summary(summary: dict[str, Any]) -> None:
    cols = st.columns(6)
    cols[0].metric("Mapped Tasks", int(summary.get("mapped_tasks") or 0))
    cols[1].metric("Complete", int(summary.get("complete_tasks") or 0))
    cols[2].metric("Incomplete", int(summary.get("incomplete_tasks") or 0))
    cols[3].metric("Missing Outputs", int(summary.get("missing_outputs") or 0))
    cols[4].metric("Duplicate Files", int(summary.get("duplicate_files") or 0))
    cols[5].metric("Unknown/Error", int(summary.get("unknown_tasks") or 0) + int(summary.get("error_tasks") or 0))


def _render_errors(summary: dict[str, Any]) -> None:
    errors = summary.get("errors", [])
    if isinstance(errors, list) and errors:
        st.warning("\n".join(str(error) for error in errors))


def _render_era_progress(df: pd.DataFrame) -> None:
    st.subheader("Data Era Progress")
    era_progress = _progress_by_era(df)
    if era_progress.empty:
        st.info("No data eras could be identified from the mapped task names.")
        return

    st.dataframe(
        era_progress[
            [
                "era",
                "status",
                "progress",
                "matched_outputs",
                "expected_jobs",
                "tasks",
                "awaiting_job_counts",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )

    for row in era_progress.itertuples(index=False):
        label = (
            f"{row.era}: {row.progress}% - {str(row.status).replace('_', ' ')} "
            f"({row.matched_outputs}/{row.expected_jobs} outputs)"
        )
        if row.awaiting_job_counts:
            label += f", {row.awaiting_job_counts} task(s) awaiting CRAB counts"
        st.progress(int(row.progress), text=label)


def _progress_by_era(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    prepared = df.copy()
    prepared["data_era"] = prepared["task_name"].astype(str).map(_data_era)
    prepared = prepared[prepared["data_era"] != ""]

    for era, group in prepared.groupby("data_era", sort=True):
        expected = pd.to_numeric(group["expected_jobs"], errors="coerce").fillna(0).astype(int)
        unique = pd.to_numeric(group["unique_outputs"], errors="coerce").fillna(0).astype(int)
        known = expected > 0
        expected_jobs = int(expected[known].sum())
        matched_outputs = int(pd.concat([expected[known], unique[known]], axis=1).min(axis=1).sum())
        awaiting_job_counts = int((~known).sum())
        progress = (100 * matched_outputs // expected_jobs) if expected_jobs else 0
        if awaiting_job_counts and progress == 100:
            progress = 99

        if progress == 100 and awaiting_job_counts == 0:
            status = "complete"
        elif matched_outputs > 0 or awaiting_job_counts < len(group):
            status = "in_progress"
        else:
            status = "not_started"

        rows.append(
            {
                "era": era,
                "status": status,
                "progress": progress,
                "matched_outputs": matched_outputs,
                "expected_jobs": expected_jobs,
                "tasks": len(group),
                "awaiting_job_counts": awaiting_job_counts,
            }
        )

    return pd.DataFrame(rows)


def _data_era(task_name: str) -> str:
    parts = task_name.split("_")
    if len(parts) < 2 or not parts[0].isdigit():
        return ""
    return f"{parts[0]}{parts[1]}"


def _render_filters(df: pd.DataFrame) -> pd.DataFrame:
    cols = st.columns(4)
    results = cols[0].multiselect("Result", _unique_strings(df, "result"))
    sources = cols[1].multiselect("Source", _unique_strings(df, "source"))
    groups = cols[2].multiselect("Group", _unique_strings(df, "group"))
    crab_failures_only = cols[3].checkbox("CRAB failures with complete output")

    filtered = df
    if results:
        filtered = filtered[filtered["result"].isin(results)]
    if sources:
        filtered = filtered[filtered["source"].isin(sources)]
    if groups:
        filtered = filtered[filtered["group"].isin(groups)]
    if crab_failures_only:
        filtered = filtered[
            (pd.to_numeric(filtered["crab_failed_jobs"], errors="coerce").fillna(0) > 0)
            & (filtered["result"] == "complete")
        ]
    return filtered


def _display_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "task_name",
        "source",
        "group",
        "expected_jobs",
        "observed_files",
        "unique_outputs",
        "missing_count",
        "duplicate_files",
        "crab_failed_jobs",
        "result",
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
