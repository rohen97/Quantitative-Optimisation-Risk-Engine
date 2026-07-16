from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.alternative_data.alt_features import run_alternative_data_pipeline
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
from src.models.ml_pipeline import run_ml_forecasting_engine
from src.models.scorecard import build_scorecard
from src.models.targets import HORIZONS_MONTHS
from src.narrative.pipeline import run_narrative_pipeline
from src.optimisation.portfolio_builder import build_proposed_portfolio
from src.portfolio.portfolio_diagnostics import build_concentration_summary, build_portfolio_diagnostics
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features
from src.regime.pipeline import run_regime_pipeline
from src.reporting.report_writer import write_csv, write_markdown
from src.risk.risk_metrics import build_risk_report
from src.risk.stress_testing import run_stress_tests
from src.utils.config import ensure_output_dir, load_yaml


REGIME_FEATURE_COLUMNS = [
    "ticker",
    "regime_suitability_score",
    "regime_weight_adjustment",
    "regime_review_required_flag",
    "regime_exclusion_flag",
    "dominant_regime",
    "regime_risk_score",
    "regime_deterioration_probability",
]


def run_full_pipeline(output_dir: str | Path | None = None) -> dict[str, pd.DataFrame]:
    config = load_yaml("configs/base.yaml")
    branch_config = load_yaml("configs/branching.yaml")
    risk_limits = load_yaml("configs/risk_limits.yaml")
    sentiment_config = load_yaml("configs/sentiment.yaml")
    alternative_data_config = load_yaml("configs/alternative_data.yaml")
    narrative_config = load_yaml("configs/narrative.yaml")
    regime_config = load_yaml("configs/regime.yaml")
    ml_config = load_yaml("configs/ml_forecasting.yaml")
    out = Path(output_dir) if output_dir else ensure_output_dir(config)

    universe = build_universe(n=int(config.get("mock_data", {}).get("securities", 24)))
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    portfolio = load_current_portfolio(config.get("current_portfolio_path", "data/external/current_portfolio_template.csv"))
    diagnostics, exposures = build_portfolio_diagnostics(portfolio)
    concentration = build_concentration_summary(portfolio)
    alt_outputs = run_alternative_data_pipeline(universe, sentiment_config, alternative_data_config)
    narrative_outputs = run_narrative_pipeline(universe, narrative_config)
    sentiment = alt_outputs["alt_features_monthly"].merge(
        narrative_outputs["narrative_reframing_features"],
        on=["security_id", "ticker"],
        how="left",
    )
    preliminary_regime = build_regime_features(universe)
    preliminary_features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, preliminary_regime)
    regime_outputs = run_regime_pipeline(
        universe,
        prices,
        preliminary_features,
        alt_outputs["alt_features_monthly"],
        narrative_outputs["narrative_reframing_features"],
        regime_config,
    )
    regime = regime_outputs["regime_suitability_scores"][REGIME_FEATURE_COLUMNS]
    features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, regime)
    ml_outputs = run_ml_forecasting_engine(features, prices, regime_outputs["regime_dashboard_summary"], ml_config)
    ml_merge_columns = [
        "ticker",
        "expected_total_return_3m",
        "expected_total_return_6m",
        "expected_total_return_9m",
        "expected_total_return_12m",
        "expected_price_return_3m",
        "expected_price_return_6m",
        "expected_price_return_9m",
        "expected_price_return_12m",
        "expected_dividend_return_3m",
        "expected_dividend_return_6m",
        "expected_dividend_return_9m",
        "expected_dividend_return_12m",
        "expected_volatility_3m",
        "expected_volatility_6m",
        "expected_volatility_9m",
        "expected_volatility_12m",
        "expected_max_drawdown_3m",
        "expected_max_drawdown_6m",
        "expected_max_drawdown_9m",
        "expected_max_drawdown_12m",
        "p5_return_3m",
        "p50_return_3m",
        "p95_return_3m",
        "p5_return_6m",
        "p50_return_6m",
        "p95_return_6m",
        "p5_return_9m",
        "p50_return_9m",
        "p95_return_9m",
        "p5_return_12m",
        "p50_return_12m",
        "p95_return_12m",
        "dividend_cut_probability",
        "large_drawdown_probability_12m",
        "ml_expected_risk_adjusted_score",
        "ml_expected_risk_adjusted_return_score",
        "forecast_uncertainty_score",
        "downside_risk_score",
        "upside_potential_score",
        "distribution_name_12m",
        "distribution_mu_12m",
        "distribution_sigma_12m",
        "distribution_nu_12m",
        "distribution_xi_12m",
        "var_5_12m",
        "var_1_12m",
        "cvar_5_12m",
        "cvar_1_12m",
        "expected_shortfall_5_12m",
        "expected_shortfall_1_12m",
        "tail_risk_score",
        "skewness_risk_score",
        "distribution_model_confidence",
    ]
    features = features.merge(ml_outputs["ml_features"][ml_merge_columns], on="ticker", how="left")
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
    stress_report = run_stress_tests(portfolio, regime_outputs["regime_dashboard_summary"])
    hedge_report = build_hedge_recommendations(portfolio, regime_outputs["regime_dashboard_summary"])

    write_csv(diagnostics, out, "current_portfolio_diagnostics.csv")
    write_csv(portfolio, out, "current_portfolio_enriched.csv")
    write_csv(concentration, out, "concentration_summary.csv")
    for name, frame in exposures.items():
        write_csv(frame, out, f"{name}_exposure.csv")
    for filename, frame in {
        "alt_text_documents.csv": alt_outputs["alt_text_documents"],
        "alt_entity_mentions.csv": alt_outputs["alt_entity_mentions"],
        "alt_sentiment_scores.csv": alt_outputs["alt_sentiment_scores"],
        "alt_event_signals.csv": alt_outputs["alt_event_signals"],
        "alt_features_monthly.csv": alt_outputs["alt_features_monthly"],
    }.items():
        write_csv(frame, out, filename)
    for filename, frame in {
        "narrative_concepts.csv": narrative_outputs["narrative_concepts"],
        "narrative_frames.csv": narrative_outputs["narrative_frames"],
        "narrative_semantic_distances.csv": narrative_outputs["narrative_semantic_distances"],
        "narrative_markov_transitions.csv": narrative_outputs["narrative_markov_transitions"],
        "narrative_reframing_features.csv": narrative_outputs["narrative_reframing_features"],
    }.items():
        write_csv(frame, out, filename)
    for filename, frame in {
        "regime_features.csv": regime_outputs["regime_features"],
        "factor_regime_probabilities.csv": regime_outputs["factor_regime_probabilities"],
        "chaos_regime_probabilities.csv": regime_outputs["chaos_regime_probabilities"],
        "informational_driver_model.csv": regime_outputs["informational_driver_model"],
        "regime_transition_matrix.csv": regime_outputs["regime_transition_matrix"],
        "regime_suitability_scores.csv": regime_outputs["regime_suitability_scores"],
        "regime_dashboard_summary.csv": regime_outputs["regime_dashboard_summary"],
    }.items():
        write_csv(frame, out, filename)
    for filename, frame in {
        "ml_forecasts_3m.csv": ml_outputs["ml_forecasts_3m"],
        "ml_forecasts_6m.csv": ml_outputs["ml_forecasts_6m"],
        "ml_forecasts_9m.csv": ml_outputs["ml_forecasts_9m"],
        "ml_forecasts_12m.csv": ml_outputs["ml_forecasts_12m"],
        "return_distribution_forecasts.csv": ml_outputs["return_distribution_forecasts"],
        "dividend_cut_probability.csv": ml_outputs["dividend_cut_probability"],
        "drawdown_probability.csv": ml_outputs["drawdown_probability"],
        "model_registry.csv": ml_outputs["model_registry"],
        "probabilistic_validation.csv": ml_outputs["probabilistic_validation"],
        "var_es_backtest_report.csv": ml_outputs["var_es_backtest_report"],
        "distribution_sensitivity_analysis.csv": ml_outputs["distribution_sensitivity_analysis"],
        "distribution_trading_research_signals.csv": ml_outputs["distribution_trading_research_signals"],
        "distribution_research_extension_points.csv": ml_outputs["distribution_research_extension_points"],
    }.items():
        write_csv(frame, out, filename)
    write_csv(features, out, "features_monthly.csv")
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
    write_markdown(ml_outputs["model_validation_report"], out, "model_validation_report.md")
    return {
        "portfolio": portfolio,
        "diagnostics": diagnostics,
        "concentration": concentration,
        "exposures": pd.concat(exposures, names=["exposure_type"]),
        "features": features,
        **alt_outputs,
        **narrative_outputs,
        **regime_outputs,
        **ml_outputs,
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
