from __future__ import annotations

import numpy as np
import pandas as pd


def run_clean_sheet_branch(scorecard: pd.DataFrame, max_names: int = 20) -> pd.DataFrame:
    """Build a fresh conservative portfolio without existing holdings constraints."""
    data = scorecard.copy()
    risk_quality = 100 * (1 - data["volatility_1y"].rank(pct=True)).fillna(0.5)
    data["clean_sheet_score"] = (
        0.25 * data["dividend_safety_score"].fillna(0)
        + 0.22 * data["cash_flow_quality_score"].fillna(0)
        + 0.18 * data["balance_sheet_strength_score"].fillna(0)
        + 0.15 * data["valuation_score"].fillna(0)
        + 0.10 * data["liquidity_score"].fillna(0)
        + 0.10 * risk_quality
    ).clip(0, 100)
    data["clean_sheet_rank"] = data["clean_sheet_score"].rank(ascending=False, method="first").astype(int)
    data["clean_sheet_recommendation"] = np.select(
        [
            (~data["passes_hard_filters"]) | (data["clean_sheet_score"] < 45),
            data["clean_sheet_score"] >= 65,
        ],
        ["Avoid", "Buy"],
        default="Hold",
    )
    buys = data["clean_sheet_recommendation"].eq("Buy")
    equal_weight = min(0.05, 1 / max(int(buys.sum()), 1))
    data["clean_sheet_target_weight"] = np.where(buys & (data["clean_sheet_rank"] <= max_names), equal_weight, 0.0)
    columns = [
        "ticker",
        "company_name",
        "region",
        "country",
        "currency",
        "sector",
        "clean_sheet_score",
        "clean_sheet_recommendation",
        "clean_sheet_target_weight",
        "clean_sheet_rank",
    ]
    return data[columns].sort_values("clean_sheet_rank").reset_index(drop=True)
