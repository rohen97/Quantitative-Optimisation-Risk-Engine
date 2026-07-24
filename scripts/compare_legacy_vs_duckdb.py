from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.comparison.backend_shadow_compare import compare_legacy_and_duckdb_frames
from src.data.config import load_data_config
from src.data.repository.duckdb_repository import DuckDBRepository
from src.reporting.report_writer import write_csv, write_markdown
from src.utils.config import ensure_output_dir


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


COMPARISON_TARGETS = {
    "price_inputs": ("prices_daily_sample.csv", "prices_daily"),
    "point_in_time_fundamentals": ("stock_scorecard.csv", "point_in_time_fundamentals"),
    "feature_snapshots": ("features_monthly.csv", "feature_snapshots_monthly"),
    "stock_scorecard": ("stock_scorecard.csv", "model_metric_snapshots"),
    "regime_outputs": ("regime_dashboard_summary.csv", "model_metric_snapshots"),
    "ml_forecasts": ("return_distribution_forecasts.csv", "model_metric_snapshots"),
    "optimiser_weights": ("portfolio_optimisation_summary.csv", "portfolio_weight_snapshots"),
    "risk_report": ("portfolio_risk_report.csv", "model_metric_snapshots"),
    "drl_target_weights": ("drl_target_weights.csv", "portfolio_weight_snapshots"),
    "final_recommendations": ("final_recommendations.csv", "portfolio_weight_snapshots"),
}


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _summary_markdown(comparison: pd.DataFrame) -> str:
    total = len(comparison)
    matched = int(comparison.get("matched", pd.Series(dtype=bool)).fillna(False).sum())
    lines = [
        "# Data Backend Comparison Summary",
        "",
        f"- Frames compared: {total}",
        f"- Matched frames: {matched}",
        f"- Differing frames: {total - matched}",
        "",
        "This report compares legacy CSV outputs with DuckDB-backed tables where both are available.",
    ]
    return "\n".join(lines)


def main() -> None:
    config = load_data_config()
    output_dir = ensure_output_dir()
    legacy: dict[str, pd.DataFrame] = {}
    duck: dict[str, pd.DataFrame] = {}
    repo = DuckDBRepository(config.duckdb_path)
    for name, (csv_name, table_name) in COMPARISON_TARGETS.items():
        legacy[name] = _read_csv(output_dir / csv_name)
        duck[name] = repo.read_table(table_name)
    comparison = compare_legacy_and_duckdb_frames(legacy, duck, config)
    write_csv(comparison, output_dir, "data_backend_comparison.csv")
    write_csv(comparison, output_dir, "backend_shadow_comparison.csv")
    write_markdown(_summary_markdown(comparison), output_dir, "data_backend_comparison_summary.md")
    logging.info("Wrote backend data comparison with %s rows.", len(comparison))


if __name__ == "__main__":
    main()
