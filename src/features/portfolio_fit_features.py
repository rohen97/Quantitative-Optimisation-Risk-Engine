from __future__ import annotations

import numpy as np
import pandas as pd


def build_portfolio_fit_features(features: pd.DataFrame, portfolio: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    held = set(portfolio["ticker"])
    sector_weights = portfolio.groupby("sector")["weight"].sum()
    country_weights = portfolio.groupby("country")["weight"].sum()
    data["correlation_with_current_portfolio"] = np.where(data["ticker"].isin(held), 0.85, 0.25 + data["volatility_1y"].rank(pct=True) * 0.35)
    data["incremental_portfolio_volatility"] = data["volatility_1y"] * (0.02 + data["correlation_with_current_portfolio"] * 0.03)
    data["incremental_portfolio_var"] = data["volatility_1y"] * 0.07
    data["incremental_portfolio_cvar"] = data["volatility_1y"] * 0.10
    data["incremental_dividend_income"] = 1_000_000 * 0.03 * data["dividend_yield"]
    data["marginal_risk_contribution"] = data["incremental_portfolio_cvar"].rank(pct=True) * 100
    existing_sector = data["sector"].map(sector_weights).fillna(0)
    existing_country = data["country"].map(country_weights).fillna(0)
    data["diversification_benefit_score"] = 100 * (1 - (0.6 * existing_sector + 0.4 * existing_country)).clip(0, 1)
    return data
