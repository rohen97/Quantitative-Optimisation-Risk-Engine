import numpy as np
import pandas as pd
import pytest

from src.validation.binary_calibration import (
    calculate_binary_calibration,
    chronological_binary_calibration_comparison,
)


def test_brier_score_and_calibration_error():
    metrics = calculate_binary_calibration(pd.Series([0.0, 1.0]), pd.Series([0, 1]), bins=2)
    assert metrics.brier_score == 0.0
    assert metrics.expected_calibration_error == 0.0


def test_invalid_probability_rejected():
    with pytest.raises(ValueError):
        calculate_binary_calibration(pd.Series([1.1]), pd.Series([1]))


def test_calibration_methods_are_selected_before_the_locked_holdout():
    rng = np.random.default_rng(42)
    dates = pd.date_range('2018-01-31', periods=72, freq='ME')
    repeated_dates = np.repeat(dates, 30)
    latent = rng.uniform(0.02, 0.45, size=len(repeated_dates))
    outcomes = rng.binomial(1, latent)
    overconfident = np.sqrt(latent)

    comparison, calibrated, split = chronological_binary_calibration_comparison(
        pd.Series(overconfident),
        pd.Series(outcomes),
        pd.Series(repeated_dates),
        embargo_months=12,
    )

    assert split['status'] == 'EVALUATED'
    assert set(comparison['method']) == {'raw', 'isotonic', 'platt', 'beta'}
    assert comparison.groupby('split').size().to_dict() == {
        'locked_holdout': 4,
        'validation': 4,
    }
    assert comparison.loc[
        comparison['split'].eq('validation'), 'selected_by_validation'
    ].sum() == 1
    assert comparison['test_period_model_selection_used'].eq(False).all()
    assert pd.Timestamp(split['training_end']) + pd.DateOffset(months=12) < pd.Timestamp(
        split['validation_start']
    )
    assert comparison['validation_end'].max() + pd.DateOffset(months=12) < comparison[
        'holdout_start'
    ].min()
    assert len(calibrated) > 0
    assert calibrated.between(0.0, 1.0).all()
