from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    config = load_data_config()
    repo = DuckDBRepository(config.duckdb_path)
    repo.execute_migrations(config.migrations_path)
    repo.execute_views(config.views_path)
    repo.close()
    logging.info("Initialised DuckDB database at %s", config.duckdb_path)


if __name__ == "__main__":
    main()
