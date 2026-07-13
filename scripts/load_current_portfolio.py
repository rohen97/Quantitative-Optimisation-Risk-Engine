from __future__ import annotations

import logging
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.portfolio.portfolio_diagnostics import build_concentration_summary, build_portfolio_diagnostics
from src.portfolio.portfolio_loader import load_current_portfolio
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load and diagnose the current portfolio.")
    parser.add_argument("--path", default=None, help="CSV or Excel current portfolio path.")
    args = parser.parse_args()

    config = load_yaml("configs/base.yaml")
    output_dir = ensure_output_dir(config)
    portfolio_path = args.path or config.get("current_portfolio_path", "data/external/current_portfolio_template.csv")
    portfolio = load_current_portfolio(portfolio_path)
    diagnostics, exposures = build_portfolio_diagnostics(portfolio)
    concentration = build_concentration_summary(portfolio)

    write_csv(portfolio, output_dir, "current_portfolio_enriched.csv")
    write_csv(diagnostics, output_dir, "current_portfolio_diagnostics.csv")
    write_csv(concentration, output_dir, "concentration_summary.csv")
    for name, frame in exposures.items():
        write_csv(frame, output_dir, f"{name}_exposure.csv")

    logging.info("Loaded portfolio with %s holdings and NAV %.2f.", len(portfolio), portfolio["market_value_usd"].sum())
