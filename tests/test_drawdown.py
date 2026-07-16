import pandas as pd

from src.risk.drawdown import max_drawdown


def test_max_drawdown_is_negative_or_zero():
    assert max_drawdown(pd.Series([1.0, 1.2, 0.9, 1.1])) <= 0
