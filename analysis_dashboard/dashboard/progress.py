from __future__ import annotations

from collections import defaultdict
from sqlite3 import Row


STATUS_PROGRESS = {
    "not_started": 0,
    "blocked": 0,
    "waiting": 25,
    "in_progress": 50,
    "review": 85,
    "complete": 100,
}


def task_progress(row: Row) -> int:
    explicit = int(row["progress"] or 0)
    if explicit > 0:
        return max(0, min(explicit, 100))
    return STATUS_PROGRESS.get(row["status"], 0)


def overall_progress(tasks: list[Row]) -> int:
    if not tasks:
        return 0
    return round(sum(task_progress(task) for task in tasks) / len(tasks))


def progress_by_era(tasks: list[Row]) -> dict[str, int]:
    grouped: dict[str, list[Row]] = defaultdict(list)
    for task in tasks:
        grouped[task["era"] or "unspecified"].append(task)
    return {era: overall_progress(era_tasks) for era, era_tasks in grouped.items()}


def blockers(tasks: list[Row]) -> list[Row]:
    return [task for task in tasks if task["status"] == "blocked"]
