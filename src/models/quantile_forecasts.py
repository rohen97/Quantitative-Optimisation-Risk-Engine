from __future__ import annotations

import numpy as np
import pandas as pd


def conformal_placeholder(forecasts: pd.DataFrame) -> pd.DataFrame:
    return forecasts.copy()


def build_return_distribution_forecasts(forecasts_wide: pd.DataFrame) -> pd.DataFrame:
    """Create p5/p50/p95 distribution bands and uncertainty scores for each stock."""
    data = forecasts_wide[[col for col in ["security_id", "ticker", "company_name"] if col in forecasts_wide]].copy()
    spreads = []
    for months in [3, 6, 9, 12]:
        expected = forecasts_wide[f"expected_total_return_{months}m"]
        volatility = forecasts_wide[f"expected_volatility_{months}m"].clip(lower=0.01)
        uncertainty = forecasts_wide.get("forecast_uncertainty_score", pd.Series(50, index=forecasts_wide.index)).fillna(50) / 100
        degrees = forecasts_wide.get("distribution_degrees_of_freedom", pd.Series(8, index=forecasts_wide.index)).fillna(8)
        skewness = forecasts_wide.get("distribution_skewness", pd.Series(1, index=forecasts_wide.index)).fillna(1).clip(0.35, 1.6)
        heavy_tail_multiplier = 1.35 + uncertainty + (8 / degrees.clip(lower=3)) * 0.25
        left_tail_multiplier = heavy_tail_multiplier * (1 + (1 - skewness).clip(lower=0) * 0.55)
        right_tail_multiplier = heavy_tail_multiplier * (1 + (skewness - 1).clip(lower=0) * 0.35)
        data[f"p5_return_{months}m"] = expected - volatility * left_tail_multiplier
        data[f"p50_return_{months}m"] = expected
        data[f"p95_return_{months}m"] = expected + volatility * right_tail_multiplier
        data[f"forecast_spread_{months}m"] = data[f"p95_return_{months}m"] - data[f"p5_return_{months}m"]
        spreads.append(data[f"forecast_spread_{months}m"])
    spread_12m = data["forecast_spread_12m"]
    data["downside_risk_score"] = (100 * (-data["p5_return_12m"]).clip(lower=0) / 0.35).clip(0, 100)
    data["upside_potential_score"] = (100 * data["p95_return_12m"].clip(lower=0) / 0.45).clip(0, 100)
    data["forecast_uncertainty_score"] = (100 * spread_12m / max(float(np.nanpercentile(spread_12m, 90)), 0.01)).clip(0, 100)
    data["distribution_family"] = forecasts_wide.get("distribution_family", "skewed_student_t_mock")
    data["distribution_degrees_of_freedom"] = forecasts_wide.get("distribution_degrees_of_freedom", pd.Series(8, index=forecasts_wide.index))
    data["distribution_skewness"] = forecasts_wide.get("distribution_skewness", pd.Series(1, index=forecasts_wide.index))
    return data
