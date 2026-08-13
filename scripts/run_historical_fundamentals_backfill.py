from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import date, datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.historical_fundamentals import (
    EASTMONEY_CHINA_SOURCE,
    EASTMONEY_HK_SOURCE,
    FINNHUB_REPORTED_SOURCE,
    EastmoneyHistoricalClient,
    FinnhubReportedClient,
    utc_now,
)
from src.data_ingestion.http_client import HttpClient, HttpClientConfig
from src.utils.config import ROOT


LOGGER = logging.getLogger(__name__)
DEFAULT_REGIONS = ("US", "Mainland China", "Hong Kong")
SOURCE_BY_REGION = {
    "US": FINNHUB_REPORTED_SOURCE,
    "Mainland China": EASTMONEY_CHINA_SOURCE,
    "Hong Kong": EASTMONEY_HK_SOURCE,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill historical annual fundamentals needed for the reconstructed "
            "point-in-time walk-forward window."
        )
    )
    parser.add_argument("--regions", nargs="*", default=list(DEFAULT_REGIONS))
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2020)
    parser.add_argument(
        "--max-symbols-per-region",
        type=int,
        default=0,
        help="Optional test cap per region; 0 means all eligible securities.",
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--commit-size", type=int, default=25)
    parser.add_argument("--request-timeout-seconds", type=int, default=30)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument("--finnhub-request-interval-seconds", type=float, default=1.05)
    parser.add_argument("--eastmoney-request-interval-seconds", type=float, default=0.05)
    parser.add_argument("--filing-lag-days", type=int, default=120)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--coverage-only", action="store_true")
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument(
        "--status-path",
        default="reports/outputs/walk_forward/historical_fundamentals_status.json",
    )
    return parser.parse_args()


def _json_value(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot serialise {type(value).__name__}")


def _atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, default=_json_value),
        encoding="utf-8",
    )
    temporary.replace(path)


def _validate_args(args: argparse.Namespace) -> None:
    unsupported = sorted(set(args.regions).difference(SOURCE_BY_REGION))
    if unsupported:
        raise ValueError(f"Unsupported historical-fundamentals regions: {unsupported}")
    if args.start_year > args.end_year:
        raise ValueError("start-year must not exceed end-year")
    if args.workers <= 0 or args.commit_size <= 0:
        raise ValueError("workers and commit-size must be positive")
    if args.filing_lag_days < 0:
        raise ValueError("filing-lag-days must not be negative")


def select_candidates(
    repo: DuckDBRepository,
    regions: list[str],
    max_symbols_per_region: int,
) -> pd.DataFrame:
    candidates = repo.query(
        """
        WITH eligible AS (
            SELECT security_id
            FROM fundamentals_reported
            WHERE fiscal_period_type = 'annual'
              AND LOWER(source) NOT LIKE '%mock%'
              AND LOWER(source) NOT LIKE '%synthetic%'
            GROUP BY security_id
            HAVING COUNT(DISTINCT fiscal_period_end) >= 2
        ),
        identifiers AS (
            SELECT
                security_id,
                MAX(identifier_value) FILTER (
                    WHERE identifier_type = 'finnhub_ticker'
                ) AS finnhub_ticker
            FROM security_identifiers
            GROUP BY security_id
        )
        SELECT
            s.security_id,
            s.region,
            s.exchange_code,
            COALESCE(
                i.finnhub_ticker,
                REGEXP_REPLACE(s.security_id, '\\.US$', '')
            ) AS finnhub_ticker
        FROM securities s
        JOIN eligible e USING (security_id)
        LEFT JOIN identifiers i USING (security_id)
        WHERE s.listing_status = 'Active'
          AND s.instrument_type = 'Equity'
          AND s.region IN (SELECT UNNEST(?))
        ORDER BY s.region, s.security_id
        """,
        [regions],
    )
    if max_symbols_per_region > 0:
        candidates = (
            candidates.groupby("region", group_keys=False, sort=False)
            .head(max_symbols_per_region)
            .reset_index(drop=True)
        )
    return candidates


