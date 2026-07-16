from pathlib import Path

from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.pipeline import run_full_pipeline
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.pipeline import run_regime_pipeline
from src.regime.regime_classifier import build_regime_features


def test_regime_pipeline_returns_required_outputs():
    universe = build_universe()
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    sentiment = universe[["security_id", "ticker"]].copy()
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    features = build_feature_store(universe, prices, fundamentals, sentiment, portfolio, build_regime_features(universe))
    outputs = run_regime_pipeline(universe, prices, features)
    expected = {
        "regime_features",
        "factor_regime_probabilities",
        "chaos_regime_probabilities",
        "informational_driver_model",
        "regime_transition_matrix",
        "regime_suitability_scores",
        "regime_dashboard_summary",
    }
    assert expected == set(outputs)
    assert outputs["regime_suitability_scores"].shape[0] == universe.shape[0]


def test_full_pipeline_writes_regime_outputs(tmp_path):
    outputs = run_full_pipeline(tmp_path)
    assert "regime_suitability_score" in outputs["scorecard"].columns
    assert "dominant_regime" in outputs["scorecard"].columns
    assert (Path(tmp_path) / "regime_dashboard_summary.csv").exists()
    assert (Path(tmp_path) / "regime_suitability_scores.csv").exists()
