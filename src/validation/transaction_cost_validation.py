from __future__ import annotations

import math

import numpy as np
import pandas as pd


def estimate_transaction_cost(
    traded_notional: float,
    commission_bps: float,
    half_spread_bps: float,
    slippage_bps: float,
    volatility: float,
    average_daily_value: float | None,
    impact_coefficient: float,
    conservative_adv_fallback: float = 5_000_000.0,
) -> dict[str, float | bool]:
    notional = abs(float(traded_notional))
    adv_missing = average_daily_value is None or not np.isfinite(average_daily_value) or average_daily_value <= 0
    adv = conservative_adv_fallback if adv_missing else float(average_daily_value)
    linear = (commission_bps + half_spread_bps + slippage_bps) / 10_000.0 * notional
    impact = impact_coefficient * max(float(volatility), 0.0) * math.sqrt(notional / max(adv, 1e-12)) * notional
    return {"linear_cost": linear, "market_impact_cost": impact, "total_cost": linear + impact, "adv_estimated": adv_missing}


def validate_cost_scenarios(strategy_returns: pd.DataFrame, multipliers: list[float], base_cost_column: str = "transaction_cost") -> pd.DataFrame:
    required = {"strategy", "gross_return", base_cost_column}
    if not required.issubset(strategy_returns):
        return pd.DataFrame(columns=["strategy", "cost_multiplier", "gross_return", "net_return", "cost_drag"])
    rows = []
    for multiplier in multipliers:
        for strategy, group in strategy_returns.groupby("strategy"):
            gross = float(group["gross_return"].sum())
            cost = float(group[base_cost_column].sum()) * multiplier
            rows.append({"strategy": strategy, "cost_multiplier": multiplier, "gross_return": gross, "net_return": gross - cost, "cost_drag": cost, "gross_alpha_consumed": cost / abs(gross) if gross else float("nan")})
    return pd.DataFrame(rows)
