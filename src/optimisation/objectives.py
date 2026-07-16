from __future__ import annotations

import pandas as pd


def score_weighted_objective(frame: pd.DataFrame) -> pd.Series:
    """Composite quality/score objective with distributional and risk penalties."""
    data = frame.copy()
    positive = (
        0.28 * data["final_recommendation_score"].fillna(50)
        + 0.15 * data["portfolio_fit_score"].fillna(50)
        + 0.12 * data["regime_suitability_score"].fillna(50)
        + 0.15 * data["dividend_safety_score"].fillna(50)
        + 0.10 * data["cashflow_quality_score"].fillna(50)
        + 0.08 * data["balance_sheet_strength_score"].fillna(50)
        + 0.12 * data.get("ml_expected_risk_adjusted_score", data["final_recommendation_score"]).fillna(50)
    )
    penalty = (
        0.10 * data["tail_risk_score"].fillna(50)
        + 0.08 * data["skewness_risk_score"].fillna(50)
        + 0.08 * data["forecast_uncertainty_score"].fillna(50)
        + 60 * data["dividend_cut_probability"].fillna(0.10)
        + 55 * data["large_drawdown_probability_12m"].fillna(0.20)
        + 10 * data["reframing_review_required_flag"].astype(bool).astype(int)
        + 10 * data["regime_review_required_flag"].astype(bool).astype(int)
    )
    return (positive - penalty + 50).clip(lower=0)


def risk_adjusted_return_objective(frame: pd.DataFrame) -> pd.Series:
    """Expected-return objective adjusted for volatility, CVaR, ES, drawdown and dividend risk."""
    ret = frame["expected_total_return_12m"].fillna(0.05)
    vol = frame["expected_volatility_12m"].fillna(0.20).clip(lower=0.03)
    dividend = frame["expected_dividend_return_12m"].fillna(frame["dividend_yield"].fillna(0.03))
    cvar = frame["cvar_5_12m"].fillna(-0.30).abs()
    es = frame["expected_shortfall_5_12m"].fillna(-0.30).abs()
    drawdown = frame["large_drawdown_probability_12m"].fillna(0.20)
    cut = frame["dividend_cut_probability"].fillna(0.10)
    regime = frame["regime_suitability_score"].fillna(50) / 100
    return (50 + 120 * (ret / vol) + 100 * dividend - 50 * cvar - 45 * es - 35 * drawdown - 30 * cut + 20 * regime).clip(lower=0)


def dividend_income_objective(frame: pd.DataFrame) -> pd.Series:
    """Safe income objective that penalises dividend traps."""
    return (
        100 * frame["dividend_yield"].fillna(0.03)
        + 0.35 * frame["dividend_safety_score"].fillna(50)
        + 0.25 * frame["cashflow_quality_score"].fillna(50)
        + 0.15 * frame["balance_sheet_strength_score"].fillna(50)
        - 80 * frame["dividend_cut_probability"].fillna(0.10)
        - 30 * (frame.get("payout_ratio", pd.Series(0.55, index=frame.index)).fillna(0.55) > 0.85).astype(int)
    ).clip(lower=0)


def cvar_expected_shortfall_objective(frame: pd.DataFrame) -> pd.Series:
    """Tail-risk-aware objective for CVaR/Expected Shortfall constrained portfolios."""
    return (
        80 * frame["expected_total_return_12m"].fillna(0.05)
        + 60 * frame["expected_dividend_return_12m"].fillna(0.03)
        + 0.45 * frame["final_recommendation_score"].fillna(50)
        - 65 * frame["cvar_5_12m"].fillna(-0.30).abs()
        - 65 * frame["expected_shortfall_5_12m"].fillna(-0.30).abs()
        - 0.35 * frame["tail_risk_score"].fillna(50)
        - 45 * frame["large_drawdown_probability_12m"].fillna(0.20)
    ).clip(lower=0)


def regime_aware_objective(frame: pd.DataFrame, dominant_regime: str = "steady_state_low_chaos") -> pd.Series:
    """Regime-aware objective with conservative sector/quality tilts."""
    base = score_weighted_objective(frame) + 0.35 * frame["regime_suitability_score"].fillna(50)
    sector = frame["sector"].astype(str)
    region = frame["region"].astype(str)
    defensive = sector.isin(["Healthcare", "Consumer Staples", "Utilities"])
    if dominant_regime == "crisis_high_chaos":
        base += defensive.astype(int) * 20 - frame["expected_volatility_12m"].fillna(0.20) * 30
    elif dominant_regime == "inflation_pressure":
        base += sector.isin(["Financials", "Energy", "Materials"]).astype(int) * 18
    elif dominant_regime == "europe_recession":
        base += defensive.astype(int) * 15 - (region.isin(["DACH", "EU ex-DACH"]) & sector.isin(["Industrials", "Consumer Discretionary"])).astype(int) * 15
    elif dominant_regime == "china_policy_stress":
        base += (region.isin(["Mainland China", "Hong Kong"]) & (frame.get("regulatory_risk_score", pd.Series(0, index=frame.index)).fillna(0) < 50)).astype(int) * 10
    elif dominant_regime == "uk_rate_pressure":
        base += (region.eq("UK") & sector.eq("Financials")).astype(int) * 12
    elif dominant_regime == "credit_stress":
        base += (frame.get("interest_coverage", pd.Series(6, index=frame.index)).fillna(6) > 6).astype(int) * 12
    return base.clip(lower=0)


def income_adjusted_score(frame: pd.DataFrame) -> pd.Series:
    return frame["final_recommendation_score"] + 100 * frame["dividend_yield"]
