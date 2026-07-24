from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data.snapshot_builder import build_feature_snapshot


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    config = load_data_config()
    features_path = Path("reports/outputs/features_monthly.csv")
    if not features_path.exists():
        raise FileNotFoundError("reports/outputs/features_monthly.csv is required before building snapshots.")
    features = pd.read_csv(features_path)
    snapshot_id, snapshot = build_feature_snapshot(features, pd.Timestamp.today().normalize(), config.mode)
    repo = DuckDBRepository(config.duckdb_path)
    repo.execute_migrations(config.migrations_path)
    repo.write_table("feature_snapshots_monthly", snapshot, SCHEMAS["feature_snapshots_monthly"].primary_key)
    repo.close()
    logging.info("Built feature snapshot %s with %s rows.", snapshot_id, len(snapshot))


if __name__ == "__main__":
    main()
