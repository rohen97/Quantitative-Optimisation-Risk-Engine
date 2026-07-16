from __future__ import annotations

import numpy as np
import pandas as pd


def _weights(frame: pd.DataFrame, weight_col: str = "target_weight") -> pd.Series:
    return frame.get(weight_col, pd.Series(0, index=frame.index)).fillna(0).astype(float)


def calculate_portfolio_expected_return(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    return float((_weights(portfolio, weight_col) * portfolio["expected_total_return_12m"].fillna(0)).sum())


def calculate_portfolio_dividend_yield(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    return float((_weights(portfolio, weight_col) * portfolio["dividend_yield"].fillna(0)).sum())


def _fallback_correlation(row_i: pd.Series, row_j: pd.Series) -> float:
    if row_i.get("sector") == row_j.get("sector"):
        return 0.60
    if row_i.get("country") == row_j.get("country"):
        return 0.50
    if row_i.get("region") == row_j.get("region"):
        return 0.40
    if row_i.get("currency") == row_j.get("currency"):
        return 0.35
    return 0.25


def calculate_portfolio_volatility(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    weights = _weights(portfolio, weight_col).to_numpy()
    vols = portfolio["expected_volatility_12m"].fillna(0.20).to_numpy()
    if len(weights) == 0:
        return 0.0
    corr = np.eye(len(weights))
    rows = portfolio.reset_index(drop=True)
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            corr[i, j] = corr[j, i] = _fallback_correlation(rows.iloc[i], rows.iloc[j])
    covariance = np.outer(vols, vols) * corr
    return float(np.sqrt(max(weights @ covariance @ weights, 0)))


def calculate_portfolio_var_proxy(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    return float((_weights(portfolio, weight_col) * portfolio["var_5_12m"].fillna(-0.20)).sum())


def calculate_portfolio_cvar_proxy(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    return float((_weights(portfolio, weight_col) * portfolio["cvar_5_12m"].fillna(-0.30)).sum())


def calculate_portfolio_expected_shortfall_proxy(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    return float((_weights(portfolio, weight_col) * portfolio["expected_shortfall_5_12m"].fillna(-0.30)).sum())


def calculate_portfolio_drawdown_probability(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    return float((_weights(portfolio, weight_col) * portfolio["large_drawdown_probability_12m"].fillna(0.20)).sum())


def calculate_portfolio_dividend_cut_risk(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    return float((_weights(portfolio, weight_col) * portfolio["dividend_cut_probability"].fillna(0.10)).sum())


def calculate_hhi(weights: pd.Series) -> float:
    return float(np.square(pd.Series(weights).fillna(0)).sum())


def calculate_effective_number_of_holdings(weights: pd.Series) -> float:
    hhi = calculate_hhi(weights)
    return float(1 / hhi) if hhi > 0 else 0.0


def _exposure(portfolio: pd.DataFrame, column: str, weight_col: str = "target_weight") -> pd.DataFrame:
    return portfolio.assign(_weight=_weights(portfolio, weight_col)).groupby(column, dropna=False)["_weight"].sum().reset_index(name="weight")


def calculate_sector_exposure(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> pd.DataFrame:
    return _exposure(portfolio, "sector", weight_col)


def calculate_country_exposure(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> pd.DataFrame:
    return _exposure(portfolio, "country", weight_col)


def calculate_region_exposure(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> pd.DataFrame:
    return _exposure(portfolio, "region", weight_col)


def calculate_currency_exposure(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> pd.DataFrame:
    return _exposure(portfolio, "currency", weight_col)


def calculate_turnover(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> float:
    return float((_weights(portfolio, weight_col) - portfolio["current_weight"].fillna(0)).abs().sum() / 2)


def calculate_liquidity_days_to_trade(portfolio: pd.DataFrame, nav_usd: float, weight_col: str = "target_weight") -> pd.Series:
    trade_usd = (_weights(portfolio, weight_col) - portfolio["current_weight"].fillna(0)).abs() * nav_usd
    adv = portfolio["average_daily_value_usd"].fillna(5_000_000).clip(lower=1)
    return trade_usd / adv


def calculate_marginal_risk_contribution(portfolio: pd.DataFrame, weight_col: str = "target_weight") -> pd.Series:
    weights = _weights(portfolio, weight_col)
    vol = portfolio["expected_volatility_12m"].fillna(0.20)
    raw = weights * vol
    total = raw.sum()
    return raw / total if total > 0 else pd.Series(0, index=portfolio.index)


def summarise_portfolio_metrics(portfolio: pd.DataFrame, nav_usd: float, method: str, weight_col: str = "target_weight") -> dict[str, float | str]:
    weights = _weights(portfolio, weight_col)
    return {
        "portfolio_method": method,
        "expected_total_return": calculate_portfolio_expected_return(portfolio, weight_col),
        "expected_dividend_yield": calculate_portfolio_dividend_yield(portfolio, weight_col),
        "expected_volatility": calculate_portfolio_volatility(portfolio, weight_col),
        "var_5": calculate_portfolio_var_proxy(portfolio, weight_col),
        "cvar_5": calculate_portfolio_cvar_proxy(portfolio, weight_col),
        "expected_shortfall_5": calculate_portfolio_expected_shortfall_proxy(portfolio, weight_col),
        "dividend_cut_risk": calculate_portfolio_dividend_cut_risk(portfolio, weight_col),
        "drawdown_probability": calculate_portfolio_drawdown_probability(portfolio, weight_col),
        "turnover": calculate_turnover(portfolio, weight_col),
        "HHI": calculate_hhi(weights),
        "effective_number_of_holdings": calculate_effective_number_of_holdings(weights),
        "max_single_name_weight": float(weights.max()) if len(weights) else 0.0,
        "max_sector_weight": float(calculate_sector_exposure(portfolio, weight_col)["weight"].max()) if len(portfolio) else 0.0,
        "max_country_weight": float(calculate_country_exposure(portfolio, weight_col)["weight"].max()) if len(portfolio) else 0.0,
        "max_currency_weight": float(calculate_currency_exposure(portfolio, weight_col)["weight"].max()) if len(portfolio) else 0.0,
        "max_liquidity_days_to_trade": float(calculate_liquidity_days_to_trade(portfolio, nav_usd, weight_col).max()) if len(portfolio) else 0.0,
    }
