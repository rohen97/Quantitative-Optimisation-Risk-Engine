from __future__ import annotations

import numpy as np
import pandas as pd


def _trade_action(row: pd.Series, threshold: float) -> str:
    target = float(row["target_weight"])
    current = float(row["current_weight"])
    eligible = bool(row.get("eligible_for_optimisation", target > 0))
    if target == 0 and not eligible:
        return "Avoid / Exit" if current > threshold else "Avoid"
    if target > current + threshold:
        return "Increase" if current > threshold else "Buy"
    if target < current - threshold:
        return "Reduce" if target > threshold else "Sell"
    return "Hold"


def _rationale(row: pd.Series) -> str:
    action = str(row["trade_action"]).split()[0]
    if "Avoid" in row["trade_action"]:
        return "Avoid: excluded by liquidity, recommendation, regime, narrative or alternative-data controls."
    if action in {"Buy", "Increase"}:
        return "Increase: improves risk-adjusted return, dividend quality, diversification or regime suitability."
    if action in {"Reduce", "Sell"}:
        return "Reduce: high CVaR/Expected Shortfall, dividend risk, drawdown risk or weak scorecard support."
    return "Hold: acceptable risk-adjusted return but limited incremental portfolio benefit."


def build_trade_list(
    optimised_portfolio: pd.DataFrame,
    nav_usd: float,
    threshold: float = 0.0025,
) -> pd.DataFrame:
    """Build actionable trade recommendations from current and target weights."""
    data = optimised_portfolio.copy()
    data["current_weight"] = data["current_weight"].fillna(0)
    data["target_weight"] = data["target_weight"].fillna(0)
    data["weight_change"] = data["target_weight"] - data["current_weight"]
    data["trade_action"] = data.apply(_trade_action, axis=1, threshold=threshold)
    data["trade_size_usd"] = data["weight_change"] * nav_usd
    data["expected_portfolio_impact"] = data["weight_change"] * data["expected_total_return_12m"].fillna(0)
    data["risk_flags"] = data.get("risk_management_flags", pd.Series("", index=data.index)).fillna("")
    data.loc[data["dividend_cut_probability"] > 0.35, "risk_flags"] += "dividend_cut_risk;"
    data.loc[data["large_drawdown_probability_12m"] > 0.35, "risk_flags"] += "drawdown_risk;"
    data.loc[data["cvar_5_12m"] < -0.25, "risk_flags"] += "cvar_risk;"
    data["trade_rationale"] = data.apply(_rationale, axis=1)
    columns = [
        "security_id",
        "ticker",
        "company_name",
        "country",
        "region",
        "sector",
        "currency",
        "current_weight",
        "target_weight",
        "weight_change",
        "trade_action",
        "trade_size_usd",
        "expected_total_return_12m",
        "expected_dividend_return_12m",
        "p5_return_12m",
        "var_5_12m",
        "cvar_5_12m",
        "expected_shortfall_5_12m",
        "dividend_cut_probability",
        "large_drawdown_probability_12m",
        "regime_suitability_score",
        "portfolio_fit_score",
        "final_recommendation_score",
        "risk_flags",
        "trade_rationale",
        "expected_portfolio_impact",
    ]
    return data[columns].sort_values("weight_change", key=np.abs, ascending=False).reset_index(drop=True)
