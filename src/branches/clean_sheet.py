from __future__ import annotations

import numpy as np
import pandas as pd


def run_clean_sheet_branch(scorecard: pd.DataFrame, max_names: int = 20) -> pd.DataFrame:
    """Build a fresh conservative portfolio without existing holdings constraints."""
    data = scorecard.copy()
    risk_quality = 100 * (1 - data["volatility_1y"].rank(pct=True)).fillna(0.5)
    regime_suitability = data.get("regime_suitability_score", pd.Series(50, index=data.index)).fillna(50)
    regime_weight_adjustment = data.get("regime_weight_adjustment", pd.Series(0, index=data.index)).fillna(0)
    ml_score = data.get("ml_expected_risk_adjusted_score", pd.Series(50, index=data.index)).fillna(50)
    p5 = data.get("p5_return_12m", pd.Series(-0.10, index=data.index)).fillna(-0.10)
    p95 = data.get("p95_return_12m", pd.Series(0.15, index=data.index)).fillna(0.15)
    var_5 = data.get("var_5_12m", pd.Series(-0.10, index=data.index)).fillna(-0.10)
    cvar_5 = data.get("cvar_5_12m", pd.Series(-0.12, index=data.index)).fillna(-0.12)
    tail_risk = data.get("tail_risk_score", pd.Series(50, index=data.index)).fillna(50)
    skewness_risk = data.get("skewness_risk_score", pd.Series(50, index=data.index)).fillna(50)
    distribution_confidence = data.get("distribution_model_confidence", pd.Series(70, index=data.index)).fillna(70)
    dividend_cut = data.get("dividend_cut_probability", pd.Series(0.15, index=data.index)).fillna(0.15)
    drawdown = data.get("large_drawdown_probability_12m", pd.Series(0.15, index=data.index)).fillna(0.15)
    data["clean_sheet_score"] = (
        0.20 * data["dividend_safety_score"].fillna(0)
        + 0.18 * data["cash_flow_quality_score"].fillna(0)
        + 0.12 * data["balance_sheet_strength_score"].fillna(0)
        + 0.12 * data["valuation_score"].fillna(0)
        + 0.08 * data["liquidity_score"].fillna(0)
        + 0.04 * regime_suitability
        + 0.14 * ml_score
        + 12 * p95.clip(lower=0)
        - 18 * (-p5).clip(lower=0)
        - 12 * (-var_5).clip(lower=0)
        - 12 * (-cvar_5).clip(lower=0)
        - 0.05 * tail_risk
        - 0.05 * skewness_risk
        + 0.04 * distribution_confidence
        - 10 * dividend_cut
        - 10 * drawdown
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
    data["clean_sheet_target_weight"] = np.where(
        buys & (data["clean_sheet_rank"] <= max_names),
        (equal_weight + regime_weight_adjustment).clip(0.0, 0.05),
        0.0,
    )
    columns = [
        "ticker",
        "company_name",
        "region",
        "country",
        "currency",
        "sector",
        "expected_total_return_12m",
        "p5_return_12m",
        "p95_return_12m",
        "var_5_12m",
        "cvar_5_12m",
        "tail_risk_score",
        "skewness_risk_score",
        "distribution_model_confidence",
        "dividend_cut_probability",
        "large_drawdown_probability_12m",
        "ml_expected_risk_adjusted_score",
        "clean_sheet_score",
        "clean_sheet_recommendation",
        "clean_sheet_target_weight",
        "clean_sheet_rank",
    ]
    return data[columns].sort_values("clean_sheet_rank").reset_index(drop=True)
