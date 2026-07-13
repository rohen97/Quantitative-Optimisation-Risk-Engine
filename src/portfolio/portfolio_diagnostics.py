from __future__ import annotations

import pandas as pd

from src.portfolio.concentration import concentration_summary
from src.portfolio.exposure import exposure_by


def portfolio_summary(portfolio: pd.DataFrame) -> dict[str, float]:
    """Calculate portfolio-level diagnostics from enriched holdings."""
    weights = portfolio["weight"]
    summary = {
        "total_nav_usd": float(portfolio["market_value_usd"].sum()),
        "position_count": int(len(portfolio)),
        "dividend_income_usd": float(portfolio["dividend_income_usd"].sum()),
        "weighted_dividend_yield": float(portfolio["weighted_dividend_yield"].sum()),
        "weighted_beta": float(portfolio["weighted_beta"].sum()),
        "weighted_volatility_proxy": float(portfolio["weighted_volatility"].sum()),
    }
    summary.update(concentration_summary(weights))
    return summary


def build_portfolio_diagnostics(portfolio: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Build summary and exposure tables for the current portfolio."""
    summary = pd.DataFrame([portfolio_summary(portfolio)])
    exposures = {
        "sector": exposure_by(portfolio, "sector"),
        "country": exposure_by(portfolio, "country"),
        "region": exposure_by(portfolio, "region"),
        "currency": exposure_by(portfolio, "currency"),
    }
    return summary, exposures


def build_concentration_summary(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Return concentration metrics as a single-row table."""
    return pd.DataFrame([concentration_summary(portfolio["weight"])])
