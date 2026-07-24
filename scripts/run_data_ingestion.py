from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.data.config import load_data_config
from src.data.ingestion.fundamentals import ingest_fundamentals
from src.data.ingestion.prices import ingest_prices
from src.data.repository.duckdb_repository import DUCKDB_AVAILABLE, DuckDBRepository
from src.data.schemas import SCHEMAS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    data_config = load_data_config()
    universe = build_universe()
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    logging.info("Ingested %s securities, %s price rows, %s fundamental rows.", len(universe), len(prices), len(fundamentals))
    if data_config.dual_write_duckdb or data_config.mode in {"duckdb", "shadow"}:
        if not DUCKDB_AVAILABLE:
            logging.warning("DuckDB unavailable; skipping dual-write and keeping legacy CSV mode operational.")
        else:
            repo = DuckDBRepository(data_config.duckdb_path)
            repo.execute_migrations(data_config.migrations_path)
            repo.execute_views(data_config.views_path)
            repo.write_table("prices_daily", ingest_prices(prices, "mock"), SCHEMAS["prices_daily"].primary_key)
            repo.write_table("fundamentals_reported", ingest_fundamentals(fundamentals, "mock"), SCHEMAS["fundamentals_reported"].primary_key)
            repo.close()
            logging.info("Dual-wrote ingestion frames to DuckDB at %s", data_config.duckdb_path)
