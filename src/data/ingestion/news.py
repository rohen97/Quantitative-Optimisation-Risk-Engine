from __future__ import annotations

import hashlib

import pandas as pd


def ingest_news(raw_news: pd.DataFrame, source: str = "mock") -> pd.DataFrame:
    data = raw_news.copy()
    if "document_id" not in data:
        text = data.astype(str).agg("|".join, axis=1)
        data["document_id"] = text.map(lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest())
    data["published_at"] = pd.to_datetime(data["published_at"])
    data["source"] = source
    data["ingested_at"] = pd.Timestamp.utcnow().tz_localize(None)
    data["record_hash"] = data["document_id"]
    return data
