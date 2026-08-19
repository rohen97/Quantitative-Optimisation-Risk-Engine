from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.free_market_adapters import OpenBBMarketDataAdapter
from src.utils.config import ROOT
from src.utils.env import get_env


DEFAULT_SYMBOLS = ("^GSPC", "^DJI", "^FTSE", "^GDAXI", "^STOXX", "000001.SS", "^HSI")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate benchmark normalization through OpenBB without treating it as a source."
    )
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="1997-01-01")
    parser.add_argument("--end", default=pd.Timestamp.today().date().isoformat())
    parser.add_argument("--provider", default=get_env("OPENBB_PROVIDER", "yfinance") or "yfinance")
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=Path("data/external/openbb/benchmark_validation.parquet"),
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("reports/outputs/validation/openbb_benchmark_validation.json"),
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path = _resolve(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        frame = OpenBBMarketDataAdapter(provider=args.provider).load_daily_bars(
            list(args.symbols), start=args.start, end=args.end
        )
        available = not frame.empty
        error = None
    except RuntimeError as exc:
        frame = pd.DataFrame()
        available = False
        error = str(exc)
    summaries = []
    if not frame.empty:
        cache_path = _resolve(args.cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(cache_path, index=False)
        for ticker, rows in frame.groupby("ticker"):
            summaries.append(
                {
                    "ticker": ticker,
                    "rows": len(rows),
                    "start": rows["date"].min(),
                    "end": rows["date"].max(),
                    "positive_volume_rows": int(pd.to_numeric(rows["volume"], errors="coerce").fillna(0).gt(0).sum()),
                }
            )
    missing = sorted(set(args.symbols).difference(frame.get("ticker", pd.Series(dtype=str)).astype(str)))
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass" if available and not missing else "warning" if available else "blocked",
        "provider": args.provider,
        "openbb_role": "normalization_layer_not_independent_source",
        "requested_symbols": list(args.symbols),
        "missing_symbols": missing,
        "summary": summaries,
        "error": error,
    }
    _write_report(args.report_path, payload)
    return 0 if available else 1


if __name__ == "__main__":
    raise SystemExit(main())
