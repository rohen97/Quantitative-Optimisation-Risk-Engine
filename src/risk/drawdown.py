from __future__ import annotations

import pandas as pd


def max_drawdown(values: pd.Series) -> float:
    drawdown = values / values.cummax() - 1
    return float(drawdown.min())
