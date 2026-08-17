from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


@dataclass(frozen=True)
class BinaryCalibrationMetrics:
    observations: int
    event_rate: float
    brier_score: float
    expected_calibration_error: float
    maximum_calibration_error: float


@dataclass(frozen=True)
class FittedBinaryCalibrator:
    method: str
    model: Any = None
    constant_probability: float | None = None

    def predict(self, probabilities: pd.Series | np.ndarray) -> np.ndarray:
        values = np.clip(np.asarray(probabilities, dtype=float), 1.0e-6, 1.0 - 1.0e-6)
        if self.constant_probability is not None:
            return np.full(values.shape, self.constant_probability, dtype=float)
        if self.method == "raw":
            return values
        if self.method == "isotonic":
            return np.clip(self.model.predict(values), 0.0, 1.0)
        if self.method == "platt":
            design = np.log(values / (1.0 - values)).reshape(-1, 1)
        elif self.method == "beta":
            design = np.column_stack([np.log(values), -np.log1p(-values)])
        else:
            raise ValueError(f"Unknown binary calibration method: {self.method}")
        return np.clip(self.model.predict_proba(design)[:, 1], 0.0, 1.0)


def fit_binary_calibrator(
    method: str,
    probabilities: pd.Series | np.ndarray,
    outcomes: pd.Series | np.ndarray,
) -> FittedBinaryCalibrator:
    name = str(method).strip().lower()
    p = np.clip(np.asarray(probabilities, dtype=float), 1.0e-6, 1.0 - 1.0e-6)
    y = np.asarray(outcomes, dtype=int)
    if p.size == 0 or p.size != y.size:
        raise ValueError("Calibration training data must be non-empty and aligned.")
    unique = np.unique(y)
    if not set(unique).issubset({0, 1}):
        raise ValueError("Calibration outcomes must be binary.")
    if unique.size < 2:
        return FittedBinaryCalibrator(
            method=name,
            constant_probability=float(y.mean()),
        )
    if name == "raw":
        return FittedBinaryCalibrator(method=name)
    if name == "isotonic":
        model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        model.fit(p, y)
        return FittedBinaryCalibrator(method=name, model=model)
    if name == "platt":
        design = np.log(p / (1.0 - p)).reshape(-1, 1)
    elif name == "beta":
        design = np.column_stack([np.log(p), -np.log1p(-p)])
    else:
        raise ValueError(f"Unknown binary calibration method: {method}")
    model = LogisticRegression(C=10.0, solver="lbfgs", max_iter=500, random_state=0)
    model.fit(design, y)
    return FittedBinaryCalibrator(method=name, model=model)


def chronological_binary_calibration_comparison(
    probabilities: pd.Series,
    outcomes: pd.Series,
    dates: pd.Series,
    *,
    methods: Sequence[str] = ("raw", "isotonic", "platt", "beta"),
    bins: int = 10,
    holdout_fraction: float = 0.20,
    validation_fraction: float = 0.25,
    embargo_months: int = 12,
    minimum_training_dates: int = 6,
    minimum_validation_dates: int = 6,
    minimum_holdout_dates: int = 6,
) -> tuple[pd.DataFrame, pd.Series, dict[str, object]]:
    """Select calibration on a purged validation period and report a locked holdout."""

    frame = pd.DataFrame(
        {
            "probability": pd.to_numeric(probabilities, errors="coerce"),
            "outcome": pd.to_numeric(outcomes, errors="coerce"),
            "date": pd.to_datetime(dates, errors="coerce"),
        }
    ).dropna()
    frame = frame.loc[
        frame["probability"].between(0.0, 1.0)
        & frame["outcome"].isin([0, 1])
    ].sort_values("date").reset_index(drop=True)
    unique_dates = tuple(pd.DatetimeIndex(frame["date"].unique()).sort_values())
    minimum_total = minimum_training_dates + minimum_validation_dates + minimum_holdout_dates
    if len(unique_dates) < minimum_total:
        return pd.DataFrame(), pd.Series(dtype=float), {
            "status": "NOT_EVALUATED",
            "reason": "insufficient_unique_dates",
            "unique_dates": len(unique_dates),
        }
    holdout_count = max(
        minimum_holdout_dates,
        int(np.ceil(len(unique_dates) * float(holdout_fraction))),
    )
    holdout_count = min(holdout_count, len(unique_dates) - minimum_training_dates - minimum_validation_dates)
    holdout_dates = unique_dates[-holdout_count:]
    holdout_start = pd.Timestamp(holdout_dates[0])
    development_cutoff = holdout_start - pd.DateOffset(months=max(int(embargo_months), 0))
    development_dates = tuple(value for value in unique_dates if value < development_cutoff)
    validation_count = max(
        minimum_validation_dates,
        int(np.ceil(len(development_dates) * float(validation_fraction))),
    )
    validation_count = min(validation_count, len(development_dates) - minimum_training_dates)
    if validation_count < minimum_validation_dates:
        return pd.DataFrame(), pd.Series(dtype=float), {
            "status": "NOT_EVALUATED",
            "reason": "insufficient_purged_development_dates",
            "unique_dates": len(unique_dates),
        }
    validation_dates = development_dates[-validation_count:]
    validation_start = pd.Timestamp(validation_dates[0])
    training_cutoff = validation_start - pd.DateOffset(months=max(int(embargo_months), 0))
    training_dates = tuple(value for value in development_dates if value < training_cutoff)
    if len(training_dates) < minimum_training_dates:
        return pd.DataFrame(), pd.Series(dtype=float), {
            "status": "NOT_EVALUATED",
            "reason": "insufficient_purged_training_dates",
            "unique_dates": len(unique_dates),
        }

    partitions = {
        "training": frame["date"].isin(training_dates),
        "validation": frame["date"].isin(validation_dates),
        "locked_holdout": frame["date"].isin(holdout_dates),
    }
    trained: dict[str, FittedBinaryCalibrator] = {}
    rows: list[dict[str, object]] = []
    for method in methods:
        calibrator = fit_binary_calibrator(
            method,
            frame.loc[partitions["training"], "probability"],
            frame.loc[partitions["training"], "outcome"],
        )
        trained[calibrator.method] = calibrator
        for split_name in ("validation", "locked_holdout"):
            mask = partitions[split_name]
            calibrated = calibrator.predict(frame.loc[mask, "probability"])
            metrics = calculate_binary_calibration(
                pd.Series(calibrated),
                frame.loc[mask, "outcome"].reset_index(drop=True),
                bins=bins,
            )
            rows.append(
                {
                    "method": calibrator.method,
                    "split": split_name,
                    **metrics.__dict__,
                    "training_start": min(training_dates),
                    "training_end": max(training_dates),
                    "validation_start": min(validation_dates),
                    "validation_end": max(validation_dates),
                    "holdout_start": min(holdout_dates),
                    "holdout_end": max(holdout_dates),
                    "embargo_months": int(embargo_months),
                    "test_period_model_selection_used": False,
                }
            )
    comparison = pd.DataFrame(rows)
    validation = comparison.loc[comparison["split"].eq("validation")].copy()
    validation["selection_score"] = (
        validation["expected_calibration_error"]
        + 0.25 * validation["brier_score"]
    )
    selected_method = str(
        validation.sort_values(
            ["selection_score", "brier_score", "method"],
            kind="stable",
        ).iloc[0]["method"]
    )
    comparison["selected_by_validation"] = comparison["method"].eq(selected_method)
    holdout_mask = partitions["locked_holdout"]
    calibrated_holdout = pd.Series(
        trained[selected_method].predict(frame.loc[holdout_mask, "probability"]),
        index=frame.index[holdout_mask],
        name="calibrated_probability",
    )
    split_info = {
        "status": "EVALUATED",
        "selected_method": selected_method,
        "training_dates": len(training_dates),
        "validation_dates": len(validation_dates),
        "holdout_dates": len(holdout_dates),
        "training_end": max(training_dates),
        "validation_start": min(validation_dates),
        "holdout_start": min(holdout_dates),
        "embargo_months": int(embargo_months),
    }
    return comparison, calibrated_holdout, split_info


