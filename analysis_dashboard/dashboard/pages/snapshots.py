from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from dashboard.config import SNAPSHOT_DIR
from dashboard.snapshots import (
    discover_snapshot_files,
    import_snapshot_metadata,
    imported_snapshots,
    read_snapshot_metadata,
)


def render_snapshots_page() -> None:
    st.title("Data Sources")
    st.caption(f"Snapshot directory: {SNAPSHOT_DIR}")

    snapshot_paths = discover_snapshot_files()
    st.subheader("Available Snapshot Files")

    if not snapshot_paths:
        st.info("No JSON snapshots found yet.")
    else:
        snapshots = [read_snapshot_metadata(path) for path in snapshot_paths]
        available_df = pd.DataFrame(
            [
                {
                    "file": snapshot.path.name,
                    "source_type": snapshot.source_type,
                    "label": snapshot.label,
                    "collected_at": snapshot.collected_at,
                    "host": snapshot.host,
                    "username": snapshot.username,
                    "status": snapshot.status,
                    "error": snapshot.error,
                }
                for snapshot in snapshots
            ]
        )
        st.dataframe(available_df, hide_index=True, use_container_width=True)

        valid_snapshots = [snapshot for snapshot in snapshots if not snapshot.error]
        if st.button("Import Snapshot Metadata", disabled=not valid_snapshots):
            for snapshot in valid_snapshots:
                import_snapshot_metadata(snapshot)
            st.success(f"Imported metadata for {len(valid_snapshots)} snapshot files.")
            st.rerun()

        invalid_snapshots = [snapshot for snapshot in snapshots if snapshot.error]
        if invalid_snapshots:
            st.warning("Some snapshot files could not be imported because their metadata is invalid.")

    st.subheader("Imported Snapshots")
    imported = imported_snapshots()
    if not imported:
        st.info("No snapshot metadata has been imported yet.")
        return

    imported_df = pd.DataFrame(imported)
    st.dataframe(
        imported_df[
            [
                "source_type",
                "label",
                "collected_at",
                "imported_at",
                "host",
                "username",
                "status",
                "path",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )

    selected = st.selectbox("Snapshot Summary", imported_df["label"].tolist())
    row = imported_df[imported_df["label"] == selected].iloc[0]
    summary = _parse_summary(row["summary_json"])
    if summary:
        st.json(summary)
    else:
        st.info("This snapshot has no summary metadata.")


def _parse_summary(value: object) -> dict[str, object]:
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
