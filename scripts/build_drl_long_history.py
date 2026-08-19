from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtesting.config import load_backtest_config
from src.backtesting.market_data import download_fred_history, download_yfinance_history
from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.drl.long_history import (
    build_long_history_regional_panel,
    convert_regional_benchmarks_to_usd,
    splice_benchmark_prehistory,
)
from src.utils.config import ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the frozen public regional/macro history used only for DRL training."
    )
    parser.add_argument("--download-start", default="1994-01-01")
    parser.add_argument("--panel-start", default="1997-01-31")
    parser.add_argument("--end", default=pd.Timestamp.today().date().isoformat())
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("data/processed/drl/regional_long_history.parquet"),
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=Path("reports/outputs/validation/drl_long_history_manifest.json"),
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    config = load_backtest_config()
    start = pd.Timestamp(args.download_start)
    end = pd.Timestamp(args.end)
    market_config = dict(config["market_data"])
    market_config["refresh_cache"] = bool(args.refresh)
    regional = config["benchmarks"]["regions"]
    prehistory_proxies = {"EU ex-DACH": "^FCHI"}
    symbols = [str(definition["symbol"]) for definition in regional.values()]
    symbols.extend(prehistory_proxies.values())
    fx_definitions = market_config["fx_series"]
    fx_series = {
        str(value)
        for definition in fx_definitions.values()
        for value in (definition.get("primary"), definition.get("pre_euro"))
        if value
    }
    cache_directory = Path(config["backtest"]["cache_directory"])
    bars, price_cache = download_yfinance_history(
        symbols, start, end, market_config, cache_directory
    )
    fred, fred_cache = download_fred_history(
        sorted(fx_series), start, end, market_config, cache_directory
    )
    splice_manifest: list[dict[str, object]] = []
    for region, fallback_symbol in prehistory_proxies.items():
        bars, splice = splice_benchmark_prehistory(
            bars,
            primary_symbol=str(regional[region]["symbol"]),
            fallback_symbol=fallback_symbol,
        )
        splice["region"] = region
        splice_manifest.append(splice)
    usd_bars = convert_regional_benchmarks_to_usd(
        bars, fred, regional, fx_definitions
    )
    missing_regions = sorted(set(regional).difference(usd_bars["region"].astype(str).unique()))
    if missing_regions:
        raise RuntimeError(f"Regional benchmark history is missing: {', '.join(missing_regions)}")
    repository = DuckDBRepository(load_data_config().duckdb_path, read_only=True)
    macro_ids = ["DFF", "FEDFUNDS", "T10Y2Y", "BAMLH0A0HYM2", "BAA10YM", "VIXCLS"]
    try:
        macro = repository.query(
            """
            SELECT series_id, observation_date, available_from, value
            FROM macro_release_vintages
            WHERE series_id IN (SELECT UNNEST(?))
            ORDER BY series_id, observation_date, available_from
            """,
            [macro_ids],
        )
    except Exception:
        macro = pd.DataFrame()
    panel = build_long_history_regional_panel(
        usd_bars,
        macro,
        start_date=args.panel_start,
        end_date=args.end,
    )
    if panel.empty:
        raise RuntimeError("No complete regional long-history panel could be built.")
    output_path = _resolve(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(output_path, index=False)
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "panel_start": panel["date"].min(),
        "panel_end": panel["date"].max(),
        "monthly_observations": int(panel["date"].nunique()),
        "rows": len(panel),
        "regions": sorted(panel["sleeve"].unique()),
        "macro_rows_available": len(macro),
        "panel_sha256": _sha256(output_path),
        "source_cache_sha256": {
            "prices": _sha256(price_cache),
            "fred_fx": _sha256(fred_cache),
        },
        "prehistory_proxies": splice_manifest,
        "evidence_semantics": (
            "Regional index and point-in-time macro proxy used for DRL training only; "
            "it is not historical constituent-level stock evidence."
        ),
    }
    manifest_path = _resolve(args.manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    temporary.replace(manifest_path)
    print(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
