from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from src.data_ingestion.free_equity_enrichment import (
    FUNDAMENTALS_SOURCE,
    REFERENCE_SOURCE,
    YahooPublicDataClient,
    build_reference_row,
    enrich_reference_row,
    normalise_reference_rows,
    utc_now,
)
from src.utils.config import ROOT


LOGGER = logging.getLogger(__name__)
DEFAULT_REGIONS = ("US", "UK", "DACH", "EU ex-DACH", "Hong Kong", "Mainland China")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pull free observed equity metadata and annual fundamentals into DuckDB."
    )
    parser.add_argument("mode", choices=["reference", "fundamentals", "all", "status"], nargs="?", default="all")
    parser.add_argument("--regions", nargs="*", default=list(DEFAULT_REGIONS))
    parser.add_argument("--quote-batch-size", type=int, default=200)
    parser.add_argument("--candidates-per-region", type=int, default=250)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--commit-size", type=int, default=20)
    parser.add_argument("--request-interval-seconds", type=float, default=0.0)
    parser.add_argument("--minimum-market-cap-usd", type=float, default=1_000_000_000)
    parser.add_argument("--minimum-daily-value-usd", type=float, default=2_000_000)
    parser.add_argument("--minimum-dividend-yield", type=float, default=0.01)
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument("--force-reference", action="store_true")
    parser.add_argument("--force-fundamentals", action="store_true")
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument(
        "--status-path",
        default="reports/outputs/free_data_enrichment_status.json",
    )
    return parser


def _atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)


def _units_per_usd(repo: DuckDBRepository) -> dict[str, float]:
    frame = repo.query(
        """
        SELECT quote_currency, ARG_MAX(rate, rate_date) AS units_per_usd
        FROM fx_rates
        WHERE base_currency = 'USD' AND rate > 0
        GROUP BY quote_currency
        """
    )
    rates = dict(zip(frame["quote_currency"].astype(str), frame["units_per_usd"].astype(float)))
    rates["USD"] = 1.0
    rates["GBX"] = rates.get("GBP", 0.0) * 100.0
    return rates


def _security_map(
    repo: DuckDBRepository,
    regions: list[str],
    max_symbols: int,
) -> pd.DataFrame:
    frame = repo.query(
        """
        WITH identifiers AS (
            SELECT
                security_id,
                MAX(identifier_value) FILTER (
                    WHERE identifier_type = 'yfinance_ticker'
                ) AS provider_symbol
            FROM security_identifiers
            GROUP BY security_id
        )
        SELECT
            s.security_id,
            s.company_name,
            s.region,
            s.trading_currency,
            i.provider_symbol
        FROM securities s
        JOIN identifiers i USING (security_id)
        WHERE s.listing_status = 'Active'
          AND s.instrument_type = 'Equity'
          AND i.provider_symbol IS NOT NULL
          AND s.region IN (SELECT UNNEST(?))
        ORDER BY s.region, s.security_id
        """,
        [regions],
    )
    if max_symbols > 0:
        frame = (
            frame.assign(_rank=frame.groupby("region").cumcount())
            .sort_values(["_rank", "region"])
            .head(max_symbols)
            .drop(columns="_rank")
        )
    return frame.reset_index(drop=True)


def _existing_reference_ids(repo: DuckDBRepository, as_of_date: pd.Timestamp) -> set[str]:
    frame = repo.query(
        """
        SELECT DISTINCT security_id
        FROM security_reference_snapshots
        WHERE source = ? AND as_of_date = ?
        """,
        [REFERENCE_SOURCE, as_of_date.normalize()],
    )
    return set(frame["security_id"].astype(str))


