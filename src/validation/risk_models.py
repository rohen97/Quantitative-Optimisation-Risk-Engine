from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm, t as student_t


CONFIDENCE_LEVELS = (0.95, 0.99)
SUPPORTED_MODELS = (
    "ewma_normal",
    "ewma_student_t",
    "filtered_historical_simulation",
    "dcc_igarch_student_t",
)


@dataclass(frozen=True)
class RiskModelSettings:
    ewma_decay: float = 0.94
    lookback_rows: int = 252
    candidate_models: tuple[str, ...] = SUPPORTED_MODELS
    calibration_rows: int = 63
    minimum_training_rows: int = 120
    student_t_degrees_freedom: float = 7.0
    dcc_alpha: float = 0.03
    dcc_beta: float = 0.95
    correlation_shrinkage: float = 0.10
    calibration_scale_factors: tuple[float, ...] = (1.0,)

    def validate(self) -> None:
        unknown = set(self.candidate_models).difference(SUPPORTED_MODELS)
        if unknown:
            raise ValueError(f"Unsupported risk models: {sorted(unknown)}")
        if not self.candidate_models:
            raise ValueError("At least one risk model candidate is required.")
        if not 0 < self.ewma_decay < 1:
            raise ValueError("Risk EWMA decay must be between zero and one.")
        if self.lookback_rows < self.minimum_training_rows:
            raise ValueError("Risk lookback must cover the minimum training rows.")
        if self.student_t_degrees_freedom <= 2:
            raise ValueError("Student-t degrees of freedom must exceed two.")
        if self.dcc_alpha < 0 or self.dcc_beta < 0 or self.dcc_alpha + self.dcc_beta >= 1:
            raise ValueError("DCC alpha and beta must be non-negative and sum below one.")
        if not 0 <= self.correlation_shrinkage <= 1:
            raise ValueError("Correlation shrinkage must be between zero and one.")
        if not self.calibration_scale_factors or any(
            not 1.0 <= factor <= 1.5 for factor in self.calibration_scale_factors
        ):
            raise ValueError(
                "Risk calibration scale factors must be between 1.0 and 1.5."
            )


@dataclass(frozen=True)
class RiskForecast:
    model: str
    volatility: float
    values: dict[str, float]


