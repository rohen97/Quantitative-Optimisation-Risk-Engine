from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_GROUPS = {
    "quality_features": ["cash_flow_quality_score", "balance_sheet_strength_score", "dividend_safety_score", "roe", "roic"],
    "income_features": ["dividend_yield", "payout_ratio", "fcf_dividend_cover", "free_cash_flow_yield"],
    "valuation_features": ["valuation_score", "pe_ratio", "pb_ratio", "ev_to_ebitda"],
    "risk_features": ["volatility_1y", "beta_local_market", "max_drawdown_1y", "var_5", "cvar_5"],
    "liquidity_features": ["liquidity_score", "liquidity_stress_score", "average_daily_value_usd"],
    "sentiment_features": ["sentiment_alt_signal_score", "negative_news_intensity", "credit_stress_score", "regulatory_risk_score"],
    "narrative_features": ["risk_reframing_score", "distress_similarity_score", "dividend_risk_similarity_score"],
    "regime_features": ["regime_suitability_score", "regime_risk_score", "regime_deterioration_probability"],
    "portfolio_fit_features": ["diversification_benefit_score", "incremental_portfolio_cvar", "portfolio_fit_score"],
    "categorical_features": ["region", "country", "sector", "currency", "dominant_regime"],
}


def _safe_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.replace([np.inf, -np.inf], np.nan)
    numeric = data.select_dtypes(include=["number", "bool"]).copy()
    for column in numeric.columns:
        numeric[column] = numeric[column].fillna(numeric[column].median() if numeric[column].notna().any() else 0)
    return numeric


def build_forecast_feature_matrix(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    """Build a model-ready feature matrix while excluding future target columns."""
    data = features.copy()
    target_like = [col for col in data.columns if col.startswith("forward_") or col.endswith("_event_forward_12m")]
    identifiers = data[[col for col in ["security_id", "ticker", "company_name", "country", "region", "sector", "currency"] if col in data]].copy()
    model_input = data.drop(columns=target_like, errors="ignore")
    grouped_columns = {name: [col for col in cols if col in model_input.columns] for name, cols in FEATURE_GROUPS.items()}
    numeric_columns = sorted({col for cols in grouped_columns.values() for col in cols if col in model_input.columns and col not in FEATURE_GROUPS["categorical_features"]})
    numeric = _safe_numeric(model_input[numeric_columns]) if numeric_columns else pd.DataFrame(index=model_input.index)
    categoricals = [col for col in FEATURE_GROUPS["categorical_features"] if col in model_input.columns]
    encoded = pd.get_dummies(model_input[categoricals].fillna("Unknown"), prefix=categoricals, dtype=float) if categoricals else pd.DataFrame(index=model_input.index)
    matrix = pd.concat([numeric, encoded], axis=1).fillna(0.0)
    return identifiers, matrix, grouped_columns
