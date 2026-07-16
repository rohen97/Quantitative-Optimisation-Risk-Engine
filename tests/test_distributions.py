import numpy as np

from src.models.distributions import (
    constrain_nu,
    constrain_sigma,
    constrain_xi,
    normal_cdf,
    normal_pdf,
    normal_ppf,
    skewed_student_t_ppf_placeholder,
    student_t_cdf,
    student_t_pdf,
    student_t_ppf,
)


def test_normal_distribution_functions_are_finite():
    assert np.isfinite(normal_pdf(0, 0, 1))
    assert np.isfinite(normal_cdf(0, 0, 1))
    assert np.isfinite(normal_ppf(0.05, 0, 1))


def test_student_t_distribution_functions_are_finite():
    assert np.isfinite(student_t_pdf(0, 0, 1, 6))
    assert np.isfinite(student_t_cdf(0, 0, 1, 6))
    assert np.isfinite(student_t_ppf(0.05, 0, 1, 6))


def test_distribution_parameter_constraints():
    assert (constrain_sigma([-10, 0, 1]) > 0).all()
    assert (constrain_nu([-10, 0, 1]) > 2).all()
    assert (constrain_xi([-10, 0, 1]) > 0).all()


def test_skewed_student_t_placeholder_adjusts_downside_tail():
    symmetric = skewed_student_t_ppf_placeholder(0.05, 0, 1, 6, 1.0)
    downside_skew = skewed_student_t_ppf_placeholder(0.05, 0, 1, 6, 0.5)
    assert downside_skew < symmetric
