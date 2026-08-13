import pandas as pd

from src.data.ingestion.prices import ingest_prices
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS


def test_duckdb_repository_migrates_and_upserts(tmp_path):
    repo = DuckDBRepository(tmp_path / "test.duckdb")
    repo.execute_migrations("sql/migrations")
    repo.execute_views("sql/views")
    frame = ingest_prices(pd.DataFrame({"date": ["2026-01-01"], "ticker": ["AAA"], "close": [100.0], "return": [0.0]}))
    repo.write_table("prices_daily", frame, SCHEMAS["prices_daily"].primary_key)
    repo.write_table("prices_daily", frame, SCHEMAS["prices_daily"].primary_key)
    stored = repo.query("SELECT * FROM point_in_time_prices")
    repo.close()
    assert len(stored) == 1
    assert stored.loc[0, "ticker"] == "AAA"


def test_duckdb_repository_applies_resource_limits(tmp_path):
    repo = DuckDBRepository(
        tmp_path / "bounded.duckdb",
        threads=2,
        memory_limit="512MB",
    )
    settings = repo.query(
        "SELECT current_setting('threads') AS threads, "
        "current_setting('memory_limit') AS memory_limit"
    ).iloc[0]
    assert int(settings["threads"]) == 2
    assert "MiB" in str(settings["memory_limit"])
