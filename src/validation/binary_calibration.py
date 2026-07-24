from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BinaryCalibrationMetrics:
    observations: int
    event_rate: float
    brier_score: float
    expected_calibration_error: float
    maximum_calibration_error: float


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
