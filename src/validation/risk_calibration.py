from __future__ import annotations

import json
import math
from itertools import product
from typing import Iterable

import numpy as np
import pandas as pd


RISK_FORECAST_COLUMNS = (
    "var_95",
    "var_99",
    "expected_shortfall_95",
    "expected_shortfall_99",
)


def _quantile_loss(
    realised: np.ndarray,
    forecast: np.ndarray,
    alpha: float,
) -> float:
    errors = realised - forecast
    return float(
        np.mean(np.maximum(alpha * errors, (alpha - 1.0) * errors))
    )


def _scale_score(
    training: pd.DataFrame,
    factor: float,
) -> float:
    realised = training["realised_return"].to_numpy(dtype=float)
    scale = max(float(np.std(realised, ddof=1)), 1.0e-4)
    score = 0.0
    for confidence, weight in ((0.95, 0.70), (0.99, 0.30)):
        alpha = 1.0 - confidence
        forecast = (
            training[f"var_{int(confidence * 100)}"].to_numpy(dtype=float)
            * factor
        )
        breaches = realised < forecast
        coverage_penalty = abs(float(breaches.mean()) - alpha) * scale
        clustered = (
            float(np.mean(breaches[1:] & breaches[:-1]))
            if len(breaches) > 1
            else 0.0
        )
        score += weight * (
            _quantile_loss(realised, forecast, alpha)
            + 0.75 * coverage_penalty
            + 2.0 * clustered * scale
        )
    return float(score)


