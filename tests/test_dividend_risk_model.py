import pandas as pd

from src.models.dividend_risk_model import estimate_dividend_cut_probability


def test_high_payout_and_weak_fcf_increase_dividend_cut_probability():
    features = pd.DataFrame(
        {
            "ticker": ["SAFE", "RISK"],
            "payout_ratio": [0.45, 0.95],
            "fcf_dividend_cover": [2.0, 0.4],
            "free_cash_flow_yield": [0.07, -0.01],
            "cash_flow_quality_score": [80, 30],
            "balance_sheet_strength_score": [80, 30],
            "net_debt_to_ebitda": [1.0, 5.0],
            "interest_coverage": [10.0, 2.0],
        }
    )
    output = estimate_dividend_cut_probability(features)
    assert output["dividend_cut_probability"].between(0, 1).all()
    assert output.loc[output["ticker"].eq("RISK"), "dividend_cut_probability"].iloc[0] > output.loc[output["ticker"].eq("SAFE"), "dividend_cut_probability"].iloc[0]
