from __future__ import annotations

import pandas as pd


def ingest_fx(raw_fx: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    data = raw_fx.copy()
    data["base_currency"] = data["base_currency"].astype(str).str.upper()
    data["quote_currency"] = data["quote_currency"].astype(str).str.upper()
    data["rate_date"] = pd.to_datetime(data.get("rate_date", data.get("date"))).dt.normalize()
    data["rate"] = pd.to_numeric(data["rate"], errors="coerce")
    data["source"] = source
    data["retrieved_at"] = pd.Timestamp.now('UTC').tz_localize(None)
    data["ingestion_run_id"] = data.get("ingestion_run_id", None)
    return data[["base_currency", "quote_currency", "rate_date", "rate", "source", "retrieved_at", "ingestion_run_id"]]
