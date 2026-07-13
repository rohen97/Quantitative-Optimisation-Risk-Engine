from __future__ import annotations

import numpy as np
import pandas as pd


def build_price_risk_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Build risk features from daily mock or vendor price history."""
    sorted_prices = prices.sort_values(["ticker", "date"]).copy()
    grouped = sorted_prices.groupby("ticker")
    features = grouped["return"].agg(
        daily_return="mean",
        annualised_volatility=lambda x: float(x.tail(252).std() * np.sqrt(252)),
        downside_volatility=lambda x: float(x.tail(252)[x.tail(252) < 0].std() * np.sqrt(252)),
        var_5=lambda x: float(x.tail(252).quantile(0.05)),
        cvar_5=lambda x: float(x.tail(252)[x.tail(252) <= x.tail(252).quantile(0.05)].mean()),
    ).reset_index()
    drawdowns: list[dict[str, float | str]] = []
    momentum: list[dict[str, float | str]] = []
    for ticker, frame in grouped:
        close = frame["close"].tail(252)
        dd = close / close.cummax() - 1
        drawdowns.append({"ticker": ticker, "max_drawdown_1y": float(dd.min())})
        first = frame["close"].tail(126).iloc[0]
        last = frame["close"].tail(126).iloc[-1]
        momentum.append({"ticker": ticker, "momentum_6m": float(last / first - 1)})
    features = features.merge(pd.DataFrame(drawdowns), on="ticker").merge(pd.DataFrame(momentum), on="ticker")
    features["volatility_1y"] = features["annualised_volatility"]
    features["beta_local_market"] = 1.0 + features["daily_return"].rank(pct=True).sub(0.5) * 0.4
    features["beta_global_market"] = 0.9 + features["annualised_volatility"].rank(pct=True).sub(0.5) * 0.5
    features["beta_1y"] = features["beta_local_market"]
    annual_return_proxy = features["daily_return"] * 252
    features["sharpe_proxy"] = annual_return_proxy / features["annualised_volatility"].replace(0, pd.NA)
    features["sortino_proxy"] = annual_return_proxy / features["downside_volatility"].replace(0, pd.NA)
    risk_penalty = (
        0.35 * features["annualised_volatility"].rank(pct=True)
        + 0.25 * features["downside_volatility"].fillna(features["annualised_volatility"]).rank(pct=True)
        + 0.25 * features["max_drawdown_1y"].abs().rank(pct=True)
        + 0.15 * features["cvar_5"].abs().rank(pct=True)
    )
    features["risk_score"] = (100 * (1 - risk_penalty)).clip(0, 100)
    return features
