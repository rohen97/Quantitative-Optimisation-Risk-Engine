import pandas as pd

from src.data_ingestion.fundamental_ingestion import load_fundamentals
from src.data_ingestion.price_ingestion import load_prices
from src.data_ingestion.universe import build_universe
from src.features.feature_store import build_feature_store
from src.portfolio.portfolio_loader import load_current_portfolio
from src.regime.regime_classifier import build_regime_features
from src.regime.regime_suitability import build_regime_suitability_scores


def _features():
    universe = build_universe()
    prices = load_prices(universe)
    fundamentals = load_fundamentals(universe)
    sentiment = universe[["security_id", "ticker"]].copy()
    portfolio = load_current_portfolio("data/external/current_portfolio_template.csv")
    return universe, build_feature_store(universe, prices, fundamentals, sentiment, portfolio, build_regime_features(universe))


def test_regime_suitability_scores_are_bounded():
    universe, features = _features()
    dashboard = pd.DataFrame([{"dominant_regime": "steady_state_low_chaos", "regime_risk_score": 35, "regime_deterioration_probability": 0.20}])
    scores = build_regime_suitability_scores(universe, features, dashboard)
    assert scores["regime_suitability_score"].between(0, 100).all()
    assert {"regime_weight_adjustment", "regime_review_required_flag", "regime_exclusion_flag"}.issubset(scores.columns)


def test_regime_suitability_penalizes_china_policy_stress():
    universe, features = _features()
    dashboard = pd.DataFrame([{"dominant_regime": "china_policy_stress", "regime_risk_score": 75, "regime_deterioration_probability": 0.80}])
    scores = build_regime_suitability_scores(universe, features, dashboard)
    china_hk = scores["region"].isin(["Mainland China", "Hong Kong"])
    assert scores.loc[china_hk, "china_policy_stress_suitability_score"].mean() < scores.loc[~china_hk, "china_policy_stress_suitability_score"].mean()
