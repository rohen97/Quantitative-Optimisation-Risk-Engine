from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.alternative_data.alt_features import build_alt_features
from src.branches.branch_comparison import build_final_recommendations, compare_branches
from src.branches.clean_sheet import run_clean_sheet_branch
from src.branches.llm_benchmark import run_llm_benchmark_branch
from src.branches.portfolio_aware import run_portfolio_aware_branch
from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.hedging.hedge_report import build_hedge_recommendations
from src.models.forecasting import generate_mock_forecasts
from src.models.scorecard import build_scorecard
from src.models.targets import HORIZONS_MONTHS
from src.optimisation.portfolio_builder import build_proposed_portfolio
from src.portfolio.portfolio_diagnostics import build_concentration_summary, build_portfolio_diagnostics
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features
from src.reporting.report_writer import write_csv, write_markdown
from src.risk.risk_metrics import build_risk_report
from src.risk.stress_testing import run_stress_tests
from src.utils.config import ensure_output_dir, load_yaml


def run_full_pipeline(output_dir: str | Path | None = None) -> dict[str, pd.DataFrame]:
    config = load_yaml("configs/base.yaml")
    branch_config = load_yaml("configs/branching.yaml")
    risk_limits = load_yaml("configs/risk_limits.yaml")
    out = Path(output_dir) if output_dir else ensure_output_dir(config)

    universe = build_universe(n=int(config.get("mock_data", {}).get("securities", 24)))
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    portfolio = load_current_portfolio(config.get("current_portfolio_path", "data/external/current_portfolio_template.csv"))
    diagnostics, exposures = build_portfolio_diagnostics(portfolio)
    concentration = build_concentration_summary(portfolio)
    sentiment = build_alt_features(universe)
    regime = build_regime_features(universe)
    features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, regime)
    scorecard = build_scorecard(features, risk_limits)
    risk_report = build_risk_report(prices, portfolio)
    branches = branch_config.get("branches", {})
    portfolio_aware = run_portfolio_aware_branch(diagnostics, scorecard, universe, risk_report)
    clean_sheet = run_clean_sheet_branch(scorecard)
    llm_mode = branches.get("llm_analyst_benchmark", {}).get("mode", "mock")
    llm_benchmark = run_llm_benchmark_branch(scorecard, mode=llm_mode)
    branch_comparison = compare_branches(portfolio_aware, clean_sheet, llm_benchmark)
    final_recommendations = build_final_recommendations(branch_comparison, scorecard)
    proposed = build_proposed_portfolio(portfolio, scorecard)
    stress_report = run_stress_tests(portfolio)
    hedge_report = build_hedge_recommendations(portfolio)

    write_csv(diagnostics, out, "current_portfolio_diagnostics.csv")
    write_csv(portfolio, out, "current_portfolio_enriched.csv")
    write_csv(concentration, out, "concentration_summary.csv")
    for name, frame in exposures.items():
        write_csv(frame, out, f"{name}_exposure.csv")
    write_csv(scorecard, out, "stock_scorecard.csv")
    write_csv(portfolio_aware, out, "recommendations_portfolio_aware.csv")
    write_csv(clean_sheet, out, "recommendations_clean_sheet.csv")
    write_csv(llm_benchmark, out, "recommendations_llm_benchmark.csv")
    write_csv(branch_comparison, out, "branch_comparison_report.csv")
    write_csv(final_recommendations, out, "final_recommendations.csv")
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
        "concentration": concentration,
        "exposures": pd.concat(exposures, names=["exposure_type"]),
        "features": features,
        "scorecard": scorecard,
        "recommendations_portfolio_aware": portfolio_aware,
        "recommendations_clean_sheet": clean_sheet,
        "recommendations_llm_benchmark": llm_benchmark,
        "branch_comparison_report": branch_comparison,
        "final_recommendations": final_recommendations,
        "proposed_portfolio": proposed,
        "risk_report": risk_report,
        "stress_report": stress_report,
        "hedge_recommendations": hedge_report,
        **{f"recommendations_{h}m": frame for h, frame in recommendations.items()},
    }
