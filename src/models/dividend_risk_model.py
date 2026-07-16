from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_dividend_cut_probability(features: pd.DataFrame) -> pd.DataFrame:
    """Estimate dividend-cut risk with deterministic conservative fallback rules."""
    data = features.copy()
    payout = data.get("payout_ratio", pd.Series(0.55, index=data.index)).fillna(0.55)
    cover = data.get("fcf_dividend_cover", pd.Series(1.5, index=data.index)).fillna(1.5)
    fcf_yield = data.get("free_cash_flow_yield", pd.Series(0.05, index=data.index)).fillna(0.05)
    quality = data.get("cash_flow_quality_score", pd.Series(50, index=data.index)).fillna(50)
    balance = data.get("balance_sheet_strength_score", pd.Series(50, index=data.index)).fillna(50)
    leverage = data.get("net_debt_to_ebitda", pd.Series(2.0, index=data.index)).fillna(2.0)
    interest = data.get("interest_coverage", pd.Series(6.0, index=data.index)).fillna(6.0)
    dividend_news = data.get("dividend_risk_score", pd.Series(0, index=data.index)).fillna(0)
    dividend_narrative = data.get("dividend_risk_similarity_score", pd.Series(0, index=data.index)).fillna(0)
    negative_news = data.get("negative_news_intensity_30d", data.get("negative_news_intensity", pd.Series(0, index=data.index))).fillna(0)
    credit = data.get("credit_stress_score", pd.Series(0, index=data.index)).fillna(0)
    deterioration = data.get("regime_deterioration_probability", pd.Series(0, index=data.index)).fillna(0)
    raw = (
        0.08
        + 0.28 * ((payout - 0.65) / 0.45).clip(0, 1)
        + 0.20 * ((1.2 - cover) / 1.2).clip(0, 1)
        + 0.12 * ((0.02 - fcf_yield) / 0.08).clip(0, 1)
        + 0.12 * ((50 - quality) / 50).clip(0, 1)
        + 0.10 * ((50 - balance) / 50).clip(0, 1)
        + 0.10 * ((leverage - 3) / 3).clip(0, 1)
        + 0.06 * ((4 - interest) / 4).clip(0, 1)
        + 0.10 * (dividend_news / 100).clip(0, 1)
        + 0.10 * (dividend_narrative / 100).clip(0, 1)
        + 0.04 * (negative_news / 5).clip(0, 1)
        + 0.08 * (credit / 100).clip(0, 1)
        + 0.06 * deterioration.clip(0, 1)
    )
    probability = raw.clip(0, 0.95)
    output = data[[col for col in ["security_id", "ticker", "company_name"] if col in data]].copy()
    output["dividend_cut_probability"] = probability
    output["dividend_sustainability_score"] = (100 * (1 - probability)).clip(0, 100)
    output["dividend_growth_probability"] = (0.65 - probability + (quality - 50) / 200).clip(0, 0.95)
    output["dividend_risk_model_confidence"] = np.where(probability > 0.35, 0.78, 0.68)
    return output
