from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.universe import build_universe
from src.data_ingestion.yfinance_adapter import YFinanceMarketDataAdapter
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull Yahoo Finance daily bars through yfinance.")
    parser.add_argument("--symbols", nargs="*", help="Optional yfinance symbols, e.g. AAPL MSFT SAP.DE VOD.L.")
    parser.add_argument("--start", help="Optional start date, YYYY-MM-DD.")
    parser.add_argument("--end", help="Optional end date, YYYY-MM-DD.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_yaml("configs/base.yaml")
    output_dir = ensure_output_dir(config)
    symbols = args.symbols or build_universe(n=int(config.get("mock_data", {}).get("securities", 24)))["ticker"].astype(str).tolist()
    adapter = YFinanceMarketDataAdapter()
    bars = adapter.load_daily_bars(symbols, start=args.start, end=args.end)
    write_csv(bars, output_dir, "yfinance_prices_daily.csv")
    logging.info("Wrote %s yfinance daily bar rows for %s symbols.", len(bars), len(set(symbols)))


if __name__ == "__main__":
    main()