def completed_security_ids(
    repo: DuckDBRepository,
    candidates: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> set[str]:
    if candidates.empty:
        return set()
    required_periods = min(2, end_year - start_year + 1)
    coverage = repo.query(
        """
        SELECT security_id
        FROM fundamentals_reported
        WHERE security_id IN (SELECT UNNEST(?))
          AND source IN (SELECT UNNEST(?))
          AND fiscal_period_type = 'annual'
          AND YEAR(fiscal_period_end) BETWEEN ? AND ?
        GROUP BY security_id
        HAVING COUNT(DISTINCT fiscal_period_end) >= ?
        """,
        [
            candidates["security_id"].astype(str).tolist(),
            list(SOURCE_BY_REGION.values()),
            start_year,
            end_year,
            required_periods,
        ],
    )
    return set(coverage["security_id"].astype(str))


def coverage_report(
    repo: DuckDBRepository,
    regions: list[str],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    return repo.query(
        """
        WITH period_coverage AS (
            SELECT
                s.region,
                f.source,
                f.security_id,
                COUNT(DISTINCT f.fiscal_period_end) AS annual_periods,
                MIN(f.fiscal_period_end) AS earliest_period,
                MAX(f.fiscal_period_end) AS latest_period,
                COUNT(*) FILTER (WHERE f.filing_date IS NOT NULL) AS dated_rows
            FROM fundamentals_reported f
            JOIN securities s USING (security_id)
            WHERE s.region IN (SELECT UNNEST(?))
              AND f.source IN (SELECT UNNEST(?))
              AND f.fiscal_period_type = 'annual'
              AND YEAR(f.fiscal_period_end) BETWEEN ? AND ?
            GROUP BY s.region, f.source, f.security_id
        )
        SELECT
            region,
            source,
            COUNT(*) AS securities_with_data,
            COUNT(*) FILTER (WHERE annual_periods >= 2) AS securities_with_two_periods,
            SUM(annual_periods) AS annual_rows,
            MIN(earliest_period) AS earliest_period,
            MAX(latest_period) AS latest_period,
            SUM(dated_rows) AS rows_with_observed_filing_date
        FROM period_coverage
        GROUP BY region, source
        ORDER BY region, source
        """,
        [regions, list(SOURCE_BY_REGION.values()), start_year, end_year],
    )


def _fetch_security(
    row: dict[str, Any],
    *,
    finnhub: FinnhubReportedClient,
    eastmoney: EastmoneyHistoricalClient,
    start_year: int,
    end_year: int,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    region = str(row["region"])
    security_id = str(row["security_id"])
    if region == "US":
        return finnhub.fetch_annual_fundamentals(
            security_id,
            str(row["finnhub_ticker"]),
            start_year=start_year,
            end_year=end_year,
            retrieved_at=retrieved_at,
            ingestion_run_id=ingestion_run_id,
        )
    if region == "Mainland China":
        return eastmoney.fetch_mainland_annual_fundamentals(
            security_id,
            start_year=start_year,
            end_year=end_year,
            retrieved_at=retrieved_at,
            ingestion_run_id=ingestion_run_id,
        )
    if region == "Hong Kong":
        return eastmoney.fetch_hong_kong_annual_fundamentals(
            security_id,
            start_year=start_year,
            end_year=end_year,
            retrieved_at=retrieved_at,
            ingestion_run_id=ingestion_run_id,
        )
    raise ValueError(f"Unsupported region: {region}")


def _flush(repo: DuckDBRepository, frames: list[pd.DataFrame]) -> int:
    if not frames:
        return 0
    combined = pd.concat(frames, ignore_index=True)
    repo.write_table(
        "fundamentals_reported",
        combined,
        SCHEMAS["fundamentals_reported"].primary_key,
    )
    frames.clear()
    return len(combined)


def run_backfill(
    repo: DuckDBRepository,
    candidates: pd.DataFrame,
    args: argparse.Namespace,
    status_path: Path,
) -> dict[str, Any]:
    completed = set() if args.force else completed_security_ids(
        repo,
        candidates,
        args.start_year,
        args.end_year,
    )
    jobs = candidates.loc[
        ~candidates["security_id"].astype(str).isin(completed)
    ].reset_index(drop=True)
    retrieved_at = utc_now()
    run_id = str(uuid4())
    http = HttpClient(
        HttpClientConfig(
            timeout_seconds=args.request_timeout_seconds,
            retry_attempts=args.retry_attempts,
            retry_backoff_seconds=1.0,
            user_agent="wolf-quant-model/1.7 historical-fundamentals",
        )
    )
    finnhub = FinnhubReportedClient(
        http,
        minimum_interval_seconds=args.finnhub_request_interval_seconds,
    )
    eastmoney = EastmoneyHistoricalClient(
        http,
        filing_lag_days=args.filing_lag_days,
        request_interval_seconds=args.eastmoney_request_interval_seconds,
    )
    pending_frames: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    securities_with_data = 0
    rows_written = 0
    finished = 0

    LOGGER.info(
        "Historical fundamentals backfill: candidates=%s jobs=%s skipped=%s years=%s-%s regions=%s.",
        len(candidates),
        len(jobs),
        len(candidates) - len(jobs),
        args.start_year,
        args.end_year,
        args.regions,
    )
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures: dict[Future[pd.DataFrame], dict[str, Any]] = {
            executor.submit(
                _fetch_security,
                row,
                finnhub=finnhub,
                eastmoney=eastmoney,
                start_year=args.start_year,
                end_year=args.end_year,
                retrieved_at=retrieved_at,
                ingestion_run_id=run_id,
            ): row
            for row in jobs.to_dict("records")
        }
        for future in as_completed(futures):
            row = futures[future]
            try:
                frame = future.result()
                if frame.empty:
                    failures.append(
                        {
                            "security_id": str(row["security_id"]),
                            "region": str(row["region"]),
                            "error": "no usable annual rows returned",
                        }
                    )
                else:
                    pending_frames.append(frame)
                    securities_with_data += 1
            except Exception as exc:
                failures.append(
                    {
                        "security_id": str(row["security_id"]),
                        "region": str(row["region"]),
                        "error": str(exc)[:500],
                    }
                )
            finished += 1
            if finished % args.commit_size == 0:
                rows_written += _flush(repo, pending_frames)
                LOGGER.info(
                    "Historical fundamentals progress: %s/%s securities, rows=%s, no_data_or_failed=%s.",
                    finished,
                    len(jobs),
                    rows_written,
                    len(failures),
                )
                _atomic_json(
                    {
                        "status": "running",
                        "run_id": run_id,
                        "candidate_count": len(candidates),
                        "job_count": len(jobs),
                        "completed_jobs": finished,
                        "securities_with_data": securities_with_data,
                        "rows_written": rows_written,
                        "failure_count": len(failures),
                        "updated_at": utc_now(),
                    },
                    status_path,
                )

    rows_written += _flush(repo, pending_frames)
    report = coverage_report(repo, args.regions, args.start_year, args.end_year)
    summary = {
        "status": "completed",
        "run_id": run_id,
        "candidate_count": len(candidates),
        "job_count": len(jobs),
        "skipped_count": len(candidates) - len(jobs),
        "securities_with_data": securities_with_data,
        "rows_written": rows_written,
        "failure_count": len(failures),
        "failure_sample": failures[:50],
        "coverage": report.to_dict("records"),
        "completed_at": utc_now(),
    }
    _atomic_json(summary, status_path)
    return summary


def main() -> None:
    args = parse_args()
    _validate_args(args)
    status_path = Path(args.status_path)
    if not status_path.is_absolute():
        status_path = ROOT / status_path
    data_config = load_data_config()
    repo = DuckDBRepository(data_config.duckdb_path, read_only=False)
    if not args.skip_migrations:
        repo.execute_migrations(data_config.migrations_path)
    if args.coverage_only:
        print(
            coverage_report(
                repo,
                args.regions,
                args.start_year,
                args.end_year,
            ).to_string(index=False)
        )
        return
    candidates = select_candidates(
        repo,
        args.regions,
        args.max_symbols_per_region,
    )
    summary = run_backfill(repo, candidates, args, status_path)
    LOGGER.info(
        "Historical fundamentals complete: rows=%s securities=%s failures=%s.",
        summary["rows_written"],
        summary["securities_with_data"],
        summary["failure_count"],
    )
    print(pd.DataFrame(summary["coverage"]).to_string(index=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
