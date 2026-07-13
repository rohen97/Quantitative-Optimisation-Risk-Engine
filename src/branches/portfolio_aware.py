from __future__ import annotations

import numpy as np
import pandas as pd


def run_portfolio_aware_branch(
    diagnostics: pd.DataFrame,
    scorecard: pd.DataFrame,
    candidate_universe: pd.DataFrame,
    risk_metrics: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Rank candidates by conservative score and incremental portfolio fit."""
    data = scorecard.merge(
        candidate_universe[["ticker", "region", "country", "currency", "sector"]],
        on="ticker",
        how="left",
        suffixes=("", "_universe"),
    ).copy()
    total_nav = float(diagnostics["total_nav_usd"].iloc[0]) if not diagnostics.empty else 0.0
    data["standalone_score"] = data["final_recommendation_score"]
    data["portfolio_fit_score"] = data["diversification_benefit_score"].fillna(0)
    data["incremental_concentration_impact"] = data["target_weight"].fillna(0) ** 2
    data["incremental_sector_exposure"] = data["target_weight"].fillna(0)
    data["incremental_country_exposure"] = data["target_weight"].fillna(0)
    data["incremental_currency_exposure"] = data["target_weight"].fillna(0)
    data["incremental_risk_impact"] = data.get("incremental_portfolio_cvar", pd.Series(0, index=data.index)).fillna(0)
    data["portfolio_aware_score"] = (
        0.55 * data["standalone_score"]
        + 0.25 * data["portfolio_fit_score"]
        + 0.20 * data["dividend_safety_score"].fillna(0)
        - 100 * data["incremental_risk_impact"].clip(lower=0)
    ).clip(0, 100)
    data["recommendation"] = np.select(
        [
            (~data["passes_hard_filters"]) | (data["portfolio_aware_score"] < 45),
            data["portfolio_aware_score"] >= 65,
        ],
        ["Avoid", "Buy"],
        default="Hold",
    )
    data["target_weight_portfolio_aware"] = np.where(
        data["recommendation"].eq("Buy"),
        (data["portfolio_aware_score"] / 100 * 0.05).clip(0.01, 0.05),
        0.0,
    )
    data["incremental_dividend_income"] = total_nav * data["target_weight_portfolio_aware"] * data["dividend_yield"].fillna(0)
    data["portfolio_aware_rank"] = data["portfolio_aware_score"].rank(ascending=False, method="first").astype(int)
    columns = [
        "ticker",
        "company_name",
        "region",
        "country",
        "currency",
        "sector",
        "standalone_score",
        "portfolio_fit_score",
        "incremental_dividend_income",
        "incremental_concentration_impact",
        "incremental_sector_exposure",
        "incremental_country_exposure",
        "incremental_currency_exposure",
        "incremental_risk_impact",
        "recommendation",
        "target_weight_portfolio_aware",
        "portfolio_aware_score",
        "portfolio_aware_rank",
    ]
    return data[columns].sort_values("portfolio_aware_rank").reset_index(drop=True)
