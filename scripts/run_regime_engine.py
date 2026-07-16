from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.alternative_data.alt_features import run_alternative_data_pipeline
from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.narrative.pipeline import run_narrative_pipeline
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.pipeline import run_regime_pipeline
from src.regime.regime_classifier import build_regime_features
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    """Run the mock/local regime analysis and market-state engine."""
    base_config = load_yaml("configs/base.yaml")
    sentiment_config = load_yaml("configs/sentiment.yaml")
    alternative_data_config = load_yaml("configs/alternative_data.yaml")
    narrative_config = load_yaml("configs/narrative.yaml")
    regime_config = load_yaml("configs/regime.yaml")
    output_dir = ensure_output_dir(base_config)

    universe = build_universe(n=int(base_config.get("mock_data", {}).get("securities", 24)))
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    portfolio = load_current_portfolio(base_config.get("current_portfolio_path", "data/external/current_portfolio_template.csv"))
    alt_outputs = run_alternative_data_pipeline(universe, sentiment_config, alternative_data_config)
    narrative_outputs = run_narrative_pipeline(universe, narrative_config)
    sentiment = alt_outputs["alt_features_monthly"].merge(
        narrative_outputs["narrative_reframing_features"],
        on=["security_id", "ticker"],
        how="left",
    )
    preliminary_features = build_feature_store(
        universe,
        prices,
        fundamentals,
        sentiment,
        portfolio,
        build_regime_features(universe),
    )
    outputs = run_regime_pipeline(
        universe,
        prices,
        preliminary_features,
        alt_outputs["alt_features_monthly"],
        narrative_outputs["narrative_reframing_features"],
        regime_config,
    )
    filenames = {
        "regime_features": "regime_features.csv",
        "factor_regime_probabilities": "factor_regime_probabilities.csv",
        "chaos_regime_probabilities": "chaos_regime_probabilities.csv",
        "informational_driver_model": "informational_driver_model.csv",
        "regime_transition_matrix": "regime_transition_matrix.csv",
        "regime_suitability_scores": "regime_suitability_scores.csv",
        "regime_dashboard_summary": "regime_dashboard_summary.csv",
    }
    for key, filename in filenames.items():
        write_csv(outputs[key], output_dir, filename)
    logging.info("Regime engine completed with dominant regime %s.", outputs["regime_dashboard_summary"].iloc[0]["dominant_regime"])


if __name__ == "__main__":
    main()
