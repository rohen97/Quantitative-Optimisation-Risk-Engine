from __future__ import annotations

import pandas as pd


HORIZON_MONTHS = {"3M": 3, "6M": 6, "9M": 9, "12M": 12}


def add_realisation_dates(forecasts: pd.DataFrame) -> pd.DataFrame:
    required = {"security_id", "forecast_date", "horizon"}
    missing = required.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Missing forecast alignment columns: {sorted(missing)}")
    result = forecasts.copy()
    result["forecast_date"] = pd.to_datetime(result["forecast_date"], errors="raise")
    invalid = set(result["horizon"].dropna().unique()).difference(HORIZON_MONTHS)
    if invalid:
        raise ValueError(f"Unsupported horizons: {sorted(invalid)}")
    result["realisation_date"] = result.apply(
        lambda row: row["forecast_date"] + pd.DateOffset(months=HORIZON_MONTHS[row["horizon"]]),
        axis=1,
    )
    return result


def align_forecasts_with_outcomes(
    forecasts: pd.DataFrame,
    outcomes: pd.DataFrame,
    horizon_months: int,
) -> pd.DataFrame:
    required_forecast = {"security_id", "as_of_date"}
    required_outcome = {"security_id", "date", "return"}
    if not required_forecast.issubset(forecasts) or not required_outcome.issubset(outcomes):
        raise ValueError("Forecasts or outcomes are missing alignment columns.")
    left = forecasts.copy()
    right = outcomes.copy()
    left["as_of_date"] = pd.to_datetime(left["as_of_date"])
    left["outcome_date"] = left["as_of_date"] + pd.DateOffset(months=horizon_months)
    right["outcome_date"] = pd.to_datetime(right["date"])
    aligned = left.merge(
        right[["security_id", "outcome_date", "return"]].rename(columns={"return": "realised_return"}),
        on=["security_id", "outcome_date"],
        how="left",
        validate="many_to_one",
    )
    aligned["horizon_months"] = horizon_months
    return aligned


def validate_chronology(splits: pd.DataFrame, purge_days: int = 0, embargo_days: int = 0) -> pd.DataFrame:
    required = {"train_end", "validation_start", "validation_end", "test_start"}
    if not required.issubset(splits):
        raise ValueError(f"Missing chronology columns: {sorted(required.difference(splits.columns))}")
    rows = []
    for index, row in splits.iterrows():
        train_end = pd.Timestamp(row["train_end"])
        validation_start = pd.Timestamp(row["validation_start"])
        validation_end = pd.Timestamp(row["validation_end"])
        test_start = pd.Timestamp(row["test_start"])
        purge_ok = validation_start > train_end + pd.Timedelta(days=purge_days)
        embargo_ok = test_start > validation_end + pd.Timedelta(days=embargo_days)
        rows.append({"window": index, "purge_ok": purge_ok, "embargo_ok": embargo_ok, "chronology_ok": purge_ok and embargo_ok})
    return pd.DataFrame(rows)
