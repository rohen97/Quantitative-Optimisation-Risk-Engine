import pandas as pd

from src.optimisation.objectives import dividend_income_objective, risk_adjusted_return_objective, score_weighted_objective


def _frame():
    return pd.DataFrame(
        {
            "final_recommendation_score": [80, 50],
            "portfolio_fit_score": [80, 50],
            "regime_suitability_score": [80, 50],
            "dividend_safety_score": [80, 40],
            "cashflow_quality_score": [80, 40],
            "balance_sheet_strength_score": [80, 40],
            "tail_risk_score": [10, 80],
            "skewness_risk_score": [10, 80],
            "forecast_uncertainty_score": [20, 80],
            "dividend_cut_probability": [0.05, 0.50],
            "large_drawdown_probability_12m": [0.10, 0.50],
            "reframing_review_required_flag": [False, True],
            "regime_review_required_flag": [False, True],
            "expected_total_return_12m": [0.12, 0.03],
            "expected_volatility_12m": [0.15, 0.35],
            "expected_dividend_return_12m": [0.04, 0.02],
            "dividend_yield": [0.04, 0.02],
            "cvar_5_12m": [-0.10, -0.35],
            "expected_shortfall_5_12m": [-0.12, -0.38],
        }
    )


def test_objectives_rank_safer_higher_quality_name_above_risky_name():
    frame = _frame()
    assert score_weighted_objective(frame).iloc[0] > score_weighted_objective(frame).iloc[1]
    assert risk_adjusted_return_objective(frame).iloc[0] > risk_adjusted_return_objective(frame).iloc[1]
    assert dividend_income_objective(frame).iloc[0] > dividend_income_objective(frame).iloc[1]
