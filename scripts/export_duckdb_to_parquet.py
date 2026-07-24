from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.ingestion.raw_archive import archive_parquet
from src.data.repository.duckdb_repository import DuckDBRepository


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    config = load_data_config()
    repo = DuckDBRepository(config.duckdb_path)
    exported = 0
    for table in ["prices_daily", "fundamentals_reported", "macro_observations", "fx_rates", "feature_snapshots_monthly", "model_runs", "model_outputs"]:
        frame = repo.read_table(table)
        if not frame.empty:
            archive_parquet(frame, config.parquet_root, table, compression=config.parquet_compression)
            exported += 1
    repo.close()
    logging.info("Exported %s DuckDB tables to Parquet under %s.", exported, config.parquet_root)


if __name__ == "__main__":
    main()
