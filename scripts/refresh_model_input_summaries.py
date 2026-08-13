from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.model_input_summaries import price_summary_status, refresh_price_summaries
from src.data.repository.duckdb_repository import DuckDBRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh bounded-memory summaries used by full-universe model queries."
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-migrations", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_data_config()
    repository = DuckDBRepository(config.duckdb_path)
    if not args.skip_migrations:
        repository.execute_migrations(config.migrations_path)
    before = price_summary_status(repository)
    if before.fresh and not args.force:
        print(json.dumps({"status": "fresh", **before.__dict__}, indent=2, default=str))
        return 0
    result = refresh_price_summaries(repository)
    after = price_summary_status(repository)
    print(
        json.dumps(
            {"status": "refreshed", **result, "fresh": after.fresh},
            indent=2,
            default=str,
        )
    )
    return 0 if after.fresh else 2


if __name__ == "__main__":
    raise SystemExit(main())
