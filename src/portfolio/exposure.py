from __future__ import annotations

import pandas as pd


def exposure_by(portfolio: pd.DataFrame, column: str) -> pd.DataFrame:
    """Aggregate portfolio exposure by a categorical column."""
    grouped = (
        portfolio.groupby(column, as_index=False)
        .agg(
            market_value_usd=("market_value_usd", "sum"),
            dividend_income_usd=("dividend_income_usd", "sum"),
            weighted_beta=("weighted_beta", "sum"),
            weighted_volatility=("weighted_volatility", "sum"),
        )
        .sort_values("market_value_usd", ascending=False)
    )
    total_nav = grouped["market_value_usd"].sum()
    grouped["weight"] = grouped["market_value_usd"] / total_nav if total_nav else 0.0
    return grouped[[column, "market_value_usd", "weight", "dividend_income_usd", "weighted_beta", "weighted_volatility"]]