def _base_forecasts(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Remove an earlier exception overlay while retaining model calibration."""

    base = forecasts.copy()
    if {
        "risk_effective_scale_factor",
        "risk_calibration_scale_factor",
    }.issubset(base.columns):
        effective = pd.to_numeric(
            base["risk_effective_scale_factor"], errors="coerce"
        )
        calibrated = pd.to_numeric(
            base["risk_calibration_scale_factor"], errors="coerce"
        )
        divisor = (effective / calibrated.replace(0.0, np.nan)).where(
            lambda values: values.ge(1.0) & np.isfinite(values),
            1.0,
        )
    else:
        divisor = pd.Series(1.0, index=base.index)
    for column in (*RISK_FORECAST_COLUMNS, "forecast_volatility"):
        if column in base:
            base[column] = pd.to_numeric(base[column], errors="coerce").div(
                divisor
            )
    return base


def _blocked_selection_slices(
    row_count: int,
    *,
    folds: int,
    warmup_rows: int,
) -> tuple[slice, ...]:
    if folds < 1:
        raise ValueError("Risk calibration selection folds must be positive.")
    if warmup_rows < 0:
        raise ValueError("Risk calibration selection warmup cannot be negative.")
    if folds == 1:
        return (slice(0, row_count),)
    minimum_fold_rows = 20
    maximum_warmup = max(row_count - folds * minimum_fold_rows, 0)
    start = min(warmup_rows, maximum_warmup)
    boundaries = np.linspace(start, row_count, folds + 1, dtype=int)
    slices = tuple(
        slice(int(left), int(right))
        for left, right in zip(boundaries[:-1], boundaries[1:], strict=True)
        if right - left >= minimum_fold_rows
    )
    return slices or (slice(0, row_count),)


def _apply_exception_response(
    forecasts: pd.DataFrame,
    *,
    scale_factor: float,
    exception_multiplier: float,
    exception_days: int,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    """Apply a causal VaR buffer after each observed 95% exception."""

    realised = pd.to_numeric(
        forecasts["realised_return"], errors="coerce"
    ).to_numpy(dtype=float)
    base_var = pd.to_numeric(
        forecasts["var_95"], errors="coerce"
    ).to_numpy(dtype=float)
    factors = np.ones(len(forecasts), dtype=float)
    active = np.zeros(len(forecasts), dtype=bool)
    triggered = np.zeros(len(forecasts), dtype=bool)
    days_remaining = 0
    for position in range(len(forecasts)):
        active[position] = days_remaining > 0
        factors[position] = scale_factor * (
            exception_multiplier if active[position] else 1.0
        )
        days_remaining = max(days_remaining - 1, 0)
        triggered[position] = bool(
            np.isfinite(realised[position])
            and np.isfinite(base_var[position])
            and realised[position] < base_var[position] * factors[position]
        )
        if triggered[position]:
            days_remaining = max(days_remaining, exception_days)

    adjusted = forecasts.copy()
    for column in (*RISK_FORECAST_COLUMNS, "forecast_volatility"):
        if column in adjusted:
            adjusted[column] = pd.to_numeric(
                adjusted[column], errors="coerce"
            ).mul(factors)
    return adjusted, factors, active, triggered


def apply_locked_risk_calibration(
    forecasts: pd.DataFrame,
    *,
    scale_factors: Iterable[float],
    holdout_fraction: float,
    minimum_training_rows: int,
    minimum_holdout_rows: int,
    exception_multipliers: Iterable[float] = (1.0,),
    exception_days: Iterable[int] = (0,),
    selection_folds: int = 1,
    selection_warmup_rows: int = 0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Select on blocked development folds, then lock feedback for holdout."""

    required = {"date", "realised_return", *RISK_FORECAST_COLUMNS}
    missing = required.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Risk forecast frame is missing columns: {sorted(missing)}")
    if not 0 < holdout_fraction < 1:
        raise ValueError("Risk holdout fraction must be between zero and one.")

    candidates = tuple(sorted({float(value) for value in scale_factors}))
    if not candidates or any(not 1.0 <= value <= 1.5 for value in candidates):
        raise ValueError("Locked risk scale factors must be between 1.0 and 1.5.")
    multipliers = tuple(
        sorted({float(value) for value in exception_multipliers})
    )
    durations = tuple(sorted({int(value) for value in exception_days}))
    if not multipliers or any(not 1.0 <= value <= 2.0 for value in multipliers):
        raise ValueError(
            "Locked exception multipliers must be between 1.0 and 2.0."
        )
    if not durations or any(value < 0 or value > 60 for value in durations):
        raise ValueError("Locked exception days must be between 0 and 60.")
    response_candidates = {(1.0, 0)}
    response_candidates.update(
        (multiplier, duration)
        for multiplier, duration in product(multipliers, durations)
        if multiplier > 1.0 and duration > 0
    )

    ordered = forecasts.copy()
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce")
    ordered = ordered.sort_values("date", kind="stable").reset_index(drop=True)
    holdout_rows = max(int(math.floor(len(ordered) * holdout_fraction)), 1)
    training_rows = len(ordered) - holdout_rows
    if (
        training_rows < int(minimum_training_rows)
        or holdout_rows < int(minimum_holdout_rows)
    ):
        raise ValueError(
            "Insufficient observations for locked risk calibration: "
            f"training={training_rows}, holdout={holdout_rows}."
        )

    base = _base_forecasts(ordered)
    training = base.iloc[:training_rows]
    selection_slices = _blocked_selection_slices(
        training_rows,
        folds=int(selection_folds),
        warmup_rows=int(selection_warmup_rows),
    )
    scores: dict[tuple[float, float, int], float] = {}
    fold_scores: dict[tuple[float, float, int], list[float]] = {}
    for factor, response in product(candidates, sorted(response_candidates)):
        multiplier, duration = response
        adjusted, _, _, _ = _apply_exception_response(
            training,
            scale_factor=factor,
            exception_multiplier=multiplier,
            exception_days=duration,
        )
        candidate = (factor, multiplier, duration)
        fold_scores[candidate] = [
            _scale_score(adjusted.iloc[selection_slice], 1.0)
            for selection_slice in selection_slices
        ]
        scores[candidate] = float(np.mean(fold_scores[candidate]))
    selected, selected_multiplier, selected_days = min(
        scores,
        key=lambda candidate: (
            scores[candidate],
            abs(candidate[0] - 1.0),
            abs(candidate[1] - 1.0),
            candidate[2],
        ),
    )
    simulated, effective_factors, exception_active, exception_triggered = (
        _apply_exception_response(
            base,
            scale_factor=selected,
            exception_multiplier=selected_multiplier,
            exception_days=selected_days,
        )
    )
    holdout = ordered.index >= training_rows

    for column in RISK_FORECAST_COLUMNS:
        ordered[f"prelock_{column}"] = ordered[column]
        ordered.loc[holdout, column] = simulated.loc[holdout, column]
    if "forecast_volatility" in ordered:
        ordered["prelock_forecast_volatility"] = ordered["forecast_volatility"]
        ordered.loc[holdout, "forecast_volatility"] = simulated.loc[
            holdout, "forecast_volatility"
        ]
    if "risk_effective_scale_factor" in ordered:
        base_scale = pd.to_numeric(
            ordered.get(
                "risk_calibration_scale_factor",
                ordered["risk_effective_scale_factor"],
            ),
            errors="coerce",
        ).fillna(1.0)
        ordered.loc[holdout, "risk_effective_scale_factor"] = (
            base_scale.loc[holdout]
            * pd.Series(effective_factors, index=ordered.index).loc[holdout]
        )

    ordered["risk_locked_scale_factor"] = selected
    ordered["risk_locked_exception_multiplier"] = selected_multiplier
    ordered["risk_locked_exception_days"] = selected_days
    ordered["risk_locked_effective_factor"] = np.where(
        holdout, effective_factors, 1.0
    )
    ordered["risk_locked_exception_active"] = holdout & exception_active
    ordered["risk_locked_exception_triggered"] = holdout & exception_triggered
    ordered["risk_locked_calibration_applied"] = holdout
    ordered["risk_calibration_segment"] = np.where(
        holdout,
        "untouched_holdout",
        "development_training",
    )
    score_payload = json.dumps(
        {
            (
                f"scale={factor:.3f}|response={multiplier:.3f}|days={duration}"
            ): round(score, 12)
            for (factor, multiplier, duration), score in scores.items()
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    ordered["risk_locked_calibration_scores"] = score_payload
    ordered["risk_locked_selection_folds"] = len(selection_slices)
    ordered["risk_locked_selection_warmup_rows"] = int(
        selection_slices[0].start or 0
    )
    metadata: dict[str, object] = {
        "selected_scale_factor": selected,
        "selected_exception_multiplier": selected_multiplier,
        "selected_exception_days": selected_days,
        "candidate_scores": json.loads(score_payload),
        "training_rows": training_rows,
        "holdout_rows": holdout_rows,
        "training_end_date": ordered.iloc[training_rows - 1]["date"],
        "holdout_start_date": ordered.iloc[training_rows]["date"],
        "selection_basis": "blocked_development_training_only",
        "selection_folds": len(selection_slices),
        "selection_warmup_rows": int(selection_slices[0].start or 0),
        "selected_fold_scores": fold_scores[
            (selected, selected_multiplier, selected_days)
        ],
    }
    return ordered, metadata
