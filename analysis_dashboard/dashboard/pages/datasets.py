from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.config import ERAS
from dashboard.db import execute, fetch_all


DATASET_STATUSES = [
    "not_started",
    "requested",
    "available",
    "processing",
    "complete",
    "missing",
    "deprecated",
]

VALIDATION_STATUSES = [
    "not_started",
    "pending",
    "valid",
    "warning",
    "failed",
]


def render_datasets_page() -> None:
    st.title("Dataset Tracking")

    with st.expander("Add Dataset", expanded=True):
        with st.form("add_dataset"):
            era = st.selectbox("Era", [""] + ERAS)
            primary_dataset = st.text_input("Primary Dataset", placeholder="Muon, EGamma, JetMET, MET, ...")
            mini_aod_dataset = st.text_area("MiniAOD Dataset", height=80)
            ntuple_path = st.text_input("Ntuple Location", placeholder="/store/user/... or root://...")
            status = st.selectbox("Status", DATASET_STATUSES)
            validation_status = st.selectbox("Validation Status", VALIDATION_STATUSES)
            submitted = st.form_submit_button("Add Dataset")

        if submitted:
            if not era:
                st.error("Era is required.")
            elif not primary_dataset.strip():
                st.error("Primary Dataset is required.")
            else:
                execute(
                    """
                    INSERT INTO datasets
                      (era, primary_dataset, miniAOD_dataset, ntuple_path, status, validation_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        era,
                        primary_dataset.strip(),
                        mini_aod_dataset.strip(),
                        ntuple_path.strip(),
                        status,
                        validation_status,
                    ),
                )
                st.success(f"Added dataset: {primary_dataset}")
                st.rerun()

    datasets = fetch_all("SELECT * FROM datasets ORDER BY era, primary_dataset, miniAOD_dataset")

    st.subheader("Current Datasets")
    if not datasets:
        st.info("No datasets recorded yet.")
        return

    rows = [dict(dataset) for dataset in datasets]
    df = pd.DataFrame(rows)
    filtered_df = _render_filters(df)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Datasets", len(filtered_df))
    metric_cols[1].metric("Complete", int((filtered_df["status"] == "complete").sum()))
    metric_cols[2].metric("Validated", int((filtered_df["validation_status"] == "valid").sum()))
    metric_cols[3].metric("Needs Attention", _needs_attention_count(filtered_df))

    st.dataframe(
        filtered_df[
            [
                "id",
                "era",
                "primary_dataset",
                "miniAOD_dataset",
                "ntuple_path",
                "status",
                "validation_status",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Update Dataset")
    dataset_ids = [int(dataset["id"]) for dataset in datasets]
    selected_id = st.selectbox("Dataset ID", dataset_ids)
    selected = next(dataset for dataset in datasets if int(dataset["id"]) == selected_id)

    with st.form("update_dataset"):
        status = st.selectbox(
            "Status",
            DATASET_STATUSES,
            index=_option_index(DATASET_STATUSES, selected["status"]),
        )
        validation_status = st.selectbox(
            "Validation Status",
            VALIDATION_STATUSES,
            index=_option_index(VALIDATION_STATUSES, selected["validation_status"]),
        )
        ntuple_path = st.text_input("Ntuple Location", value=selected["ntuple_path"] or "")
        submitted = st.form_submit_button("Update Dataset")

    if submitted:
        execute(
            """
            UPDATE datasets
            SET status = ?, validation_status = ?, ntuple_path = ?
            WHERE id = ?
            """,
            (status, validation_status, ntuple_path.strip(), selected_id),
        )
        st.success(f"Updated dataset {selected_id}")
        st.rerun()


def _render_filters(df: pd.DataFrame) -> pd.DataFrame:
    filter_cols = st.columns(3)
    eras = filter_cols[0].multiselect("Era Filter", ERAS)
    statuses = filter_cols[1].multiselect("Status Filter", DATASET_STATUSES)
    validation_statuses = filter_cols[2].multiselect("Validation Filter", VALIDATION_STATUSES)

    filtered = df
    if eras:
        filtered = filtered[filtered["era"].isin(eras)]
    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]
    if validation_statuses:
        filtered = filtered[filtered["validation_status"].isin(validation_statuses)]

    return filtered


def _needs_attention_count(df: pd.DataFrame) -> int:
    statuses = df["status"].isin(["missing", "deprecated"])
    validations = df["validation_status"].isin(["warning", "failed"])
    return int((statuses | validations).sum())


def _option_index(options: list[str], value: object) -> int:
    text = str(value or "")
    return options.index(text) if text in options else 0
