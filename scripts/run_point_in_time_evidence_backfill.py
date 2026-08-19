from __future__ import annotations

import argparse
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
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient, HttpClientConfig
from src.data_ingestion.point_in_time_sources import (
    BeamSecMetadataClient,
    EodhdReferenceHistoryClient,
    NasdaqMergentClient,
    SecCompanyFactsClient,
    SecSubmissionsClient,
    point_in_time_coverage,
)
from src.utils.config import ROOT


LOGGER = logging.getLogger(__name__)
VALID_SOURCES = ("beam", "sec", "nasdaq", "eodhd")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill auditable filing and historical-universe evidence."
    )
    parser.add_argument("--sources", nargs="+", choices=VALID_SOURCES, default=list(VALID_SOURCES))
    parser.add_argument("--start-year", type=int, default=1997)
    parser.add_argument("--end-year", type=int, default=datetime.now(UTC).year)
    parser.add_argument("--max-us-symbols", type=int, default=100)
    parser.add_argument(
        "--listing-status",
        nargs="+",
        default=["Active", "Inactive"],
        help="Security-master statuses eligible for filing backfill.",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        default=[],
        help="Optional US ticker allowlist for targeted entitlement checks/backfills.",
    )
    parser.add_argument("--exchanges", nargs="+", default=["US"])
    parser.add_argument(
        "--indices",
        nargs="+",
        default=["GSPC.INDX", "DJI.INDX"],
        help="EODHD index symbols whose historical membership should be archived.",
    )
    parser.add_argument("--reporting-lag-days", type=int, default=120)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument(
        "--request-sleep-seconds",
        type=float,
        default=0.12,
        help="Delay between per-symbol requests; keep SEC traffic below 10 requests/second.",
    )
    parser.add_argument("--coverage-only", action="store_true")
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument(
        "--report-path",
        default="reports/outputs/validation/pit_evidence_coverage.json",
    )
    return parser.parse_args()


def _candidates(
    repository: DuckDBRepository,
    maximum: int,
    symbols: list[str] | None = None,
    listing_statuses: list[str] | None = None,
) -> pd.DataFrame:
    frame = repository.query(
        """
        WITH price_coverage AS (
            SELECT security_id, COUNT(*) AS price_rows
            FROM prices_daily
            GROUP BY security_id
            HAVING COUNT(*) >= 756
        ), identifiers AS (
            SELECT security_id,
                   MAX(identifier_value) FILTER (
                       WHERE identifier_type IN ('finnhub_ticker', 'ticker')
                   ) AS ticker
            FROM security_identifiers
            GROUP BY security_id
        )
        SELECT s.security_id,
               COALESCE(i.ticker, REGEXP_REPLACE(s.security_id, '\\.US$', '')) AS ticker
        FROM securities s
        JOIN price_coverage p USING (security_id)
        LEFT JOIN identifiers i USING (security_id)
        WHERE s.region = 'US'
          AND s.instrument_type = 'Equity'
        ORDER BY s.security_id
        """
    )
    accepted_statuses = {
        str(value).strip().casefold()
        for value in (listing_statuses or ["Active", "Inactive"])
        if str(value).strip()
    }
    if accepted_statuses:
        status = repository.query(
            "SELECT security_id, listing_status FROM securities WHERE region = 'US'"
        )
        frame = frame.merge(status, on="security_id", how="left")
        frame = frame.loc[
            frame["listing_status"].astype(str).str.casefold().isin(accepted_statuses)
        ].drop(columns="listing_status")
    if symbols:
        requested = {str(symbol).strip().upper() for symbol in symbols}
        frame = frame.loc[frame['ticker'].astype(str).str.upper().isin(requested)]
    if maximum > 0:
        frame = frame.head(maximum)
    return frame


def _write_report(
    repository: DuckDBRepository,
    path: Path,
    *,
    source_status: dict[str, object],
    started_at: datetime,
) -> None:
    coverage = point_in_time_coverage(repository)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "started_at": started_at.isoformat(),
        "source_status": source_status,
        "coverage": coverage.iloc[0].to_dict() if not coverage.empty else {},
        "governance_note": (
            "Coverage evidence is descriptive. Production PIT approval still requires "
            "observed availability, historical membership, inactive-security prices, "
            "and historical liquidity to meet configured thresholds."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)
    LOGGER.info("PIT evidence coverage written to %s", path)


