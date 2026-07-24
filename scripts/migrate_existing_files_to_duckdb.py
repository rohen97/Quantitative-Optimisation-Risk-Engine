from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.config import load_data_config
from src.data.ingestion.fundamentals import ingest_fundamentals
from src.data.ingestion.prices import ingest_prices
from src.data.lineage import calculate_json_hash
from src.data.normalisers import normalise_macro_vintages
from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS
from src.data.validators import validate_schema


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


MIGRATION_FILES = {
    "prices_daily_sample.csv": "prices",
    "yfinance_prices_daily.csv": "prices",
    "features_monthly.csv": "feature_snapshot",
    "current_portfolio_enriched.csv": "portfolio_snapshot",
    "stock_scorecard.csv": "scorecard_snapshot",
    "regime_dashboard_summary.csv": "regime_snapshot",
    "return_distribution_forecasts.csv": "forecast_snapshot",
    "portfolio_risk_report.csv": "risk_snapshot",
    "stress_test_report.csv": "stress_snapshot",
    "drl_target_weights.csv": "drl_snapshot",
    "final_recommendations.csv": "recommendation_snapshot",
}

SEARCH_ROOTS = [Path("reports/outputs"), Path("data"), Path("fixtures")]


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _discover_files() -> list[tuple[Path, str]]:
    discovered: list[tuple[Path, str]] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for filename, dataset_type in MIGRATION_FILES.items():
            for path in root.rglob(filename):
                if "tests" in path.parts or "golden" in path.parts or "excluded" in path.name.lower():
                    continue
                discovered.append((path, dataset_type))
    return discovered


def _register_migration_run(repo: DuckDBRepository, path: Path, dataset_type: str) -> str:
    file_hash = _hash_file(path)
    run_id = f"migration_{dataset_type}_{file_hash[:16]}"
    now = pd.Timestamp.utcnow().tz_localize(None)
    row = pd.DataFrame(
        [
            {
                "ingestion_run_id": run_id,
                "source_name": "legacy_file_migration",
                "dataset_name": dataset_type,
                "started_at": now,
                "completed_at": now,
                "status": "completed",
                "requested_start_date": None,
                "requested_end_date": None,
                "request_parameters_json": json.dumps({"source_file_path": str(path), "dataset_type": dataset_type}, sort_keys=True),
                "row_count": len(pd.read_csv(path)),
                "inserted_count": 0,
                "updated_count": 0,
                "rejected_count": 0,
                "payload_hash": file_hash,
                "config_hash": calculate_json_hash({"source_path": str(path), "dataset_type": dataset_type}),
                "error_message": None,
            }
        ]
    )
    repo.write_table("data_ingestion_runs", row, SCHEMAS["data_ingestion_runs"].primary_key)
    return run_id


def _complete_migration_run(repo: DuckDBRepository, run_id: str, rows_received: int, rows_inserted: int, rows_rejected: int = 0) -> None:
    current = repo.read_table("data_ingestion_runs")
    row = current[current["ingestion_run_id"].astype(str).eq(run_id)].copy()
    if row.empty:
        return
    row.loc[:, "row_count"] = rows_received
    row.loc[:, "inserted_count"] = rows_inserted
    row.loc[:, "updated_count"] = 0
    row.loc[:, "rejected_count"] = rows_rejected
    row.loc[:, "completed_at"] = pd.Timestamp.utcnow().tz_localize(None)
    row.loc[:, "status"] = "completed" if rows_rejected == 0 else "completed_with_rejections"
    repo.write_table("data_ingestion_runs", row[list(SCHEMAS["data_ingestion_runs"].column_names)], SCHEMAS["data_ingestion_runs"].primary_key)


def _feature_snapshot(frame: pd.DataFrame, model_run_id: str, version: str) -> pd.DataFrame:
    if frame.empty or "ticker" not in frame:
        return pd.DataFrame(columns=SCHEMAS["feature_snapshots_monthly"].column_names)
    rows = []
    for _, row in frame.iterrows():
        for column, value in row.items():
            if column == "ticker":
                continue
            numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            if pd.isna(numeric_value):
                continue
            rows.append(
                {
                    "model_run_id": model_run_id,
                    "security_id": str(row["ticker"]).upper(),
                    "as_of_date": pd.Timestamp.today().normalize(),
                    "feature_name": column,
                    "feature_value": float(numeric_value),
                    "feature_text_value": None,
                    "feature_version": version,
                    "calculated_at": pd.Timestamp.utcnow().tz_localize(None),
                }
            )
    return pd.DataFrame(rows)


