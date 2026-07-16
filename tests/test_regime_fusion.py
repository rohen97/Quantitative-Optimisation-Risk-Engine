import pandas as pd

from src.regime.regime_fusion import fuse_regime_signals


def test_regime_fusion_identifies_crisis_high_chaos():
    factor = pd.DataFrame(
        [
            {
                "crisis_probability": 0.75,
                "steady_state_probability": 0.10,
                "inflation_probability": 0.05,
                "walking_on_ice_probability": 0.10,
                "dominant_factor_regime": "crisis",
                "factor_regime_confidence": 0.75,
            }
        ]
    )
    chaos = pd.DataFrame(
        [
            {
                "low_chaos_probability": 0.05,
                "intermediate_chaos_probability": 0.15,
                "high_chaos_probability": 0.80,
                "dominant_chaos_regime": "high_chaos",
                "chaos_regime_confidence": 0.80,
                "wolf_chaos_index": 88,
            }
        ]
    )
    drivers = pd.DataFrame(
        [
            {
                "regime_deterioration_probability": 0.80,
                "top_driver_1": "credit_stress_news",
                "top_driver_2": "policy_uncertainty",
                "top_driver_3": "macro_news_uncertainty",
            }
        ]
    )
    dashboard = fuse_regime_signals(factor, chaos, drivers)
    assert dashboard["dominant_regime"].iloc[0] == "crisis_high_chaos"
    assert dashboard["regime_risk_score"].iloc[0] > 70
