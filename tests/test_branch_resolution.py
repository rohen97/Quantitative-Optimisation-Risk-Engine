import pandas as pd

from src.branches.branch_comparison import build_final_recommendations


def test_quantitative_hold_is_not_downgraded_to_avoid():
    comparison = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "portfolio_aware_recommendation": ["Hold"],
            "clean_sheet_recommendation": ["Hold"],
            "llm_recommendation": ["Avoid"],
            "final_review_required": [True],
            "target_weight_portfolio_aware": [0.0],
        }
    )
    scorecard = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "passes_hard_filters": [True],
            "dividend_safety_score": [70],
            "cash_flow_quality_score": [70],
            "balance_sheet_strength_score": [70],
            "final_recommendation_score": [60],
            "risk_management_flags": [""],
        }
    )
    result = build_final_recommendations(comparison, scorecard)
    assert result.loc[0, "final_recommendation"] == "Watchlist"
