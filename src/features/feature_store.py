from __future__ import annotations

import pandas as pd

from src.features.dividend_features import build_dividend_features
from src.features.financial_features import build_financial_features
from src.features.liquidity_features import build_liquidity_features
from src.features.portfolio_fit_features import build_portfolio_fit_features
from src.features.risk_features import build_price_risk_features
from src.features.valuation_features import build_valuation_features


def build_feature_store(
    universe: pd.DataFrame,
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame,
    sentiment: pd.DataFrame,
    portfolio: pd.DataFrame,
    regime: pd.DataFrame,
    *,
    price_risk_features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build stock-level monthly features from raw/mock inputs."""
    data = universe.merge(fundamentals.drop(columns=["sector"], errors="ignore"), on=["security_id", "ticker"], how="left")
    data["instrument_type"] = data.get("instrument_type", "Equity")
    data["listing_status"] = data.get("listing_status", "Active")
    data = build_financial_features(data)
    data = build_dividend_features(data)
    data = build_valuation_features(data)
    risk_features = price_risk_features if price_risk_features is not None else build_price_risk_features(prices)
    data = data.merge(risk_features, on="ticker", how="left")
    data = data.merge(build_liquidity_features(universe, float(portfolio["market_value_usd"].sum())), on="ticker", how="left")
    data = data.merge(sentiment, on=["security_id", "ticker"], how="left")
    if "liquidity_stress_score_x" in data.columns or "liquidity_stress_score_y" in data.columns:
        data["liquidity_stress_score"] = data.get("liquidity_stress_score_y", pd.Series(index=data.index, dtype="float64")).fillna(
            data.get("liquidity_stress_score_x", pd.Series(index=data.index, dtype="float64"))
        )
        data = data.drop(columns=["liquidity_stress_score_x", "liquidity_stress_score_y"], errors="ignore")
    data = data.merge(regime, on="ticker", how="left")
    data["news_sentiment_30d"] = data.get("news_sentiment_30d", pd.Series(0, index=data.index)).fillna(0)
    data["negative_news_intensity"] = data.get("negative_news_intensity", pd.Series(0, index=data.index)).fillna(0)
    data["controversy_score"] = data.get("controversy_score", pd.Series(0, index=data.index)).fillna(0)
    fallback_sentiment_score = (
        50
        + 20 * data["news_sentiment_30d"].fillna(0)
        - 0.25 * data["negative_news_intensity"].fillna(0)
        - 0.15 * data["controversy_score"].fillna(0)
    ).clip(0, 100)
    data["sentiment_alt_data_score"] = data.get("sentiment_alt_data_score", fallback_sentiment_score).fillna(fallback_sentiment_score)
    data["sentiment_alt_signal_score"] = data["sentiment_alt_data_score"]
    data["ml_expected_risk_adjusted_return_score"] = (55 + 25 * data["momentum_6m"] - 80 * data["volatility_1y"]).clip(0, 100)
    data["ml_expected_risk_adjusted_score"] = data["ml_expected_risk_adjusted_return_score"]
    data["regime_suitability_score"] = data["regime_suitability_score"].fillna(50)
    data["feature_month"] = pd.Timestamp.today().normalize().replace(day=1)
    return build_portfolio_fit_features(data, portfolio)
