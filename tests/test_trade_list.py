import pandas as pd

from src.optimisation.trade_list import build_trade_list


def test_trade_actions_are_assigned():
    portfolio = pd.DataFrame(
        {
            "security_id": ["S1", "S2", "S3"],
            "ticker": ["BUY", "REDUCE", "HOLD"],
            "company_name": ["Buy", "Reduce", "Hold"],
            "country": ["A", "A", "A"],
            "region": ["R", "R", "R"],
            "sector": ["S", "S", "S"],
            "currency": ["USD", "USD", "USD"],
            "current_weight": [0.0, 0.05, 0.03],
            "target_weight": [0.03, 0.01, 0.031],
            "eligible_for_optimisation": [True, True, True],
            "expected_total_return_12m": [0.1, 0.02, 0.05],
            "expected_dividend_return_12m": [0.03, 0.02, 0.02],
            "p5_return_12m": [-0.1, -0.2, -0.1],
            "var_5_12m": [-0.1, -0.2, -0.1],
            "cvar_5_12m": [-0.12, -0.25, -0.12],
            "expected_shortfall_5_12m": [-0.12, -0.25, -0.12],
            "dividend_cut_probability": [0.1, 0.2, 0.1],
            "large_drawdown_probability_12m": [0.1, 0.2, 0.1],
            "regime_suitability_score": [70, 40, 60],
            "portfolio_fit_score": [70, 40, 60],
            "final_recommendation_score": [80, 40, 60],
            "risk_management_flags": ["", "", ""],
        }
    )
    trades = build_trade_list(portfolio, 100_000_000, threshold=0.0025)
    actions = dict(zip(trades["ticker"], trades["trade_action"]))
    assert actions["BUY"] == "Buy"
    assert actions["REDUCE"] == "Reduce"
    assert actions["HOLD"] == "Hold"
