from __future__ import annotations

import pandas as pd

from src.data.normalisers import record_hash
from src.data.schemas import SCHEMAS


def normalise_macro_release_vintages(
    observations: pd.DataFrame,
    ingestion_run_id: str | None = None,
) -> pd.DataFrame:
    """Preserve original releases and every observed revision as immutable rows."""
    if observations.empty:
        return pd.DataFrame(columns=SCHEMAS["macro_release_vintages"].column_names)
    output = observations.copy()
    output["observation_date"] = pd.to_datetime(output["observation_date"], errors="coerce")
    output["revision_at"] = pd.to_datetime(output["vintage_date"], errors="coerce")
    output["available_from"] = pd.to_datetime(output["available_from"], errors="coerce")
    output["release_at"] = output.groupby(
        ["series_id", "observation_date", "source"], sort=False
    )["revision_at"].transform("min")
    output["retrieved_at"] = pd.to_datetime(output["retrieved_at"], errors="coerce")
    output["ingestion_run_id"] = ingestion_run_id
    hash_columns = [
        "series_id",
        "observation_date",
        "release_at",
        "revision_at",
        "available_from",
        "value",
        "unit",
        "frequency",
        "source",
    ]
    output = output.dropna(
        subset=["series_id", "observation_date", "release_at", "revision_at", "available_from"]
    )
    output["row_hash"] = record_hash(output, hash_columns)
    output["vintage_id"] = output["row_hash"]
    return output[list(SCHEMAS["macro_release_vintages"].column_names)]