def main() -> int:
    args = parse_args()
    if args.start_year > args.end_year:
        raise ValueError("start-year must not exceed end-year")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_data_config()
    repository = DuckDBRepository(config.duckdb_path)
    if not args.skip_migrations:
        repository.execute_migrations(ROOT / "sql" / "migrations")
    report_path = Path(args.report_path)
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    started_at = datetime.now(UTC)
    status: dict[str, object] = {}
    if args.coverage_only:
        _write_report(repository, report_path, source_status=status, started_at=started_at)
        return 0

    http = HttpClient(
        HttpClientConfig(
            timeout_seconds=args.timeout_seconds,
            retry_attempts=args.retry_attempts,
        )
    )
    run_id = str(uuid4())
    retrieved_at = pd.Timestamp(started_at).tz_localize(None)
    candidates = _candidates(
        repository,
        args.max_us_symbols,
        args.symbols,
        args.listing_status,
    )

    if "beam" in args.sources:
        client = BeamSecMetadataClient(http)
        frames: list[pd.DataFrame] = []
        failed = 0
        for row in candidates.itertuples(index=False):
            try:
                cik = client.ticker_cik(str(row.ticker))
                if cik:
                    frame = client.filings(
                        str(row.security_id),
                        cik,
                        start_date=date(args.start_year, 1, 1),
                        end_date=date(args.end_year, 12, 31),
                        retrieved_at=retrieved_at,
                        ingestion_run_id=run_id,
                    )
                    if not frame.empty:
                        frames.append(frame)
            except (DataSourceRequestError, ValueError) as exc:
                failed += 1
                LOGGER.warning("Beam metadata failed for %s: %s", row.ticker, exc)
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not combined.empty:
            repository.write_table(
                "filing_metadata", combined, SCHEMAS["filing_metadata"].primary_key
            )
        status["beam"] = {"rows": len(combined), "failed_symbols": failed}

    if "sec" in args.sources:
        client = SecSubmissionsClient(http)
        facts_client = SecCompanyFactsClient(http)
        frames = []
        failed = 0
        fact_failures = 0
        facts_seen = 0
        fundamental_vintages_written = 0
        fundamentals_written = 0
        ticker_map_available = False
        ticker_ciks: dict[str, str] = {}
        try:
            ticker_ciks = client.ticker_ciks()
            ticker_map_available = True
        except DataSourceRequestError as exc:
            failed = len(candidates)
            fact_failures = len(candidates)
            LOGGER.warning("SEC ticker map failed: %s", exc)
        for row in candidates.itertuples(index=False) if ticker_map_available else ():
            ticker = str(row.ticker).strip().upper()
            cik = ticker_ciks.get(ticker) or ticker_ciks.get(ticker.replace(".", "-"))
            if not cik:
                failed += 1
                continue
            frame = pd.DataFrame()
            try:
                frame = client.filings(
                    str(row.security_id),
                    cik,
                    start_date=date(args.start_year, 1, 1),
                    end_date=date(args.end_year, 12, 31),
                    retrieved_at=retrieved_at,
                    ingestion_run_id=run_id,
                )
                if not frame.empty:
                    frames.append(frame)
            except (DataSourceRequestError, ValueError) as exc:
                failed += 1
                LOGGER.warning("SEC submissions failed for %s: %s", ticker, exc)
            acceptance_by_accession = (
                frame.dropna(subset=["acceptance_datetime"])
                .set_index("accession_number")["acceptance_datetime"]
                .to_dict()
                if not frame.empty
                else {}
            )
            try:
                facts = facts_client.fundamentals(
                    str(row.security_id),
                    cik,
                    start_date=date(args.start_year, 1, 1),
                    end_date=date(args.end_year, 12, 31),
                    retrieved_at=retrieved_at,
                    ingestion_run_id=run_id,
                    acceptance_by_accession=acceptance_by_accession,
                )
                facts_seen += facts.facts_seen
                if not facts.fundamental_vintages.empty:
                    repository.write_table(
                        "fundamental_vintages",
                        facts.fundamental_vintages,
                        SCHEMAS["fundamental_vintages"].primary_key,
                    )
                    fundamental_vintages_written += len(facts.fundamental_vintages)
                if not facts.fundamentals_reported.empty:
                    repository.write_table(
                        "fundamentals_reported",
                        facts.fundamentals_reported,
                        SCHEMAS["fundamentals_reported"].primary_key,
                    )
                    fundamentals_written += len(facts.fundamentals_reported)
            except (DataSourceRequestError, ValueError) as exc:
                fact_failures += 1
                LOGGER.warning("SEC companyfacts failed for %s: %s", ticker, exc)
            time.sleep(max(args.request_sleep_seconds, 0.0))
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not combined.empty:
            repository.write_table(
                "filing_metadata", combined, SCHEMAS["filing_metadata"].primary_key
            )
        status["sec"] = {
            "filing_rows": len(combined),
            "companyfacts_seen": facts_seen,
            "fundamental_vintage_rows": fundamental_vintages_written,
            "fundamentals_reported_rows": fundamentals_written,
            "filing_failed_symbols": failed,
            "companyfacts_failed_symbols": fact_failures,
            "ticker_map_available": ticker_map_available,
            "source_status": (
                "completed"
                if ticker_map_available
                and (
                    candidates.empty
                    or len(combined) > 0
                    or fundamentals_written > 0
                )
                else "blocked"
            ),
        }

    if "nasdaq" in args.sources:
        client = NasdaqMergentClient(http, reporting_lag_days=args.reporting_lag_days)
        written = 0
        failed = 0
        for row in candidates.itertuples(index=False):
            try:
                frame = client.annual_fundamentals(
                    str(row.security_id),
                    str(row.ticker),
                    start_year=args.start_year,
                    end_year=args.end_year,
                    retrieved_at=retrieved_at,
                    ingestion_run_id=run_id,
                )
                if not frame.empty:
                    repository.write_table(
                        "fundamentals_reported",
                        frame,
                        SCHEMAS["fundamentals_reported"].primary_key,
                    )
                    written += len(frame)
            except (DataSourceRequestError, ValueError) as exc:
                failed += 1
                LOGGER.warning("Nasdaq Mergent failed for %s: %s", row.ticker, exc)
        status["nasdaq"] = {"rows": written, "failed_symbols": failed}

    if "eodhd" in args.sources:
        client = EodhdReferenceHistoryClient(http)
        frames = []
        failed = 0
        for exchange in args.exchanges:
            try:
                frames.append(
                    client.delisted_symbols(
                        exchange,
                        retrieved_at=retrieved_at,
                        ingestion_run_id=run_id,
                    )
                )
            except DataSourceRequestError as exc:
                failed += 1
                LOGGER.warning("EODHD delisted list failed for %s: %s", exchange, exc)
        try:
            frames.append(
                client.symbol_changes(
                    start_date=date(max(args.start_year, 2022), 1, 1),
                    end_date=date(args.end_year, 12, 31),
                    retrieved_at=retrieved_at,
                    ingestion_run_id=run_id,
                )
            )
        except DataSourceRequestError as exc:
            failed += 1
            LOGGER.warning("EODHD symbol history failed: %s", exc)
        for index_symbol in args.indices:
            try:
                frames.append(
                    client.historical_index_membership(
                        index_symbol,
                        retrieved_at=retrieved_at,
                        ingestion_run_id=run_id,
                    )
                )
            except DataSourceRequestError as exc:
                failed += 1
                LOGGER.warning("EODHD membership failed for %s: %s", index_symbol, exc)
        combined = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True) if any(not frame.empty for frame in frames) else pd.DataFrame()
        if not combined.empty:
            repository.write_table(
                "security_reference_events",
                combined,
                SCHEMAS["security_reference_events"].primary_key,
            )
        status["eodhd"] = {"rows": len(combined), "failed_requests": failed}

    _write_report(repository, report_path, source_status=status, started_at=started_at)
    blocked = [
        source
        for source in args.sources
        if isinstance(status.get(source), dict)
        and status[source].get("source_status") in {"blocked", "failed"}
    ]
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
