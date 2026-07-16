import numpy as np
import pandas as pd

from src.models.var_es_backtesting import (
    build_var_es_backtest_report,
    calculate_cvar,
    calculate_expected_shortfall,
    calculate_var,
    kupiec_test,
    var_exceedance_rate,
)


def test_var_and_es_backtesting_outputs_are_valid():
    returns = pd.Series([-0.20, -0.10, -0.05, 0.01, 0.03, 0.05])
    var_5 = calculate_var(returns, 0.05)
    var_1 = calculate_var(returns, 0.01)
    cvar_5 = calculate_cvar(returns, 0.05)
    assert var_1 <= var_5
    assert cvar_5 <= var_5
    assert calculate_expected_shortfall(returns, 0.05) == cvar_5
    assert 0 <= var_exceedance_rate(returns, pd.Series([-0.08] * len(returns))) <= 1
    kupiec = kupiec_test(returns, pd.Series([-0.08] * len(returns)), 0.05)
    assert np.isfinite(kupiec["kupiec_statistic"])
    assert np.isfinite(kupiec["kupiec_p_value"])


def test_var_es_backtest_report_is_created():
    forecasts = pd.DataFrame(
        {
            "var_5_12m": [-0.08, -0.09, -0.10],
            "var_1_12m": [-0.15, -0.16, -0.17],
            "expected_shortfall_5_12m": [-0.11, -0.12, -0.13],
            "expected_shortfall_1_12m": [-0.18, -0.19, -0.20],
        }
    )
    report = build_var_es_backtest_report(pd.Series([-0.05, -0.12, 0.02]), forecasts, horizon=12)
    assert set(report["alpha"]) == {0.05, 0.01}
