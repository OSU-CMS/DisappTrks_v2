from __future__ import annotations

from dataclasses import dataclass

from dashboard.config import BACKGROUNDS, ERAS, LEPTON_BACKGROUND_COMPONENTS, VALIDATION_TASKS
from dashboard.db import get_connection


@dataclass(frozen=True)
class SeedTask:
    name: str
    category: str
    era: str
    priority: str = "medium"
    status: str = "not_started"
    progress: int = 0
    depends_on: str = ""


def standard_analysis_tasks() -> list[SeedTask]:
    tasks: list[SeedTask] = []

    for era in ERAS:
        for background in BACKGROUNDS:
            for component in LEPTON_BACKGROUND_COMPONENTS:
                priority = "high" if component in {"Pveto", "final_estimate"} else "medium"
                dependencies = _component_dependencies(background, component, era)
                tasks.append(
                    SeedTask(
                        name=f"{background} {component} {era}",
                        category=f"background:{background}",
                        era=era,
                        priority=priority,
                        depends_on=dependencies,
                    )
                )

        for task_name in VALIDATION_TASKS:
            tasks.append(
                SeedTask(
                    name=f"{task_name} {era}",
                    category="validation",
                    era=era,
                    priority="high" if task_name in {"fiducial_maps", "root_output_validation"} else "medium",
                )
            )

        tasks.append(
            SeedTask(
                name=f"unblinding readiness {era}",
                category="unblinding",
                era=era,
                priority="critical",
                depends_on=", ".join(
                    [
                        f"electron final_estimate {era}",
                        f"muon final_estimate {era}",
                        f"tau final_estimate {era}",
                        f"fake_track final_estimate {era}",
                        f"analysis_note_documentation {era}",
                    ]
                ),
            )
        )

    return tasks


def seed_standard_tasks() -> tuple[int, int]:
    tasks = standard_analysis_tasks()
    inserted = 0
    skipped = 0

    with get_connection() as conn:
        for task in tasks:
            exists = conn.execute(
                """
                SELECT 1 FROM tasks
                WHERE name = ? AND category = ? AND era = ?
                LIMIT 1
                """,
                (task.name, task.category, task.era),
            ).fetchone()

            if exists:
                skipped += 1
                continue

            conn.execute(
                """
                INSERT INTO tasks
                  (name, category, era, priority, status, progress, depends_on)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.name,
                    task.category,
                    task.era,
                    task.priority,
                    task.status,
                    task.progress,
                    task.depends_on,
                ),
            )
            inserted += 1

    return inserted, skipped


def _component_dependencies(background: str, component: str, era: str) -> str:
    if component == "final_estimate":
        return ", ".join(
            [
                f"{background} Nctrl {era}",
                f"{background} Pveto {era}",
                f"{background} Poffline {era}",
                f"{background} Ptrigger {era}",
                f"{background} closure {era}",
            ]
        )
    if component == "closure":
        return ", ".join(
            [
                f"{background} Nctrl {era}",
                f"{background} Pveto {era}",
                f"{background} Poffline {era}",
                f"{background} Ptrigger {era}",
            ]
        )
    return ""
