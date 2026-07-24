from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DUCKDB_AVAILABLE, DuckDBRepository


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    config = load_data_config()
    if config.mode == "legacy_csv":
        logging.info("Data layer mode is legacy_csv; DuckDB validation is optional.")
        return
    if not DUCKDB_AVAILABLE:
        raise RuntimeError("DuckDB selected but duckdb is not installed.")
    repo = DuckDBRepository(config.duckdb_path)
    summary = repo.query("SELECT * FROM data_quality_summary")
    repo.close()
    logging.info("Data quality summary:\n%s", summary.to_string(index=False))


if __name__ == "__main__":
    main()
