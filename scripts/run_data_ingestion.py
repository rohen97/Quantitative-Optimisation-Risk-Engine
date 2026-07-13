from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    universe = build_universe()
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    logging.info("Ingested %s securities, %s price rows, %s fundamental rows.", len(universe), len(prices), len(fundamentals))
