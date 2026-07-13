from __future__ import annotations

import numpy as np
import pandas as pd


def var_cvar(returns: pd.Series, alpha: float = 0.05) -> tuple[float, float]:
    values = returns.dropna().to_numpy()
    if values.size == 0:
        return 0.0, 0.0
    var = float(np.quantile(values, alpha))
    cvar = float(values[values <= var].mean()) if (values <= var).any() else var
    return var, cvar
