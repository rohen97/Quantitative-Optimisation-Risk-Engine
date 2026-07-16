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
    data["regime_suitability_score"] = data.get("regime_suitability_score", pd.Series(50, index=data.index)).fillna(50)
    data["regime_weight_adjustment"] = data.get("regime_weight_adjustment", pd.Series(0, index=data.index)).fillna(0)
    data["incremental_concentration_impact"] = data["target_weight"].fillna(0) ** 2
    data["incremental_sector_exposure"] = data["target_weight"].fillna(0)
    data["incremental_country_exposure"] = data["target_weight"].fillna(0)
    data["incremental_currency_exposure"] = data["target_weight"].fillna(0)
    data["incremental_risk_impact"] = data.get("incremental_portfolio_cvar", pd.Series(0, index=data.index)).fillna(0)
    data["portfolio_aware_score"] = (
        0.55 * data["standalone_score"]
        + 0.25 * data["portfolio_fit_score"]
        + 0.12 * data["dividend_safety_score"].fillna(0)
        + 0.08 * data["regime_suitability_score"]
        - 100 * data["incremental_risk_impact"].clip(lower=0)
    ).clip(0, 100)
    europe_cyclical = data["dominant_regime"].eq("europe_recession") & data["region"].isin(["DACH", "EU ex-DACH"]) & data["sector"].isin(
        ["Industrials", "Consumer Discretionary", "Technology"]
    )
    china_policy = data["dominant_regime"].eq("china_policy_stress") & data["region"].isin(["Mainland China", "Hong Kong"])
    data.loc[europe_cyclical | china_policy, "portfolio_aware_score"] = (data["portfolio_aware_score"] - 10).clip(0, 100)
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
        ((data["portfolio_aware_score"] / 100 * 0.05) + data["regime_weight_adjustment"]).clip(0.01, 0.05),
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
