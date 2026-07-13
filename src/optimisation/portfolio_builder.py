from __future__ import annotations

import pandas as pd


def build_proposed_portfolio(current: pd.DataFrame, recommendations: pd.DataFrame, max_new_names: int = 8) -> pd.DataFrame:
    buys = recommendations[recommendations["target_weight"] > 0].head(max_new_names)
    proposed = buys[["ticker", "company_name", "sector", "country", "currency", "target_weight", "recommendation"]].copy()
    if proposed["target_weight"].sum() > 0.35:
        proposed["target_weight"] *= 0.35 / proposed["target_weight"].sum()
    return proposed
