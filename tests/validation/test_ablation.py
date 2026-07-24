from src.validation.ablation import build_ablation_report


def test_missing_ablations_are_not_claimed_as_evidence():
    report = build_ablation_report({}, {})
    assert report["status"].eq("NOT_EVALUATED").all()
