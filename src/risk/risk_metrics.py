from __future__ import annotations

import numpy as np
import pandas as pd

from src.risk.drawdown import max_drawdown
from src.risk.var_cvar import var_cvar


def portfolio_return_series(prices: pd.DataFrame, portfolio: pd.DataFrame) -> pd.Series:
    returns = prices.pivot(index="date", columns="ticker", values="return").fillna(0)
    weights = portfolio.set_index("ticker")["weight"].reindex(returns.columns).fillna(0)
    return returns.mul(weights, axis=1).sum(axis=1)


def build_risk_report(prices: pd.DataFrame, portfolio: pd.DataFrame) -> pd.DataFrame:
    returns = portfolio_return_series(prices, portfolio)
    var5, cvar5 = var_cvar(returns, 0.05)
    wealth = (1 + returns).cumprod()
    ann_return = float((1 + returns.mean()) ** 252 - 1)
    ann_vol = float(returns.std() * np.sqrt(252))
    return pd.DataFrame(
        [
            {
                "annualised_return": ann_return,
                "annualised_volatility": ann_vol,
                "sharpe_ratio": ann_return / ann_vol if ann_vol else 0.0,
                "sortino_ratio": ann_return / (returns[returns < 0].std() * np.sqrt(252)) if (returns < 0).any() else 0.0,
                "calmar_ratio": ann_return / abs(max_drawdown(wealth)) if max_drawdown(wealth) else 0.0,
                "max_drawdown": max_drawdown(wealth),
                "var_5": var5,
                "cvar_5": cvar5,
            }
        ]
    )
