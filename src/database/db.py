from __future__ import annotations

import sqlite3
from pathlib import Path

from src.database.schema import sqlite_schema


def connect(path: str | Path = "data/interim/wolf_quant.sqlite") -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(sqlite_schema())
    return conn
