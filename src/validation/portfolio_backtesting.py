from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PortfolioPerformance:
    observations: int
    annualised_return: float
    annualised_volatility: float
    sharpe: float
    sortino: float
    maximum_drawdown: float
    expected_shortfall: float
    positive_period_ratio: float
    worst_period: float
    best_period: float


def drift_weights(weights: np.ndarray, asset_returns: np.ndarray) -> np.ndarray:
    weight_array = np.asarray(weights, dtype=float)
    return_array = np.asarray(asset_returns, dtype=float)
    if not np.isfinite(return_array).all():
        raise ValueError("Missing or non-finite returns cannot be silently zero-filled.")
    gross_values = weight_array * (1.0 + return_array)
    total = gross_values.sum()
    if not np.isfinite(total) or total <= 0:
        raise ValueError("Invalid portfolio value during weight drift.")
    return gross_values / total


def calculate_turnover(target_weights: np.ndarray, pre_trade_weights: np.ndarray) -> float:
    return float(0.5 * np.sum(np.abs(np.asarray(target_weights, dtype=float) - np.asarray(pre_trade_weights, dtype=float))))


def calculate_drawdown(portfolio_values: pd.Series) -> pd.Series:
    values = pd.to_numeric(portfolio_values, errors="coerce")
    if values.isna().any():
        raise ValueError("Portfolio values contain missing observations.")
    return values / values.cummax() - 1.0


def calculate_portfolio_performance(returns: pd.Series, periods_per_year: int = 12) -> PortfolioPerformance:
    values = pd.to_numeric(returns, errors="coerce")
    if values.isna().any() or values.empty:
        raise ValueError("Portfolio returns must be complete and non-empty.")
    array = values.to_numpy(dtype=float)
    annual_return = float(np.prod(1.0 + array) ** (periods_per_year / len(array)) - 1.0)
    volatility = float(array.std(ddof=1) * np.sqrt(periods_per_year)) if len(array) > 1 else 0.0
    downside = array[array < 0]
    downside_deviation = float(downside.std(ddof=1) * np.sqrt(periods_per_year)) if downside.size > 1 else 0.0
    wealth = pd.Series(np.cumprod(1.0 + array))
    max_drawdown = float(calculate_drawdown(wealth).min())
    var = float(np.quantile(array, 0.05))
    tail = array[array <= var]
    es = float(-tail.mean()) if tail.size else float(-var)
    return PortfolioPerformance(
        observations=len(array),
        annualised_return=annual_return,
        annualised_volatility=volatility,
        sharpe=annual_return / volatility if volatility > 0 else 0.0,
        sortino=annual_return / downside_deviation if downside_deviation > 0 else 0.0,
        maximum_drawdown=max_drawdown,
        expected_shortfall=es,
        positive_period_ratio=float((array > 0).mean()),
        worst_period=float(array.min()),
        best_period=float(array.max()),
    )


def backtest_rebalanced_portfolio(
    returns: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_rate: float = 0.0,
) -> pd.DataFrame:
    if returns.isna().any().any():
        raise ValueError("Missing asset returns require an explicit data policy.")
    aligned_dates = returns.index.intersection(target_weights.index)
    if aligned_dates.empty:
        raise ValueError("No aligned rebalance dates.")
    rows = []
    previous = target_weights.loc[aligned_dates[0]].to_numpy(dtype=float)
    for date in aligned_dates:
        target = target_weights.loc[date].to_numpy(dtype=float)
        period_return = returns.loc[date].to_numpy(dtype=float)
        pre_trade = drift_weights(previous, period_return)
        turnover = calculate_turnover(target, pre_trade)
        gross_return = float(previous @ period_return)
        cost = turnover * cost_rate
        rows.append({"date": date, "gross_return": gross_return, "net_return": gross_return - cost, "turnover": turnover, "transaction_cost": cost})
        previous = target
    return pd.DataFrame(rows)
