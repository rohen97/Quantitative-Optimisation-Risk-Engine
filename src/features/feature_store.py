from __future__ import annotations

import pandas as pd

from src.features.dividend_features import build_dividend_features
from src.features.financial_features import build_financial_features
from src.features.liquidity_features import build_liquidity_features
from src.features.portfolio_fit_features import build_portfolio_fit_features
from src.features.risk_features import build_price_risk_features
from src.features.valuation_features import build_valuation_features


def build_feature_store(universe: pd.DataFrame, prices: pd.DataFrame, fundamentals: pd.DataFrame, sentiment: pd.DataFrame, portfolio: pd.DataFrame, regime: pd.DataFrame) -> pd.DataFrame:
    data = universe.merge(fundamentals.drop(columns=["sector"], errors="ignore"), on=["security_id", "ticker"], how="left")
    data = build_financial_features(data)
    data = build_dividend_features(data)
    data = build_valuation_features(data)
    data = data.merge(build_price_risk_features(prices), on="ticker", how="left")
    data = data.merge(build_liquidity_features(universe), on="ticker", how="left")
    data = data.merge(sentiment, on=["security_id", "ticker"], how="left")
    data = data.merge(regime, on="ticker", how="left")
    data["sentiment_alt_signal_score"] = (
        50
        + 20 * data["news_sentiment_30d"].fillna(0)
        - 0.25 * data["negative_news_intensity"].fillna(0)
        - 0.15 * data["controversy_score"].fillna(0)
    ).clip(0, 100)
    data["ml_expected_risk_adjusted_return_score"] = (55 + 25 * data["momentum_6m"] - 80 * data["volatility_1y"]).clip(0, 100)
    return build_portfolio_fit_features(data, portfolio)
