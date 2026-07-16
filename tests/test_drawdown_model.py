import pandas as pd

from src.models.drawdown_model import estimate_drawdown_probability


def test_high_volatility_and_chaos_increase_drawdown_probability():
    features = pd.DataFrame(
        {
            "ticker": ["LOW", "HIGH"],
            "volatility_1y": [0.12, 0.45],
            "beta_local_market": [0.7, 1.5],
            "max_drawdown_1y": [-0.05, -0.35],
            "downside_volatility": [0.08, 0.35],
            "liquidity_stress_score": [10, 90],
            "risk_reframing_score": [20, 90],
        }
    )
    regime = pd.DataFrame([{"wolf_chaos_index": 85, "high_chaos_probability": 0.80}])
    output = estimate_drawdown_probability(features, regime)
    assert output["large_drawdown_probability_12m"].between(0, 1).all()
    assert output.loc[output["ticker"].eq("HIGH"), "large_drawdown_probability_12m"].iloc[0] > output.loc[
        output["ticker"].eq("LOW"), "large_drawdown_probability_12m"
    ].iloc[0]
