from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json

import pandas as pd


@dataclass(frozen=True)
class ArchiveMetadata:
    archive_path: Path
    payload_hash: str
    row_count: int


class RawArchiver:
    """Archive clean/raw API pulls to deterministic Parquet files."""

    def __init__(self, root_path: str | Path, compression: str = "zstd") -> None:
        self.root_path = Path(root_path)
        self.compression = compression

    def archive(self, data: pd.DataFrame, request, ingestion_run_id: str) -> ArchiveMetadata:
        dataset_root = self.root_path / request.source_name / request.dataset_name
        dataset_root.mkdir(parents=True, exist_ok=True)
        archive_path = dataset_root / f"{ingestion_run_id}.parquet"
        data.to_parquet(archive_path, index=False, compression=self.compression)
        payload_hash = dataframe_hash(data)
        return ArchiveMetadata(archive_path=archive_path, payload_hash=payload_hash, row_count=len(data))


def dataframe_hash(data: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(data, index=True).values.tobytes()).hexdigest()


def archive_json(payload: dict[str, Any], root: str | Path, provider: str, name: str) -> Path:
    path = Path(root) / provider
    path.mkdir(parents=True, exist_ok=True)
    output = path / f"{name}.json"
    scrubbed = {key: value for key, value in payload.items() if str(key).lower() not in {"authorization", "api_key", "secret", "headers"}}
    output.write_text(json.dumps(scrubbed, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return output


def _partitioned_root(frame: pd.DataFrame, root: Path, dataset: str) -> Path:
    if dataset == "prices_daily" and {"source", "trade_date"}.issubset(frame.columns) and not frame.empty:
        source = str(frame["source"].iloc[0])
        year = pd.to_datetime(frame["trade_date"]).dt.year.iloc[0]
        return root / dataset / f"source={source}" / f"trade_year={year}"
    if dataset in {"macro", "macro_observations"} and {"source", "series_id"}.issubset(frame.columns) and not frame.empty:
        return root / "macro" / f"source={frame['source'].iloc[0]}" / f"series_id={frame['series_id'].iloc[0]}"
    if dataset in {"news", "news_documents"} and {"source", "published_at"}.issubset(frame.columns) and not frame.empty:
        published = pd.to_datetime(frame["published_at"])
        return root / "news" / f"source={frame['source'].iloc[0]}" / f"published_year={published.dt.year.iloc[0]}" / f"published_month={published.dt.month.iloc[0]:02d}"
    return root / dataset


def archive_parquet(frame: pd.DataFrame, root: str | Path, dataset: str, compression: str = "zstd") -> Path:
    path = _partitioned_root(frame, Path(root), dataset)
    path.mkdir(parents=True, exist_ok=True)
    output = path / f"part-{dataframe_hash(frame)[:16]}.parquet"
    frame.to_parquet(output, index=False, compression=compression)
    return output
