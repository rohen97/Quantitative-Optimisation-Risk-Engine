from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
import logging
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import pandas as pd

from src.data.ingestion.dividends import ingest_dividends
from src.data.ingestion.fx import ingest_fx
from src.data.normalisers import normalise_fundamentals, normalise_macro_vintages, normalise_prices, record_hash
from src.data.schemas import SCHEMAS

try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:  # pragma: no cover
    duckdb = None
    DUCKDB_AVAILABLE = False


LOGGER = logging.getLogger(__name__)


class DuckDBUnavailableError(RuntimeError):
    """Raised when the selected backend requires DuckDB but it is unavailable."""


class DuckDBRepository:
    """DuckDB-backed repository with deterministic upserts and PIT reads."""

    def __init__(self, database_path: str | Path, read_only: bool = False) -> None:
        if not DUCKDB_AVAILABLE:
            raise DuckDBUnavailableError("DuckDB backend selected but duckdb is not installed.")
        self.database_path = Path(database_path)
        self.read_only = read_only
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator:
        connection = duckdb.connect(str(self.database_path), read_only=self.read_only)
        try:
            yield connection
        finally:
            connection.close()

    def close(self) -> None:
        """Compatibility no-op; connections are scoped per operation."""

    def execute_sql_file(self, path: str | Path) -> None:
        sql = Path(path).read_text(encoding="utf-8")
        with self.connection() as connection:
            connection.execute(sql)

    def execute_migrations(self, migrations_path: str | Path) -> None:
        for path in sorted(Path(migrations_path).glob("*.sql")):
            LOGGER.info("Applying DuckDB migration %s", path.name)
            self.execute_sql_file(path)

    def execute_views(self, views_path: str | Path) -> None:
        for path in sorted(Path(views_path).glob("*.sql")):
            LOGGER.info("Applying DuckDB view %s", path.name)
            self.execute_sql_file(path)

    def query(self, sql: str, parameters: list | tuple | None = None) -> pd.DataFrame:
        with self.connection() as connection:
            return connection.execute(sql, parameters or []).fetchdf()

    def read_table(self, name: str) -> pd.DataFrame:
        try:
            return self.query(f"SELECT * FROM {name}")
        except Exception:
            return pd.DataFrame()

    def write_table(self, name: str, frame: pd.DataFrame, primary_key: tuple[str, ...] | None = None) -> None:
        if frame.empty:
            return
        data = frame.copy()
        with self.connection() as connection:
            connection.register("_incoming_frame", data)
            try:
                if primary_key:
                    conditions = " AND ".join([f"{name}.{column} = _incoming_frame.{column}" for column in primary_key])
                    connection.execute(f"DELETE FROM {name} USING _incoming_frame WHERE {conditions}")
                connection.execute(f"INSERT INTO {name} BY NAME SELECT * FROM _incoming_frame")
            finally:
                connection.unregister("_incoming_frame")

    def save_prices(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        source = str(data["source"].iloc[0]) if "source" in data and not data.empty else "mock"
        clean = normalise_prices(data, source=source)
        clean["ingestion_run_id"] = ingestion_run_id
        self.write_table("prices_daily", clean, SCHEMAS["prices_daily"].primary_key)

    def save_fundamentals(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        source = str(data["source"].iloc[0]) if "source" in data and not data.empty else "mock"
        clean = normalise_fundamentals(data, source=source)
        clean["ingestion_run_id"] = ingestion_run_id
        self.write_table("fundamentals_reported", clean, SCHEMAS["fundamentals_reported"].primary_key)

    def save_dividends(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        source = str(data["source"].iloc[0]) if "source" in data and not data.empty else "mock"
        clean = ingest_dividends(data, source=source)
        clean["ingestion_run_id"] = ingestion_run_id
        self.write_table("dividends", clean, SCHEMAS["dividends"].primary_key)

    def save_fx_rates(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        source = str(data["source"].iloc[0]) if "source" in data and not data.empty else "mock"
        clean = ingest_fx(data, source=source)
        clean["ingestion_run_id"] = ingestion_run_id
        self.write_table("fx_rates", clean, SCHEMAS["fx_rates"].primary_key)

    def save_macro_observations(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        source = str(data["source"].iloc[0]) if "source" in data and not data.empty else "mock"
        clean = normalise_macro_vintages(data, source=source)
        clean["ingestion_run_id"] = ingestion_run_id
        # Primary key includes vintage_date, so later macro revisions insert as new vintages.
        self.write_table("macro_observations", clean, SCHEMAS["macro_observations"].primary_key)

    def save_news_documents(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        clean = data.copy()
        clean["document_id"] = clean.get("document_id", [str(uuid4()) for _ in range(len(clean))])
        clean["published_at"] = pd.to_datetime(clean.get("published_at", clean.get("published_date", pd.NaT)))
        clean["available_from"] = pd.to_datetime(clean.get("available_from", clean["published_at"])).fillna(pd.Timestamp.utcnow().tz_localize(None))
        clean["retrieved_at"] = pd.to_datetime(clean.get("retrieved_at", pd.Timestamp.utcnow().tz_localize(None)))
        clean["source"] = clean.get("source", "mock")
        clean["headline"] = clean.get("headline", clean.get("title", ""))
        clean["body_text"] = clean.get("body_text", clean.get("body", ""))
        clean["language"] = clean.get("language", "en")
        clean["url_hash"] = clean.get("url_hash", "")
        clean["payload_hash"] = clean.get("payload_hash", record_hash(clean.assign(_row=range(len(clean))), ["document_id", "headline", "body_text"]))
        clean["raw_archive_path"] = clean.get("raw_archive_path", None)
        self.write_table("news_documents", clean[list(SCHEMAS["news_documents"].column_names)], SCHEMAS["news_documents"].primary_key)

    def load_prices(self, security_ids: list[str], start_date: date, end_date: date) -> pd.DataFrame:
        return self.query(
            """
            SELECT *
            FROM prices_daily
            WHERE security_id IN (SELECT UNNEST(?))
              AND trade_date BETWEEN ? AND ?
            ORDER BY security_id, trade_date
            """,
            [security_ids, start_date, end_date],
        )

    def load_point_in_time_fundamentals(self, security_ids: list[str], as_of_date: datetime) -> pd.DataFrame:
        return self.query(
            """
            WITH ranked AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY security_id, fiscal_period_type
                        ORDER BY available_from DESC, retrieved_at DESC
                    ) AS row_number
                FROM fundamentals_reported
                WHERE security_id IN (SELECT UNNEST(?))
                  AND available_from <= ?
            )
            SELECT * EXCLUDE (row_number)
            FROM ranked
            WHERE row_number = 1
            """,
            [security_ids, as_of_date],
        )

    def load_point_in_time_macro(self, series_ids: list[str], as_of_date: datetime) -> pd.DataFrame:
        return self.query(
            """
            WITH ranked AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY series_id, observation_date
                        ORDER BY vintage_date DESC, retrieved_at DESC
                    ) AS row_number
                FROM macro_observations
                WHERE series_id IN (SELECT UNNEST(?))
                  AND available_from <= ?
            )
            SELECT * EXCLUDE (row_number)
            FROM ranked
            WHERE row_number = 1
            """,
            [series_ids, as_of_date],
        )

    def load_feature_snapshot(self, as_of_date: date) -> pd.DataFrame:
        return self.query(
            """
            SELECT *
            FROM feature_snapshots_monthly
            WHERE as_of_date = ?
            ORDER BY security_id, feature_name
            """,
            [as_of_date],
        )

    def register_model_run(self, metadata: dict[str, object]) -> str:
        now = pd.Timestamp.utcnow().tz_localize(None)
        model_run_id = str(metadata.get("model_run_id") or uuid4())
        row = {
            "model_run_id": model_run_id,
            "model_name": metadata.get("model_name", "wolf_quant_model"),
            "model_version": metadata.get("model_version", "local"),
            "git_commit_hash": metadata.get("git_commit_hash"),
            "git_is_dirty": bool(metadata.get("git_is_dirty", False)),
            "backend": metadata.get("backend", "legacy_csv"),
            "mode": metadata.get("mode", "dry_run"),
            "as_of_date": metadata.get("as_of_date", now),
            "started_at": metadata.get("started_at", now),
            "completed_at": metadata.get("completed_at"),
            "status": metadata.get("status", "running"),
            "config_hash": metadata.get("config_hash", ""),
            "input_snapshot_hash": metadata.get("input_snapshot_hash"),
            "random_seed": metadata.get("random_seed"),
            "train_start": metadata.get("train_start"),
            "train_end": metadata.get("train_end"),
            "validation_start": metadata.get("validation_start"),
            "validation_end": metadata.get("validation_end"),
            "test_start": metadata.get("test_start"),
            "test_end": metadata.get("test_end"),
            "output_path": metadata.get("output_path"),
            "error_message": metadata.get("error_message"),
            "runtime_seconds": metadata.get("runtime_seconds"),
        }
        self.write_table("model_runs", pd.DataFrame([row]), SCHEMAS["model_runs"].primary_key)
        return model_run_id

    def complete_model_run(
        self,
        model_run_id: str,
        status: str,
        output_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE model_runs
                SET completed_at = ?, status = ?, output_path = ?, error_message = ?
                WHERE model_run_id = ?
                """,
                [pd.Timestamp.utcnow().tz_localize(None), status, output_path, error_message, model_run_id],
            )
