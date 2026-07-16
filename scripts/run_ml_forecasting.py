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
from src.models.ml_pipeline import run_ml_forecasting_engine
from src.narrative.pipeline import run_narrative_pipeline
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.pipeline import run_regime_pipeline
from src.regime.regime_classifier import build_regime_features
from src.reporting.report_writer import write_csv, write_markdown
from src.utils.config import ensure_output_dir, load_yaml


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    """Run the mock ML Forecasting & Return Distribution Engine."""
    base_config = load_yaml("configs/base.yaml")
    sentiment_config = load_yaml("configs/sentiment.yaml")
    alternative_data_config = load_yaml("configs/alternative_data.yaml")
    narrative_config = load_yaml("configs/narrative.yaml")
    regime_config = load_yaml("configs/regime.yaml")
    ml_config = load_yaml("configs/ml_forecasting.yaml")
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
    preliminary_features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, build_regime_features(universe))
    regime_outputs = run_regime_pipeline(
        universe,
        prices,
        preliminary_features,
        alt_outputs["alt_features_monthly"],
        narrative_outputs["narrative_reframing_features"],
        regime_config,
    )
    regime_columns = [
        "ticker",
        "regime_suitability_score",
        "regime_weight_adjustment",
        "regime_review_required_flag",
        "regime_exclusion_flag",
        "dominant_regime",
        "regime_risk_score",
        "regime_deterioration_probability",
    ]
    features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, regime_outputs["regime_suitability_scores"][regime_columns])
    outputs = run_ml_forecasting_engine(features, prices, regime_outputs["regime_dashboard_summary"], ml_config)
    for key, filename in {
        "ml_forecasts_3m": "ml_forecasts_3m.csv",
        "ml_forecasts_6m": "ml_forecasts_6m.csv",
        "ml_forecasts_9m": "ml_forecasts_9m.csv",
        "ml_forecasts_12m": "ml_forecasts_12m.csv",
        "return_distribution_forecasts": "return_distribution_forecasts.csv",
        "dividend_cut_probability": "dividend_cut_probability.csv",
        "drawdown_probability": "drawdown_probability.csv",
        "model_registry": "model_registry.csv",
        "probabilistic_validation": "probabilistic_validation.csv",
        "var_es_backtest_report": "var_es_backtest_report.csv",
        "distribution_sensitivity_analysis": "distribution_sensitivity_analysis.csv",
        "distribution_trading_research_signals": "distribution_trading_research_signals.csv",
        "distribution_research_extension_points": "distribution_research_extension_points.csv",
    }.items():
        write_csv(outputs[key], output_dir, filename)
    write_markdown(outputs["model_validation_report"], output_dir, "model_validation_report.md")
    logging.info("ML forecasting engine completed for %s securities.", len(outputs["ml_features"]))


if __name__ == "__main__":
    main()
