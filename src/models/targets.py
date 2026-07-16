from __future__ import annotations

import numpy as np
import pandas as pd


HORIZONS_MONTHS = [3, 6, 9, 12]
TRADING_DAYS_PER_MONTH = 21


def _forward_window_returns(group: pd.DataFrame, days: int) -> pd.DataFrame:
    """Create forward price, dividend, volatility and drawdown targets for one ticker."""
    data = group.sort_values("date").copy()
    if "ticker" not in data:
        data["ticker"] = group.name
    future_close = data["close"].shift(-days)
    price_return = future_close / data["close"] - 1
    daily_yield = data.get("dividend_yield", pd.Series(0.03, index=data.index)).fillna(0.03) / 252
    dividend_return = daily_yield.rolling(days, min_periods=1).sum().shift(-days).fillna(daily_yield * days)
    future_vol = data["return"].rolling(days, min_periods=5).std().shift(-days) * np.sqrt(252)
    rolling_forward = data["return"].shift(-1).rolling(days, min_periods=5)
    future_drawdown = rolling_forward.sum().clip(upper=0)
    months = int(round(days / TRADING_DAYS_PER_MONTH))
    data[f"forward_price_return_{months}m"] = price_return
    data[f"forward_dividend_return_{months}m"] = dividend_return
    data[f"forward_total_return_{months}m"] = price_return + dividend_return
    data[f"forward_volatility_{months}m"] = future_vol
    data[f"forward_max_drawdown_{months}m"] = future_drawdown
    return data


def build_forward_return_targets(prices: pd.DataFrame, features: pd.DataFrame | None = None) -> pd.DataFrame:
    """Generate mock/sample forward targets from historical prices without using future data as features."""
    data = prices.copy()
    if features is not None and "dividend_yield" in features:
        data = data.merge(features[["ticker", "dividend_yield"]].drop_duplicates("ticker"), on="ticker", how="left")
    for months in HORIZONS_MONTHS:
        days = months * TRADING_DAYS_PER_MONTH
        data = data.groupby("ticker", group_keys=False).apply(_forward_window_returns, days=days, include_groups=False).reset_index(drop=True)
    data["dividend_cut_event_forward_12m"] = (
        (data.get("forward_dividend_return_12m", 0) < data.get("dividend_yield", 0.03) * 0.35)
        | (data.get("forward_total_return_12m", 0) < -0.25)
    ).astype(int)
    data["large_drawdown_event_forward_12m"] = (data["forward_max_drawdown_12m"] < -0.20).astype(int)
    return data
