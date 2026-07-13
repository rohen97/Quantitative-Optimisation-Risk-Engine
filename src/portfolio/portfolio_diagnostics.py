from __future__ import annotations

import pandas as pd

from src.portfolio.concentration import effective_number_of_holdings, hhi, top_concentration
from src.portfolio.exposure import exposure_by


def portfolio_summary(portfolio: pd.DataFrame) -> dict[str, float]:
    weights = portfolio["weight"]
    return {
        "total_nav_usd": float(portfolio["market_value_usd"].sum()),
        "top_1_concentration": top_concentration(weights, 1),
        "top_3_concentration": top_concentration(weights, 3),
        "top_5_concentration": top_concentration(weights, 5),
        "hhi": hhi(weights),
        "effective_number_of_holdings": effective_number_of_holdings(weights),
    }


def build_portfolio_diagnostics(portfolio: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    summary = pd.DataFrame([portfolio_summary(portfolio)])
    exposures = {
        "sector": exposure_by(portfolio, "sector"),
        "country": exposure_by(portfolio, "country"),
        "currency": exposure_by(portfolio, "currency"),
    }
    return summary, exposures
