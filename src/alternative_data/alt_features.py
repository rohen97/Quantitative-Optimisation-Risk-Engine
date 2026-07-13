from __future__ import annotations

import pandas as pd

from src.data_ingestion.mock_data import generate_mock_sentiment


def build_alt_features(universe: pd.DataFrame) -> pd.DataFrame:
    data = generate_mock_sentiment(universe)
    data["sentiment_momentum"] = data["news_sentiment_30d"] - data["news_sentiment_90d"]
    return data
