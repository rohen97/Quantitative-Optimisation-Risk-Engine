import numpy as np
import pandas as pd
import pytest

from src.validation.forecast_metrics import calculate_point_forecast_metrics


def test_point_forecast_metrics_are_correct():
    metrics = calculate_point_forecast_metrics(pd.Series([1.0, -1.0, 2.0]), pd.Series([0.0, -2.0, 2.0]))
    assert metrics.mae == pytest.approx(2 / 3)
    assert metrics.rmse == pytest.approx(np.sqrt(2 / 3))
    assert metrics.directional_accuracy == pytest.approx(2 / 3)
    assert metrics.spearman_rank_ic is not None


def test_empty_forecasts_fail_clearly():
    with pytest.raises(ValueError):
        calculate_point_forecast_metrics(pd.Series(dtype=float), pd.Series(dtype=float))
