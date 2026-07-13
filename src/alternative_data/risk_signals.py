from __future__ import annotations

import pandas as pd


def risk_flags(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[["ticker"]].copy()
    data["negative_sentiment_flag"] = frame["negative_news_intensity"] > 3
    data["credit_stress_flag"] = frame["credit_stress_score"] > 85
    data["regulatory_risk_flag"] = frame["regulatory_risk_score"] > 85
    return data
