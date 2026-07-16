import pandas as pd

from src.optimisation.portfolio_math import calculate_effective_number_of_holdings, calculate_hhi, calculate_portfolio_expected_return


def test_hhi_and_effective_holdings_are_computed_correctly():
    weights = pd.Series([0.5, 0.5])
    assert calculate_hhi(weights) == 0.5
    assert calculate_effective_number_of_holdings(weights) == 2.0


def test_portfolio_expected_return_is_weighted_sum():
    portfolio = pd.DataFrame({"target_weight": [0.4, 0.6], "expected_total_return_12m": [0.10, 0.05]})
    assert round(calculate_portfolio_expected_return(portfolio), 4) == 0.07
