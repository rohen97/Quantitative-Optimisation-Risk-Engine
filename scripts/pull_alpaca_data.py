from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.alpaca_adapter import (
    ALPACA_PY_AVAILABLE,
    AlpacaMarketDataAdapter,
    AlpacaSdkMarketDataAdapter,
)
from src.data_ingestion.universe import build_universe
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml
from src.utils.env import env_flag


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Alpaca credentials and pull optional daily bars.")
    parser.add_argument("--account", action="store_true", help="Fetch the Alpaca account profile.")
    parser.add_argument("--bars", action="store_true", help="Fetch daily bars for the mock universe tickers.")
    parser.add_argument("--crypto-bars", action="store_true", help="Fetch no-key crypto daily bars through alpaca-py.")
    parser.add_argument("--symbols", nargs="*", help="Optional Alpaca symbols for bars, e.g. AAPL MSFT.")
    parser.add_argument("--start", help="Optional historical start date, YYYY-MM-DD.")
    parser.add_argument("--end", help="Optional historical end date, YYYY-MM-DD.")
    parser.add_argument("--rest", action="store_true", help="Use the REST adapter instead of alpaca-py for stock bars.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.account and not args.bars and not args.crypto_bars:
        args.account = True
    if args.account:
        adapter = AlpacaMarketDataAdapter()
        account = adapter.fetch_account()
        logging.info("Alpaca account connected: id=%s status=%s", account.get("id"), account.get("status"))
    if args.bars:
        config = load_yaml("configs/base.yaml")
        output_dir = ensure_output_dir(config)
        symbols = args.symbols or build_universe(n=int(config.get("mock_data", {}).get("securities", 24)))["ticker"].astype(str).tolist()
        use_sdk = ALPACA_PY_AVAILABLE and env_flag("ALPACA_USE_SDK", True) and not args.rest
        adapter = AlpacaSdkMarketDataAdapter() if use_sdk else AlpacaMarketDataAdapter()
        bars = adapter.load_daily_bars(symbols, start=args.start, end=args.end)
        write_csv(bars, output_dir, "alpaca_prices_daily.csv")
        logging.info("Wrote %s Alpaca stock daily bar rows using %s.", len(bars), "alpaca-py" if use_sdk else "REST")
    if args.crypto_bars:
        config = load_yaml("configs/base.yaml")
        output_dir = ensure_output_dir(config)
        symbols = args.symbols or ["BTC/USD"]
        adapter = AlpacaSdkMarketDataAdapter()
        bars = adapter.load_crypto_daily_bars(symbols, start=args.start, end=args.end)
        write_csv(bars, output_dir, "alpaca_crypto_prices_daily.csv")
        logging.info("Wrote %s no-key Alpaca crypto daily bar rows.", len(bars))


if __name__ == "__main__":
    main()
