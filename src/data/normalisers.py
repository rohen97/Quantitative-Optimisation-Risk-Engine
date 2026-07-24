from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid5, NAMESPACE_URL

import pandas as pd


def _now() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(UTC)).tz_localize(None)


def record_hash(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    values = frame[columns].astype(str).agg("|".join, axis=1)
    return values.map(lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest())


def rename_and_require(data: pd.DataFrame, column_mapping: Mapping[str, str] | None, required_columns: set[str]) -> pd.DataFrame:
    renamed = data.rename(columns=dict(column_mapping or {})).copy()
    missing = required_columns.difference(renamed.columns)
    if missing:
        raise ValueError(f"Missing required canonical columns: {sorted(missing)}")
    return renamed


def normalise_security_ids(data: pd.DataFrame, column: str = "security_id") -> pd.DataFrame:
    clean = data.copy()
    clean[column] = clean[column].astype(str).str.strip().str.upper()
    return clean


def normalise_currency_codes(data: pd.DataFrame, columns: tuple[str, ...] = ("currency", "trading_currency", "base_currency", "quote_currency")) -> pd.DataFrame:
    clean = data.copy()
    for column in columns:
        if column in clean:
            clean[column] = clean[column].astype(str).str.strip().str.upper()
    return clean


def normalise_country_codes(data: pd.DataFrame, column: str = "country") -> pd.DataFrame:
    clean = data.copy()
    if column in clean:
        clean[column] = clean[column].astype(str).str.strip()
    return clean


def normalise_timestamps(data: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    clean = data.copy()
    for column in columns:
        if column in clean:
            clean[column] = pd.to_datetime(clean[column], errors="raise")
    return clean


def normalise_prices(
    frame: pd.DataFrame,
    source: str = "mock",
    column_mapping: Mapping[str, str] | None = None,
    retrieved_at: pd.Timestamp | None = None,
) -> pd.DataFrame:
    data = frame.rename(columns=dict(column_mapping or {})).copy()
    date_column = "trade_date" if "trade_date" in data else "date"
    ticker_column = "security_id" if "security_id" in data else "ticker"
    close_column = "close_price" if "close_price" in data else "close"
    data["security_id"] = data[ticker_column].astype(str).str.upper()
    data["trade_date"] = pd.to_datetime(data[date_column]).dt.normalize()
    data["close_price"] = pd.to_numeric(data[close_column], errors="coerce")
    data["open_price"] = pd.to_numeric(data.get("open_price", data.get("open", data["close_price"])), errors="coerce")
    data["high_price"] = pd.to_numeric(data.get("high_price", data.get("high", data["close_price"])), errors="coerce")
    data["low_price"] = pd.to_numeric(data.get("low_price", data.get("low", data["close_price"])), errors="coerce")
    data["adjusted_close"] = pd.to_numeric(data.get("adjusted_close", data.get("adj_close", data["close_price"])), errors="coerce")
    volume = data["volume"] if "volume" in data else pd.Series(0.0, index=data.index)
    data["volume"] = pd.to_numeric(volume, errors="coerce").fillna(0.0)
    data["trading_currency"] = data.get("trading_currency", data.get("currency", "USD"))
    data["source"] = source
    data["retrieved_at"] = pd.Timestamp(retrieved_at).tz_localize(None) if retrieved_at is not None else _now()
    data["ingestion_run_id"] = data.get("ingestion_run_id", None)
    data["row_hash"] = record_hash(
        data,
        ["security_id", "trade_date", "open_price", "high_price", "low_price", "close_price", "adjusted_close", "volume", "source"],
    )
    return data[
        [
            "security_id",
            "trade_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "adjusted_close",
            "volume",
            "trading_currency",
            "source",
            "retrieved_at",
            "ingestion_run_id",
            "row_hash",
        ]
    ]


def normalise_fundamentals(
    frame: pd.DataFrame,
    source: str = "mock",
    column_mapping: Mapping[str, str] | None = None,
    retrieved_at: pd.Timestamp | None = None,
) -> pd.DataFrame:
    data = frame.rename(columns=dict(column_mapping or {})).copy()
    if "security_id" not in data:
        data["security_id"] = data["ticker"].astype(str).str.upper()
    if "fiscal_period_end" not in data:
        data["fiscal_period_end"] = pd.Timestamp.today().normalize()
    if "fiscal_period_type" not in data:
        data["fiscal_period_type"] = "quarterly"
    if "filing_date" not in data:
        data["filing_date"] = pd.Timestamp.today().normalize()
    data["security_id"] = data["security_id"].astype(str).str.upper()
    data["fiscal_period_end"] = pd.to_datetime(data["fiscal_period_end"]).dt.normalize()
    data["filing_date"] = pd.to_datetime(data["filing_date"]).dt.normalize()
    data["available_from"] = pd.to_datetime(data.get("available_from", data["filing_date"])).dt.normalize()
    data["currency"] = data.get("currency", "USD")
    canonical_metrics = {
        "revenue": "revenue",
        "operating_income": "operating_income",
        "net_income": "net_income",
        "operating_cash_flow": "operating_cash_flow",
        "capital_expenditure": "capital_expenditure",
        "capex": "capital_expenditure",
        "free_cash_flow": "free_cash_flow",
        "total_assets": "total_assets",
        "total_liabilities": "total_liabilities",
        "total_debt": "total_debt",
        "cash_and_equivalents": "cash_and_equivalents",
        "cash": "cash_and_equivalents",
        "shareholders_equity": "shareholders_equity",
        "dividends_paid": "dividends_paid",
        "diluted_shares": "diluted_shares",
    }
    for output_column in set(canonical_metrics.values()):
        source_column = next((candidate for candidate, target in canonical_metrics.items() if target == output_column and candidate in data), None)
        data[output_column] = pd.to_numeric(data[source_column], errors="coerce") if source_column else pd.NA
    data["source"] = source
    data["retrieved_at"] = pd.Timestamp(retrieved_at).tz_localize(None) if retrieved_at is not None else _now()
    data["ingestion_run_id"] = data.get("ingestion_run_id", None)
    data["vintage_id"] = data.apply(
        lambda row: str(uuid5(NAMESPACE_URL, f"{row['security_id']}|{row['fiscal_period_end']}|{row['fiscal_period_type']}|{source}|{row['available_from']}")),
        axis=1,
    )
    data["row_hash"] = record_hash(
        data,
        ["security_id", "fiscal_period_end", "fiscal_period_type", "available_from", "revenue", "net_income", "free_cash_flow", "source", "vintage_id"],
    )
    return data[
        [
            "security_id",
            "fiscal_period_end",
            "fiscal_period_type",
            "filing_date",
            "available_from",
            "currency",
            "revenue",
            "operating_income",
            "net_income",
            "operating_cash_flow",
            "capital_expenditure",
            "free_cash_flow",
            "total_assets",
            "total_liabilities",
            "total_debt",
            "cash_and_equivalents",
            "shareholders_equity",
            "dividends_paid",
            "diluted_shares",
            "source",
            "retrieved_at",
            "ingestion_run_id",
            "vintage_id",
            "row_hash",
        ]
    ]


def normalise_macro_observations(
    frame: pd.DataFrame,
    source: str = "mock",
    column_mapping: Mapping[str, str] | None = None,
    retrieved_at: pd.Timestamp | None = None,
) -> pd.DataFrame:
    data = frame.rename(columns=dict(column_mapping or {})).copy()
    data["series_id"] = data["series_id"].astype(str)
    data["observation_date"] = pd.to_datetime(data["observation_date"]).dt.normalize()
    data["vintage_date"] = pd.to_datetime(data["vintage_date"]).dt.normalize()
    data["available_from"] = pd.to_datetime(data.get("available_from", data["vintage_date"])).dt.normalize()
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data["unit"] = data.get("unit", "")
    data["frequency"] = data.get("frequency", "")
    data["source"] = source
    data["retrieved_at"] = pd.Timestamp(retrieved_at).tz_localize(None) if retrieved_at is not None else _now()
    data["ingestion_run_id"] = data.get("ingestion_run_id", None)
    return data[["series_id", "observation_date", "vintage_date", "available_from", "value", "unit", "frequency", "source", "retrieved_at", "ingestion_run_id"]]


def normalise_macro_vintages(frame: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    return normalise_macro_observations(frame, source=source)


def normalise_dividends(frame: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    from src.data.ingestion.dividends import ingest_dividends

    return ingest_dividends(frame, source=source)


def normalise_fx_rates(frame: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    from src.data.ingestion.fx import ingest_fx

    return ingest_fx(frame, source=source)


def normalise_news_documents(frame: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    data = frame.copy()
    data["document_id"] = data["document_id"].astype(str)
    data["published_at"] = pd.to_datetime(data.get("published_at", pd.NaT))
    data["available_from"] = pd.to_datetime(data.get("available_from", data["published_at"])).fillna(pd.Timestamp.utcnow().tz_localize(None))
    data["retrieved_at"] = pd.to_datetime(data.get("retrieved_at", pd.Timestamp.utcnow().tz_localize(None)))
    data["source"] = source
    data["headline"] = data.get("headline", data.get("title", ""))
    data["body_text"] = data.get("body_text", data.get("body", ""))
    data["language"] = data.get("language", "en")
    data["url_hash"] = data.get("url_hash", "")
    data["payload_hash"] = data.get("payload_hash", record_hash(data.assign(_row=range(len(data))), ["document_id", "headline", "body_text"]))
    data["raw_archive_path"] = data.get("raw_archive_path", None)
    return data[["document_id", "published_at", "available_from", "retrieved_at", "source", "headline", "body_text", "language", "url_hash", "payload_hash", "raw_archive_path"]]