def _symbol_groups(frame: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in frame.to_dict("records"):
        groups.setdefault(str(row["provider_symbol"]).upper(), []).append(row)
    return groups


def pull_reference_data(
    repo: DuckDBRepository,
    securities: pd.DataFrame,
    units_per_usd: dict[str, float],
    *,
    batch_size: int,
    force: bool,
    status_path: Path,
) -> dict[str, Any]:
    if batch_size <= 0:
        raise ValueError("quote batch size must be positive")
    retrieved_at = utc_now()
    run_id = str(uuid4())
    existing = set() if force else _existing_reference_ids(repo, retrieved_at)
    pending = securities.loc[~securities["security_id"].astype(str).isin(existing)].copy()
    groups = _symbol_groups(pending)
    symbols = list(groups)
    client = YahooPublicDataClient()
    written = 0
    returned_symbols = 0
    failures: list[dict[str, str]] = []
    for start in range(0, len(symbols), batch_size):
        batch = symbols[start : start + batch_size]
        try:
            quotes = client.fetch_quotes(batch)
        except Exception as exc:
            LOGGER.warning("Reference batch %s-%s failed: %s", start + 1, start + len(batch), exc)
            failures.extend({"provider_symbol": symbol, "error": str(exc)} for symbol in batch)
            continue
        quote_by_symbol = {
            str(quote.get("symbol", "")).upper(): quote
            for quote in quotes
            if quote.get("symbol")
        }
        rows: list[dict[str, Any]] = []
        for symbol in batch:
            quote = quote_by_symbol.get(symbol)
            if quote is None:
                failures.append({"provider_symbol": symbol, "error": "quote_not_returned"})
                continue
            returned_symbols += 1
            for security in groups[symbol]:
                rows.append(
                    build_reference_row(
                        security,
                        quote,
                        units_per_usd,
                        retrieved_at=retrieved_at,
                        ingestion_run_id=run_id,
                    )
                )
        clean = normalise_reference_rows(rows)
        repo.write_table(
            "security_reference_snapshots",
            clean,
            SCHEMAS["security_reference_snapshots"].primary_key,
        )
        written += len(clean)
        LOGGER.info(
            "Reference batch %s-%s: requested=%s returned=%s wrote=%s.",
            start + 1,
            start + len(batch),
            len(batch),
            len(quotes),
            len(clean),
        )
        _atomic_json(
            {
                "stage": "reference",
                "status": "running",
                "run_id": run_id,
                "requested_securities": len(pending),
                "processed_provider_symbols": min(start + len(batch), len(symbols)),
                "written_rows": written,
                "failure_count": len(failures),
                "updated_at": utc_now(),
            },
            status_path,
        )
    summary = {
        "stage": "reference",
        "status": "completed",
        "run_id": run_id,
        "requested_securities": len(pending),
        "skipped_securities": len(securities) - len(pending),
        "requested_provider_symbols": len(symbols),
        "returned_provider_symbols": returned_symbols,
        "written_rows": written,
        "failure_count": len(failures),
        "failure_sample": failures[:25],
        "completed_at": utc_now(),
    }
    _atomic_json(summary, status_path)
    return summary


def select_candidates(
    repo: DuckDBRepository,
    regions: list[str],
    *,
    per_region: int,
    minimum_market_cap_usd: float,
    minimum_daily_value_usd: float,
    minimum_dividend_yield: float,
) -> pd.DataFrame:
    return repo.query(
        """
        WITH latest AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id
                    ORDER BY as_of_date DESC, retrieved_at DESC
                ) AS recency_row
            FROM security_reference_snapshots
            WHERE source = ?
        ),
        eligible AS (
            SELECT
                r.*,
                s.region,
                s.country,
                s.trading_currency,
                COALESCE(
                    NULLIF(REGEXP_REPLACE(LOWER(r.company_name), '[^a-z0-9]+', '', 'g'), ''),
                    r.security_id
                ) AS issuer_key,
                0.65 * LN(GREATEST(r.market_cap_usd, 1.0))
                    + 0.35 * LN(GREATEST(r.average_daily_value_usd, 1.0)) AS candidate_score
            FROM latest r
            JOIN securities s USING (security_id)
            WHERE r.recency_row = 1
              AND s.region IN (SELECT UNNEST(?))
              AND r.market_cap_usd >= ?
              AND r.average_daily_value_usd >= ?
              AND r.dividend_yield >= ?
        ),
        issuer_ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY region, issuer_key
                    ORDER BY candidate_score DESC, security_id
                ) AS issuer_row
            FROM eligible
        ),
        region_ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY region
                    ORDER BY candidate_score DESC, security_id
                ) AS region_row
            FROM issuer_ranked
            WHERE issuer_row = 1
        )
        SELECT * EXCLUDE (recency_row, issuer_row)
        FROM region_ranked
        WHERE region_row <= ?
        ORDER BY region, region_row
        """,
        [
            REFERENCE_SOURCE,
            regions,
            float(minimum_market_cap_usd),
            float(minimum_daily_value_usd),
            float(minimum_dividend_yield),
            int(per_region),
        ],
    )


def _completed_profile_ids(repo: DuckDBRepository) -> set[str]:
    frame = repo.query(
        """
        WITH latest AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id
                    ORDER BY as_of_date DESC, retrieved_at DESC
                ) AS recency_row
            FROM security_reference_snapshots
            WHERE source = ?
        )
        SELECT security_id
        FROM latest
        WHERE recency_row = 1
          AND sector IS NOT NULL
          AND industry IS NOT NULL
        """,
        [REFERENCE_SOURCE],
    )
    return set(frame["security_id"].astype(str))


def _completed_fundamental_ids(repo: DuckDBRepository) -> set[str]:
    frame = repo.query(
        """
        SELECT security_id
        FROM fundamentals_reported
        WHERE source = ? AND fiscal_period_type = 'annual'
        GROUP BY security_id
        HAVING COUNT(DISTINCT fiscal_period_end) >= 2
        """,
        [FUNDAMENTALS_SOURCE],
    )
    return set(frame["security_id"].astype(str))


def _candidate_job(
    row: dict[str, Any],
    *,
    fetch_profile: bool,
    fetch_fundamentals: bool,
    units_per_usd: dict[str, float],
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
    request_interval_seconds: float,
) -> tuple[dict[str, Any] | None, pd.DataFrame, list[str]]:
    client = YahooPublicDataClient(minimum_interval_seconds=request_interval_seconds)
    errors: list[str] = []
    reference_row: dict[str, Any] | None = None
    fundamentals = pd.DataFrame(columns=SCHEMAS["fundamentals_reported"].column_names)
    symbol = str(row["provider_symbol"])
    security_id = str(row["security_id"])
    if fetch_profile:
        try:
            base = dict(row)
            base["as_of_date"] = retrieved_at.normalize()
            base["retrieved_at"] = retrieved_at
            base["ingestion_run_id"] = ingestion_run_id
            base["source"] = REFERENCE_SOURCE
            reference_row = enrich_reference_row(
                base,
                client.fetch_summary(symbol),
                units_per_usd,
            )
        except Exception as exc:
            errors.append(f"profile: {exc}")
    if fetch_fundamentals:
        try:
            fundamentals = client.fetch_annual_fundamentals(
                security_id,
                symbol,
                retrieved_at=retrieved_at,
                ingestion_run_id=ingestion_run_id,
            )
            if fundamentals.empty:
                errors.append("fundamentals: no annual rows returned")
        except Exception as exc:
            errors.append(f"fundamentals: {exc}")
    return reference_row, fundamentals, errors


def _flush_candidate_rows(
    repo: DuckDBRepository,
    reference_rows: list[dict[str, Any]],
    fundamental_frames: list[pd.DataFrame],
) -> tuple[int, int]:
    reference_count = 0
    fundamental_count = 0
    if reference_rows:
        reference = normalise_reference_rows(reference_rows)
        repo.write_table(
            "security_reference_snapshots",
            reference,
            SCHEMAS["security_reference_snapshots"].primary_key,
        )
        reference_count = len(reference)
        reference_rows.clear()
    if fundamental_frames:
        fundamentals = pd.concat(fundamental_frames, ignore_index=True)
        repo.write_table(
            "fundamentals_reported",
            fundamentals,
            SCHEMAS["fundamentals_reported"].primary_key,
        )
        fundamental_count = len(fundamentals)
        fundamental_frames.clear()
    return reference_count, fundamental_count


def pull_candidate_fundamentals(
    repo: DuckDBRepository,
    candidates: pd.DataFrame,
    units_per_usd: dict[str, float],
    *,
    workers: int,
    commit_size: int,
    request_interval_seconds: float,
    force: bool,
    status_path: Path,
) -> dict[str, Any]:
    if workers <= 0 or commit_size <= 0:
        raise ValueError("workers and commit size must be positive")
    profile_done = set() if force else _completed_profile_ids(repo)
    fundamentals_done = set() if force else _completed_fundamental_ids(repo)
    jobs: list[tuple[dict[str, Any], bool, bool]] = []
    for row in candidates.to_dict("records"):
        security_id = str(row["security_id"])
        fetch_profile = security_id not in profile_done
        fetch_fundamentals = security_id not in fundamentals_done
        if fetch_profile or fetch_fundamentals:
            jobs.append((row, fetch_profile, fetch_fundamentals))
    retrieved_at = utc_now()
    run_id = str(uuid4())
    reference_rows: list[dict[str, Any]] = []
    fundamental_frames: list[pd.DataFrame] = []
    failures: list[dict[str, Any]] = []
    completed = 0
    reference_written = 0
    fundamental_rows_written = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _candidate_job,
                row,
                fetch_profile=fetch_profile,
                fetch_fundamentals=fetch_fundamentals,
                units_per_usd=units_per_usd,
                retrieved_at=retrieved_at,
                ingestion_run_id=run_id,
                request_interval_seconds=request_interval_seconds,
            ): row
            for row, fetch_profile, fetch_fundamentals in jobs
        }
        for future in as_completed(futures):
            row = futures[future]
            try:
                reference, fundamentals, errors = future.result()
            except Exception as exc:
                reference = None
                fundamentals = pd.DataFrame()
                errors = [f"worker: {exc}"]
            if reference is not None:
                reference_rows.append(reference)
            if not fundamentals.empty:
                fundamental_frames.append(fundamentals)
            if errors:
                failures.append(
                    {
                        "security_id": row["security_id"],
                        "provider_symbol": row["provider_symbol"],
                        "errors": errors,
                    }
                )
            completed += 1
            if completed % commit_size == 0:
                refs, fundamentals_count = _flush_candidate_rows(
                    repo,
                    reference_rows,
                    fundamental_frames,
                )
                reference_written += refs
                fundamental_rows_written += fundamentals_count
                LOGGER.info(
                    "Fundamentals progress: jobs=%s/%s profile_rows=%s statement_rows=%s failures=%s.",
                    completed,
                    len(jobs),
                    reference_written,
                    fundamental_rows_written,
                    len(failures),
                )
                _atomic_json(
                    {
                        "stage": "fundamentals",
                        "status": "running",
                        "run_id": run_id,
                        "candidate_count": len(candidates),
                        "job_count": len(jobs),
                        "completed_jobs": completed,
                        "profile_rows_written": reference_written,
                        "fundamental_rows_written": fundamental_rows_written,
                        "failure_count": len(failures),
                        "updated_at": utc_now(),
                    },
                    status_path,
                )
    refs, fundamentals_count = _flush_candidate_rows(repo, reference_rows, fundamental_frames)
    reference_written += refs
    fundamental_rows_written += fundamentals_count
    summary = {
        "stage": "fundamentals",
        "status": "completed",
        "run_id": run_id,
        "candidate_count": len(candidates),
        "job_count": len(jobs),
        "skipped_count": len(candidates) - len(jobs),
        "profile_rows_written": reference_written,
        "fundamental_rows_written": fundamental_rows_written,
        "failure_count": len(failures),
        "failure_sample": failures[:25],
        "completed_at": utc_now(),
    }
    _atomic_json(summary, status_path)
    return summary


