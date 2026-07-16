import pandas as pd

from src.models.quantile_forecasts import build_return_distribution_forecasts


def test_distribution_quantiles_are_ordered():
    forecasts = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "expected_total_return_3m": [0.02],
            "expected_total_return_6m": [0.04],
            "expected_total_return_9m": [0.06],
            "expected_total_return_12m": [0.08],
            "expected_volatility_3m": [0.10],
            "expected_volatility_6m": [0.14],
            "expected_volatility_9m": [0.17],
            "expected_volatility_12m": [0.20],
            "forecast_uncertainty_score": [50],
            "distribution_degrees_of_freedom": [6],
            "distribution_skewness": [0.8],
            "distribution_family": ["student_t"],
        }
    )
    distribution = build_return_distribution_forecasts(forecasts)
    for horizon in [3, 6, 9, 12]:
        assert (distribution[f"p5_return_{horizon}m"] <= distribution[f"p50_return_{horizon}m"]).all()
        assert (distribution[f"p50_return_{horizon}m"] <= distribution[f"p95_return_{horizon}m"]).all()
