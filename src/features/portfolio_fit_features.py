from __future__ import annotations

import numpy as np
import pandas as pd


def build_portfolio_fit_features(features: pd.DataFrame, portfolio: pd.DataFrame) -> pd.DataFrame:
    """Build candidate-level portfolio fit and diversification features."""
    data = features.copy()
    held = set(portfolio["ticker"])
    sector_weights = portfolio.groupby("sector")["weight"].sum()
    country_weights = portfolio.groupby("country")["weight"].sum()
    region_weights = portfolio.groupby("region")["weight"].sum()
    currency_weights = portfolio.groupby("currency")["weight"].sum()
    existing_sector = data["sector"].map(sector_weights).fillna(0)
    existing_country = data["country"].map(country_weights).fillna(0)
    existing_region = data["region"].map(region_weights).fillna(0)
    existing_currency = data["currency"].map(currency_weights).fillna(0)
    data["correlation_with_current_portfolio"] = np.where(
        data["ticker"].isin(held),
        0.85,
        (0.20 + 0.30 * existing_sector + 0.20 * existing_region + 0.15 * existing_currency).clip(0.15, 0.85),
    )
    data["incremental_portfolio_volatility"] = data["volatility_1y"] * (0.02 + data["correlation_with_current_portfolio"] * 0.03)
    data["incremental_portfolio_var"] = data["volatility_1y"] * 0.07
    data["incremental_portfolio_cvar"] = data["volatility_1y"] * 0.10
    total_nav = float(portfolio["market_value_usd"].sum())
    data["incremental_dividend_income"] = total_nav * 0.01 * data["dividend_yield"].fillna(0)
    data["marginal_risk_contribution"] = data["incremental_portfolio_cvar"].rank(pct=True) * 100
    data["incremental_sector_exposure"] = existing_sector + 0.01
    data["incremental_country_exposure"] = existing_country + 0.01
    data["incremental_region_exposure"] = existing_region + 0.01
    data["incremental_currency_exposure"] = existing_currency + 0.01
    data["concentration_impact_score"] = (100 * (1 - (0.01 + existing_sector * 0.35 + existing_country * 0.25 + existing_currency * 0.20))).clip(0, 100)
    data["diversification_benefit_score"] = (
        100 * (1 - (0.35 * existing_sector + 0.25 * existing_country + 0.20 * existing_region + 0.20 * existing_currency))
    ).clip(0, 100)
    income_score = 100 * data["dividend_yield"].rank(pct=True)
    risk_score = data.get("risk_score", pd.Series(50, index=data.index)).fillna(50)
    data["portfolio_fit_score"] = (
        0.40 * data["diversification_benefit_score"]
        + 0.25 * data["concentration_impact_score"]
        + 0.20 * income_score
        + 0.15 * risk_score
    ).clip(0, 100)
    return data
