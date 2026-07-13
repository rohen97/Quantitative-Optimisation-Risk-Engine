from __future__ import annotations

import pandas as pd

from src.backtesting.metrics import backtest_metrics


def run_buy_and_hold_backtest(returns: pd.Series) -> dict[str, float]:
    return backtest_metrics(returns)
