from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.model_input_summaries import price_summary_status, refresh_price_summaries
from src.data.normalisers import normalise_prices
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS


def _write_prices(
    repository: DuckDBRepository,
    rows: list[dict[str, object]],
    retrieved_at: str,
    source: str = "test",
) -> None:
    frame = normalise_prices(
        pd.DataFrame(rows),
        source=source,
        retrieved_at=pd.Timestamp(retrieved_at),
    )
    repository.write_table(
        "prices_daily",
        frame,
        SCHEMAS["prices_daily"].primary_key,
    )


def test_price_summary_refresh_and_staleness(tmp_path: Path):
    repository = DuckDBRepository(tmp_path / "summary.duckdb", threads=1, memory_limit="512MB")
    repository.execute_migrations("sql/migrations")
    _write_prices(
        repository,
        [
            {"ticker": "AAA", "date": "2024-01-02", "close": 10.0, "volume": 100.0},
            {"ticker": "AAA", "date": "2024-01-03", "close": 11.0, "volume": 200.0},
            {"ticker": "BBB", "date": "2024-01-03", "close": 20.0, "volume": 50.0},
        ],
        "2024-01-04",
    )

    assert not price_summary_status(repository).fresh
    result = refresh_price_summaries(repository)
    assert result["source_row_count"] == 3
    assert result["summary_row_count"] == 2
    assert price_summary_status(repository).fresh

    summary = repository.query(
        "SELECT * FROM security_price_summaries ORDER BY security_id"
    )
    assert summary["price_rows"].tolist() == [2, 1]
    assert summary.loc[0, "latest_trade_date"] == pd.Timestamp("2024-01-03")
    assert summary.loc[0, "avg_daily_traded_value_local"] == 1_600.0

    _write_prices(
        repository,
        [{"ticker": "BBB", "date": "2024-01-04", "close": 21.0, "volume": 60.0}],
        "2024-01-05",
    )
    assert not price_summary_status(repository).fresh


def test_price_summary_uses_preferred_close_and_best_available_volume(
    tmp_path: Path,
):
    repository = DuckDBRepository(
        tmp_path / "provider_summary.duckdb",
        threads=1,
        memory_limit="512MB",
    )
    repository.execute_migrations("sql/migrations")
    _write_prices(
        repository,
        [
            {
                "ticker": "AAA",
                "date": "2024-01-02",
                "close": 10.0,
                "volume": None,
            }
        ],
        "2024-01-03",
        source="yfinance",
    )
    _write_prices(
        repository,
        [
            {
                "ticker": "AAA",
                "date": "2024-01-02",
                "close": 999.0,
                "volume": 300.0,
            }
        ],
        "2024-01-04",
        source="akshare",
    )

    refresh_price_summaries(repository)
    summary = repository.query(
        "SELECT * FROM security_price_summaries WHERE security_id = 'AAA'"
    ).iloc[0]

    assert summary["avg_daily_traded_value_local"] == 3_000.0
    assert summary["observed_volume_rows"] == 1
