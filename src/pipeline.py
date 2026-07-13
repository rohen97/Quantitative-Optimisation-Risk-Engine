from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.alternative_data.alt_features import build_alt_features
from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.mock_data import generate_mock_current_portfolio
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.hedging.hedge_report import build_hedge_recommendations
from src.models.forecasting import generate_mock_forecasts
from src.models.scorecard import build_scorecard
from src.models.targets import HORIZONS_MONTHS
from src.optimisation.portfolio_builder import build_proposed_portfolio
from src.portfolio.portfolio_diagnostics import build_portfolio_diagnostics
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features
from src.reporting.report_writer import write_csv, write_markdown
from src.risk.risk_metrics import build_risk_report
from src.risk.stress_testing import run_stress_tests
from src.utils.config import ensure_output_dir, load_yaml


def run_full_pipeline(output_dir: str | Path | None = None) -> dict[str, pd.DataFrame]:
    config = load_yaml("configs/base.yaml")
    risk_limits = load_yaml("configs/risk_limits.yaml")
    out = Path(output_dir) if output_dir else ensure_output_dir(config)

    universe = build_universe(n=int(config.get("mock_data", {}).get("securities", 24)))
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    mock_portfolio = generate_mock_current_portfolio(universe)
    portfolio = load_current_portfolio(mock_portfolio=mock_portfolio)
    diagnostics, exposures = build_portfolio_diagnostics(portfolio)
    sentiment = build_alt_features(universe)
    regime = build_regime_features(universe)
    features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, regime)
    scorecard = build_scorecard(features, risk_limits)
    proposed = build_proposed_portfolio(portfolio, scorecard)
    risk_report = build_risk_report(prices, portfolio)
    stress_report = run_stress_tests(portfolio)
    hedge_report = build_hedge_recommendations(portfolio)

    write_csv(diagnostics, out, "current_portfolio_diagnostics.csv")
    for name, frame in exposures.items():
        write_csv(frame, out, f"current_portfolio_{name}_exposure.csv")
    write_csv(scorecard, out, "stock_scorecard.csv")
    recommendations = {}
    for horizon in HORIZONS_MONTHS:
        forecast = generate_mock_forecasts(scorecard, horizon)
        recommendations[horizon] = forecast
        write_csv(forecast, out, f"recommendations_{horizon}m.csv")
    write_csv(proposed, out, "proposed_portfolio.csv")
    write_csv(risk_report, out, "portfolio_risk_report.csv")
    write_csv(stress_report, out, "stress_test_report.csv")
    write_csv(hedge_report, out, "hedge_recommendations.csv")
    write_markdown(
        "# Model Validation Report\n\nMVP uses deterministic mock data, rule-based scorecards, placeholder forecasts and walk-forward-ready interfaces.\n",
        out,
        "model_validation_report.md",
    )
    return {
        "portfolio": portfolio,
        "diagnostics": diagnostics,
        "features": features,
        "scorecard": scorecard,
        "proposed_portfolio": proposed,
        "risk_report": risk_report,
        "stress_report": stress_report,
        "hedge_recommendations": hedge_report,
        **{f"recommendations_{h}m": frame for h, frame in recommendations.items()},
    }
