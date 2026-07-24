from __future__ import annotations

from datetime import date, datetime
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.comparison.frame_compare import compare_frames
from src.data.config import DataLayerConfig
from src.data.repository.csv_repository import CSVRepository
from src.data.repository.duckdb_repository import DuckDBRepository, DuckDBUnavailableError


LOGGER = logging.getLogger(__name__)


def _get(settings: Any, path: str, default: Any = None) -> Any:
    current = settings
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part, default)
        else:
            current = getattr(current, part, default)
        if current is default:
            break
    return current


class ShadowRepository:
    """Read both backends, log comparisons, and return legacy data by default."""

    def __init__(
        self,
        legacy_repository: CSVRepository,
        duckdb_repository: DuckDBRepository,
        comparison_settings: Any | None = None,
        output_root: str | Path = "reports/outputs",
        return_duckdb: bool = False,
    ) -> None:
        self.legacy_repository = legacy_repository
        self.duckdb_repository = duckdb_repository
        self.comparison_settings = comparison_settings or {}
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.return_duckdb = return_duckdb

    def _compare(self, name: str, legacy: pd.DataFrame, duckdb_frame: pd.DataFrame) -> None:
        tolerance = float(_get(self.comparison_settings, "relative_tolerance", _get(self.comparison_settings, "relative_tolerance", 1e-6)))
        result = compare_frames(legacy, duckdb_frame, numeric_tolerance=tolerance)
        report = pd.DataFrame(
            [
                {
                    "dataset": name,
                    "matched": result.matched,
                    "row_count_left": result.row_count_left,
                    "row_count_right": result.row_count_right,
                    "max_numeric_difference": result.max_numeric_difference,
                    "row_count_difference": result.row_count_difference,
                }
            ]
        )
        report.to_csv(self.output_root / f"shadow_{name}_comparison.csv", index=False)
        if not result.matched:
            LOGGER.warning("Shadow repository difference for %s: rows=%s max_diff=%s", name, result.row_count_difference, result.max_numeric_difference)

    def _shadow_read(self, name: str, method_name: str, *args):
        legacy = getattr(self.legacy_repository, method_name)(*args)
        duckdb_frame = getattr(self.duckdb_repository, method_name)(*args)
        self._compare(name, legacy, duckdb_frame)
        return duckdb_frame if self.return_duckdb else legacy

    def read_table(self, name: str) -> pd.DataFrame:
        legacy = self.legacy_repository.read_table(name)
        duckdb_frame = self.duckdb_repository.read_table(name)
        self._compare(name, legacy, duckdb_frame)
        return duckdb_frame if self.return_duckdb else legacy

    def write_table(self, name: str, frame: pd.DataFrame, primary_key: tuple[str, ...] | None = None) -> None:
        self.legacy_repository.write_table(name, frame, primary_key)
        self.duckdb_repository.write_table(name, frame, primary_key)

    def _shadow_save(self, method_name: str, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        getattr(self.legacy_repository, method_name)(data, ingestion_run_id=ingestion_run_id)
        getattr(self.duckdb_repository, method_name)(data, ingestion_run_id=ingestion_run_id)

    def save_prices(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._shadow_save("save_prices", data, ingestion_run_id)

    def save_fundamentals(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._shadow_save("save_fundamentals", data, ingestion_run_id)

    def save_dividends(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._shadow_save("save_dividends", data, ingestion_run_id)

    def save_fx_rates(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._shadow_save("save_fx_rates", data, ingestion_run_id)

    def save_macro_observations(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._shadow_save("save_macro_observations", data, ingestion_run_id)

    def save_news_documents(self, data: pd.DataFrame, ingestion_run_id: str | None = None) -> None:
        self._shadow_save("save_news_documents", data, ingestion_run_id)

    def load_prices(self, security_ids: list[str], start_date: date, end_date: date) -> pd.DataFrame:
        return self._shadow_read("prices", "load_prices", security_ids, start_date, end_date)

    def load_point_in_time_fundamentals(self, security_ids: list[str], as_of_date: datetime) -> pd.DataFrame:
        return self._shadow_read("fundamentals", "load_point_in_time_fundamentals", security_ids, as_of_date)

    def load_point_in_time_macro(self, series_ids: list[str], as_of_date: datetime) -> pd.DataFrame:
        return self._shadow_read("macro", "load_point_in_time_macro", series_ids, as_of_date)

    def load_feature_snapshot(self, as_of_date: date) -> pd.DataFrame:
        return self._shadow_read("features", "load_feature_snapshot", as_of_date)

    def register_model_run(self, metadata: dict[str, object]) -> str:
        model_run_id = self.duckdb_repository.register_model_run(metadata)
        legacy_metadata = {"model_run_id": model_run_id, **metadata}
        self.legacy_repository.register_model_run(legacy_metadata)
        return model_run_id

    def complete_model_run(
        self,
        model_run_id: str,
        status: str,
        output_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.duckdb_repository.complete_model_run(model_run_id, status, output_path, error_message)
        self.legacy_repository.complete_model_run(model_run_id, status, output_path, error_message)


def build_repository(settings):
    backend = _get(settings, "data.backend", _get(settings, "backend", "legacy_csv"))
    database_path = Path(_get(settings, "data.duckdb.database_path", _get(settings, "duckdb_database_path", "data/database/wolf.duckdb")))
    read_only = bool(_get(settings, "data.duckdb.read_only_for_models", _get(settings, "duckdb_read_only_for_models", True)))
    output_root = Path(_get(settings, "output_root", "reports/outputs"))

    if backend == "legacy_csv":
        return CSVRepository(output_root=output_root)
    if backend == "duckdb":
        return DuckDBRepository(database_path=database_path, read_only=read_only)
    if backend == "shadow":
        return ShadowRepository(
            legacy_repository=CSVRepository(output_root=output_root),
            duckdb_repository=DuckDBRepository(database_path=database_path, read_only=False),
            comparison_settings=_get(settings, "data.comparison", _get(settings, "comparison", {})),
            return_duckdb=bool(_get(settings, "data.migration.return_duckdb_in_shadow", False)),
        )
    raise ValueError(f"Unsupported data backend: {backend}")


def repository_for_mode(config: DataLayerConfig, csv_root: str | Path = "reports/outputs"):
    """Return the configured repository while keeping legacy CSV safe by default."""
    try:
        if config.mode == "legacy_csv":
            return CSVRepository(output_root=csv_root)
        if config.mode == "duckdb":
            return DuckDBRepository(config.duckdb_path, read_only=False)
        if config.mode == "shadow":
            return ShadowRepository(CSVRepository(output_root=csv_root), DuckDBRepository(config.duckdb_path, read_only=False))
    except DuckDBUnavailableError:
        if config.mode == "duckdb":
            raise
        LOGGER.warning("DuckDB unavailable in shadow mode; falling back to legacy CSV repository.")
        return CSVRepository(output_root=csv_root)
    raise ValueError(f"Unsupported data mode: {config.mode}")
