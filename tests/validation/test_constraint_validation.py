import numpy as np
import pandas as pd

from src.validation.constraint_validation import validate_portfolio_frame, validate_weight_vector


def test_weight_vector_rejects_negative_sum_and_caps():
    assert not validate_weight_vector(np.array([1.1, -0.1])).valid
    report = validate_portfolio_frame(pd.DataFrame({"weight": [0.6, 0.4]}), "weight", 0.5)
    assert report.loc[report["check_name"].eq("single_name_cap"), "status"].item() == "FAIL"


def test_excluded_assets_fail():
    report = validate_portfolio_frame(pd.DataFrame({"weight": [0.5, 0.5], "eligible": [True, False]}), "weight", 0.6, eligibility_column="eligible")
    assert report.iloc[-1]["status"] == "FAIL"


def test_cash_sleeve_is_not_subject_to_the_equity_single_name_cap():
    portfolio = pd.DataFrame(
        {
            "security_id": ["AAA", "BBB", "CASH"],
            "weight": [0.375, 0.375, 0.25],
        }
    )

    report = validate_portfolio_frame(portfolio, "weight", 0.40)

    assert report.loc[
        report["check_name"].eq("single_name_cap"), "status"
    ].item() == "PASS"
    assert report.loc[
        report["check_name"].eq("weights_sum_to_one"), "status"
    ].item() == "PASS"
