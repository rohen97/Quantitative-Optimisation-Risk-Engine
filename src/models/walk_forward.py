from __future__ import annotations

import pandas as pd


def walk_forward_splits(dates: pd.Series, min_train_periods: int = 12) -> list[tuple[pd.Index, pd.Index]]:
    unique_dates = pd.Series(pd.to_datetime(dates).sort_values().unique())
    splits = []
    for idx in range(min_train_periods, len(unique_dates)):
        train_dates = unique_dates.iloc[:idx]
        test_date = unique_dates.iloc[[idx]]
        splits.append((dates[dates.isin(train_dates)].index, dates[dates.isin(test_date)].index))
    return splits
