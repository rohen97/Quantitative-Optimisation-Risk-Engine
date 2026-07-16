from __future__ import annotations

import pandas as pd

from src.alternative_data.risk_signals import build_risk_signal_overlay
from src.sentiment.entity_mapping import map_entities
from src.sentiment.event_classifier import classify_event_signals
from src.sentiment.sentiment_features import build_sentiment_features
from src.sentiment.sentiment_model import score_documents
from src.sentiment.text_ingestion import load_or_generate_text_documents


def run_alternative_data_pipeline(
    universe: pd.DataFrame,
    sentiment_config: dict | None = None,
    alternative_data_config: dict | None = None,
) -> dict[str, pd.DataFrame]:
    """Run mock/local text ingestion, entity mapping, sentiment, event and feature aggregation."""
    sentiment = (sentiment_config or {}).get("sentiment", sentiment_config or {})
    alt_config = (alternative_data_config or {}).get("alternative_data", alternative_data_config or {})
    documents = load_or_generate_text_documents(universe, use_mock=alt_config.get("use_mock_alt_data", True))
    mentions = map_entities(documents, universe, min_confidence=sentiment.get("min_entity_confidence", 0.70))
    sentiment_scores = score_documents(
        documents,
        mentions,
        sentiment.get("model_name", "rule_based_financial_sentiment"),
        sentiment.get("model_version", "v0.1"),
    )
    events = classify_event_signals(documents, mentions)
    features = build_sentiment_features(documents, mentions, sentiment_scores, events, universe)
    flags = build_risk_signal_overlay(
        features,
        dividend_risk_threshold=alt_config.get("dividend_risk_threshold", 80),
        regulatory_risk_threshold=alt_config.get("regulatory_risk_threshold", 85),
        credit_stress_threshold=alt_config.get("credit_stress_threshold", 85),
        negative_news_spike_zscore=alt_config.get("negative_news_spike_zscore", 3.0),
    )
    features = features.merge(flags, on="ticker", how="left")
    features["news_sentiment_30d"] = features["news_sentiment_30d_raw"]
    features["news_sentiment_90d"] = features["news_sentiment_90d_raw"]
    features["negative_news_intensity"] = features["negative_news_intensity_30d"]
    features["controversy_score"] = features["controversy_score_90d"]
    features["sentiment_momentum"] = features["sentiment_momentum_30d"]
    return {
        "alt_text_documents": documents,
        "alt_entity_mentions": mentions,
        "alt_sentiment_scores": sentiment_scores,
        "alt_event_signals": events,
        "alt_features_monthly": features,
    }


def build_alt_features(universe: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible helper returning monthly alt-data features only."""
    return run_alternative_data_pipeline(universe)["alt_features_monthly"]
