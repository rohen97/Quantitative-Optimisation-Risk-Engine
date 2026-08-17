from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.price_ingestion import load_prices
from src.data.normalisers import normalise_prices

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEFAULT_REGIONS = ("US", "UK", "DACH", "Mainland China", "Hong Kong", "EU ex-DACH")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill model price data for live equity universes into DuckDB.")
    parser.add_argument("--regions", nargs="*", default=list(DEFAULT_REGIONS), help="Universe regions to include.")
    parser.add_argument("--listing-status", nargs="*", default=["Active"], help="Listing statuses to include, e.g. Active Delisted.")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of securities per provider batch.")
    parser.add_argument("--max-symbols", type=int, default=0, help="Optional cap for this run; 0 means no cap.")
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Delay between batches to be gentle with APIs.")
    parser.add_argument("--resume", action="store_true", default=True, help="Skip securities already present in prices_daily.")
    parser.add_argument("--include-delisted", action="store_true", help="Include delisted names as well as active names.")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip DuckDB migrations for faster repeat backfill passes.")
    parser.add_argument("--ignore-skip-list", action="store_true", help="Retry securities even if a previous provider wrote them to the no-data skip list.")
    parser.add_argument(
        "--refresh-missing-volume",
        action="store_true",
        help="Re-fetch securities until they have enough positive-volume observations.",
    )
    parser.add_argument("--minimum-volume-rows", type=int, default=20)
    return parser.parse_args()


def sql_list(values: list[str]) -> str:
    escaped = [value.replace("'", "''") for value in values]
    return ", ".join(f"'{value}'" for value in escaped)


def load_skip_list(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}

def append_skip(path: Path, security_ids: list[str]) -> None:
    if not security_ids:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for security_id in security_ids:
            handle.write(security_id + chr(10))

def load_universe(
    repo: DuckDBRepository,
    regions: list[str],
    statuses: list[str],
    resume: bool,
    max_symbols: int,
    skip_ids: set[str],
    refresh_missing_volume: bool = False,
    minimum_volume_rows: int = 20,
) -> pd.DataFrame:
    query = f"""
        SELECT s.*,
               max(CASE WHEN i.identifier_type = 'bloomberg_ticker' THEN i.identifier_value END) AS bloomberg_ticker,
               max(CASE WHEN i.identifier_type = 'eodhd_ticker' THEN i.identifier_value END) AS eodhd_ticker,
               max(CASE WHEN i.identifier_type = 'yfinance_ticker' THEN i.identifier_value END) AS yfinance_ticker,
               max(CASE WHEN i.identifier_type = 'finnhub_ticker' THEN i.identifier_value END) AS finnhub_ticker,
               max(CASE WHEN i.identifier_type = 'alpha_vantage_ticker' THEN i.identifier_value END) AS alpha_vantage_ticker,
               max(CASE WHEN i.identifier_type = 'alpaca_ticker' THEN i.identifier_value END) AS alpaca_ticker,
               max(CASE WHEN i.identifier_type = 'tickdb_ticker' THEN i.identifier_value END) AS tickdb_ticker,
               max(CASE WHEN i.identifier_type = 'itick_code' THEN i.identifier_value END) AS itick_code,
               max(CASE WHEN i.identifier_type = 'itick_region' THEN i.identifier_value END) AS itick_region
        FROM securities s
        LEFT JOIN security_identifiers i USING (security_id)
        WHERE s.region IN ({sql_list(regions)})
          AND s.listing_status IN ({sql_list(statuses)})
          AND s.instrument_type = 'Equity'
        GROUP BY ALL
        ORDER BY s.region, s.country, s.exchange_code, s.security_id
    """
    universe = repo.query(query)
    universe["ticker"] = universe["security_id"].astype(str)
    universe["currency"] = universe["trading_currency"]
    if resume:
        if refresh_missing_volume:
            existing = repo.query(
                """
                SELECT security_id
                FROM prices_daily
                GROUP BY security_id
                HAVING COUNT(*) FILTER (WHERE volume IS NOT NULL AND volume > 0) >= ?
                """,
                [int(minimum_volume_rows)],
            )
        else:
            existing = repo.query("SELECT DISTINCT security_id FROM prices_daily")
        if not existing.empty:
            completed = set(existing["security_id"].astype(str))
            universe = universe[~universe["security_id"].astype(str).isin(completed)].copy()
    if skip_ids:
        universe = universe[~universe["security_id"].astype(str).isin(skip_ids)].copy()
    if max_symbols and max_symbols > 0:
        universe = universe.head(max_symbols).copy()
    return universe.reset_index(drop=True)


def batches(frame: pd.DataFrame, size: int):
    for start in range(0, len(frame), size):
        yield start, frame.iloc[start : start + size].copy()


def write_prices(repo: DuckDBRepository, prices: pd.DataFrame, source_name: str) -> int:
    if prices.empty:
        return 0
    total = 0
    if "source" not in prices:
        prices = prices.assign(source=source_name)
    for provider_name, provider_rows in prices.groupby("source", sort=False):
        clean = normalise_prices(provider_rows, source=str(provider_name))
        repo.write_table("prices_daily", clean, SCHEMAS["prices_daily"].primary_key)
        total += len(clean)
    return total


def main() -> None:
    args = parse_args()
    statuses = list(args.listing_status)
    if args.include_delisted and "Delisted" not in statuses:
        statuses.append("Delisted")
    data_config = load_data_config()
    repo = DuckDBRepository(data_config.duckdb_path)
    if not args.skip_migrations:
        repo.execute_migrations(data_config.migrations_path)
    skip_filename = "price_volume_backfill_no_data.txt" if args.refresh_missing_volume else "price_backfill_no_data.txt"
    skip_path = Path("data/locks") / skip_filename
    skip_ids = set() if args.ignore_skip_list else load_skip_list(skip_path)
    universe = load_universe(
        repo,
        list(args.regions),
        statuses,
        args.resume,
        args.max_symbols,
        skip_ids,
        refresh_missing_volume=args.refresh_missing_volume,
        minimum_volume_rows=args.minimum_volume_rows,
    )
    logging.info("Starting price backfill for %s securities across regions=%s statuses=%s.", len(universe), args.regions, statuses)
    total_rows = 0
    failed_batches = 0
    for index, batch in batches(universe, max(args.batch_size, 1)):
        label = f"{index + 1}-{index + len(batch)}"
        try:
            prices = load_prices(batch, use_mock=False)
            source_name = str(prices["source"].iloc[0]) if not prices.empty and "source" in prices else "multi_source"
            rows = write_prices(repo, prices, source_name)
            total_rows += rows
            if rows == 0:
                append_skip(skip_path, batch["security_id"].astype(str).tolist())
            else:
                covered = set(prices["ticker"].astype(str)) if "ticker" in prices else set()
                missed = [sid for sid in batch["security_id"].astype(str).tolist() if sid not in covered]
                append_skip(skip_path, missed)
            logging.info("Batch %s wrote %s price rows for %s securities.", label, rows, len(batch))
        except Exception as exc:
            failed_batches += 1
            logging.warning("Batch %s failed for %s securities: %s", label, len(batch), exc)
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
    repo.close()
    logging.info("Price backfill pass complete. Wrote %s rows. Failed batches=%s.", total_rows, failed_batches)


if __name__ == "__main__":
    main()
