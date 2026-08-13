from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, date, datetime
import json
import logging
from pathlib import Path
import sys
import time
from uuid import uuid4

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.normalisers import normalise_prices
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.bloomberg_adapter import (
    BloombergConfig,
    BloombergDesktopAdapter,
    BloombergRequestError,
    bloomberg_symbol_for_row,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_REGIONS = ("Mainland China", "Hong Kong")
RETRYABLE_EXIT_CODE = 75


def _is_retryable_bloomberg_error(error: Exception) -> bool:
    message = str(error).lower()
    retryable_markers = (
        "daily capacity reached",
        "request timed out",
        "session startup timed out",
        "connection reset",
        "connection aborted",
        "connection refused",
        "temporarily unavailable",
        "service unavailable",
    )
    return isinstance(error, BloombergRequestError) and any(
        marker in message for marker in retryable_markers
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill entitled Bloomberg Desktop API prices into the local DuckDB."
    )
    parser.add_argument("--regions", nargs="*", default=list(DEFAULT_REGIONS))
    parser.add_argument("--listing-status", nargs="*", default=["Active"])
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=[],
        help="Optional canonical security_id allow-list, for example 00001.HK 000001.SHE.",
    )
    parser.add_argument("--start", default="1997-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--request-size", type=int, default=10)
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument("--sleep-seconds", type=float, default=0.10)
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip securities whose Bloomberg history already covers the requested dates.",
    )
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Retry symbols in the local Bloomberg no-data quarantine.",
    )
    parser.add_argument("--include-delisted", action="store_true")
    parser.add_argument("--health-check", action="store_true")
    parser.add_argument("--coverage-only", action="store_true")
    parser.add_argument(
        "--sync-identifiers-only",
        action="store_true",
        help="Persist generated Bloomberg identifiers without requesting observations.",
    )
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument(
        "--failure-report",
        type=Path,
        default=Path("data/locks/bloomberg_backfill_failures.csv"),
    )
    return parser.parse_args()


