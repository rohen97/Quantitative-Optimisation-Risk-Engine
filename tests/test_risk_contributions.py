import pandas as pd

from src.risk.risk_contributions import build_risk_contribution_report


def test_risk_contributions_are_created_and_ranked():
    portfolio = pd.DataFrame(
        {
            "security_id": ["S1", "S2"],
            "ticker": ["A", "B"],
            "company_name": ["A", "B"],
            "target_weight": [0.5, 0.5],
            "current_weight": [0.4, 0.6],
            "sector": ["Healthcare", "Industrials"],
            "country": ["UK", "Germany"],
            "region": ["UK", "DACH"],
            "currency": ["GBP", "EUR"],
            "expected_total_return_12m": [0.08, 0.04],
            "dividend_yield": [0.03, 0.04],
            "expected_volatility_12m": [0.15, 0.25],
            "var_5_12m": [-0.10, -0.20],
            "cvar_5_12m": [-0.14, -0.28],
            "expected_shortfall_5_12m": [-0.15, -0.30],
            "large_drawdown_probability_12m": [0.10, 0.25],
            "dividend_cut_probability": [0.05, 0.20],
        }
    )
    report = build_risk_contribution_report(portfolio)
    assert report["contribution_to_cvar_5"].sum() < 0
    assert report["risk_contribution_rank"].min() == 1
