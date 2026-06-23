#!/usr/bin/env python3

from __future__ import annotations

import streamlit as st

from dashboard.db import initialize_database
from dashboard.pages.condor import render_condor_page
from dashboard.pages.datasets import render_datasets_page
from dashboard.pages.overview import render_overview_page
from dashboard.pages.snapshots import render_snapshots_page
from dashboard.pages.tasks import render_tasks_page


def main() -> None:
    st.set_page_config(
        page_title="DisappTrks Run 3 Dashboard",
        page_icon="",
        layout="wide",
    )

    initialize_database()

    st.sidebar.title("DisappTrks Run 3")
    page = st.sidebar.radio(
        "Page",
        [
            "Overview",
            "Analysis Tasks",
            "Dataset Tracking",
            "Data Sources",
            "HTCondor Monitoring",
        ],
    )

    if page == "Overview":
        render_overview_page()
    elif page == "Analysis Tasks":
        render_tasks_page()
    elif page == "Dataset Tracking":
        render_datasets_page()
    elif page == "Data Sources":
        render_snapshots_page()
    elif page == "HTCondor Monitoring":
        render_condor_page()


if __name__ == "__main__":
    main()
