from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.config import ROOT


REQUIRED_OPTIMISER_COLUMNS = [
    "security_id",
    "ticker",
    "company_name",
    "country",
    "region",
    "sector",
    "currency",
    "current_weight",
    "current_market_value_usd",
    "final_recommendation",
    "final_recommendation_score",
    "scorecard_score",
    "portfolio_fit_score",
    "regime_suitability_score",
    "sentiment_alt_data_score",
    "narrative_reframing_score",
    "expected_total_return_12m",
    "expected_dividend_return_12m",
    "expected_volatility_12m",
    "p5_return_12m",
    "p50_return_12m",
    "p95_return_12m",
    "var_5_12m",
    "cvar_5_12m",
    "expected_shortfall_5_12m",
    "dividend_cut_probability",
    "large_drawdown_probability_12m",
    "tail_risk_score",
    "skewness_risk_score",
    "forecast_uncertainty_score",
    "liquidity_score",
    "average_daily_value_usd",
    "dividend_yield",
    "free_cash_flow_yield",
    "balance_sheet_strength_score",
    "cashflow_quality_score",
    "dividend_safety_score",
    "regime_review_required_flag",
    "regime_exclusion_flag",
    "reframing_review_required_flag",
    "reframing_exclusion_flag",
    "alt_data_review_required_flag",
    "alt_data_exclusion_flag",
]


def _read_output(filename: str, output_dir: str | Path = "reports/outputs") -> pd.DataFrame:
    path = ROOT / output_dir / filename
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _series(data: pd.DataFrame, column: str, default) -> pd.Series:
    if column in data:
        return data[column]
    return pd.Series(default, index=data.index)


def build_optimiser_input_dataset(
    scorecard: pd.DataFrame,
    current_portfolio: pd.DataFrame | None = None,
    final_recommendations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build one clean stock-level optimiser input dataset with conservative fallbacks."""
    data = scorecard.copy()
    current = current_portfolio.copy() if current_portfolio is not None else pd.DataFrame()
    if not current.empty:
        nav = float(current["market_value_usd"].sum()) if "market_value_usd" in current else 0.0
        current_weights = current[["ticker", "market_value_usd"]].copy()
        current_weights["current_market_value_usd"] = current_weights["market_value_usd"].fillna(0)
        current_weights["current_weight"] = current_weights["current_market_value_usd"] / nav if nav > 0 else 0.0
        data = data.merge(current_weights[["ticker", "current_market_value_usd", "current_weight"]], on="ticker", how="left")
    if final_recommendations is not None and not final_recommendations.empty and "final_recommendation" in final_recommendations:
        data = data.merge(final_recommendations[["ticker", "final_recommendation"]], on="ticker", how="left", suffixes=("", "_branch"))
    data["current_weight"] = _series(data, "current_weight", 0.0).fillna(0.0)
    data["current_market_value_usd"] = _series(data, "current_market_value_usd", 0.0).fillna(0.0)
    data["final_recommendation"] = _series(data, "final_recommendation", data.get("recommendation", "Hold")).fillna(_series(data, "recommendation", "Hold"))
    data["scorecard_score"] = _series(data, "final_recommendation_score", 50).fillna(50)
    data["portfolio_fit_score"] = _series(data, "portfolio_fit_score", data.get("diversification_benefit_score", 50)).fillna(50)
    data["cashflow_quality_score"] = _series(data, "cashflow_quality_score", data.get("cash_flow_quality_score", 50)).fillna(50)
    fallback_values = {
        "expected_total_return_12m": 0.05,
        "expected_dividend_return_12m": _series(data, "dividend_yield", 0.03),
        "expected_volatility_12m": 0.20,
        "p5_return_12m": -0.20,
        "p50_return_12m": 0.05,
        "p95_return_12m": 0.20,
        "var_5_12m": -0.20,
        "cvar_5_12m": -0.30,
        "expected_shortfall_5_12m": -0.30,
        "dividend_cut_probability": 0.10,
        "large_drawdown_probability_12m": 0.20,
        "regime_suitability_score": 50,
        "sentiment_alt_data_score": 50,
        "narrative_reframing_score": 50,
        "liquidity_score": 50,
        "average_daily_value_usd": 5_000_000,
        "tail_risk_score": 50,
        "skewness_risk_score": 50,
        "forecast_uncertainty_score": 50,
        "free_cash_flow_yield": 0.04,
        "balance_sheet_strength_score": 50,
        "dividend_safety_score": 50,
        "regime_review_required_flag": False,
        "regime_exclusion_flag": False,
        "reframing_review_required_flag": False,
        "reframing_exclusion_flag": False,
        "alt_data_review_required_flag": False,
        "alt_data_exclusion_flag": False,
    }
    for column, default in fallback_values.items():
        data[column] = _series(data, column, default).fillna(default)
    for column in ["security_id", "company_name", "country", "region", "sector", "currency"]:
        data[column] = _series(data, column, "Unknown").fillna("Unknown")
    data["dividend_yield"] = _series(data, "dividend_yield", 0.03).fillna(0.03)
    data["final_recommendation_score"] = _series(data, "final_recommendation_score", data["scorecard_score"]).fillna(50)
    data["instrument_type"] = _series(data, "instrument_type", "Equity").fillna("Equity")
    data["listing_status"] = _series(data, "listing_status", "Active").fillna("Active")
    data["risk_management_flags"] = _series(data, "risk_management_flags", "").fillna("")
    return data[[col for col in REQUIRED_OPTIMISER_COLUMNS if col in data] + ["instrument_type", "listing_status", "risk_management_flags"]].copy()


def load_optimiser_input_dataset(output_dir: str | Path = "reports/outputs") -> pd.DataFrame:
    """Load optimiser inputs from output CSVs, returning an empty frame when scorecard is missing."""
    scorecard = _read_output("stock_scorecard.csv", output_dir)
    if scorecard.empty:
        return pd.DataFrame()
    current = _read_output("current_portfolio_enriched.csv", output_dir)
    final = _read_output("final_recommendations.csv", output_dir)
    return build_optimiser_input_dataset(scorecard, current, final)
