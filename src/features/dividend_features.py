from __future__ import annotations

import pandas as pd


def build_dividend_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build dividend yield, growth, cover and safety features."""
    data = frame.copy()
    data["trailing_12m_dps"] = data.get("trailing_12m_dps", data["dividend_yield"] * 100).fillna(0)
    data["dividend_growth_3y"] = data.get("dividend_growth_3y", data["dividend_growth_5y"]).fillna(0)
    data["fcf_dividend_cover"] = (
        data["free_cash_flow_yield"].fillna(0) / data["dividend_yield"].replace(0, pd.NA)
    ).fillna(0).clip(lower=0)
    data["dividend_stability_score"] = (
        50
        + 25 * data["dividend_growth_3y"].rank(pct=True)
        + 25 * data["dividend_growth_5y"].rank(pct=True)
        - 35 * data["dividend_cut_flag_3y"].fillna(0)
    ).clip(0, 100)
    data["dividend_safety_score"] = (
        25 * data["dividend_yield"].rank(pct=True)
        + 20 * data["dividend_growth_5y"].rank(pct=True)
        + 25 * (1 - data["payout_ratio"].clip(0, 1).fillna(1))
        + 20 * (data["fcf_dividend_cover"].clip(0, 2) / 2)
        + 10 * (1 - data["dividend_cut_flag_3y"].fillna(0))
    ).clip(0, 100)
    data["dividend_income_usd"] = data["market_cap_usd"].fillna(0) * data["dividend_yield"].fillna(0)
    return data
