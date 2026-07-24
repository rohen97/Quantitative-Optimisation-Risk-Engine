import pandas as pd

from src.validation.leakage import check_availability_dates, check_split_overlap, leakage_report


def test_future_information_and_target_leakage_are_detected():
    issues = check_availability_dates(pd.DataFrame({"decision": ["2020-01-01"], "available": ["2020-01-02"]}), "decision", "available", "fundamentals")
    assert issues[0].severity == "critical"
    report = leakage_report(pd.DataFrame({"feature": [1], "forward_return": [0.1]}))
    assert report.loc[0, "status"] == "FAIL"


def test_training_test_overlap_is_detected():
    issues = check_split_overlap(pd.DataFrame([{"train_end": "2020-02-01", "validation_start": "2020-01-01", "validation_end": "2020-03-01", "test_start": "2020-03-01"}]))
    assert len(issues) == 2
