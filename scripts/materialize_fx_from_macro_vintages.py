from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.fx_materialization import materialize_fx_rates_from_macro_vintages
from src.data.repository.duckdb_repository import DuckDBRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize PIT-safe USD FX rates from stored FRED macro vintages."
    )
    parser.add_argument("--skip-migrations", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_data_config()
    repository = DuckDBRepository(config.duckdb_path)
    if not args.skip_migrations:
        repository.execute_migrations(config.migrations_path)
    result = materialize_fx_rates_from_macro_vintages(repository)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
