from __future__ import annotations

import pandas as pd


def build_liquidity_features(universe: pd.DataFrame, total_nav_usd: float = 1_000_000) -> pd.DataFrame:
    """Build liquidity and liquidation-capacity features."""
    data = universe[["ticker", "avg_daily_traded_value_usd"]].copy()
    data["average_daily_value_usd"] = data["avg_daily_traded_value_usd"]
    data["average_volume"] = data["average_daily_value_usd"] / 50
    data["turnover_ratio"] = data["average_daily_value_usd"] / universe["market_cap_usd"].replace(0, pd.NA)
    data["days_to_liquidate_1pct_nav"] = (0.01 * total_nav_usd) / data["average_daily_value_usd"].clip(lower=1)
    data["days_to_liquidate"] = data["days_to_liquidate_1pct_nav"]
    data["liquidity_score"] = (100 * data["average_daily_value_usd"].rank(pct=True)).clip(0, 100)
    data["liquidity_stress_score"] = (100 - data["liquidity_score"]).clip(0, 100)
    return data[
        [
            "ticker",
            "average_daily_value_usd",
            "average_volume",
            "turnover_ratio",
            "days_to_liquidate_1pct_nav",
            "liquidity_score",
            "liquidity_stress_score",
            "days_to_liquidate",
        ]
    ]
