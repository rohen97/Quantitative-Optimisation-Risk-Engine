from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.alpaca_adapter import AlpacaMarketDataAdapter
from src.data_ingestion.universe import build_universe
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Alpaca credentials and pull optional daily bars.")
    parser.add_argument("--account", action="store_true", help="Fetch the Alpaca account profile.")
    parser.add_argument("--bars", action="store_true", help="Fetch daily bars for the mock universe tickers.")
    parser.add_argument("--symbols", nargs="*", help="Optional Alpaca symbols for bars, e.g. AAPL MSFT.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.account and not args.bars:
        args.account = True
    adapter = AlpacaMarketDataAdapter()
    if args.account:
        account = adapter.fetch_account()
        logging.info("Alpaca account connected: id=%s status=%s", account.get("id"), account.get("status"))
    if args.bars:
        config = load_yaml("configs/base.yaml")
        output_dir = ensure_output_dir(config)
        symbols = args.symbols or build_universe(n=int(config.get("mock_data", {}).get("securities", 24)))["ticker"].astype(str).tolist()
        bars = adapter.load_daily_bars(symbols)
        write_csv(bars, output_dir, "alpaca_prices_daily.csv")
        logging.info("Wrote %s Alpaca daily bar rows.", len(bars))


if __name__ == "__main__":
    main()
