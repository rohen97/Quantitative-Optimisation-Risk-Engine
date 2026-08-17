from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pandas as pd

from src.data.repository.duckdb_repository import DuckDBRepository
from src.data.schemas import SCHEMAS


@dataclass(frozen=True)
class FxSeriesSpec:
    quote_currency: str
    invert: bool = False


FRED_USD_FX_SERIES: dict[str, FxSeriesSpec] = {
    "DEXCHUS": FxSeriesSpec("CNY"),
    "DEXHKUS": FxSeriesSpec("HKD"),
    "DEXSZUS": FxSeriesSpec("CHF"),
    "DEXUSEU": FxSeriesSpec("EUR", invert=True),
    "DEXUSUK": FxSeriesSpec("GBP", invert=True),
}


def fx_rates_from_macro_vintages(vintages: pd.DataFrame) -> pd.DataFrame:
    """Derive USD quote rates from already-observed, non-revising FRED vintages."""

    columns = [
        "base_currency",
        "quote_currency",
        "rate_date",
        "rate",
        "source",
        "retrieved_at",
        "ingestion_run_id",
    ]
    if vintages.empty:
        return pd.DataFrame(columns=columns)

    required = {"series_id", "observation_date", "available_from", "value"}
    missing = required.difference(vintages.columns)
    if missing:
        raise ValueError(f"Macro vintage frame is missing columns: {sorted(missing)}")

    clean = vintages.loc[
        vintages["series_id"].isin(FRED_USD_FX_SERIES)
    ].copy()
    clean["observation_date"] = pd.to_datetime(
        clean["observation_date"], errors="coerce"
    ).dt.normalize()
    clean["available_from"] = pd.to_datetime(
        clean["available_from"], errors="coerce"
    )
    clean["value"] = pd.to_numeric(clean["value"], errors="coerce")
    clean = clean.loc[
        clean["observation_date"].notna()
        & clean["available_from"].notna()
        & clean["value"].gt(0)
        & clean["available_from"].dt.normalize().le(clean["observation_date"])
    ]
    if clean.empty:
        return pd.DataFrame(columns=columns)

    sort_columns = ["series_id", "observation_date", "available_from"]
    if "retrieved_at" in clean.columns:
        clean["retrieved_at"] = pd.to_datetime(
            clean["retrieved_at"], errors="coerce"
        )
        sort_columns.append("retrieved_at")
    clean = clean.sort_values(sort_columns).drop_duplicates(
        ["series_id", "observation_date"], keep="first"
    )

    clean["base_currency"] = "USD"
    clean["quote_currency"] = clean["series_id"].map(
        lambda series_id: FRED_USD_FX_SERIES[str(series_id)].quote_currency
    )
    inverted = clean["series_id"].map(
        lambda series_id: FRED_USD_FX_SERIES[str(series_id)].invert
    )
    clean["rate"] = clean["value"].where(~inverted, 1.0 / clean["value"])
    clean["rate_date"] = clean["observation_date"]
    clean["source"] = "fred_macro_vintage"
    clean["retrieved_at"] = pd.Timestamp.now("UTC").tz_localize(None)
    clean["ingestion_run_id"] = None
    return clean[columns].sort_values(
        ["quote_currency", "rate_date"]
    ).reset_index(drop=True)


def materialize_fx_rates_from_macro_vintages(
    repository: DuckDBRepository,
    *,
    ingestion_run_id: str | None = None,
) -> dict[str, object]:
    series_ids = sorted(FRED_USD_FX_SERIES)
    vintages = repository.query(
        """
        SELECT
            series_id, observation_date, available_from, value, retrieved_at
        FROM macro_release_vintages
        WHERE series_id IN (SELECT UNNEST(?))
        ORDER BY series_id, observation_date, available_from, retrieved_at
        """,
        [series_ids],
    )
    rates = fx_rates_from_macro_vintages(vintages)
    if rates.empty:
        raise RuntimeError(
            "No eligible FRED FX macro vintages were available for materialization."
        )

    run_id = ingestion_run_id or f"fx-macro-{uuid4()}"
    rates["ingestion_run_id"] = run_id
    repository.write_table(
        "fx_rates",
        rates,
        SCHEMAS["fx_rates"].primary_key,
    )
    coverage = (
        rates.groupby("quote_currency", as_index=False)
        .agg(rows=("rate", "size"), first_date=("rate_date", "min"), last_date=("rate_date", "max"))
        .sort_values("quote_currency")
    )
    return {
        "ingestion_run_id": run_id,
        "rows": int(len(rates)),
        "coverage": coverage.to_dict(orient="records"),
    }
