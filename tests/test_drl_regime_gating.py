import pandas as pd

import numpy as np

from src.drl.policy_ensemble import apply_risk_throttle
from src.drl.regime_gating import (
    blend_specialist_weights,
    calculate_regime_agent_weights,
    calculate_risk_throttle,
    calculate_risk_throttle_from_dashboard,
    map_regime_specialist_probabilities,
)


def test_drl_regime_gating_weights_sum_to_one():
    dashboard = pd.DataFrame([{"crisis_probability": 0.3, "high_chaos_probability": 0.4, "steady_state_probability": 0.2}])
    weights = calculate_regime_agent_weights(dashboard)
    assert round(weights["agent_weight"].sum(), 12) == 1
    assert set(weights["agent"]) == {
        "stable_low_chaos_agent",
        "crisis_high_chaos_agent",
        "inflation_agent",
        "regional_stress_agent",
        "credit_stress_agent",
    }
    assert set(weights["agent_status"]) == {"mvp_active", "future_ready"}


def test_risk_throttle_normal_and_extreme_bands():
    normal = calculate_risk_throttle(20, 0.05, 0.05, 0.10, 0.05)
    extreme = calculate_risk_throttle(90, 0.20, 0.10, 0.10, 0.10)
    assert normal.action_scale == 1.0
    assert not normal.additions_blocked
    assert extreme.fallback_to_baseline
    assert extreme.minimum_cash_weight == 0.20


def test_risk_throttle_from_dashboard_and_blocks_additions():
    throttle = calculate_risk_throttle_from_dashboard(
        pd.DataFrame([{"wolf_chaos_index": 72, "high_chaos_probability": 0.2, "crisis_probability": 0.2}])
    )
    action = apply_risk_throttle(np.array([0.01, -0.02, 0.005]), throttle)
    assert throttle.defensive_only
    assert (action <= 0).all()


def test_specialist_probability_mapping_and_blend():
    dashboard = pd.DataFrame(
        [
            {
                "steady_state_probability": 0.50,
                "low_chaos_probability": 0.40,
                "crisis_probability": 0.10,
                "high_chaos_probability": 0.20,
                "regime_deterioration_probability": 0.20,
            }
        ]
    )
    probs = map_regime_specialist_probabilities(dashboard)
    assert round(sum(probs.values()), 12) == 1
    assert probs["stable_low_chaos_agent"] > probs["crisis_high_chaos_agent"]
    blended = blend_specialist_weights(np.array([0.7, 0.3]), np.array([0.2, 0.8]), 0.75, 0.25)
    assert round(blended.sum(), 12) == 1
    assert blended[0] > blended[1]
