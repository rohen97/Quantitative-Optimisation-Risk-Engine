from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import run_full_pipeline
from src.data.config import load_data_config
from src.data.lineage import new_model_run_metadata
from src.data.repository.duckdb_repository import DUCKDB_AVAILABLE, DuckDBRepository
from src.reporting.ic_pipeline import run_ic_reporting
from src.utils.config import ensure_output_dir, load_yaml
from src.validation.validation_pipeline import run_validation_pipeline


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


FULL_PIPELINE_STAGES = [
    "Data Ingestion and Point-in-Time Snapshots",
    "Current Portfolio Engine",
    "Feature Store",
    "Sentiment and Alternative Data",
    "Narrative Reframing",
    "Regime Engine",
    "ML and Distributional Forecasting",
    "Conservative Stock Scorecard",
    "Portfolio-Aware Branch",
    "Clean-Sheet Branch",
    "LLM Benchmark Branch",
    "Branch Comparison",
    "Portfolio Optimisation",
    "Risk Engine",
    "Stress Testing",
    "Hedge Recommendations",
    "DRL Overlay",
    "Final Portfolio Resolution",
    "Investment Committee Dashboard and Reporting Engine",
    "Validation and Governance",
]


if __name__ == "__main__":
    started = time.perf_counter()
    data_config = load_data_config()
    logging.info(
        "Data backend mode: %s. CSV/mock fallback remains active unless mode is changed in configs/data.yaml.",
        data_config.mode,
    )
    for index, stage in enumerate(FULL_PIPELINE_STAGES, start=1):
        logging.info("Full pipeline stage %02d: %s", index, stage)
    outputs = run_full_pipeline()
    runtime_seconds = time.perf_counter() - started
    metadata = new_model_run_metadata(
        model_name="wolf_quant_full_pipeline",
        model_version="local",
        backend=data_config.backend,
        mode="dry_run",
        config={"base": load_yaml("configs/base.yaml"), "data": load_yaml("configs/data.yaml")},
        input_snapshot_hash=None,
        repository_root=Path(__file__).resolve().parents[1],
    )
    metadata_row = {**metadata.to_dict(), "status": "completed", "runtime_seconds": runtime_seconds, "output_path": str(ensure_output_dir())}
    pd.DataFrame([metadata_row]).to_csv(ensure_output_dir() / "model_run_lineage.csv", index=False)
    if DUCKDB_AVAILABLE:
        try:
            repo = DuckDBRepository(data_config.duckdb_path, read_only=False)
            repo.execute_migrations(data_config.migrations_path)
            repo.register_model_run(metadata_row)
            repo.complete_model_run(metadata.model_run_id, "completed", output_path=str(ensure_output_dir()))
        except Exception as exc:  # pragma: no cover - lineage must not alter calculations
            logging.warning("Could not register full-pipeline model run in DuckDB: %s", exc)
    ic_bundle = run_ic_reporting()
    logging.info(
        "Investment Committee report generated at %s with readiness=%s",
        ic_bundle.html_path,
        ic_bundle.readiness_status,
    )
    for warning in ic_bundle.warnings:
        logging.warning("IC reporting warning: %s", warning)
    validation_result = run_validation_pipeline(execution_mode="smoke", run_sensitivity=False, run_ablation=False)
    logging.info(
        "Validation completed at %s with approval=%s score=%.1f",
        validation_result.output_directory,
        validation_result.approval_status,
        validation_result.overall_score,
    )
    logging.info("Wolf Quant MVP pipeline completed with %s output frames.", len(outputs))
