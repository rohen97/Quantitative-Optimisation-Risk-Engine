from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.mock_data import generate_mock_current_portfolio, generate_mock_universe
from src.portfolio.portfolio_loader import load_current_portfolio

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    portfolio = load_current_portfolio(mock_portfolio=generate_mock_current_portfolio(generate_mock_universe()))
    logging.info("Loaded mock portfolio with %s holdings and NAV %.2f.", len(portfolio), portfolio["market_value_usd"].sum())
