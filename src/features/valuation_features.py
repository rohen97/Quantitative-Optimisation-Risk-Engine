from __future__ import annotations

import pandas as pd


def build_valuation_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build cross-sectional valuation features and scores."""
    data = frame.copy()
    data["enterprise_value"] = data.get("enterprise_value", data["market_cap_usd"] + data["total_debt"].fillna(0) - data["cash"].fillna(0))
    data["fcf_yield"] = (data["free_cash_flow"] / data["market_cap_usd"].replace(0, pd.NA)).fillna(data["free_cash_flow_yield"])
    universe_median_yield = data["dividend_yield"].median()
    data["dividend_yield_spread"] = data["dividend_yield"] - universe_median_yield
    cheapness = (
        (1 - data["pe_ratio"].rank(pct=True)) * 0.30
        + (1 - data["pb_ratio"].rank(pct=True)) * 0.20
        + (1 - data["ev_ebitda"].rank(pct=True)) * 0.25
        + data["fcf_yield"].rank(pct=True) * 0.25
    )
    data["valuation_score"] = 100 * cheapness
    data["valuation_percentile"] = cheapness
    return data
