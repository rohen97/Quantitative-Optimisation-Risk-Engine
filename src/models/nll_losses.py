from __future__ import annotations

import numpy as np

from src.models.distributions import EPSILON, normal_pdf, skewed_student_t_pdf, student_t_pdf


def _summarize_nll(pdf_values) -> dict[str, object]:
    observation_level = -np.log(np.clip(np.asarray(pdf_values, dtype=float), EPSILON, None))
    observation_level = np.where(np.isfinite(observation_level), observation_level, -np.log(EPSILON))
    return {
        "mean_nll": float(observation_level.mean()),
        "sum_nll": float(observation_level.sum()),
        "observation_level_nll": observation_level,
    }


def normal_nll(realized_returns, mu, sigma) -> dict[str, object]:
    """Negative log-likelihood for Normal return forecasts."""
    return _summarize_nll(normal_pdf(realized_returns, mu, sigma))


def student_t_nll(realized_returns, mu, sigma, nu) -> dict[str, object]:
    """Negative log-likelihood for Student-t return forecasts."""
    return _summarize_nll(student_t_pdf(realized_returns, mu, sigma, nu))


def skewed_student_t_nll_placeholder(realized_returns, mu, sigma, nu, xi) -> dict[str, object]:
    """Approximate NLL for the documented skewed Student-t placeholder distribution."""
    return _summarize_nll(skewed_student_t_pdf(realized_returns, mu, sigma, nu, xi))
