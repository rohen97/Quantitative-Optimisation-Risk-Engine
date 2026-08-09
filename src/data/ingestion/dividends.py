from __future__ import annotations

import pandas as pd


def _optional_date(data: pd.DataFrame, column: str) -> pd.Series:
    if column in data:
        return pd.to_datetime(data[column]).dt.normalize()
    return pd.Series(pd.NaT, index=data.index)


def ingest_dividends(raw_dividends: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    data = raw_dividends.copy()
    if "security_id" not in data:
        data["security_id"] = data["ticker"].astype(str).str.upper()
    data["security_id"] = data["security_id"].astype(str).str.upper()
    data["declaration_date"] = _optional_date(data, "declaration_date")
    data["ex_dividend_date"] = pd.to_datetime(data.get("ex_dividend_date", data.get("ex_date"))).dt.normalize()
    data["record_date"] = _optional_date(data, "record_date")
    data["payment_date"] = pd.to_datetime(data.get("payment_date", data.get("pay_date", pd.NaT))).dt.normalize()
    data["dividend_amount"] = pd.to_numeric(data.get("dividend_amount", data.get("dividend_per_share")), errors="coerce")
    data["currency"] = data.get("currency", "USD")
    data["dividend_type"] = data.get("dividend_type", "cash")
    data["available_from"] = pd.to_datetime(data.get("available_from", data["ex_dividend_date"])).dt.normalize()
    data["source"] = source
    data["retrieved_at"] = pd.Timestamp.now('UTC').tz_localize(None)
    data["ingestion_run_id"] = data.get("ingestion_run_id", None)
    return data[
        [
            "security_id",
            "declaration_date",
            "ex_dividend_date",
            "record_date",
            "payment_date",
            "dividend_amount",
            "currency",
            "dividend_type",
            "available_from",
            "source",
            "retrieved_at",
            "ingestion_run_id",
        ]
    ]
