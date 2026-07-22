from __future__ import annotations

import numpy as np
import pandas as pd


DEFENSIVE_SECTORS = {"Utilities", "Health Care", "Healthcare", "Consumer Staples", "Telecommunications"}


def _normalise_signal(signal: pd.Series) -> pd.Series:
    signal = pd.to_numeric(signal, errors="coerce").fillna(0.0)
    z = (signal - signal.mean()) / (signal.std(ddof=0) + 1e-8)
    return z


def _bounded_action(signal: pd.Series, scale: float) -> np.ndarray:
    return np.clip((_normalise_signal(signal) * float(scale)).to_numpy(dtype=float), -float(scale), float(scale))


def _column(data: pd.DataFrame, column: str, default: float) -> pd.Series:
    if column in data:
        return pd.to_numeric(data[column], errors="coerce").fillna(default)
    return pd.Series(default, index=data.index, dtype=float)


def stable_low_chaos_action(asset_data: pd.DataFrame, scale: float = 0.01) -> np.ndarray:
    """Stable-regime specialist: return, dividends, quality, cash flow and low turnover."""
    ret = _column(asset_data, "expected_total_return_12m", 0.05)
    div = _column(asset_data, "expected_dividend_return_12m", _column(asset_data, "dividend_yield", 0.03))
    quality = _column(asset_data, "cashflow_quality_score", 50) / 100
    safety = _column(asset_data, "dividend_safety_score", 50) / 100
    turnover_drag = (_column(asset_data, "current_weight", 0.0) - _column(asset_data, "target_weight", 0.0)).abs()
    signal = ret + div + 0.25 * quality + 0.20 * safety - 0.20 * turnover_drag
    return _bounded_action(signal, scale)


def crisis_high_chaos_action(asset_data: pd.DataFrame, scale: float = 0.01) -> np.ndarray:
    """Crisis specialist: lower tail risk, drawdown, leverage and liquidity stress."""
    cvar = _column(asset_data, "cvar_5_12m", -0.25)
    es = _column(asset_data, "expected_shortfall_5_12m", -0.25)
    drawdown = _column(asset_data, "large_drawdown_probability_12m", 0.20)
    liquidity = _column(asset_data, "liquidity_score", 50) / 100
    leverage = _column(asset_data, "leverage_metric", _column(asset_data, "net_debt_to_ebitda", 2.0)) / 5
    safety = _column(asset_data, "dividend_safety_score", 50) / 100
    sector_bonus = asset_data.get("sector", pd.Series("", index=asset_data.index)).astype(str).isin(DEFENSIVE_SECTORS).astype(float) * 0.15
    signal = cvar + es - drawdown - leverage + liquidity + safety + sector_bonus
    return _bounded_action(signal, scale)


def inflation_action(asset_data: pd.DataFrame, scale: float = 0.01) -> np.ndarray:
    """Future-ready inflation specialist placeholder."""
    pricing_power = _column(asset_data, "cashflow_quality_score", 50) / 100
    dividend = _column(asset_data, "dividend_yield", 0.03)
    valuation = _column(asset_data, "valuation_score", 50) / 100
    return _bounded_action(pricing_power + dividend + valuation, scale)


def regional_stress_action(asset_data: pd.DataFrame, scale: float = 0.01) -> np.ndarray:
    """Future-ready regional stress specialist placeholder."""
    liquidity = _column(asset_data, "liquidity_score", 50) / 100
    regime = _column(asset_data, "regime_suitability_score", 50) / 100
    return _bounded_action(liquidity + regime, scale)


def credit_stress_action(asset_data: pd.DataFrame, scale: float = 0.01) -> np.ndarray:
    """Future-ready credit stress specialist placeholder."""
    balance = _column(asset_data, "balance_sheet_strength_score", 50) / 100
    interest = _column(asset_data, "interest_coverage", 5.0) / 10
    credit = _column(asset_data, "credit_stress_similarity", 0.0)
    return _bounded_action(balance + interest - credit, scale)


def low_volatility_action(asset_data: pd.DataFrame, scale: float = 0.01) -> np.ndarray:
    """Tilt toward lower volatility and stronger liquidity."""
    vol = _column(asset_data, "expected_volatility_12m", 0.20).clip(lower=0.03)
    liq = _column(asset_data, "liquidity_score", 50) / 100
    signal = (1 / vol) * liq
    return _bounded_action(signal, scale)


def high_volatility_defensive_action(asset_data: pd.DataFrame, scale: float = 0.012) -> np.ndarray:
    """Reduce high tail-risk names and tilt toward dividend safety."""
    safety = _column(asset_data, "dividend_safety_score", 50) / 100
    tail = _column(asset_data, "tail_risk_score", 50) / 100
    drawdown = _column(asset_data, "large_drawdown_probability_12m", 0.20)
    signal = safety - tail - drawdown
    return _bounded_action(signal, scale)
