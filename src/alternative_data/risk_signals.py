from __future__ import annotations

import pandas as pd


def build_risk_signal_overlay(
    frame: pd.DataFrame,
    dividend_risk_threshold: float = 80,
    regulatory_risk_threshold: float = 85,
    credit_stress_threshold: float = 85,
    negative_news_spike_zscore: float = 3.0,
) -> pd.DataFrame:
    """Build rule-based alt-data risk flags for scorecard/risk overlays."""
    data = frame[["ticker"]].copy()
    negative = frame["negative_news_intensity_30d"].fillna(0)
    std = negative.std()
    spike_threshold = negative.mean() + negative_news_spike_zscore * (std if std > 0 else 1)
    data["dividend_risk_flag"] = frame["dividend_risk_score"] > dividend_risk_threshold
    data["regulatory_risk_flag"] = frame["regulatory_risk_score"] > regulatory_risk_threshold
    data["governance_risk_flag"] = frame["governance_red_flag_count"] > 2
    data["credit_stress_flag"] = frame["credit_stress_score"] > credit_stress_threshold
    data["litigation_risk_flag"] = frame["litigation_risk_score"] > regulatory_risk_threshold
    data["negative_sentiment_spike_flag"] = negative > spike_threshold
    data["management_confidence_deterioration_flag"] = frame["management_confidence_score"] < 35
    data["alt_data_exclusion_flag"] = data["regulatory_risk_flag"] | data["credit_stress_flag"]
    data["alt_data_review_required_flag"] = (
        data["dividend_risk_flag"]
        | data["governance_risk_flag"]
        | data["litigation_risk_flag"]
        | data["negative_sentiment_spike_flag"]
        | data["management_confidence_deterioration_flag"]
    )
    return data


def risk_flags(frame: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible alias for existing tests/callers."""
    return build_risk_signal_overlay(frame)
