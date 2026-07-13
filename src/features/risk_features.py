from __future__ import annotations

import numpy as np
import pandas as pd


def build_price_risk_features(prices: pd.DataFrame) -> pd.DataFrame:
    grouped = prices.sort_values("date").groupby("ticker")
    features = grouped["return"].agg(volatility_1y=lambda x: float(x.tail(252).std() * np.sqrt(252)), beta_1y="mean").reset_index()
    drawdowns = []
    momentum = []
    for ticker, frame in grouped:
        close = frame["close"].tail(252)
        dd = close / close.cummax() - 1
        drawdowns.append({"ticker": ticker, "max_drawdown_1y": float(dd.min())})
        first = frame["close"].tail(126).iloc[0]
        last = frame["close"].tail(126).iloc[-1]
        momentum.append({"ticker": ticker, "momentum_6m": float(last / first - 1)})
    return features.merge(pd.DataFrame(drawdowns), on="ticker").merge(pd.DataFrame(momentum), on="ticker")
