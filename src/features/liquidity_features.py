from __future__ import annotations

import pandas as pd


def build_liquidity_features(universe: pd.DataFrame) -> pd.DataFrame:
    data = universe[["ticker", "avg_daily_traded_value_usd"]].copy()
    data["liquidity_score"] = 100 * data["avg_daily_traded_value_usd"].rank(pct=True)
    data["days_to_liquidate"] = 2_000_000 / data["avg_daily_traded_value_usd"].clip(lower=1)
    return data[["ticker", "liquidity_score", "days_to_liquidate"]]
