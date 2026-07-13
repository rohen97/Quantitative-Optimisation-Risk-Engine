from __future__ import annotations

import numpy as np
import pandas as pd

from src.risk.var_cvar import var_cvar


def backtest_metrics(returns: pd.Series) -> dict[str, float]:
    var5, cvar5 = var_cvar(returns)
    return {
        "annualised_return": float((1 + returns.mean()) ** 252 - 1),
        "annualised_volatility": float(returns.std() * np.sqrt(252)),
        "var": var5,
        "cvar": cvar5,
        "hit_ratio": float((returns > 0).mean()),
    }
