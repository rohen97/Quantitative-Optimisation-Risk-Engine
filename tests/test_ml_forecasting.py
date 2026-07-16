import pandas as pd

from src.models.forecast_features import build_forecast_feature_matrix
from src.models.forecasting import build_ml_forecast_features


def test_forecast_feature_matrix_excludes_future_targets():
    features = pd.DataFrame(
        {
            "security_id": ["S1"],
            "ticker": ["AAA"],
            "company_name": ["AAA Plc"],
            "sector": ["Healthcare"],
            "region": ["UK"],
            "forward_total_return_12m": [0.50],
            "dividend_yield": [0.04],
            "valuation_score": [60],
        }
    )
    _, matrix, _ = build_forecast_feature_matrix(features)
    assert "forward_total_return_12m" not in matrix.columns


def test_ml_forecasts_have_numeric_expected_return_and_scores():
    features = pd.DataFrame(
        {
            "security_id": ["S1", "S2"],
            "ticker": ["AAA", "BBB"],
            "company_name": ["AAA Plc", "BBB Plc"],
            "sector": ["Healthcare", "Industrials"],
            "region": ["UK", "DACH"],
            "country": ["United Kingdom", "Germany"],
            "currency": ["GBP", "EUR"],
            "dividend_yield": [0.04, 0.03],
            "momentum_6m": [0.1, -0.1],
            "valuation_score": [60, 40],
            "cash_flow_quality_score": [70, 45],
            "balance_sheet_strength_score": [75, 40],
            "volatility_1y": [0.18, 0.32],
        }
    )
    outputs = build_ml_forecast_features(features)
    wide = outputs["ml_features"]
    assert pd.api.types.is_numeric_dtype(wide["expected_total_return_12m"])
    assert wide["ml_expected_risk_adjusted_score"].between(0, 100).all()
