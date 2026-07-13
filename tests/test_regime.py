from src.data_ingestion.universe import build_universe
from src.regime.regime_rules import build_regime_scores, classify_regime


def test_regime_rules():
    assert classify_regime({"growth_trend": -0.8}) == "Defensive / low growth"
    scores = build_regime_scores(build_universe())
    assert scores["regime_suitability_score"].between(0, 100).all()