def _metric_snapshot(frame: pd.DataFrame, model_run_id: str, component: str) -> pd.DataFrame:
    rows = []
    if frame.empty:
        return pd.DataFrame(columns=SCHEMAS["model_metric_snapshots"].column_names)
    for column in frame.columns:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.notna().any():
            rows.append(
                {
                    "model_run_id": model_run_id,
                    "model_component": component,
                    "as_of_date": pd.Timestamp.today().normalize(),
                    "metric_name": column,
                    "metric_value": float(numeric.dropna().mean()),
                    "metric_text_value": None,
                }
            )
    return pd.DataFrame(rows)


def _portfolio_snapshot(frame: pd.DataFrame, model_run_id: str, name: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=SCHEMAS["portfolio_weight_snapshots"].column_names)
    id_col = "security_id" if "security_id" in frame else "ticker" if "ticker" in frame else None
    weight_col = "weight" if "weight" in frame else "target_weight" if "target_weight" in frame else None
    if id_col is None or weight_col is None:
        return pd.DataFrame(columns=SCHEMAS["portfolio_weight_snapshots"].column_names)
    return pd.DataFrame(
        {
            "model_run_id": model_run_id,
            "portfolio_name": name,
            "as_of_date": pd.Timestamp.today().normalize(),
            "security_id": frame[id_col].astype(str).str.upper(),
            "weight": pd.to_numeric(frame[weight_col], errors="coerce").fillna(0.0),
            "market_value_usd": pd.to_numeric(frame.get("market_value_usd", pd.Series([pd.NA] * len(frame))), errors="coerce"),
            "recommendation": frame.get("recommendation", frame.get("final_recommendation", "")),
        }
    )


def main() -> None:
    config = load_data_config()
    repo = DuckDBRepository(config.duckdb_path)
    repo.execute_migrations(config.migrations_path)
    repo.execute_views(config.views_path)
    migrated = 0

    for path, dataset_type in _discover_files():
        frame = pd.read_csv(path)
        run_id = _register_migration_run(repo, path, dataset_type)
        if dataset_type == "prices":
            clean = ingest_prices(frame, source="legacy_file")
            clean["ingestion_run_id"] = run_id
            validate_schema(clean, SCHEMAS["prices_daily"])
            repo.write_table("prices_daily", clean, SCHEMAS["prices_daily"].primary_key)
            _complete_migration_run(repo, run_id, len(frame), len(clean))
            migrated += len(clean)
        elif dataset_type == "feature_snapshot":
            clean = _feature_snapshot(frame, run_id, "legacy_csv")
            validate_schema(clean, SCHEMAS["feature_snapshots_monthly"])
            repo.write_table("feature_snapshots_monthly", clean, SCHEMAS["feature_snapshots_monthly"].primary_key)
            _complete_migration_run(repo, run_id, len(frame), len(clean), max(len(frame) - len(clean), 0))
            migrated += len(clean)
        elif dataset_type in {"scorecard_snapshot", "regime_snapshot", "forecast_snapshot", "risk_snapshot", "stress_snapshot"}:
            clean = _metric_snapshot(frame, run_id, dataset_type)
            validate_schema(clean, SCHEMAS["model_metric_snapshots"])
            repo.write_table("model_metric_snapshots", clean, SCHEMAS["model_metric_snapshots"].primary_key)
            _complete_migration_run(repo, run_id, len(frame), len(clean), max(len(frame) - len(clean), 0))
            migrated += len(clean)
        elif dataset_type in {"portfolio_snapshot", "drl_snapshot", "recommendation_snapshot"}:
            clean = _portfolio_snapshot(frame, run_id, dataset_type)
            if not clean.empty:
                validate_schema(clean, SCHEMAS["portfolio_weight_snapshots"])
            repo.write_table("portfolio_weight_snapshots", clean, SCHEMAS["portfolio_weight_snapshots"].primary_key)
            _complete_migration_run(repo, run_id, len(frame), len(clean), max(len(frame) - len(clean), 0))
            migrated += len(clean)

    macro = pd.DataFrame(
        {
            "series_id": ["wolf_mock_regime"],
            "observation_date": [pd.Timestamp.today().normalize()],
            "vintage_date": [pd.Timestamp.today().normalize()],
            "available_from": [pd.Timestamp.today().normalize()],
            "value": [1.0],
        }
    )
    repo.write_table("macro_observations", normalise_macro_vintages(macro, "mock"), SCHEMAS["macro_observations"].primary_key)
    logging.info("Migrated %s rows into DuckDB at %s", migrated, config.duckdb_path)


if __name__ == "__main__":
    main()
