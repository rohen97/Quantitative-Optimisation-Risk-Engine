from __future__ import annotations

import pandas as pd


def build_financial_features(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Build cash-flow, profitability and balance-sheet quality features."""
    data = fundamentals.copy()
    data["free_cash_flow"] = data.get("free_cash_flow", data["free_cash_flow_yield"] * data["market_cap_usd"]).fillna(0)
    data["operating_cash_flow"] = data.get("operating_cash_flow", data["free_cash_flow"]).fillna(data["free_cash_flow"])
    data["capex"] = data.get("capex", (data["operating_cash_flow"] - data["free_cash_flow"]).clip(lower=0)).fillna(0)
    data["revenue"] = data.get("revenue", data["free_cash_flow"] / data["fcf_margin"].replace(0, pd.NA)).fillna(0)
    data["ebitda"] = data.get("ebitda", data["revenue"] * data.get("ebitda_margin", 0.2)).fillna(0)
    data["net_income"] = data.get("net_income", data["operating_cash_flow"] / data["cfo_to_net_income"].replace(0, pd.NA)).fillna(0)
    data["revenue_growth"] = data.get("revenue_growth", 0.0)
    data["ebitda_margin"] = data.get("ebitda_margin", data["ebitda"] / data["revenue"].replace(0, pd.NA)).fillna(0)
    data["net_income_margin"] = data.get("net_income_margin", data["net_income"] / data["revenue"].replace(0, pd.NA)).fillna(0)
    data["free_cash_flow_yield"] = (data["free_cash_flow"] / data["market_cap_usd"].replace(0, pd.NA)).fillna(data["free_cash_flow_yield"])
    data["fcf_margin"] = (data["free_cash_flow"] / data["revenue"].replace(0, pd.NA)).fillna(data["fcf_margin"])
    data["cfo_to_net_income"] = (data["operating_cash_flow"] / data["net_income"].replace(0, pd.NA)).fillna(data["cfo_to_net_income"])
    data["total_debt"] = data.get("total_debt", data["net_debt_to_ebitda"] * data["ebitda"]).fillna(0)
    data["cash"] = data.get("cash", 0.0)
    data["net_debt"] = data["total_debt"] - data["cash"]
    data["shareholders_equity"] = data.get("shareholders_equity", data["market_cap_usd"] / data["pb_ratio"].replace(0, pd.NA)).fillna(0)
    data["net_debt_to_ebitda"] = (data["net_debt"] / data["ebitda"].replace(0, pd.NA)).fillna(data["net_debt_to_ebitda"]).clip(lower=-5, upper=10)
    data["debt_to_equity"] = (data["total_debt"] / data["shareholders_equity"].replace(0, pd.NA)).fillna(0).clip(lower=0, upper=10)
    data["earnings_stability_score"] = data["fcf_stability"].fillna(50).clip(0, 100)
    data["cash_flow_quality_score"] = (
        35 * data["free_cash_flow_yield"].rank(pct=True)
        + 30 * data["fcf_margin"].rank(pct=True)
        + 20 * data["fcf_stability"].fillna(50) / 100
        + 15 * data["cfo_to_net_income"].clip(0, 1.5) / 1.5
    ).clip(0, 100)
    data["balance_sheet_strength_score"] = (
        45 * (1 - (data["net_debt_to_ebitda"] / 5).clip(0, 1))
        + 25 * (1 - (data["debt_to_equity"] / 3).clip(0, 1))
        + 20 * (data["interest_coverage"].fillna(8) / 20).clip(0, 1)
        + 10 * data["roic"].rank(pct=True)
    ).clip(0, 100)
    data["cet1_ratio"] = data.get("cet1_ratio", pd.NA)
    data["solvency_ratio"] = data.get("solvency_ratio", pd.NA)
    data["npl_ratio"] = data.get("npl_ratio", pd.NA)
    data["book_value_growth"] = data.get("book_value_growth", pd.NA)
    financial_strength = (
        30 * (data["cet1_ratio"].astype("float64").fillna(0.12).clip(0.08, 0.20) - 0.08) / 0.12
        + 30 * (data["solvency_ratio"].astype("float64").fillna(1.5).clip(1.0, 2.5) - 1.0) / 1.5
        + 20 * (1 - (data["npl_ratio"].astype("float64").fillna(0.03) / 0.08).clip(0, 1))
        + 20 * data["book_value_growth"].astype("float64").fillna(0.04).rank(pct=True)
    )
    data["financial_sector_strength_score"] = financial_strength.where(data["sector"].eq("Financials")).clip(0, 100)
    data.loc[data["sector"].eq("Financials"), "balance_sheet_strength_score"] = data.loc[
        data["sector"].eq("Financials"), "financial_sector_strength_score"
    ].fillna(data["balance_sheet_strength_score"])
    return data
