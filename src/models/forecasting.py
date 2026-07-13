from __future__ import annotations

import pandas as pd


def generate_mock_forecasts(scorecard: pd.DataFrame, horizon_months: int) -> pd.DataFrame:
    data = scorecard.copy()
    horizon_scale = horizon_months / 12
    data["expected_total_return"] = (data["dividend_yield"] + data["momentum_6m"].clip(-0.2, 0.3) * 0.4) * horizon_scale
    data["expected_volatility"] = data["volatility_1y"] * horizon_scale**0.5
    data["risk_adjusted_return"] = data["expected_total_return"] / data["expected_volatility"].clip(lower=0.01)
    data["var_5"] = data["expected_total_return"] - 1.65 * data["expected_volatility"]
    data["cvar_5"] = data["expected_total_return"] - 2.05 * data["expected_volatility"]
    data["p5_return"] = data["var_5"]
    data["p50_return"] = data["expected_total_return"]
    data["p95_return"] = data["expected_total_return"] + 1.65 * data["expected_volatility"]
    data["horizon_months"] = horizon_months
    return data
