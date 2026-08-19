from __future__ import annotations

from dataclasses import dataclass
import time

import pandas as pd

from src.data.repository.duckdb_repository import DuckDBRepository
from src.data_ingestion.provider_registry import load_data_source_registry


PRICE_SUMMARY_DATASET = "prices_daily"


def _price_source_priority_case() -> str:
    providers = load_data_source_registry().price_provider_order
    clauses = []
    for rank, source in enumerate(providers):
        escaped = str(source).replace("'", "''")
        clauses.append(f"WHEN source = '{escaped}' THEN {rank}")
    return "CASE " + " ".join(clauses) + f" ELSE {len(providers)} END"


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
    source_priority = _price_source_priority_case()
    with repository.connection() as connection:
        connection.execute("SET preserve_insertion_order = false")
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute("DELETE FROM security_price_summaries")
            connection.execute(
                """
                CREATE OR REPLACE TEMP TABLE price_source_stats AS
                SELECT
                    security_id,
                    source,
                    {source_priority} AS source_priority,
                    COUNT(*) AS price_rows,
                    COUNT(*) FILTER (WHERE volume IS NOT NULL AND volume > 0)
                        AS positive_volume_rows,
                    MAX(trade_date) AS latest_trade_date,
                    MAX(retrieved_at) AS latest_retrieved_at
                FROM prices_daily
                WHERE COALESCE(adjusted_close, close_price) IS NOT NULL
                GROUP BY security_id, source
                """.format(source_priority=source_priority)
            )
            connection.execute(
                """
                CREATE OR REPLACE TEMP TABLE price_source_choices AS
                WITH coverage AS (
                    SELECT *,
                           MAX(price_rows) OVER (PARTITION BY security_id)
                               AS maximum_price_rows,
                           MAX(positive_volume_rows) OVER (PARTITION BY security_id)
                               AS maximum_volume_rows,
                           MAX(latest_trade_date) OVER (PARTITION BY security_id)
                               AS maximum_latest_date
                    FROM price_source_stats
                ), close_ranked AS (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY security_id
                               ORDER BY
                                   CASE WHEN
                                       price_rows >= 0.8 * maximum_price_rows
                                       AND latest_trade_date >= maximum_latest_date - INTERVAL 30 DAY
                                   THEN 0 ELSE 1 END,
                                   CASE WHEN
                                       price_rows >= 0.8 * maximum_price_rows
                                       AND latest_trade_date >= maximum_latest_date - INTERVAL 30 DAY
                                   THEN source_priority ELSE 999 END,
                                   price_rows DESC,
                                   latest_trade_date DESC,
                                   source_priority
                           ) AS close_rank
                    FROM coverage
                ), volume_ranked AS (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY security_id
                               ORDER BY
                                   CASE WHEN
                                       positive_volume_rows >= 0.8 * maximum_volume_rows
                                       AND maximum_volume_rows > 0
                                   THEN 0 ELSE 1 END,
                                   CASE WHEN
                                       positive_volume_rows >= 0.8 * maximum_volume_rows
                                       AND maximum_volume_rows > 0
                                   THEN source_priority ELSE 999 END,
                                   positive_volume_rows DESC,
                                   source_priority
                           ) AS volume_rank
                    FROM coverage
                    WHERE positive_volume_rows > 0
                )
                SELECT
                    close.security_id,
                    close.source AS close_source,
                    volume.source AS volume_source,
                    close.price_rows,
                    close.latest_trade_date,
                    GREATEST(
                        close.latest_retrieved_at,
                        COALESCE(volume.latest_retrieved_at, close.latest_retrieved_at)
                    ) AS latest_source_retrieved_at
                FROM close_ranked close
                LEFT JOIN volume_ranked volume
                  ON volume.security_id = close.security_id
                 AND volume.volume_rank = 1
                WHERE close.close_rank = 1
                """
            )
            connection.execute(
                """
                CREATE OR REPLACE TEMP TABLE recent_close_rows AS
                SELECT security_id, trade_date, close_price
                FROM (
                    SELECT
                        p.security_id,
                        p.trade_date,
                        COALESCE(p.adjusted_close, p.close_price) AS close_price,
                        ROW_NUMBER() OVER (
                            PARTITION BY p.security_id
                            ORDER BY p.trade_date DESC
                        ) AS recency_row
                    FROM prices_daily p
                    JOIN price_source_choices choice
                      ON choice.security_id = p.security_id
                     AND choice.close_source = p.source
                    WHERE p.trade_date >= choice.latest_trade_date - INTERVAL 180 DAY
                      AND COALESCE(p.adjusted_close, p.close_price) IS NOT NULL
                )
                WHERE recency_row <= 60
                """
            )
            connection.execute(
                """
                CREATE OR REPLACE TEMP TABLE recent_volume_rows AS
                SELECT
                    p.security_id,
                    p.trade_date,
                    p.volume
                FROM prices_daily p
                JOIN price_source_choices choice
                  ON choice.security_id = p.security_id
                 AND choice.volume_source = p.source
                WHERE p.trade_date >= choice.latest_trade_date - INTERVAL 180 DAY
                  AND p.volume IS NOT NULL
                  AND p.volume > 0
                """
            )
            connection.execute(
                """
                INSERT INTO security_price_summaries
                WITH liquidity AS (
                    SELECT
                        close.security_id,
                        AVG(volume.volume * close.close_price)
                            AS avg_daily_traded_value_local,
                        COUNT(volume.volume) AS observed_volume_rows
                    FROM recent_close_rows close
                    LEFT JOIN recent_volume_rows volume
                      ON volume.security_id = close.security_id
                     AND volume.trade_date = close.trade_date
                    GROUP BY close.security_id
                )
                SELECT
                    choice.security_id,
                    choice.price_rows,
                    choice.latest_trade_date,
                    liquidity.avg_daily_traded_value_local,
                    COALESCE(liquidity.observed_volume_rows, 0),
                    choice.latest_source_retrieved_at,
                    CURRENT_TIMESTAMP
                FROM price_source_choices choice
                LEFT JOIN liquidity USING (security_id)
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