def _clean_sample(returns: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(returns, dtype=float)
    return values[np.isfinite(values)]


def _ewma_volatility(sample: np.ndarray, decay: float) -> float:
    if len(sample) == 0:
        return float("nan")
    powers = np.arange(len(sample) - 1, -1, -1, dtype=float)
    weights = np.power(decay, powers)
    variance = float(np.average(np.square(sample), weights=weights))
    return math.sqrt(max(variance, 1.0e-12))


def _parametric_values(
    volatility: float,
    distribution: str,
    degrees_freedom: float,
) -> dict[str, float]:
    output: dict[str, float] = {}
    for confidence in CONFIDENCE_LEVELS:
        alpha = 1.0 - confidence
        suffix = int(confidence * 100)
        if distribution == "normal":
            quantile = float(norm.ppf(alpha))
            expected_shortfall = -float(norm.pdf(quantile)) / alpha
        else:
            raw_quantile = float(student_t.ppf(alpha, degrees_freedom))
            scale = math.sqrt((degrees_freedom - 2.0) / degrees_freedom)
            quantile = raw_quantile * scale
            density = float(student_t.pdf(raw_quantile, degrees_freedom))
            expected_shortfall = -(
                (degrees_freedom + raw_quantile**2)
                / (degrees_freedom - 1.0)
                * density
                / alpha
                * scale
            )
        output[f"var_{suffix}"] = quantile * volatility
        output[f"expected_shortfall_{suffix}"] = expected_shortfall * volatility
    return output


def _filtered_historical_values(
    sample: np.ndarray,
    decay: float,
) -> tuple[float, dict[str, float]]:
    initial = max(float(np.mean(np.square(sample[: min(20, len(sample))]))), 1.0e-12)
    variance = initial
    residuals: list[float] = []
    for value in sample:
        sigma = math.sqrt(max(variance, 1.0e-12))
        residuals.append(float(value) / sigma)
        variance = decay * variance + (1.0 - decay) * float(value) ** 2
    volatility = math.sqrt(max(variance, 1.0e-12))
    filtered = np.asarray(residuals[min(20, len(residuals) // 5) :], dtype=float)
    values: dict[str, float] = {}
    for confidence in CONFIDENCE_LEVELS:
        alpha = 1.0 - confidence
        suffix = int(confidence * 100)
        quantile = float(np.quantile(filtered, alpha, method="linear"))
        tail = filtered[filtered <= quantile]
        expected_shortfall = float(tail.mean()) if len(tail) else quantile
        values[f"var_{suffix}"] = quantile * volatility
        values[f"expected_shortfall_{suffix}"] = expected_shortfall * volatility
    return volatility, values


def _nearest_correlation(correlation: np.ndarray) -> np.ndarray:
    symmetric = (correlation + correlation.T) / 2.0
    values, vectors = np.linalg.eigh(symmetric)
    positive = vectors @ np.diag(np.clip(values, 1.0e-6, None)) @ vectors.T
    scale = np.sqrt(np.clip(np.diag(positive), 1.0e-12, None))
    return positive / np.outer(scale, scale)


def _dcc_portfolio_volatility(
    asset_returns: pd.DataFrame,
    asset_weights: pd.Series,
    settings: RiskModelSettings,
) -> float:
    matrix = asset_returns.reindex(columns=asset_weights.index).to_numpy(dtype=float)
    matrix = np.where(np.isfinite(matrix), matrix, 0.0)
    if matrix.shape[0] < settings.minimum_training_rows or matrix.shape[1] < 2:
        portfolio = matrix @ asset_weights.to_numpy(dtype=float)
        return _ewma_volatility(portfolio, settings.ewma_decay)

    seed_rows = min(20, matrix.shape[0])
    variances = np.nanmean(np.square(matrix[:seed_rows]), axis=0)
    variances = np.clip(variances, 1.0e-10, None)
    standardised: list[np.ndarray] = []
    for observation in matrix:
        standardised.append(observation / np.sqrt(variances))
        variances = (
            settings.ewma_decay * variances
            + (1.0 - settings.ewma_decay) * np.square(observation)
        )
        variances = np.clip(variances, 1.0e-10, None)

    z = np.vstack(standardised)
    long_run = np.corrcoef(z, rowvar=False)
    if np.ndim(long_run) != 2 or not np.isfinite(long_run).all():
        long_run = np.eye(matrix.shape[1])
    long_run = (
        (1.0 - settings.correlation_shrinkage) * long_run
        + settings.correlation_shrinkage * np.eye(matrix.shape[1])
    )
    long_run = _nearest_correlation(long_run)
    q_matrix = long_run.copy()
    intercept = 1.0 - settings.dcc_alpha - settings.dcc_beta
    for observation in z:
        q_matrix = (
            intercept * long_run
            + settings.dcc_alpha * np.outer(observation, observation)
            + settings.dcc_beta * q_matrix
        )
    correlation = _nearest_correlation(q_matrix)
    covariance = np.outer(np.sqrt(variances), np.sqrt(variances)) * correlation
    weights = asset_weights.to_numpy(dtype=float)
    variance = float(weights @ covariance @ weights)
    return math.sqrt(max(variance, 1.0e-12))


def forecast_risk(
    returns: pd.Series,
    model: str,
    settings: RiskModelSettings,
    *,
    asset_returns: pd.DataFrame | None = None,
    asset_weights: pd.Series | None = None,
) -> RiskForecast:
    settings.validate()
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported risk model: {model}")
    sample = _clean_sample(returns.tail(settings.lookback_rows))
    if len(sample) < settings.minimum_training_rows:
        raise ValueError("Insufficient returns for a risk forecast.")

    if model == "filtered_historical_simulation":
        volatility, values = _filtered_historical_values(sample, settings.ewma_decay)
    elif model == "dcc_igarch_student_t":
        if asset_returns is None or asset_weights is None:
            raise ValueError("DCC risk forecasts require asset returns and weights.")
        volatility = _dcc_portfolio_volatility(
            asset_returns.tail(settings.lookback_rows),
            asset_weights,
            settings,
        )
        values = _parametric_values(
            volatility,
            "student_t",
            settings.student_t_degrees_freedom,
        )
    else:
        volatility = _ewma_volatility(sample, settings.ewma_decay)
        distribution = "normal" if model == "ewma_normal" else "student_t"
        values = _parametric_values(
            volatility,
            distribution,
            settings.student_t_degrees_freedom,
        )
    return RiskForecast(model=model, volatility=volatility, values=values)


def _quantile_loss(realised: np.ndarray, forecast: np.ndarray, alpha: float) -> float:
    errors = realised - forecast
    return float(np.mean(np.maximum(alpha * errors, (alpha - 1.0) * errors)))


def _candidate_score(
    realised: np.ndarray,
    forecasts: dict[float, np.ndarray],
) -> float:
    scale = max(float(np.std(realised, ddof=1)), 1.0e-4)
    score = 0.0
    for confidence, weight in ((0.95, 0.70), (0.99, 0.30)):
        alpha = 1.0 - confidence
        values = forecasts[confidence]
        breaches = realised < values
        loss = _quantile_loss(realised, values, alpha)
        coverage_penalty = abs(float(breaches.mean()) - alpha) * scale
        clustered = float(np.mean(breaches[1:] & breaches[:-1])) if len(breaches) > 1 else 0.0
        score += weight * (loss + 0.75 * coverage_penalty + 2.0 * clustered * scale)
    return float(score)


def select_risk_model(
    returns: pd.Series,
    settings: RiskModelSettings,
    *,
    asset_returns: pd.DataFrame | None = None,
    asset_weights: pd.Series | None = None,
) -> tuple[str, float, dict[str, float], int]:
    """Select on a trailing calibration slice; callers keep future data untouched."""

    settings.validate()
    clean = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    available_calibration = len(clean) - settings.minimum_training_rows
    calibration_rows = min(settings.calibration_rows, max(available_calibration, 0))
    if (
        len(settings.candidate_models) == 1
        and len(settings.calibration_scale_factors) == 1
    ) or calibration_rows < 20:
        model = settings.candidate_models[0]
        factor = settings.calibration_scale_factors[0]
        return model, factor, {f"{model}@{factor:.3f}": float("nan")}, calibration_rows

    start = len(clean) - calibration_rows
    realised = clean.iloc[start:].to_numpy(dtype=float)
    scores: dict[str, float] = {}
    choices: list[tuple[float, int, int, str, float]] = []
    for model in settings.candidate_models:
        forecasts = {confidence: [] for confidence in CONFIDENCE_LEVELS}
        valid_realised: list[float] = []
        for position in range(start, len(clean)):
            training = clean.iloc[max(0, position - settings.lookback_rows) : position]
            date = clean.index[position]
            training_assets = None
            if asset_returns is not None:
                training_assets = asset_returns.loc[asset_returns.index < date].tail(
                    settings.lookback_rows
                )
            try:
                forecast = forecast_risk(
                    training,
                    model,
                    settings,
                    asset_returns=training_assets,
                    asset_weights=asset_weights,
                )
            except (ValueError, np.linalg.LinAlgError, FloatingPointError):
                continue
            valid_realised.append(float(clean.iloc[position]))
            for confidence in CONFIDENCE_LEVELS:
                forecasts[confidence].append(
                    forecast.values[f"var_{int(confidence * 100)}"]
                )
        if len(valid_realised) != calibration_rows:
            for factor in settings.calibration_scale_factors:
                scores[f"{model}@{factor:.3f}"] = float("inf")
            continue
        realised_array = np.asarray(valid_realised, dtype=float)
        forecast_arrays = {
            confidence: np.asarray(values, dtype=float)
            for confidence, values in forecasts.items()
        }
        for factor_index, factor in enumerate(settings.calibration_scale_factors):
            key = f"{model}@{factor:.3f}"
            score = _candidate_score(
                realised_array,
                {
                    confidence: values * factor
                    for confidence, values in forecast_arrays.items()
                },
            )
            scores[key] = score
            choices.append(
                (
                    score,
                    settings.candidate_models.index(model),
                    factor_index,
                    model,
                    factor,
                )
            )
    finite = [choice for choice in choices if math.isfinite(choice[0])]
    if finite:
        _, _, _, selected, selected_factor = min(finite)
    else:
        selected = settings.candidate_models[0]
        selected_factor = settings.calibration_scale_factors[0]
    return selected, selected_factor, scores, calibration_rows


def serialise_scores(scores: dict[str, float]) -> str:
    clean = {
        model: (round(value, 10) if math.isfinite(value) else None)
        for model, value in scores.items()
    }
    return json.dumps(clean, sort_keys=True, separators=(",", ":"))
