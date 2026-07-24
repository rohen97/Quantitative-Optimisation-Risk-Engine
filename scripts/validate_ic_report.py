from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reporting.config import load_reporting_config


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


if __name__ == "__main__":
    cfg = load_reporting_config()
    required = [
        cfg.latest_folder / "investment_committee_report.html",
        cfg.latest_folder / "investment_committee_report.md",
        cfg.latest_folder / "investment_committee_summary.md",
        cfg.latest_folder / "manifest.json",
        cfg.latest_folder / "report_manifest.json",
        cfg.latest_folder / "report_bundle.json",
        cfg.latest_folder / "report_data_quality.csv",
        cfg.latest_folder / "executive_summary.csv",
        cfg.latest_folder / "final_portfolio_weights.csv",
        cfg.latest_folder / "data_quality_report.csv",
        cfg.latest_folder / "current_vs_target_holdings.csv",
        cfg.latest_folder / "sector_exposures.csv",
        cfg.latest_folder / "country_exposures.csv",
        cfg.latest_folder / "region_exposures.csv",
        cfg.latest_folder / "currency_exposures.csv",
        cfg.latest_folder / "concentration_summary.csv",
        cfg.latest_folder / "final_trade_recommendations.csv",
        cfg.latest_folder / "model_branch_comparison.csv",
        cfg.latest_folder / "forecast_horizon_summary.csv",
        cfg.latest_folder / "security_forecast_summary.csv",
        cfg.latest_folder / "regime_summary.csv",
        cfg.latest_folder / "portfolio_risk_summary.csv",
        cfg.latest_folder / "top_risk_contributors.csv",
        cfg.latest_folder / "stress_scenario_summary.csv",
        cfg.latest_folder / "hedge_summary.csv",
        cfg.latest_folder / "defensive_substitution_summary.csv",
        cfg.latest_folder / "drl_governance_summary.csv",
        cfg.latest_folder / "drl_constraint_trace.csv",
        cfg.latest_folder / "drl_seed_summary.csv",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing IC report files: {missing}")
    logging.info("IC report validation passed for %s", cfg.latest_folder)
