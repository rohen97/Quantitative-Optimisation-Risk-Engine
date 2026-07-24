from src.validation.governance import make_governance_decision


def test_critical_failure_overrides_high_score():
    decision = make_governance_decision({"x": 100}, ["leakage"], [])
    assert decision.status == "REJECTED"


def test_thresholds_and_insufficient_data_are_distinct():
    assert make_governance_decision({"x": 75}, [], []).status == "APPROVED"
    assert make_governance_decision({"x": 65}, [], []).status == "CONDITIONALLY_APPROVED"
    assert make_governance_decision({"x": 90}, [], [], insufficient_components=["risk"]).status == "INSUFFICIENT_DATA"