def coverage(repo: DuckDBRepository, regions: list[str]) -> pd.DataFrame:
    return repo.query(
        """
        WITH latest_reference AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY security_id
                    ORDER BY as_of_date DESC, retrieved_at DESC
                ) AS recency_row
            FROM security_reference_snapshots
            WHERE source = ?
        ),
        annual AS (
            SELECT security_id, COUNT(DISTINCT fiscal_period_end) AS annual_periods
            FROM fundamentals_reported
            WHERE source = ? AND fiscal_period_type = 'annual'
            GROUP BY security_id
        )
        SELECT
            s.region,
            COUNT(*) AS active_equities,
            COUNT(r.security_id) AS reference_rows,
            COUNT(*) FILTER (WHERE r.market_cap_usd > 0) AS market_cap_covered,
            COUNT(*) FILTER (WHERE r.average_daily_value_usd > 0) AS liquidity_covered,
            COUNT(*) FILTER (WHERE r.sector IS NOT NULL AND r.industry IS NOT NULL) AS profile_covered,
            COUNT(*) FILTER (WHERE a.annual_periods >= 2) AS fundamentals_covered
        FROM securities s
        LEFT JOIN latest_reference r
          ON r.security_id = s.security_id AND r.recency_row = 1
        LEFT JOIN annual a ON a.security_id = s.security_id
        WHERE s.listing_status = 'Active'
          AND s.instrument_type = 'Equity'
          AND s.region IN (SELECT UNNEST(?))
        GROUP BY s.region
        ORDER BY s.region
        """,
        [REFERENCE_SOURCE, FUNDAMENTALS_SOURCE, regions],
    )


