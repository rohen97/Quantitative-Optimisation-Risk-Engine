import numpy as np

from src.models.probabilistic_metrics import (
    calibration_error,
    continuous_ranked_probability_score,
    log_predictive_score,
    pit_uniformity_diagnostic,
    pit_values,
    quantile_coverage,
)


def test_probabilistic_metrics_are_finite_and_bounded():
    realized = np.array([0.01, -0.02, 0.03])
    mu = np.array([0.0, 0.0, 0.0])
    sigma = np.array([0.1, 0.1, 0.1])
    pit = pit_values(realized, "student_t", mu, sigma, nu=np.array([6, 6, 6]))
    diagnostic = pit_uniformity_diagnostic(pit)
    assert pit.between(0, 1).all()
    assert np.isfinite(log_predictive_score(realized, "student_t", mu, sigma, nu=np.array([6, 6, 6])))
    assert np.isfinite(continuous_ranked_probability_score(realized, mu, sigma))
    assert np.isfinite(calibration_error(realized, mu))
    assert 0 <= quantile_coverage(realized, np.array([-0.1, -0.1, -0.1]), np.array([0.1, 0.1, 0.1])) <= 1
    assert np.isfinite(diagnostic["pit_ks_statistic"])
