from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import pandas as pd


@dataclass(frozen=True)
class IngestionRequest:
    source_name: str
    dataset_name: str
    start_date: str | None = None
    end_date: str | None = None
    parameters: dict[str, object] | None = None


@dataclass(frozen=True)
class IngestionResult:
    ingestion_run_id: str
    dataset_name: str
    source_name: str
    rows_received: int
    rows_accepted: int
    rows_rejected: int
    status: str


class DataFetcher(Protocol):
    def fetch(self, request: IngestionRequest) -> pd.DataFrame: ...


class DataNormaliser(Protocol):
    def normalise(self, data: pd.DataFrame, request: IngestionRequest) -> pd.DataFrame: ...


@dataclass(frozen=True)
class IngestionRunMetadata:
    """Raw-layer metadata for one ingestion run."""

    ingestion_run_id: str
    source_name: str
    dataset_name: str
    started_at: pd.Timestamp
    completed_at: pd.Timestamp | None
    status: str
    requested_start_date: pd.Timestamp | None
    requested_end_date: pd.Timestamp | None
    request_parameters_json: str
    row_count: int
    inserted_count: int
    updated_count: int
    rejected_count: int
    payload_hash: str | None
    config_hash: str | None
    error_message: str | None

    @classmethod
    def build(
        cls,
        source_name: str,
        dataset_name: str,
        status: str,
        row_count: int,
        request_parameters: dict | None = None,
        ingestion_run_id: str | None = None,
        payload_hash: str | None = None,
        config_hash: str | None = None,
        error_message: str | None = None,
    ) -> "IngestionRunMetadata":
        now = pd.Timestamp(datetime.now(UTC)).tz_localize(None)
        completed = now if status.lower() in {"completed", "success"} else None
        return cls(
            ingestion_run_id=ingestion_run_id or str(uuid4()),
            source_name=source_name,
            dataset_name=dataset_name,
            started_at=now,
            completed_at=completed,
            status=status,
            requested_start_date=None,
            requested_end_date=None,
            request_parameters_json=json.dumps(request_parameters or {}, sort_keys=True),
            row_count=row_count,
            inserted_count=row_count if completed is not None else 0,
            updated_count=0,
            rejected_count=0,
            payload_hash=payload_hash,
            config_hash=config_hash,
            error_message=error_message,
        )

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([self.__dict__])


@dataclass(frozen=True)
class RawPayloadMetadata:
    """Metadata and archive pointer for raw payloads kept outside DuckDB."""

    payload_id: str
    ingestion_run_id: str
    source_name: str
    dataset_name: str
    retrieved_at: pd.Timestamp
    request_parameters_json: str
    response_status: int | None
    payload_hash: str
    archive_path: str | None
    row_count: int | None

    @classmethod
    def build(
        cls,
        ingestion_run_id: str,
        source_name: str,
        dataset_name: str,
        payload_hash: str,
        request_parameters: dict | None = None,
        response_status: int | None = None,
        archive_path: str | Path | None = None,
        row_count: int | None = None,
        payload_id: str | None = None,
    ) -> "RawPayloadMetadata":
        return cls(
            payload_id=payload_id or str(uuid4()),
            ingestion_run_id=ingestion_run_id,
            source_name=source_name,
            dataset_name=dataset_name,
            retrieved_at=pd.Timestamp(datetime.now(UTC)).tz_localize(None),
            request_parameters_json=json.dumps(request_parameters or {}, sort_keys=True),
            response_status=response_status,
            payload_hash=payload_hash,
            archive_path=str(archive_path) if archive_path is not None else None,
            row_count=row_count,
        )

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([self.__dict__])


class IngestionTask:
    table_name: str

    def run(self) -> pd.DataFrame:
        raise NotImplementedError