def main() -> None:
    args = _parser().parse_args()
    status_path = Path(args.status_path)
    if not status_path.is_absolute():
        status_path = ROOT / status_path
    data_config = load_data_config()
    repo = DuckDBRepository(data_config.duckdb_path, read_only=False)
    if not args.skip_migrations:
        repo.execute_migrations(data_config.migrations_path)
    if args.mode == "status":
        print(coverage(repo, args.regions).to_string(index=False))
        return
    rates = _units_per_usd(repo)
    securities = _security_map(repo, args.regions, args.max_symbols)
    LOGGER.info("Free-source enrichment universe: %s active equities.", len(securities))
    if args.mode in {"reference", "all"}:
        summary = pull_reference_data(
            repo,
            securities,
            rates,
            batch_size=args.quote_batch_size,
            force=args.force_reference,
            status_path=status_path,
        )
        LOGGER.info("Reference pull complete: %s", summary)
    if args.mode in {"fundamentals", "all"}:
        candidates = select_candidates(
            repo,
            args.regions,
            per_region=args.candidates_per_region,
            minimum_market_cap_usd=args.minimum_market_cap_usd,
            minimum_daily_value_usd=args.minimum_daily_value_usd,
            minimum_dividend_yield=args.minimum_dividend_yield,
        )
        LOGGER.info(
            "Selected %s distinct liquid candidates for observed profiles and annual statements.",
            len(candidates),
        )
        summary = pull_candidate_fundamentals(
            repo,
            candidates,
            rates,
            workers=args.workers,
            commit_size=args.commit_size,
            request_interval_seconds=args.request_interval_seconds,
            force=args.force_fundamentals,
            status_path=status_path,
        )
        LOGGER.info("Fundamentals pull complete: %s", summary)
    report = coverage(repo, args.regions)
    print(report.to_string(index=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
