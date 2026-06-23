from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from dashboard.config import DATA_DIR, DB_PATH, SCHEMA_PATH


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text()
    with get_connection() as conn:
        conn.executescript(schema)


def fetch_all(query: str, params: Iterable[object] = ()) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(query, tuple(params)).fetchall()


def execute(query: str, params: Iterable[object] = ()) -> None:
    with get_connection() as conn:
        conn.execute(query, tuple(params))


def database_path() -> Path:
    return DB_PATH
