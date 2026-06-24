from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.config import ERAS, TASK_PRIORITIES, TASK_STATUSES
from dashboard.db import execute, fetch_all
from dashboard.production_tasks import sync_production_tasks
from dashboard.seed import seed_standard_tasks


def render_tasks_page() -> None:
    st.title("Analysis Tasks")

    seed_cols = st.columns([1, 1, 3])
    if seed_cols[0].button("Seed Run 3 Tasks"):
        inserted, skipped = seed_standard_tasks()
        st.success(f"Seeded {inserted} tasks. Skipped {skipped} existing tasks.")
        st.rerun()
    if seed_cols[1].button("Sync Production Tasks"):
        result = sync_production_tasks()
        st.success(
            f"Synced {result['total']} production tasks: "
            f"{result['inserted']} added, {result['updated']} updated, "
            f"{result['complete']} complete."
        )
        st.rerun()
    seed_cols[2].caption(
        "Creates the standard era/background/component tasks from the dashboard roadmap. "
        "Production task status is derived from the latest CRAB-to-EOS completeness snapshot."
    )

    with st.expander("Add Task", expanded=True):
        with st.form("add_task"):
            name = st.text_input("Task Name")
            category = st.text_input("Category", placeholder="muon, electron, systematics, plots, ...")
            era = st.selectbox("Era", [""] + ERAS)
            owner = st.text_input("Owner")
            priority = st.selectbox("Priority", TASK_PRIORITIES, index=1)
            status = st.selectbox("Status", TASK_STATUSES)
            progress = st.slider("Progress", 0, 100, 0)
            depends_on = st.text_input("Dependencies")
            submitted = st.form_submit_button("Add Task")

        if submitted:
            if not name.strip():
                st.error("Task Name is required.")
            else:
                execute(
                    """
                    INSERT INTO tasks
                      (name, category, era, owner, priority, status, progress, depends_on)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, category, era, owner, priority, status, progress, depends_on),
                )
                st.success(f"Added task: {name}")
                st.rerun()

    tasks = fetch_all("SELECT * FROM tasks ORDER BY era, category, priority, name")

    st.subheader("Current Tasks")
    if not tasks:
        st.info("No tasks recorded yet.")
        return

    rows = [dict(task) for task in tasks]
    df = pd.DataFrame(rows)
    st.dataframe(
        df[["id", "name", "category", "era", "owner", "priority", "status", "progress", "depends_on", "updated_at"]],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Update Task")
    task_ids = [int(task["id"]) for task in tasks]
    selected_id = st.selectbox("Task ID", task_ids)
    selected = next(task for task in tasks if int(task["id"]) == selected_id)

    with st.form("update_task"):
        status = st.selectbox(
            "Status",
            TASK_STATUSES,
            index=TASK_STATUSES.index(selected["status"]) if selected["status"] in TASK_STATUSES else 0,
        )
        progress = st.slider("Progress", 0, 100, int(selected["progress"] or 0))
        owner = st.text_input("Owner", value=selected["owner"] or "")
        submitted = st.form_submit_button("Update Task")

    if submitted:
        execute(
            "UPDATE tasks SET status = ?, progress = ?, owner = ? WHERE id = ?",
            (status, progress, owner, selected_id),
        )
        st.success(f"Updated task {selected_id}")
        st.rerun()
