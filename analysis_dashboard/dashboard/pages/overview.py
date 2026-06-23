from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.config import ERAS
from dashboard.db import database_path, fetch_all
from dashboard.progress import blockers, overall_progress, progress_by_era


def render_overview_page() -> None:
    st.title("Run 3 Disappearing Tracks Analysis")
    st.caption(f"Database: {database_path()}")

    tasks = fetch_all("SELECT * FROM tasks ORDER BY era, priority, name")
    overall = overall_progress(tasks)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Overall Progress", f"{overall}%")
    metric_cols[1].metric("Tasks", len(tasks))
    metric_cols[2].metric("Blocked", len(blockers(tasks)))
    metric_cols[3].metric("Complete", sum(1 for task in tasks if task["status"] == "complete"))

    st.subheader("Progress By Era")
    era_progress = progress_by_era(tasks)
    for era in ERAS:
        st.progress(era_progress.get(era, 0), text=f"{era}: {era_progress.get(era, 0)}%")

    blocked = blockers(tasks)
    st.subheader("Critical Blockers")
    if blocked:
        st.dataframe(
            pd.DataFrame([dict(task) for task in blocked]),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No blocked tasks recorded.")

    st.subheader("Recent Tasks")
    if tasks:
        rows = [dict(task) for task in tasks]
        st.dataframe(
            pd.DataFrame(rows)[
                ["name", "category", "era", "owner", "priority", "status", "progress", "updated_at"]
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No tasks yet. Add the first ones on the Analysis Tasks page.")
