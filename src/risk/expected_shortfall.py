from __future__ import annotations

import numpy as np
import pandas as pd


def expected_shortfall(returns: pd.Series, alpha: float = 0.05) -> float:
    """Calculate empirical Expected Shortfall at alpha."""
    values = pd.Series(returns).dropna()
    if values.empty:
        return 0.0
    var = float(np.quantile(values, alpha))
    tail = values[values <= var]
    return float(tail.mean()) if not tail.empty else var


def expected_shortfall_proxy(values: pd.Series, weights: pd.Series) -> float:
    """Weighted Expected Shortfall proxy from stock-level ES forecasts."""
    return float((pd.Series(values).fillna(-0.30) * pd.Series(weights).fillna(0)).sum())
