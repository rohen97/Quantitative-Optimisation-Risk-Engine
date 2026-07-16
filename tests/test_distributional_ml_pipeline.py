from pathlib import Path

from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.models.ml_pipeline import run_ml_forecasting_engine
from src.pipeline import run_full_pipeline
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features


def _inputs():
    universe = build_universe(n=8)
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    sentiment = universe[["security_id", "ticker"]].copy()
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, build_regime_features(universe))
    return universe, prices, features


def test_distributional_ml_pipeline_outputs_all_horizons_and_reports():
    universe, prices, features = _inputs()
    outputs = run_ml_forecasting_engine(features, prices)
    for horizon in [3, 6, 9, 12]:
        key = f"ml_forecasts_{horizon}m"
        assert key in outputs
        frame = outputs[key]
        assert frame["horizon_months"].eq(horizon).all()
        assert {"distribution_name", "distribution_mu", "distribution_sigma", "distribution_nu", "distribution_xi"}.issubset(frame.columns)
        assert frame["ml_expected_risk_adjusted_score"].between(0, 100).all()
    assert "probabilistic_validation" in outputs
    assert "var_es_backtest_report" in outputs
    assert "distribution_sensitivity_analysis" in outputs
    assert "distribution_trading_research_signals" in outputs
    assert "India" not in set(universe["region"])


def test_full_pipeline_writes_distributional_outputs(tmp_path):
    outputs = run_full_pipeline(tmp_path)
    assert "distribution_mu_12m" in outputs["scorecard"].columns
    assert "tail_risk_score" in outputs["scorecard"].columns
    assert "portfolio_distribution_improvement_score" in outputs["recommendations_portfolio_aware"].columns
    assert (Path(tmp_path) / "probabilistic_validation.csv").exists()
    assert (Path(tmp_path) / "var_es_backtest_report.csv").exists()
    assert (Path(tmp_path) / "distribution_sensitivity_analysis.csv").exists()
