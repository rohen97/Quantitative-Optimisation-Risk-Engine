from src.validation.transaction_cost_validation import estimate_transaction_cost


def test_costs_are_positive_and_missing_adv_is_conservative():
    result = estimate_transaction_cost(1_000_000, 5, 7.5, 5, 0.2, None, 0.1)
    assert result["total_cost"] > result["linear_cost"] > 0
    assert result["adv_estimated"] is True
