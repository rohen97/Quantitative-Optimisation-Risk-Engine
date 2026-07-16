from __future__ import annotations

import pandas as pd


def _windowed_mean(frame: pd.DataFrame, value: str, days: int, as_of: pd.Timestamp) -> pd.Series:
    cutoff = as_of - pd.Timedelta(days=days)
    window = frame[frame["publication_timestamp"] >= cutoff]
    return window.groupby("security_id")[value].mean()


def _windowed_count(frame: pd.DataFrame, condition: pd.Series, days: int, as_of: pd.Timestamp) -> pd.Series:
    cutoff = as_of - pd.Timedelta(days=days)
    window = frame[(frame["publication_timestamp"] >= cutoff) & condition]
    return window.groupby("security_id").size()


def build_sentiment_features(
    documents: pd.DataFrame,
    mentions: pd.DataFrame,
    sentiment_scores: pd.DataFrame,
    event_signals: pd.DataFrame,
    universe: pd.DataFrame,
    as_of_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Aggregate document-level sentiment/events into stock-level monthly features."""
    as_of = (as_of_date or pd.Timestamp.today()).normalize()
    scored = sentiment_scores.merge(mentions[["document_id", "security_id", "ticker"]], on=["document_id", "security_id"], how="left")
    scored = scored.merge(documents[["document_id", "publication_timestamp"]], on="document_id", how="left")
    scored["publication_timestamp"] = pd.to_datetime(scored["publication_timestamp"])
    base = universe[["security_id", "ticker"]].copy()
    for days in [7, 30, 90]:
        base[f"news_sentiment_{days}d"] = base["security_id"].map(_windowed_mean(scored, "sentiment_score", days, as_of)).fillna(50)
    base["sentiment_momentum_30d"] = base["news_sentiment_30d"] - base["news_sentiment_90d"]
    base["sentiment_momentum_90d"] = base["news_sentiment_90d"] - 50
    negative = scored["negative_score"] > scored["positive_score"]
    positive = scored["positive_score"] > scored["negative_score"]
    base["negative_news_intensity_30d"] = base["security_id"].map(_windowed_count(scored, negative, 30, as_of)).fillna(0).astype(float)
    base["positive_news_intensity_30d"] = base["security_id"].map(_windowed_count(scored, positive, 30, as_of)).fillna(0).astype(float)
    for column in [
        "management_confidence_score",
        "regulatory_risk_score",
        "litigation_risk_score",
        "governance_risk_score",
        "credit_stress_score",
        "dividend_language_score",
        "cashflow_language_score",
    ]:
        base[column] = base["security_id"].map(_windowed_mean(scored, column, 90, as_of)).fillna(50 if "risk" not in column and "stress" not in column else 0)
    if event_signals.empty:
        event_summary = pd.DataFrame(columns=["security_id", "event_severity_score", "governance_red_flag_count"])
    else:
        event_summary = event_signals.groupby("security_id").agg(
            event_severity_score=("event_severity", "max"),
            governance_red_flag_count=("event_type", lambda values: int((values == "governance_red_flag").sum())),
        )
    base = base.merge(event_summary, on="security_id", how="left")
    base["event_severity_score"] = base["event_severity_score"].fillna(0)
    base["governance_red_flag_count"] = base["governance_red_flag_count"].fillna(0)
    base["controversy_score_90d"] = (
        base["negative_news_intensity_30d"] * 15
        + base["event_severity_score"] * 0.45
        + base["governance_red_flag_count"] * 20
    ).clip(0, 100)
    base["dividend_risk_score"] = (100 - base["dividend_language_score"] + base["event_severity_score"] * 0.25).clip(0, 100)
    base["cashflow_deterioration_score"] = (100 - base["cashflow_language_score"] + base["negative_news_intensity_30d"] * 10).clip(0, 100)
    doc_counts = mentions.groupby("security_id").size()
    base["abnormal_attention_score"] = (base["security_id"].map(doc_counts).fillna(0) * 12).clip(0, 100)
    base["alt_data_quality_score"] = (50 + base["security_id"].map(doc_counts).fillna(0) * 10).clip(0, 100)
    base["sentiment_alt_data_score"] = (
        0.45 * base["news_sentiment_30d"]
        + 0.20 * base["management_confidence_score"]
        + 0.15 * (100 - base["controversy_score_90d"])
        + 0.20 * (100 - base["credit_stress_score"])
    ).clip(0, 100)
    base["news_sentiment_30d_raw"] = (base["news_sentiment_30d"] - 50) / 50
    base["news_sentiment_90d_raw"] = (base["news_sentiment_90d"] - 50) / 50
    return base
