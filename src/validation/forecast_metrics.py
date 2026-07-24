from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PointForecastMetrics:
    observations: int
    mae: float
    rmse: float
    normalised_rmse: float
    median_absolute_error: float
    bias: float
    directional_accuracy: float
    pearson_correlation: float | None
    spearman_rank_ic: float | None


def calculate_point_forecast_metrics(predictions: pd.Series, realised: pd.Series) -> PointForecastMetrics:
    frame = pd.DataFrame({"prediction": pd.to_numeric(predictions, errors="coerce"), "realised": pd.to_numeric(realised, errors="coerce")}).dropna()
    if frame.empty:
        raise ValueError("No valid forecast observations.")
    errors = frame["prediction"].to_numpy(dtype=float) - frame["realised"].to_numpy(dtype=float)
    scale = float(frame["realised"].std(ddof=1))
    rmse = float(np.sqrt(np.mean(errors**2)))
    return PointForecastMetrics(
        observations=len(frame),
        mae=float(np.mean(np.abs(errors))),
        rmse=rmse,
        normalised_rmse=rmse / scale if scale > 0 else float("nan"),
        median_absolute_error=float(np.median(np.abs(errors))),
        bias=float(np.mean(errors)),
        directional_accuracy=float(np.mean(np.sign(frame["prediction"]) == np.sign(frame["realised"]))),
        pearson_correlation=float(frame["prediction"].corr(frame["realised"])) if len(frame) >= 3 else None,
        spearman_rank_ic=float(frame["prediction"].corr(frame["realised"], method="spearman")) if len(frame) >= 3 else None,
    )


def forecast_accuracy(
    actual: pd.Series,
    predicted: pd.Series,
    minimum_observations: int = 30,
) -> dict[str, float | int | str]:
    frame = pd.DataFrame({"actual": pd.to_numeric(actual, errors="coerce"), "predicted": pd.to_numeric(predicted, errors="coerce")}).dropna()
    count = len(frame)
    if count < minimum_observations:
        return {"observation_count": count, "status": "NOT_EVALUATED", "mae": float("nan"), "rmse": float("nan"), "normalised_rmse": float("nan"), "directional_accuracy": float("nan"), "rank_ic": float("nan")}
    errors = frame["predicted"] - frame["actual"]
    scale = max(float(frame["actual"].std(ddof=0)), 1e-12)
    return {
        "observation_count": count,
        "status": "EVALUATED",
        "mae": float(errors.abs().mean()),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "normalised_rmse": float(np.sqrt(np.mean(np.square(errors))) / scale),
        "directional_accuracy": float(np.mean(np.sign(frame["predicted"]) == np.sign(frame["actual"]))),
        "rank_ic": float(frame["predicted"].corr(frame["actual"], method="spearman")),
    }


def accuracy_by_group(data: pd.DataFrame, groups: list[str], actual_column: str, prediction_column: str, minimum_observations: int = 30) -> pd.DataFrame:
    rows = []
    available_groups = [group for group in groups if group in data]
    iterator = data.groupby(available_groups, dropna=False) if available_groups else [((), data)]
    for keys, group in iterator:
        metrics = forecast_accuracy(group[actual_column], group[prediction_column], minimum_observations)
        key_values = keys if isinstance(keys, tuple) else (keys,)
        rows.append({**dict(zip(available_groups, key_values)), **metrics})
    return pd.DataFrame(rows)
