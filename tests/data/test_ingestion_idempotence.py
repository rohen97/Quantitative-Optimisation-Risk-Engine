import pandas as pd

from src.data.ingestion.prices import ingest_prices
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS


def test_price_ingestion_is_idempotent_by_primary_key(tmp_path):
    repo = DuckDBRepository(tmp_path / "idempotent.duckdb")
    repo.execute_migrations("sql/migrations")
    raw = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "ticker": ["AAA", "AAA"], "close": [100.0, 101.0]})
    frame = ingest_prices(raw, "mock")
    repo.write_table("prices_daily", frame, SCHEMAS["prices_daily"].primary_key)
    repo.write_table("prices_daily", frame, SCHEMAS["prices_daily"].primary_key)
    count = repo.query("SELECT COUNT(*) AS n FROM prices_daily").loc[0, "n"]
    repo.close()
    assert count == 2
