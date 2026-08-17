from __future__ import annotations

from dataclasses import dataclass
import time

import pandas as pd

from src.data.repository.duckdb_repository import DuckDBRepository


PRICE_SUMMARY_DATASET = "prices_daily"


@dataclass(frozen=True)
class PriceSummaryStatus:
    fresh: bool
    source_row_count: int
    summary_row_count: int
    source_max_retrieved_at: pd.Timestamp | None
    refreshed_at: pd.Timestamp | None


def _timestamp(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def price_summary_status(repository: DuckDBRepository) -> PriceSummaryStatus:
    """Return whether the compact price summary exactly matches its source table."""
    try:
        source = repository.query(
            "SELECT COUNT(*) AS rows, MAX(retrieved_at) AS max_retrieved_at "
            "FROM prices_daily"
        ).iloc[0]
        state = repository.query(
            "SELECT * FROM model_input_summary_state WHERE dataset_name = ?",
            [PRICE_SUMMARY_DATASET],
        )
    except Exception:
        return PriceSummaryStatus(False, 0, 0, None, None)
    source_rows = int(source["rows"])
    source_max = _timestamp(source["max_retrieved_at"])
    if state.empty:
        return PriceSummaryStatus(False, source_rows, 0, source_max, None)
    row = state.iloc[0]
    recorded_max = _timestamp(row["source_max_retrieved_at"])
    fresh = (
        str(row["status"]) == "complete"
        and int(row["source_row_count"]) == source_rows
        and recorded_max == source_max
    )
    return PriceSummaryStatus(
        fresh=fresh,
        source_row_count=source_rows,
        summary_row_count=int(row["summary_row_count"]),
        source_max_retrieved_at=source_max,
        refreshed_at=_timestamp(row["refreshed_at"]),
    )


def refresh_price_summaries(repository: DuckDBRepository) -> dict[str, object]:
    """Materialise one compact row per security from the 100M+ row price table."""
    started = time.perf_counter()
    with repository.connection() as connection:
        connection.execute("SET preserve_insertion_order = false")
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("DELETE FROM security_price_summaries")
            connection.execute(
                """
                INSERT INTO security_price_summaries
                WITH source_ranked AS (
                    SELECT
                        security_id,
                        trade_date,
                        COALESCE(adjusted_close, close_price) AS close_price,
                        volume,
                        retrieved_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY security_id, trade_date
                            ORDER BY retrieved_at DESC, source DESC
                        ) AS source_row
                    FROM prices_daily
                    WHERE COALESCE(adjusted_close, close_price) IS NOT NULL
                ),
                daily AS (
                    SELECT
                        security_id,
                        trade_date,
                        close_price,
                        volume,
                        retrieved_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY security_id ORDER BY trade_date DESC
                        ) AS recency_row
                    FROM source_ranked
                    WHERE source_row = 1
                )
                SELECT
                    security_id,
                    COUNT(*) AS price_rows,
                    MAX(trade_date) AS latest_trade_date,
                    AVG(volume * close_price) FILTER (
                        WHERE recency_row <= 60 AND volume IS NOT NULL AND volume > 0
                    ) AS avg_daily_traded_value_local,
                    COUNT(*) FILTER (
                        WHERE recency_row <= 60 AND volume IS NOT NULL AND volume > 0
                    ) AS observed_volume_rows,
                    MAX(retrieved_at) AS latest_source_retrieved_at,
                    CURRENT_TIMESTAMP AS refreshed_at
                FROM daily
                GROUP BY security_id
                """
            )
            source = connection.execute(
                "SELECT COUNT(*) AS rows, MAX(retrieved_at) AS max_retrieved_at "
                "FROM prices_daily"
            ).fetchone()
            summary_rows = int(
                connection.execute("SELECT COUNT(*) FROM security_price_summaries").fetchone()[0]
            )
            connection.execute(
                "DELETE FROM model_input_summary_state WHERE dataset_name = ?",
                [PRICE_SUMMARY_DATASET],
            )
            connection.execute(
                """
                INSERT INTO model_input_summary_state
                VALUES (?, ?, ?, ?, 'complete', CURRENT_TIMESTAMP)
                """,
                [PRICE_SUMMARY_DATASET, int(source[0]), source[1], summary_rows],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    return {
        "dataset_name": PRICE_SUMMARY_DATASET,
        "source_row_count": int(source[0]),
        "summary_row_count": summary_rows,
        "source_max_retrieved_at": source[1],
        "runtime_seconds": time.perf_counter() - started,
    }
