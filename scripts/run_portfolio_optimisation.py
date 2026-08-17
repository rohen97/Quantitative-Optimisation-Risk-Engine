from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import run_full_pipeline
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    """Run the portfolio optimisation outputs using the full mock pipeline inputs."""
    base_config = load_yaml("configs/base.yaml")
    output_dir = ensure_output_dir(base_config)
    outputs = run_full_pipeline(output_dir)
    for key, filename in {
        "optimiser_input_dataset": "optimiser_input_dataset.csv",
        "optimised_portfolio_score_weighted": "optimised_portfolio_score_weighted.csv",
        "optimised_portfolio_risk_parity": "optimised_portfolio_risk_parity.csv",
        "optimised_portfolio_mean_variance": "optimised_portfolio_mean_variance.csv",
        "optimised_portfolio_cvar_constrained": "optimised_portfolio_cvar_constrained.csv",
        "optimised_portfolio_regional_alpha": "optimised_portfolio_regional_alpha.csv",
        "optimised_portfolio_dividend_income": "optimised_portfolio_dividend_income.csv",
        "optimised_portfolio_regime_aware": "optimised_portfolio_regime_aware.csv",
        "portfolio_trade_list": "portfolio_trade_list.csv",
        "portfolio_constraint_report": "portfolio_constraint_report.csv",
        "portfolio_optimisation_summary": "portfolio_optimisation_summary.csv",
    }.items():
        if key in outputs:
            write_csv(outputs[key], output_dir, filename)
    logging.info("Portfolio optimisation completed with %s trade-list rows.", len(outputs.get("portfolio_trade_list", [])))


if __name__ == "__main__":
    main()
