from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.ingestion.fundamentals import ingest_fundamentals
from src.data.ingestion.prices import ingest_prices
from src.data.repository.duckdb_repository import DUCKDB_AVAILABLE, DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.utils.config import ensure_output_dir
from src.utils.env import env_flag

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


SECURITIES_COLUMNS = [
    "security_id",
    "company_name",
    "instrument_type",
    "listing_status",
    "exchange_code",
    "country",
    "region",
    "sector",
    "industry",
    "trading_currency",
    "domicile_currency",
    "first_seen_at",
    "last_seen_at",
    "source",
]

IDENTIFIER_COLUMNS = ["eodhd_ticker", "yfinance_ticker", "finnhub_ticker", "alpha_vantage_ticker", "alpaca_ticker", "tickdb_ticker", "itick_code", "itick_region", "isin"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run equity universe, price, and fundamental ingestion.")
    parser.add_argument("--universe-only", action="store_true", help="Only pull and persist active/delisted equity universe symbols.")
    return parser.parse_args()


def build_identifier_frame(universe: pd.DataFrame) -> pd.DataFrame:
    retrieved_at = pd.Timestamp.utcnow().tz_localize(None)
    frames = []
    for column in IDENTIFIER_COLUMNS:
        if column not in universe:
            continue
        frame = universe[["security_id", column]].dropna().copy()
        frame[column] = frame[column].astype(str).str.strip()
        frame = frame[frame[column].ne("") & frame[column].ne("<NA")]
        if frame.empty:
            continue
        frame = frame.rename(columns={column: "identifier_value"})
        frame["identifier_type"] = column
        frame["valid_from"] = pd.Timestamp("1900-01-01")
        frame["valid_to"] = pd.NaT
        frame["source"] = "eodhd" if column in {"eodhd_ticker", "isin"} else column.replace("_ticker", "")
        frame["retrieved_at"] = retrieved_at
        frames.append(frame[["security_id", "identifier_type", "identifier_value", "valid_from", "valid_to", "source", "retrieved_at"]])
    return pd.concat(frames, ignore_index=True).drop_duplicates() if frames else pd.DataFrame(columns=SCHEMAS["security_identifiers"].column_names)


def write_universe_to_duckdb(data_config, universe: pd.DataFrame) -> None:
    if not (data_config.dual_write_duckdb or data_config.mode in {"duckdb", "shadow"}):
        logging.info("DuckDB write skipped because backend mode is %s and dual-write is disabled.", data_config.mode)
        return
    if not DUCKDB_AVAILABLE:
        raise RuntimeError("DuckDB backend selected but duckdb is not installed.")
    repo = DuckDBRepository(data_config.duckdb_path)
    repo.execute_migrations(data_config.migrations_path)
    repo.execute_views(data_config.views_path)
    if not all(column in universe.columns for column in SECURITIES_COLUMNS):
        missing = [column for column in SECURITIES_COLUMNS if column not in universe.columns]
        raise ValueError(f"Universe is missing DuckDB securities columns: {missing}")
    repo.write_table("securities", universe[SECURITIES_COLUMNS], SCHEMAS["securities"].primary_key)
    identifiers = build_identifier_frame(universe)
    repo.write_table("security_identifiers", identifiers, SCHEMAS["security_identifiers"].primary_key)
    repo.close()
    logging.info("Wrote %s securities and %s identifiers to DuckDB at %s.", len(universe), len(identifiers), data_config.duckdb_path)


def main() -> None:
    args = parse_args()
    data_config = load_data_config()
    use_mock = env_flag("USE_MOCK_DATA", True)
    output_dir = ensure_output_dir()
    universe = build_universe(use_mock=use_mock)
    universe_path = output_dir / "equity_universe.csv"
    universe.to_csv(universe_path, index=False)
    logging.info("Ingested %s securities. Universe written to %s.", len(universe), universe_path)
    write_universe_to_duckdb(data_config, universe)

    if args.universe_only:
        return

    # Vendor fundamentals are still scaffolded; keep model inputs usable while
    # live universe and price ingestion are brought online.
    fundamentals = load_fundamentals(universe, use_mock=True)
    prices = load_prices(universe, use_mock=use_mock)
    logging.info("Ingested %s price rows and %s fundamental rows.", len(prices), len(fundamentals))

    if data_config.dual_write_duckdb or data_config.mode in {"duckdb", "shadow"}:
        source_name = "mock" if use_mock else "eodhd"
        repo = DuckDBRepository(data_config.duckdb_path)
        repo.execute_migrations(data_config.migrations_path)
        repo.execute_views(data_config.views_path)
        repo.write_table("prices_daily", ingest_prices(prices, source_name), SCHEMAS["prices_daily"].primary_key)
        repo.write_table("fundamentals_reported", ingest_fundamentals(fundamentals, "mock"), SCHEMAS["fundamentals_reported"].primary_key)
        repo.close()
        logging.info("Wrote price and fundamental frames to DuckDB at %s", data_config.duckdb_path)


if __name__ == "__main__":
    main()
