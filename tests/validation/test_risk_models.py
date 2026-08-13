import numpy as np
import pandas as pd

from src.validation.risk_models import (
    RiskModelSettings,
    forecast_risk,
    select_risk_model,
)


def _settings(*models: str) -> RiskModelSettings:
    return RiskModelSettings(
        lookback_rows=180,
        minimum_training_rows=120,
        calibration_rows=40,
        candidate_models=models,
    )


def test_all_risk_models_produce_ordered_loss_forecasts():
    rng = np.random.default_rng(42)
    index = pd.bdate_range('2024-01-01', periods=180)
    matrix = pd.DataFrame(
        rng.standard_t(7, size=(180, 3)) * 0.009,
        index=index,
        columns=['A', 'B', 'C'],
    )
    weights = pd.Series({'A': 0.4, 'B': 0.35, 'C': 0.25})
    returns = matrix.mul(weights, axis=1).sum(axis=1)
    settings = _settings(
        'ewma_normal',
        'ewma_student_t',
        'filtered_historical_simulation',
        'dcc_igarch_student_t',
    )
    for model in settings.candidate_models:
        forecast = forecast_risk(
            returns,
            model,
            settings,
            asset_returns=matrix,
            asset_weights=weights,
        )
        assert forecast.values['expected_shortfall_99'] <= forecast.values['var_99']
        assert forecast.values['var_99'] < forecast.values['var_95'] < 0
        assert forecast.volatility > 0


def test_dcc_forecast_responds_to_cross_asset_correlation():
    rng = np.random.default_rng(7)
    base = rng.normal(0, 0.01, 180)
    noise = rng.normal(0, 0.002, 180)
    index = pd.bdate_range('2024-01-01', periods=180)
    positive = pd.DataFrame({'A': base, 'B': base + noise}, index=index)
    negative = pd.DataFrame({'A': base, 'B': -base + noise}, index=index)
    weights = pd.Series({'A': 0.5, 'B': 0.5})
    settings = _settings('dcc_igarch_student_t')
    high = forecast_risk(
        positive.mean(axis=1),
        'dcc_igarch_student_t',
        settings,
        asset_returns=positive,
        asset_weights=weights,
    )
    low = forecast_risk(
        negative.mean(axis=1),
        'dcc_igarch_student_t',
        settings,
        asset_returns=negative,
        asset_weights=weights,
    )
    assert high.volatility > low.volatility * 2


def test_model_selection_is_deterministic_and_uses_trailing_calibration():
    rng = np.random.default_rng(11)
    index = pd.bdate_range('2023-01-01', periods=180)
    returns = pd.Series(rng.standard_t(5, size=180) * 0.008, index=index)
    settings = _settings('ewma_normal', 'ewma_student_t', 'filtered_historical_simulation')
    first = select_risk_model(returns, settings)
    second = select_risk_model(returns.copy(), settings)
    assert first == second
    assert first[0] in settings.candidate_models
    assert first[1] == 1.0
    assert first[3] == settings.calibration_rows


def test_model_selection_calibrates_scale_without_future_observations():
    rng = np.random.default_rng(17)
    index = pd.bdate_range('2023-01-01', periods=180)
    returns = pd.Series(rng.normal(0, 0.012, 180), index=index)
    settings = RiskModelSettings(
        lookback_rows=180,
        minimum_training_rows=120,
        calibration_rows=40,
        candidate_models=('ewma_normal',),
        calibration_scale_factors=(1.0, 1.08, 1.12),
    )
    model, factor, scores, observations = select_risk_model(returns, settings)
    assert model == 'ewma_normal'
    assert factor in settings.calibration_scale_factors
    assert observations == 40
    assert set(scores) == {
        'ewma_normal@1.000',
        'ewma_normal@1.080',
        'ewma_normal@1.120',
    }
