from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.regional_alpha import RegionalAlphaSettings, add_regional_alpha_signals
from src.optimisation.optimisers import regional_alpha_portfolio
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml


LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh the cost-aware regional-alpha challenger without rerunning the full pipeline."
    )
    parser.add_argument("--input", default="optimiser_input_dataset.csv")
    parser.add_argument("--output-directory", default=None)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    output = Path(args.output_directory) if args.output_directory else ensure_output_dir()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = output / input_path
    data = pd.read_csv(input_path, low_memory=False)

    raw = load_yaml("configs/optimisation.yaml").get("optimisation", {})
    method = raw.get("methods", {}).get("regional_alpha", {})
    constraints = {
        **raw.get("constraints", {}),
        "maximum_candidates": int(raw.get("maximum_candidates", 2000)),
        "allow_synthetic_data": str(raw.get("mode", "")).lower() == "mock",
    }
    observed_nav = float(
        pd.to_numeric(data.get("current_market_value_usd"), errors="coerce")
        .fillna(0.0)
        .sum()
    )
    portfolio_nav = float(raw.get("portfolio_nav_usd", observed_nav or 100_000_000.0))
    settings = RegionalAlphaSettings.from_mapping(
        method,
        portfolio_nav_usd=portfolio_nav,
    )
    enriched = add_regional_alpha_signals(data, settings)
    portfolio = regional_alpha_portfolio(enriched, constraints)
    write_csv(
        portfolio,
        output,
        "optimised_portfolio_regional_alpha.csv",
    )
    LOGGER.info(
        "Regional-alpha challenger refreshed: candidates=%s holdings=%s projected_turnover=%.4f.",
        len(enriched),
        int(pd.to_numeric(portfolio["target_weight"], errors="coerce").gt(0).sum()),
        float(pd.to_numeric(portfolio.get("projected_turnover"), errors="coerce").max()),
    )


if __name__ == "__main__":
    main()