def _validate_dates(start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_date = pd.Timestamp(start).normalize()
    end_date = pd.Timestamp(end).normalize()
    if start_date > end_date:
        raise ValueError("--start must not be after --end")
    return start_date, end_date


def load_candidates(
    repository: DuckDBRepository,
    regions: list[str],
    statuses: list[str],
    symbols: list[str],
) -> pd.DataFrame:
    candidates = repository.query(
        """
        WITH identifiers AS (
            SELECT
                security_id,
                MAX(identifier_value) FILTER (
                    WHERE identifier_type = 'bloomberg_ticker'
                ) AS bloomberg_ticker,
                MAX(identifier_value) FILTER (
                    WHERE identifier_type = 'isin'
                ) AS isin
            FROM security_identifiers
            GROUP BY security_id
        )
        , price_coverage AS (
            SELECT security_id, COUNT(*) AS existing_price_rows
            FROM prices_daily
            GROUP BY security_id
        )
        SELECT
            s.security_id,
            s.company_name,
            s.exchange_code,
            s.region,
            s.listing_status,
            s.trading_currency,
            i.bloomberg_ticker,
            i.isin,
            COALESCE(p.existing_price_rows, 0) AS existing_price_rows
        FROM securities s
        LEFT JOIN identifiers i USING (security_id)
        LEFT JOIN price_coverage p USING (security_id)
        WHERE s.instrument_type = 'Equity'
          AND s.region IN (SELECT UNNEST(?))
          AND s.listing_status IN (SELECT UNNEST(?))
        ORDER BY s.region, s.exchange_code, s.security_id
        """,
        [regions, statuses],
    )
    if symbols:
        wanted = {str(value).strip().upper() for value in symbols if str(value).strip()}
        candidates = candidates[candidates["security_id"].astype(str).str.upper().isin(wanted)].copy()
    if candidates.empty:
        return candidates.assign(provider_symbol=pd.Series(dtype=str))
    candidates["provider_symbol"] = candidates.apply(
        lambda row: bloomberg_symbol_for_row(row.to_dict()), axis=1
    )
    return candidates.dropna(subset=["provider_symbol"]).reset_index(drop=True)


def _completed_ids(
    repository: DuckDBRepository,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> set[str]:
    coverage = repository.query(
        """
        SELECT security_id
        FROM prices_daily
        WHERE source = 'bloomberg'
        GROUP BY security_id
        HAVING MIN(trade_date) <= ?
           AND MAX(trade_date) >= ? - INTERVAL 7 DAY
        """,
        [start_date.date(), end_date.date()],
    )
    return set(coverage["security_id"].astype(str)) if not coverage.empty else set()


def _batches(frame: pd.DataFrame, size: int):
    batch_size = max(int(size), 1)
    for start in range(0, len(frame), batch_size):
        yield start, frame.iloc[start : start + batch_size].copy()


def write_bloomberg_identifiers(
    repository: DuckDBRepository,
    candidates: pd.DataFrame,
) -> int:
    if candidates.empty:
        return 0
    retrieved_at = pd.Timestamp.now("UTC").tz_localize(None)
    identifiers = candidates[["security_id", "provider_symbol"]].copy()
    identifiers = identifiers.rename(columns={"provider_symbol": "identifier_value"})
    identifiers["identifier_type"] = "bloomberg_ticker"
    identifiers["valid_from"] = pd.Timestamp("1900-01-01")
    identifiers["valid_to"] = pd.NaT
    identifiers["source"] = "bloomberg_mapping"
    identifiers["retrieved_at"] = retrieved_at
    identifiers = identifiers[list(SCHEMAS["security_identifiers"].column_names)]
    repository.write_table(
        "security_identifiers",
        identifiers,
        SCHEMAS["security_identifiers"].primary_key,
    )
    return len(identifiers)


def _ingestion_run_frame(
    run_id: str,
    started_at: pd.Timestamp,
    status: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    parameters: dict[str, object],
    row_count: int,
    rejected_count: int,
    error_message: str | None = None,
) -> pd.DataFrame:
    completed = pd.Timestamp.now("UTC").tz_localize(None) if status != "running" else pd.NaT
    return pd.DataFrame(
        [
            {
                "ingestion_run_id": run_id,
                "source_name": "bloomberg",
                "dataset_name": "prices_daily",
                "started_at": started_at,
                "completed_at": completed,
                "status": status,
                "requested_start_date": start_date,
                "requested_end_date": end_date,
                "request_parameters_json": json.dumps(parameters, sort_keys=True),
                "row_count": row_count,
                "inserted_count": row_count,
                "updated_count": 0,
                "rejected_count": rejected_count,
                "payload_hash": None,
                "config_hash": None,
                "error_message": error_message,
            }
        ]
    )


def _write_run(repository: DuckDBRepository, frame: pd.DataFrame) -> None:
    repository.write_table(
        "data_ingestion_runs",
        frame[list(SCHEMAS["data_ingestion_runs"].column_names)],
        SCHEMAS["data_ingestion_runs"].primary_key,
    )


def _read_failure_report(path: Path) -> pd.DataFrame:
    columns = ["security_id", "provider_symbol", "error"]
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        frame = pd.read_csv(path, dtype=str).fillna("")
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame:
            frame[column] = ""
    return frame[columns]


def _write_failure_report(
    path: Path,
    failures: list[dict[str, str]],
    attempted_ids: set[str],
) -> None:
    existing = _read_failure_report(path)
    if attempted_ids and not existing.empty:
        existing = existing[~existing["security_id"].astype(str).isin(attempted_ids)]
    current = pd.DataFrame(failures)
    combined = pd.concat([existing, current], ignore_index=True) if not current.empty else existing
    combined = combined.drop_duplicates(["security_id", "provider_symbol"], keep="last")
    if combined.empty:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)


def _coverage(repository: DuckDBRepository, regions: list[str]) -> pd.DataFrame:
    return repository.query(
        """
        SELECT
            s.region,
            COUNT(DISTINCT p.security_id) AS priced_securities,
            COUNT(*) AS price_rows,
            MIN(p.trade_date) AS earliest_date,
            MAX(p.trade_date) AS latest_date,
            COUNT(DISTINCT p.security_id) FILTER (
                WHERE p.volume IS NOT NULL AND p.volume > 0
            ) AS securities_with_volume
        FROM prices_daily p
        JOIN securities s USING (security_id)
        WHERE p.source = 'bloomberg'
          AND s.region IN (SELECT UNNEST(?))
        GROUP BY s.region
        ORDER BY s.region
        """,
        [regions],
    )


def main() -> int:
    args = parse_args()
    start_date, end_date = _validate_dates(args.start, args.end)
    statuses = list(args.listing_status)
    if args.include_delisted and "Delisted" not in statuses:
        statuses.append("Delisted")

    data_config = load_data_config()
    repository = DuckDBRepository(data_config.duckdb_path)
    if not args.skip_migrations:
        repository.execute_migrations(data_config.migrations_path)

    adapter_config = replace(
        BloombergConfig.from_env(),
        max_securities_per_request=max(int(args.request_size), 1),
    )
    adapter = BloombergDesktopAdapter(adapter_config)
    health = adapter.health_check()
    LOGGER.info(
        "Bloomberg Desktop API connected at %s:%s using blpapi %s.",
        health["host"],
        health["port"],
        health["blpapi_version"],
    )
    if args.health_check:
        print(json.dumps(health, indent=2, default=str))
        repository.close()
        return 0
    if args.coverage_only:
        print(_coverage(repository, list(args.regions)).to_string(index=False))
        repository.close()
        return 0

    candidates = load_candidates(
        repository,
        list(args.regions),
        statuses,
        list(args.symbols),
    )
    duplicate_symbols = (
        candidates["provider_symbol"].duplicated(keep=False)
        if not candidates.empty
        else pd.Series(dtype=bool)
    )
    if bool(duplicate_symbols.any()):
        duplicate_count = int(duplicate_symbols.sum())
        LOGGER.warning(
            "Resolving %s duplicate Bloomberg mappings to the canonical security with the most existing price history.",
            duplicate_count,
        )
        candidates = (
            candidates.sort_values(
                ["provider_symbol", "existing_price_rows", "security_id"],
                ascending=[True, False, True],
            )
            .drop_duplicates("provider_symbol", keep="first")
            .reset_index(drop=True)
        )
    identifier_count = write_bloomberg_identifiers(repository, candidates)
    LOGGER.info("Persisted %s canonical Bloomberg identifiers.", identifier_count)
    if args.sync_identifiers_only:
        print(
            candidates.groupby("region")["provider_symbol"]
            .nunique()
            .rename("bloomberg_identifiers")
            .to_string()
        )
        repository.close()
        return 0
    if not args.retry_failures:
        quarantined = set(
            _read_failure_report(args.failure_report)["security_id"].astype(str)
        )
        before_quarantine = len(candidates)
        candidates = candidates[
            ~candidates["security_id"].astype(str).isin(quarantined)
        ].copy()
        skipped = before_quarantine - len(candidates)
        if skipped:
            LOGGER.info("Skipped %s quarantined Bloomberg symbols.", skipped)
    if args.resume:
        completed = _completed_ids(repository, start_date, end_date)
        candidates = candidates[~candidates["security_id"].astype(str).isin(completed)].copy()
    if args.max_symbols > 0:
        candidates = candidates.head(args.max_symbols).copy()
    candidates = candidates.reset_index(drop=True)

    LOGGER.info(
        "Starting Bloomberg backfill for %s securities across regions=%s, dates=%s to %s.",
        len(candidates),
        list(args.regions),
        start_date.date(),
        end_date.date(),
    )
    if candidates.empty:
        print(_coverage(repository, list(args.regions)).to_string(index=False))
        repository.close()
        return 0

    run_id = str(uuid4())
    started_at = pd.Timestamp(datetime.now(UTC)).tz_localize(None)
    parameters = {
        "regions": list(args.regions),
        "listing_status": statuses,
        "start": start_date.date().isoformat(),
        "end": end_date.date().isoformat(),
        "candidate_count": len(candidates),
        "batch_size": int(args.batch_size),
        "request_size": int(args.request_size),
    }
    _write_run(
        repository,
        _ingestion_run_frame(
            run_id,
            started_at,
            "running",
            start_date,
            end_date,
            parameters,
            0,
            0,
        ),
    )

    total_rows = 0
    failures: list[dict[str, str]] = []
    attempted_ids: set[str] = set()
    try:
        for offset, batch in _batches(candidates, args.batch_size):
            attempted_ids.update(batch["security_id"].astype(str))
            symbol_map = dict(
                zip(batch["provider_symbol"].astype(str), batch["security_id"].astype(str), strict=True)
            )
            currency_map = batch.set_index("security_id")["trading_currency"].astype(str).to_dict()
            try:
                bars = adapter.load_daily_bars(
                    list(symbol_map),
                    start=start_date.date().isoformat(),
                    end=end_date.date().isoformat(),
                )
                request_error = adapter.last_errors.get("request")
                bars["ticker"] = bars["ticker"].map(symbol_map)
                bars = bars.dropna(subset=["ticker"])
                bars["currency"] = bars["ticker"].map(currency_map)
                clean = normalise_prices(bars, source="bloomberg")
                clean["ingestion_run_id"] = run_id
                repository.write_table(
                    "prices_daily",
                    clean,
                    SCHEMAS["prices_daily"].primary_key,
                )
                total_rows += len(clean)
                returned = set(clean["security_id"].astype(str))
                for provider_symbol, message in adapter.last_errors.items():
                    if provider_symbol == "request":
                        continue
                    failures.append(
                        {
                            "security_id": symbol_map.get(provider_symbol, ""),
                            "provider_symbol": provider_symbol,
                            "error": message,
                        }
                    )
                for row in batch.itertuples(index=False):
                    if str(row.security_id) not in returned and str(row.provider_symbol) not in adapter.last_errors:
                        failures.append(
                            {
                                "security_id": str(row.security_id),
                                "provider_symbol": str(row.provider_symbol),
                                "error": "No historical rows returned",
                            }
                        )
                LOGGER.info(
                    "Bloomberg batch %s-%s wrote %s rows for %s securities.",
                    offset + 1,
                    offset + len(batch),
                    len(clean),
                    len(returned),
                )
                if request_error:
                    raise BloombergRequestError(
                        f"Bloomberg price batch {offset + 1}-{offset + len(batch)}: "
                        f"{request_error}"
                    )
            except BloombergRequestError as exc:
                if _is_retryable_bloomberg_error(exc):
                    raise
                LOGGER.warning(
                    "Bloomberg batch %s-%s failed: %s",
                    offset + 1,
                    offset + len(batch),
                    exc,
                )
                for row in batch.itertuples(index=False):
                    failures.append(
                        {
                            "security_id": str(row.security_id),
                            "provider_symbol": str(row.provider_symbol),
                            "error": str(exc),
                        }
                    )
            except Exception as exc:
                LOGGER.warning(
                    "Bloomberg batch %s-%s failed: %s",
                    offset + 1,
                    offset + len(batch),
                    exc,
                )
                for row in batch.itertuples(index=False):
                    failures.append(
                        {
                            "security_id": str(row.security_id),
                            "provider_symbol": str(row.provider_symbol),
                            "error": str(exc),
                        }
                    )
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)
        status = "completed_with_errors" if failures else "completed"
        _write_run(
            repository,
            _ingestion_run_frame(
                run_id,
                started_at,
                status,
                start_date,
                end_date,
                parameters,
                total_rows,
                len(failures),
            ),
        )
    except Exception as exc:
        _write_run(
            repository,
            _ingestion_run_frame(
                run_id,
                started_at,
                "failed",
                start_date,
                end_date,
                parameters,
                total_rows,
                len(failures),
                str(exc),
            ),
        )
        if _is_retryable_bloomberg_error(exc):
            LOGGER.error(
                "Bloomberg price run paused after durable database writes: %s",
                exc,
            )
            return RETRYABLE_EXIT_CODE
        raise
    finally:
        _write_failure_report(args.failure_report, failures, attempted_ids)

    LOGGER.info(
        "Bloomberg backfill complete. Wrote %s rows; unresolved securities=%s.",
        total_rows,
        len(failures),
    )
    print(_coverage(repository, list(args.regions)).to_string(index=False))
    repository.close()
    return 0 if total_rows > 0 else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
