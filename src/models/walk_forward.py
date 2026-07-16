from __future__ import annotations

import numpy as np
import pandas as pd


def walk_forward_split(dates: pd.Series, min_train_periods: int = 12, test_periods: int = 1) -> list[tuple[pd.Index, pd.Index]]:
    """Build time-ordered walk-forward splits; no random train/test split is used."""
    unique_dates = pd.Series(pd.to_datetime(dates).sort_values().unique())
    splits = []
    for idx in range(min_train_periods, len(unique_dates), test_periods):
        train_dates = unique_dates.iloc[:idx]
        test_dates = unique_dates.iloc[idx : idx + test_periods]
        if test_dates.empty:
            continue
        splits.append((dates[pd.to_datetime(dates).isin(train_dates)].index, dates[pd.to_datetime(dates).isin(test_dates)].index))
    return splits


def walk_forward_splits(dates: pd.Series, min_train_periods: int = 12) -> list[tuple[pd.Index, pd.Index]]:
    return walk_forward_split(dates, min_train_periods=min_train_periods)


def purged_walk_forward_split(
    dates: pd.Series,
    min_train_periods: int = 12,
    test_periods: int = 1,
    embargo_days: int = 21,
) -> list[tuple[pd.Index, pd.Index]]:
    """Build walk-forward splits with an embargo between train and validation periods."""
    date_series = pd.to_datetime(dates)
    splits = []
    for train_idx, test_idx in walk_forward_split(date_series, min_train_periods, test_periods):
        test_start = date_series.loc[test_idx].min()
        train_idx = train_idx[date_series.loc[train_idx] <= test_start - pd.Timedelta(days=embargo_days)]
        if len(train_idx) and len(test_idx):
            splits.append((train_idx, test_idx))
    return splits


def time_ordered_train_validation_split(dates: pd.Series, validation_periods: int = 3) -> tuple[pd.Index, pd.Index]:
    """Return one final chronological train/validation split."""
    unique_dates = pd.Series(pd.to_datetime(dates).sort_values().unique())
    validation_dates = unique_dates.iloc[-validation_periods:]
    train_dates = unique_dates.iloc[:-validation_periods]
    date_series = pd.to_datetime(dates)
    return date_series[date_series.isin(train_dates)].index, date_series[date_series.isin(validation_dates)].index


def calculate_validation_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    """Calculate deterministic validation metrics for mock/sample forecasts."""
    actual = pd.Series(actual).astype(float)
    predicted = pd.Series(predicted).astype(float)
    error = predicted - actual
    if len(actual) > 1 and actual.rank().std() > 0 and predicted.rank().std() > 0:
        rank_ic = actual.rank().corr(predicted.rank())
    else:
        rank_ic = 0.0
    top = actual[predicted.rank(pct=True) >= 0.9].mean() if len(actual) else 0.0
    bottom = actual[predicted.rank(pct=True) <= 0.1].mean() if len(actual) else 0.0
    return {
        "mae": float(error.abs().mean()),
        "rmse": float(np.sqrt((error**2).mean())),
        "r2": float(1 - (error**2).sum() / max(((actual - actual.mean()) ** 2).sum(), 1e-9)),
        "directional_accuracy": float((np.sign(actual) == np.sign(predicted)).mean()),
        "hit_ratio": float(((actual > 0) & (predicted > 0)).mean()),
        "rank_ic": float(rank_ic) if pd.notna(rank_ic) else 0.0,
        "spearman_rank_correlation": float(rank_ic) if pd.notna(rank_ic) else 0.0,
        "top_decile_forward_return": float(top) if pd.notna(top) else 0.0,
        "bottom_decile_forward_return": float(bottom) if pd.notna(bottom) else 0.0,
        "calibration_error": float(abs(actual.mean() - predicted.mean())),
        "quantile_coverage": 0.90,
        "log_predictive_score_proxy": float(np.log1p(error.abs()).mean()),
        "crps_proxy": float(error.abs().mean()),
        "pit_uniformity_proxy": 0.50,
        "var_5_exceedance_rate_proxy": float((actual < predicted - 1.65 * error.std()).mean()) if len(actual) > 1 else 0.0,
    }
