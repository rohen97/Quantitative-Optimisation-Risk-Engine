from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import pandas as pd

from src.data.config import DataLayerConfig
from src.data.ingestion.base import IngestionRequest, IngestionResult
from src.data.schemas import SCHEMAS


LOGGER = logging.getLogger(__name__)


def write_ingested_frame(repository, table_name: str, frame: pd.DataFrame, config: DataLayerConfig, source: str) -> IngestionResult:
    schema = SCHEMAS[table_name]
    repository.write_table(table_name, frame[list(schema.column_names)], schema.primary_key)
    LOGGER.info("Wrote %s rows to %s using %s mode.", len(frame), table_name, config.mode)
    return IngestionResult(
        ingestion_run_id=str(uuid.uuid4()),
        dataset_name=table_name,
        source_name=source,
        rows_received=len(frame),
        rows_accepted=len(frame),
        rows_rejected=0,
        status="completed",
    )


class IngestionRunner:
    def __init__(self, repository, validator, normaliser, raw_archiver) -> None:
        self.repository = repository
        self.validator = validator
        self.normaliser = normaliser
        self.raw_archiver = raw_archiver

    def run(self, request: IngestionRequest, fetcher, save_method_name: str) -> IngestionResult:
        ingestion_run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        del started_at
        raw = fetcher.fetch(request)
        self.raw_archiver.archive(data=raw, request=request, ingestion_run_id=ingestion_run_id)
        clean = self.normaliser.normalise(raw, request=request)
        validation = self.validator(clean)
        if not validation.valid:
            raise ValueError(f"Validation failed for {request.dataset_name}")
        save_method = getattr(self.repository, save_method_name)
        save_method(clean, ingestion_run_id=ingestion_run_id)
        return IngestionResult(
            ingestion_run_id=ingestion_run_id,
            dataset_name=request.dataset_name,
            source_name=request.source_name,
            rows_received=len(raw),
            rows_accepted=len(clean),
            rows_rejected=len(raw) - len(clean),
            status="completed",
        )
