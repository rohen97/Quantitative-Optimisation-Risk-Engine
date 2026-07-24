import numpy as np
import pandas as pd

from src.validation.risk_backtesting import backtest_var, kupiec_test


def test_kupiec_detects_var_breaches_and_sign_conversion():
    result = kupiec_test(np.array([1.0, 3.0, 1.0]), np.array([2.0, 2.0, 2.0]), 0.95)
    assert result.breaches == 1
    report = backtest_var(pd.Series([-0.01, -0.03]), pd.Series([-0.02, -0.02]), 0.95)
    assert report["violations"] == 1
