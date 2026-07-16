import pandas as pd

from src.risk.risk_metrics import build_risk_report


def test_portfolio_risk_report_is_created():
    portfolio = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "target_weight": [0.5, 0.5],
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
    report = build_risk_report(pd.DataFrame(), portfolio)
    assert "portfolio_expected_total_return" in report.columns
    assert report["portfolio_drawdown_probability"].between(0, 1).all()
