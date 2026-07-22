import numpy as np
import pandas as pd

from src.drl.specialist_agents import (
    credit_stress_action,
    crisis_high_chaos_action,
    inflation_action,
    regional_stress_action,
    stable_low_chaos_action,
)


def _asset_data():
    return pd.DataFrame(
        {
            "ticker": ["AAA", "BBB", "CCC"],
            "sector": ["Utilities", "Technology", "Health Care"],
            "expected_total_return_12m": [0.05, 0.10, 0.04],
            "expected_dividend_return_12m": [0.04, 0.01, 0.035],
            "cashflow_quality_score": [80, 55, 75],
            "dividend_safety_score": [85, 50, 80],
            "current_weight": [0.03, 0.03, 0.03],
            "target_weight": [0.03, 0.05, 0.03],
            "cvar_5_12m": [-0.12, -0.35, -0.16],
            "expected_shortfall_5_12m": [-0.15, -0.40, -0.18],
            "large_drawdown_probability_12m": [0.10, 0.45, 0.15],
            "liquidity_score": [85, 45, 75],
            "leverage_metric": [1.0, 4.0, 1.5],
            "balance_sheet_strength_score": [80, 45, 75],
            "interest_coverage": [10, 2, 8],
            "credit_stress_similarity": [0.05, 0.60, 0.10],
            "valuation_score": [60, 70, 50],
            "dividend_yield": [0.04, 0.01, 0.035],
            "regime_suitability_score": [85, 40, 80],
        }
    )


def test_specialist_actions_are_bounded_continuous_vectors():
    data = _asset_data()
    for fn in [stable_low_chaos_action, crisis_high_chaos_action, inflation_action, regional_stress_action, credit_stress_action]:
        action = fn(data, scale=0.01)
        assert action.shape == (3,)
        assert action.dtype.kind == "f"
        assert np.abs(action).max() <= 0.011


def test_stable_and_crisis_specialists_prefer_different_risk_profiles():
    data = _asset_data()
    stable = stable_low_chaos_action(data, scale=0.01)
    crisis = crisis_high_chaos_action(data, scale=0.01)
    assert not np.allclose(stable, crisis)
    assert crisis[0] > crisis[1]
