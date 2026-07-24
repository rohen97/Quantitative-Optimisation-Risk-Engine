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
