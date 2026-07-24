import pandas as pd
import pytest

from src.validation.binary_calibration import calculate_binary_calibration


def test_brier_score_and_calibration_error():
    metrics = calculate_binary_calibration(pd.Series([0.0, 1.0]), pd.Series([0, 1]), bins=2)
    assert metrics.brier_score == 0.0
    assert metrics.expected_calibration_error == 0.0


def test_invalid_probability_rejected():
    with pytest.raises(ValueError):
        calculate_binary_calibration(pd.Series([1.1]), pd.Series([1]))
