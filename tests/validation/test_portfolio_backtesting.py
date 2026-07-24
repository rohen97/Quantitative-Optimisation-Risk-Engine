import numpy as np
import pandas as pd
import pytest

from src.validation.portfolio_backtesting import calculate_drawdown, calculate_turnover, drift_weights


def test_weight_drift_turnover_and_drawdown():
    drifted = drift_weights(np.array([0.5, 0.5]), np.array([0.1, 0.0]))
    assert drifted.sum() == pytest.approx(1.0)
    assert calculate_turnover(np.array([0.5, 0.5]), drifted) > 0
    drawdown = calculate_drawdown(pd.Series([100.0, 80.0, 120.0]))
    assert drawdown.min() == pytest.approx(-0.2)


def test_missing_returns_are_not_zero_filled():
    with pytest.raises(ValueError):
        drift_weights(np.array([0.5, 0.5]), np.array([0.1, np.nan]))
