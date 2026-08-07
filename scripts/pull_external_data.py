from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DUCKDB_AVAILABLE, DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data_ingestion.multi_source import build_source_status, pull_configured_macro_and_fx
from src.utils.config import ensure_output_dir


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull configured external macro and FX data sources.")
    parser.add_argument("--start", default=None, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", default=None, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--status-only", action="store_true", help="Validate configuration without network calls.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = ensure_output_dir()
    configured = build_source_status()
    configured.to_csv(output_dir / "data_source_status.csv", index=False)
    if args.status_only:
        LOGGER.info("Wrote provider configuration status for %s sources.", len(configured))
        return 0

    result = pull_configured_macro_and_fx(start=args.start, end=args.end)
    result.source_status.to_csv(output_dir / "external_data_pull_status.csv", index=False)
    result.fx_rates.to_csv(output_dir / "external_fx_rates.csv", index=False)
    result.macro_observations.to_csv(output_dir / "external_macro_observations.csv", index=False)
    data_config = load_data_config()
    if DUCKDB_AVAILABLE and (data_config.mode in {"duckdb", "shadow"} or data_config.dual_write_duckdb):
        repo = DuckDBRepository(data_config.duckdb_path)
        repo.execute_migrations(data_config.migrations_path)
        if not result.fx_rates.empty:
            repo.write_table("fx_rates", result.fx_rates, SCHEMAS["fx_rates"].primary_key)
        if not result.macro_observations.empty:
            repo.write_table("macro_observations", result.macro_observations, SCHEMAS["macro_observations"].primary_key)
        repo.close()
        LOGGER.info("Wrote external FX and macro frames to DuckDB at %s.", data_config.duckdb_path)
    failed = int((result.source_status["status"] == "failed").sum()) if not result.source_status.empty else 0
    LOGGER.info(
        "Pulled %s FX rows and %s macro rows; %s datasets failed.",
        len(result.fx_rates),
        len(result.macro_observations),
        failed,
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
