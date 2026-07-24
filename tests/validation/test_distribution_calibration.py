import numpy as np
import pandas as pd
import pytest

from src.validation.distribution_calibration import calculate_quantile_calibration, pinball_loss, quantile_crossing_count


def test_quantile_coverage_and_pinball_loss():
    result = calculate_quantile_calibration(pd.Series([0.0, 2.0]), pd.Series([1.0, 1.0]), 0.5)
    assert result.empirical_coverage == 0.5
    assert result.pinball_loss == pytest.approx(0.5)
    assert pinball_loss(np.array([0.0]), np.array([1.0]), 0.05) == pytest.approx(0.95)


def test_quantile_crossing_detected():
    assert quantile_crossing_count(pd.Series([0.2]), pd.Series([0.1]), pd.Series([0.3])) == 1
