from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.validation.risk_calibration import apply_locked_risk_calibration


def _forecasts() -> pd.DataFrame:
    rng = np.random.default_rng(17)
    realised = rng.normal(0.0, 0.01, 120)
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=120, freq="B"),
            "realised_return": realised,
            "var_95": -0.014,
            "var_99": -0.021,
            "expected_shortfall_95": -0.018,
            "expected_shortfall_99": -0.025,
            "forecast_volatility": 0.01,
            "risk_effective_scale_factor": 1.0,
        }
    )


def test_locked_risk_calibration_does_not_use_holdout_outcomes_for_selection() -> None:
    original = _forecasts()
    altered = original.copy()
    altered.loc[altered.index[-48:], "realised_return"] = -0.20
    options = {
        "scale_factors": [1.0, 1.05, 1.10],
        "holdout_fraction": 0.40,
        "minimum_training_rows": 60,
        "minimum_holdout_rows": 40,
        "selection_folds": 3,
        "selection_warmup_rows": 12,
    }

    calibrated, metadata = apply_locked_risk_calibration(original, **options)
    _, altered_metadata = apply_locked_risk_calibration(altered, **options)

    assert metadata["selected_scale_factor"] == altered_metadata[
        "selected_scale_factor"
    ]
    assert metadata["selection_basis"] == "blocked_development_training_only"
    assert metadata["selection_folds"] == 3
    assert metadata["selection_warmup_rows"] == 12
    assert len(metadata["selected_fold_scores"]) == 3
    training = calibrated["risk_calibration_segment"].eq("development_training")
    holdout = ~training
    assert calibrated.loc[training, "var_95"].equals(
        calibrated.loc[training, "prelock_var_95"]
    )
    assert np.allclose(
        calibrated.loc[holdout, "var_95"],
        calibrated.loc[holdout, "prelock_var_95"]
        * float(metadata["selected_scale_factor"]),
    )


def test_locked_exception_response_is_selected_before_holdout() -> None:
    forecasts = _forecasts()
    forecasts["realised_return"] = 0.0
    for start in range(0, 72, 12):
        forecasts.loc[start : start + 1, "realised_return"] = -0.016
    altered = forecasts.copy()
    altered.loc[altered.index[-48:], "realised_return"] = -0.20
    options = {
        "scale_factors": [1.0],
        "exception_multipliers": [1.0, 1.5],
        "exception_days": [0, 1],
        "holdout_fraction": 0.40,
        "minimum_training_rows": 60,
        "minimum_holdout_rows": 40,
    }

    calibrated, metadata = apply_locked_risk_calibration(forecasts, **options)
    altered_calibrated, altered_metadata = apply_locked_risk_calibration(
        altered, **options
    )

    assert metadata["selected_exception_multiplier"] == 1.5
    assert metadata["selected_exception_days"] == 1
    assert metadata["selected_exception_multiplier"] == altered_metadata[
        "selected_exception_multiplier"
    ]
    assert metadata["selected_exception_days"] == altered_metadata[
        "selected_exception_days"
    ]
    training = calibrated["risk_calibration_segment"].eq(
        "development_training"
    )
    assert calibrated.loc[training, "var_95"].equals(
        calibrated.loc[training, "prelock_var_95"]
    )
    first_holdout = int(training.sum())
    assert calibrated.loc[first_holdout, "var_95"] == pytest.approx(
        altered_calibrated.loc[first_holdout, "var_95"]
    )
