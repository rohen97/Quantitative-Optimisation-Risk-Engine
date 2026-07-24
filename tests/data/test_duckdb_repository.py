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
