import pandas as pd

from src.validation.drl_validation import evaluate_drl_approval, validate_seed_stability


def test_unstable_or_underseeded_drl_is_rejected():
    stability = validate_seed_stability(pd.DataFrame({"seed": [1, 2], "sharpe": [0, 2], "total_net_return": [0, 1]}))
    assert stability.loc[0, "status"] == "FAIL"
    decision = evaluate_drl_approval(1.0, 0.5, -0.1, -0.2, 0.1, 0.2, 0.1, True, 0.35, 0.25)
    assert decision.status == "rejected"
    assert decision.accepted_blend == 0.0


def test_accepted_blend_is_capped_at_25_percent():
    decision = evaluate_drl_approval(0.5, 1.0, -0.2, -0.1, 0.2, 0.1, 0.1, True, 0.35, 0.8)
    assert decision.accepted_blend == 0.25
