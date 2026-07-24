from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "sql" / "migrations"


def duckdb_schema() -> str:
    """Return the canonical DuckDB-compatible DDL used by the data foundation."""
    return "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS_DIR.glob("*.sql")))


def sqlite_schema() -> str:
    """Compatibility wrapper for older local DB callers."""
    return duckdb_schema()


TABLES: dict[str, str] = {
    path.stem: path.read_text(encoding="utf-8")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
}