def calculate_binary_calibration(probabilities: pd.Series, outcomes: pd.Series, bins: int = 10) -> BinaryCalibrationMetrics:
    probability = pd.to_numeric(probabilities, errors="coerce")
    outcome = pd.to_numeric(outcomes, errors="coerce")
    invalid_probability = probability.notna() & ~probability.between(0.0, 1.0)
    if invalid_probability.any():
        raise ValueError("Probabilities must be between zero and one.")
    valid = probability.notna() & outcome.notna() & outcome.isin([0, 1])
    p = probability[valid].to_numpy(dtype=float)
    y = outcome[valid].to_numpy(dtype=float)
    if p.size == 0:
        raise ValueError("No valid probability observations.")
    assignments = np.clip(np.digitize(p, np.linspace(0.0, 1.0, bins + 1), right=True) - 1, 0, bins - 1)
    errors = []
    weights = []
    for bin_index in range(bins):
        mask = assignments == bin_index
        if mask.any():
            errors.append(abs(float(p[mask].mean() - y[mask].mean())))
            weights.append(float(mask.mean()))
    return BinaryCalibrationMetrics(len(p), float(y.mean()), float(np.mean((p - y) ** 2)), float(np.dot(errors, weights)), float(max(errors, default=0.0)))


def binary_calibration(
    probabilities: pd.Series,
    outcomes: pd.Series,
    bins: int = 10,
    minimum_observations: int = 30,
) -> tuple[dict[str, float | int | str], pd.DataFrame]:
    frame = pd.DataFrame({"probability": pd.to_numeric(probabilities, errors="coerce"), "outcome": pd.to_numeric(outcomes, errors="coerce")}).dropna()
    frame = frame[frame["probability"].between(0.0, 1.0) & frame["outcome"].isin([0, 1])]
    if len(frame) < minimum_observations:
        return ({"observation_count": len(frame), "status": "NOT_EVALUATED", "brier_score": float("nan"), "expected_calibration_error": float("nan")}, pd.DataFrame())
    frame["bin"] = pd.cut(frame["probability"], bins=np.linspace(0.0, 1.0, bins + 1), include_lowest=True)
    table = frame.groupby("bin", observed=False).agg(mean_probability=("probability", "mean"), event_rate=("outcome", "mean"), observation_count=("outcome", "size")).reset_index()
    table["absolute_calibration_error"] = (table["mean_probability"] - table["event_rate"]).abs()
    ece = float((table["absolute_calibration_error"] * table["observation_count"]).sum() / len(frame))
    return ({"observation_count": len(frame), "status": "EVALUATED", "brier_score": float(np.mean(np.square(frame["probability"] - frame["outcome"]))), "expected_calibration_error": ece}, table)
