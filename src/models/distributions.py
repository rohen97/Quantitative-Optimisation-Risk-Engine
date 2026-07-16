from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


EPSILON = 1e-8


def softplus(value) -> np.ndarray:
    values = np.asarray(value, dtype=float)
    return np.log1p(np.exp(-np.abs(values))) + np.maximum(values, 0)


def constrain_sigma(raw_sigma, min_sigma: float = 0.0001) -> np.ndarray:
    return softplus(raw_sigma) + min_sigma


def constrain_nu(raw_nu, min_nu: float = 2.01) -> np.ndarray:
    return softplus(raw_nu) + min_nu


def constrain_xi(raw_xi, min_xi: float = 0.1, max_xi: float = 10.0) -> np.ndarray:
    return np.clip(softplus(raw_xi) + EPSILON, min_xi, max_xi)


def normal_pdf(x, mu, sigma):
    return stats.norm.pdf(x, loc=mu, scale=np.maximum(sigma, EPSILON))


def normal_cdf(x, mu, sigma):
    return stats.norm.cdf(x, loc=mu, scale=np.maximum(sigma, EPSILON))


def normal_ppf(q, mu, sigma):
    return stats.norm.ppf(q, loc=mu, scale=np.maximum(sigma, EPSILON))


def student_t_pdf(x, mu, sigma, nu):
    return stats.t.pdf((np.asarray(x) - mu) / np.maximum(sigma, EPSILON), df=np.maximum(nu, 2.01)) / np.maximum(sigma, EPSILON)


def student_t_cdf(x, mu, sigma, nu):
    return stats.t.cdf((np.asarray(x) - mu) / np.maximum(sigma, EPSILON), df=np.maximum(nu, 2.01))


def student_t_ppf(q, mu, sigma, nu):
    return mu + np.maximum(sigma, EPSILON) * stats.t.ppf(q, df=np.maximum(nu, 2.01))


def skewed_student_t_pdf(x, mu, sigma, nu, xi):
    """Approximate skewed Student-t PDF using two-piece scale adjustment."""
    x_arr = np.asarray(x, dtype=float)
    xi_arr = np.maximum(xi, EPSILON)
    left_scale = np.maximum(sigma, EPSILON) / xi_arr
    right_scale = np.maximum(sigma, EPSILON) * xi_arr
    scale = np.where(x_arr < mu, left_scale, right_scale)
    return student_t_pdf(x_arr, mu, scale, nu)


def skewed_student_t_cdf_placeholder(x, mu, sigma, nu, xi):
    """Approximate skewed Student-t CDF; upgradeable to a full Fernandez-Steel implementation later."""
    x_arr = np.asarray(x, dtype=float)
    xi_arr = np.maximum(xi, EPSILON)
    left_scale = np.maximum(sigma, EPSILON) / xi_arr
    right_scale = np.maximum(sigma, EPSILON) * xi_arr
    scale = np.where(x_arr < mu, left_scale, right_scale)
    return student_t_cdf(x_arr, mu, scale, nu)


def skewed_student_t_ppf_placeholder(q, mu, sigma, nu, xi):
    """Approximate skewed Student-t quantile by widening the tail implied by xi."""
    q_arr = np.asarray(q, dtype=float)
    xi_arr = np.maximum(xi, EPSILON)
    base = student_t_ppf(q_arr, mu, sigma, nu)
    downside = q_arr < 0.5
    multiplier = np.where(downside, 1 + np.maximum(1 - xi_arr, 0) * 0.65, 1 + np.maximum(xi_arr - 1, 0) * 0.45)
    return mu + (base - mu) * multiplier


def distribution_ppf(distribution_name: str, q, mu, sigma, nu=None, xi=None):
    if distribution_name == "normal":
        return normal_ppf(q, mu, sigma)
    if distribution_name == "student_t":
        return student_t_ppf(q, mu, sigma, 8 if nu is None else nu)
    return skewed_student_t_ppf_placeholder(q, mu, sigma, 8 if nu is None else nu, 1 if xi is None else xi)


def distribution_cdf(distribution_name: str, x, mu, sigma, nu=None, xi=None):
    if distribution_name == "normal":
        return normal_cdf(x, mu, sigma)
    if distribution_name == "student_t":
        return student_t_cdf(x, mu, sigma, 8 if nu is None else nu)
    return skewed_student_t_cdf_placeholder(x, mu, sigma, 8 if nu is None else nu, 1 if xi is None else xi)
