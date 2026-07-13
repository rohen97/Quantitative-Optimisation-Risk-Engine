from __future__ import annotations

import pandas as pd


def exposure_by(portfolio: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        portfolio.groupby(column, as_index=False)["market_value_usd"]
        .sum()
        .assign(weight=lambda df: df["market_value_usd"] / df["market_value_usd"].sum())
        .sort_values("weight", ascending=False)
    )
