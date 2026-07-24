import pandas as pd

from src.reporting.executive_summary import build_executive_summary
from src.reporting.models import ICDataBundle


def test_executive_summary_extracts_key_fields():
    bundle = ICDataBundle(
        {
            "final_recommendations": pd.DataFrame({"ticker": ["AAA"], "final_selected_weight": [0.1]}),
            "regime_summary": pd.DataFrame({"dominant_regime": ["stable"], "wolf_chaos_index": [20]}),
            "risk_report": pd.DataFrame({"portfolio_var_5": [-0.1]}),
        }
    )
    summary = build_executive_summary(bundle)
    assert summary["top_recommendation"] == "AAA"
    assert summary["dominant_regime"] == "stable"


def test_executive_summary_counts_only_true_hard_breaches():
    bundle = ICDataBundle(
        {
            "final_recommendations": pd.DataFrame(
                {"security_id": ["sec-1"], "ticker": ["AAA"], "final_selected_weight": [1.0]}
            ),
            "portfolio_constraint_report": pd.DataFrame(
                {
                    "constraint_type": ["hard", "hard", "soft"],
                    "breach_flag": ["False", "True", "True"],
                }
            ),
        }
    )
    summary = build_executive_summary(bundle)
    assert summary["number_of_hard_constraint_breaches"] == 1
