from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class QuantileCalibration:
    quantile: float
    empirical_coverage: float
    coverage_error: float
    pinball_loss: float
    observations: int


def pinball_loss(realised: np.ndarray, forecast_quantile: np.ndarray, quantile: float) -> float:
    if not 0.0 < quantile < 1.0:
        raise ValueError("Quantile must be strictly between zero and one.")
    error = np.asarray(realised, dtype=float) - np.asarray(forecast_quantile, dtype=float)
    return float(np.mean(np.maximum(quantile * error, (quantile - 1.0) * error)))


def calculate_quantile_calibration(realised: pd.Series, quantile_forecast: pd.Series, quantile: float) -> QuantileCalibration:
    frame = pd.DataFrame({"realised": pd.to_numeric(realised, errors="coerce"), "forecast": pd.to_numeric(quantile_forecast, errors="coerce")}).dropna()
    if frame.empty:
        raise ValueError("No valid quantile observations.")
    coverage = float((frame["realised"] <= frame["forecast"]).mean())
    return QuantileCalibration(quantile, coverage, coverage - quantile, pinball_loss(frame["realised"].to_numpy(), frame["forecast"].to_numpy(), quantile), len(frame))


def quantile_crossing_count(p5: pd.Series, p50: pd.Series, p95: pd.Series) -> int:
    frame = pd.DataFrame({"p5": p5, "p50": p50, "p95": p95}).apply(pd.to_numeric, errors="coerce").dropna()
    return int(((frame["p5"] > frame["p50"]) | (frame["p50"] > frame["p95"])).sum())


def distribution_coverage(
    actual: pd.Series,
    p5: pd.Series,
    p50: pd.Series,
    p95: pd.Series,
    minimum_observations: int = 50,
) -> dict[str, float | int | str]:
    frame = pd.DataFrame({"actual": actual, "p5": p5, "p50": p50, "p95": p95}).apply(pd.to_numeric, errors="coerce").dropna()
    count = len(frame)
    if count < minimum_observations:
        return {"observation_count": count, "status": "NOT_EVALUATED", "p5_coverage": float("nan"), "p50_coverage": float("nan"), "p95_coverage": float("nan"), "interval_coverage": float("nan")}
    ordered = (frame["p5"] <= frame["p50"]) & (frame["p50"] <= frame["p95"])
    return {
        "observation_count": count,
        "status": "EVALUATED" if ordered.all() else "FAIL",
        "p5_coverage": float((frame["actual"] <= frame["p5"]).mean()),
        "p50_coverage": float((frame["actual"] <= frame["p50"]).mean()),
        "p95_coverage": float((frame["actual"] <= frame["p95"]).mean()),
        "interval_coverage": float(((frame["actual"] >= frame["p5"]) & (frame["actual"] <= frame["p95"])).mean()),
    }


def probability_integral_transform(actual: pd.Series, p5: pd.Series, p50: pd.Series, p95: pd.Series) -> np.ndarray:
    frame = pd.DataFrame({"actual": actual, "p5": p5, "p50": p50, "p95": p95}).apply(pd.to_numeric, errors="coerce").dropna()
    if frame.empty:
        return np.array([], dtype=float)
    lower = np.where(frame["actual"] <= frame["p50"], frame["p5"], frame["p50"])
    upper = np.where(frame["actual"] <= frame["p50"], frame["p50"], frame["p95"])
    base = np.where(frame["actual"] <= frame["p50"], 0.05, 0.50)
    width = np.maximum(upper - lower, 1e-12)
    scale = np.where(frame["actual"] <= frame["p50"], 0.45, 0.45)
    return np.clip(base + scale * (frame["actual"].to_numpy() - lower) / width, 0.0, 1.0)
