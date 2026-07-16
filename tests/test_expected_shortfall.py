import pandas as pd

from src.risk.expected_shortfall import expected_shortfall


def test_expected_shortfall_is_at_least_as_severe_as_var_proxy():
    returns = pd.Series([-0.20, -0.10, -0.05, 0.02, 0.05])
    es = expected_shortfall(returns, 0.05)
    assert es <= returns.quantile(0.05)
