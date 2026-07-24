from __future__ import annotations

import pandas as pd


def latest_by_as_of(frame: pd.DataFrame, keys: list[str], as_of_date: str | pd.Timestamp, vintage_column: str) -> pd.DataFrame:
    data = frame.copy()
    cutoff = pd.Timestamp(as_of_date)
    data[vintage_column] = pd.to_datetime(data[vintage_column])
    available = data[data[vintage_column] <= cutoff].sort_values(keys + [vintage_column])
    if available.empty:
        return available
    return available.groupby(keys, as_index=False).tail(1).reset_index(drop=True)


def point_in_time_prices(prices: pd.DataFrame, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
    data = prices.copy()
    date_column = "trade_date" if "trade_date" in data else "date"
    id_column = "security_id" if "security_id" in data else "ticker"
    data[date_column] = pd.to_datetime(data[date_column])
    return data[data[date_column] <= pd.Timestamp(as_of_date)].sort_values([id_column, date_column]).reset_index(drop=True)


def point_in_time_fundamentals(fundamentals: pd.DataFrame, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
    if "available_from" in fundamentals:
        keys = ["security_id", "fiscal_period_end", "fiscal_period_type"]
        return latest_by_as_of(fundamentals, keys, as_of_date, "available_from")
    return latest_by_as_of(fundamentals, ["ticker", "metric"], as_of_date, "filing_date")


def point_in_time_macro(macro: pd.DataFrame, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
    vintage_column = "available_from" if "available_from" in macro else "vintage_date"
    return latest_by_as_of(macro, ["series_id", "observation_date"], as_of_date, vintage_column)
