from __future__ import annotations

import numpy as np
import pandas as pd


PRICE_RISK_BASE_COLUMNS = [
    "ticker",
    "daily_return",
    "annualised_volatility",
    "downside_volatility",
    "var_5",
    "cvar_5",
    "max_drawdown_1y",
    "momentum_6m",
    "price_return_outlier_count",
    "price_stale_return_fraction",
    "price_data_quality_score",
    "price_data_exclusion_flag",
]


def build_price_risk_base(prices: pd.DataFrame) -> pd.DataFrame:
    """Build ticker-local price statistics without cross-universe ranks."""
    if prices.empty:
        return pd.DataFrame(columns=PRICE_RISK_BASE_COLUMNS)
    sorted_prices = prices.sort_values(["ticker", "date"]).copy()
    sorted_prices["return"] = pd.to_numeric(sorted_prices["return"], errors="coerce")
    outlier = sorted_prices.get(
        "return_outlier_flag",
        sorted_prices["return"].abs().gt(1.0),
    ).fillna(False).astype(bool)
    sorted_prices["_clean_return"] = sorted_prices["return"].where(~outlier)
    grouped = sorted_prices.groupby("ticker", sort=False)
    recent = grouped.tail(252).copy()
    recent_grouped = recent.groupby("ticker", sort=False)
    features = recent_grouped["_clean_return"].agg(
        annualised_volatility="std",
        var_5=lambda values: values.quantile(0.05),
    ).reset_index()
    features["annualised_volatility"] *= np.sqrt(252)
    downside = (
        recent.loc[recent["_clean_return"].lt(0)]
        .groupby("ticker", sort=False)["_clean_return"]
        .std()
        .mul(np.sqrt(252))
        .rename("downside_volatility")
    )
    recent = recent.merge(features[["ticker", "var_5"]], on="ticker", how="left")
    cvar = (
        recent.loc[recent["_clean_return"].le(recent["var_5"])]
        .groupby("ticker", sort=False)["_clean_return"]
        .mean()
        .rename("cvar_5")
    )
    features = features.merge(downside, on="ticker", how="left").merge(cvar, on="ticker", how="left")
    if "full_history_daily_return" in sorted_prices:
        daily_return = grouped["full_history_daily_return"].first().rename("daily_return").reset_index()
    else:
        daily_return = grouped["return"].mean().rename("daily_return").reset_index()
    features = features.merge(daily_return, on="ticker", how="left")
    recent["_running_peak"] = recent.groupby("ticker", sort=False)["close"].cummax()
    drawdown = (
        (recent["close"] / recent["_running_peak"] - 1.0)
        .groupby(recent["ticker"], sort=False)
        .min()
        .rename("max_drawdown_1y")
    )
    momentum_prices = grouped.tail(126)
    momentum_grouped = momentum_prices.groupby("ticker", sort=False)["close"]
    momentum = (momentum_grouped.last() / momentum_grouped.first() - 1.0).rename("momentum_6m")
    quality = grouped.agg(
        price_return_outlier_count=("return_outlier_flag", "sum")
        if "return_outlier_flag" in sorted_prices
        else ("return", lambda values: int(values.abs().gt(1.0).sum())),
        price_stale_return_fraction=("_clean_return", lambda values: float(values.fillna(0.0).eq(0.0).mean())),
    ).reset_index()
    quality["price_return_outlier_count"] = quality["price_return_outlier_count"].fillna(0).astype(int)
    quality["price_data_exclusion_flag"] = quality["price_return_outlier_count"].gt(0)
    quality["price_data_quality_score"] = (
        100.0
        - quality["price_return_outlier_count"].clip(upper=4) * 25.0
        - quality["price_stale_return_fraction"].sub(0.50).clip(lower=0.0) * 100.0
    ).clip(0.0, 100.0)
    features = (
        features.merge(drawdown, on="ticker", how="left")
        .merge(momentum, on="ticker", how="left")
        .merge(quality, on="ticker", how="left")
    )
    return features[PRICE_RISK_BASE_COLUMNS]


def finalise_price_risk_features(base_features: pd.DataFrame) -> pd.DataFrame:
    """Apply cross-universe price ranks after all ticker batches are merged."""
    if base_features.empty:
        return base_features.copy()
    features = base_features.copy()
    features["volatility_1y"] = features["annualised_volatility"]
    features["beta_local_market"] = 1.0 + features["daily_return"].rank(pct=True).sub(0.5) * 0.4
    features["beta_global_market"] = 0.9 + features["annualised_volatility"].rank(pct=True).sub(0.5) * 0.5
    features["beta_1y"] = features["beta_local_market"]
    annual_return_proxy = features["daily_return"] * 252
    features["sharpe_proxy"] = annual_return_proxy / features["annualised_volatility"].replace(0, pd.NA)
    features["sortino_proxy"] = annual_return_proxy / features["downside_volatility"].replace(0, pd.NA)
    risk_penalty = (
        0.35 * features["annualised_volatility"].rank(pct=True)
        + 0.25 * features["downside_volatility"].fillna(features["annualised_volatility"]).rank(pct=True)
        + 0.25 * features["max_drawdown_1y"].abs().rank(pct=True)
        + 0.15 * features["cvar_5"].abs().rank(pct=True)
    )
    features["risk_score"] = (100 * (1 - risk_penalty)).clip(0, 100)
    return features


def build_price_risk_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Build ticker-local price statistics and cross-universe risk ranks."""
    return finalise_price_risk_features(build_price_risk_base(prices))
