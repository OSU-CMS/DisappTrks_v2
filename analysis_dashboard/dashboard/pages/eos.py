from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.config import SNAPSHOT_DIR
from dashboard.snapshots import read_snapshot_payload


EOS_SNAPSHOT_PATH = SNAPSHOT_DIR / "eos_latest.json"


def render_eos_page() -> None:
    st.title("EOS Outputs")
    st.caption(f"Snapshot: {EOS_SNAPSHOT_PATH}")

    payload = _load_snapshot(EOS_SNAPSHOT_PATH)
    if payload is None:
        st.info("No EOS snapshot found yet. Run the LPC snapshot sync to create eos_latest.json.")
        return

    metadata = payload.get("metadata", {})
    summary = payload.get("summary", {})
    roots = payload.get("roots", [])
    records = payload.get("records", [])
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(roots, list):
        roots = []
    if not isinstance(records, list):
        records = []

    _render_header(metadata)
    _render_summary(summary)
    _render_errors(summary)

    st.subheader("Configured Roots")
    if roots:
        st.dataframe(pd.DataFrame(roots), hide_index=True, use_container_width=True)
    else:
        st.info("No EOS roots were configured.")

    st.subheader("ROOT Files")
    if not records:
        st.info("No ROOT files were found under the configured EOS roots.")
        return

    df = pd.DataFrame(record for record in records if isinstance(record, dict))
    filtered = _render_filters(df)
    st.caption(f"Showing {len(filtered)} of {len(df)} ROOT files.")
    st.dataframe(
        filtered[["root", "top_level", "relative_path", "path", "url"]],
        hide_index=True,
        use_container_width=True,
    )


def _load_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_snapshot_payload(path)
    except (json.JSONDecodeError, ValueError) as error:
        st.error(f"Could not read EOS snapshot: {error}")
        return None


def _render_header(metadata: dict[str, Any]) -> None:
    cols = st.columns(4)
    cols[0].metric("Status", str(metadata.get("status") or "unknown"))
    cols[1].metric("Collected", str(metadata.get("collected_at") or "unknown"))
    cols[2].metric("Host", str(metadata.get("host") or "unknown"))
    cols[3].metric("User", str(metadata.get("username") or "unknown"))


def _render_summary(summary: dict[str, Any]) -> None:
    cols = st.columns(5)
    cols[0].metric("Configured Roots", int(summary.get("configured_roots") or 0))
    cols[1].metric("Available", int(summary.get("available_roots") or 0))
    cols[2].metric("Not Created", int(summary.get("not_created_roots") or 0))
    cols[3].metric("Failed", int(summary.get("failed_roots") or 0))
    cols[4].metric("ROOT Files", int(summary.get("root_files") or 0))


def _render_errors(summary: dict[str, Any]) -> None:
    errors = summary.get("errors", [])
    if isinstance(errors, list) and errors:
        st.warning("\n".join(str(error) for error in errors))


def _render_filters(df: pd.DataFrame) -> pd.DataFrame:
    cols = st.columns(3)
    roots = cols[0].multiselect("EOS Root", _unique_strings(df, "root"))
    top_levels = cols[1].multiselect("Top-Level Directory", _unique_strings(df, "top_level"))
    search = cols[2].text_input("Path Search")

    filtered = df
    if roots:
        filtered = filtered[filtered["root"].isin(roots)]
    if top_levels:
        filtered = filtered[filtered["top_level"].isin(top_levels)]
    if search:
        filtered = filtered[filtered["path"].astype(str).str.contains(search, case=False, regex=False)]
    return filtered


def _unique_strings(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    return sorted(str(value) for value in df[column].dropna().unique() if str(value))
