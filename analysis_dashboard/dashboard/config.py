from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
APP_DIR = PACKAGE_DIR.parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "dashboard.sqlite"
SCHEMA_PATH = PACKAGE_DIR / "schema.sql"
SNAPSHOT_DIR = APP_DIR / "snapshots"

ERAS = ["2022", "2023", "2024", "2025"]
BACKGROUNDS = ["electron", "muon", "tau", "fake_track"]
SIGNAL_CATEGORIES = ["NLayers4", "NLayers5", "NLayers6plus"]
LEPTON_BACKGROUND_COMPONENTS = [
    "Nctrl",
    "Pveto",
    "Poffline",
    "Ptrigger",
    "closure",
    "final_estimate",
]
VALIDATION_TASKS = [
    "fiducial_maps",
    "pveto_tables",
    "root_output_validation",
    "plot_review",
    "analysis_note_documentation",
]

TASK_STATUSES = [
    "not_started",
    "in_progress",
    "waiting",
    "review",
    "complete",
    "blocked",
]

TASK_PRIORITIES = ["low", "medium", "high", "critical"]

BACKGROUND_COMPONENT_WEIGHTS = {
    "Nctrl": 20,
    "Pveto": 30,
    "Poffline": 20,
    "Ptrigger": 20,
    "closure": 10,
}
