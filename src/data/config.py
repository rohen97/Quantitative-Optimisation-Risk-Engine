from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.utils.config import ROOT, load_yaml


DataMode = Literal["legacy_csv", "duckdb", "shadow"]


@dataclass(frozen=True)
class DataLayerConfig:
    backend: DataMode = "legacy_csv"
    duckdb_enabled: bool = True
    duckdb_database_path: Path = ROOT / "data/database/wolf.duckdb"
    duckdb_read_only_for_models: bool = True
    duckdb_threads: int = 4
    duckdb_memory_limit: str = "4GB"
    migrations_path: Path = ROOT / "sql/migrations"
    views_path: Path = ROOT / "sql/views"
    parquet_root: Path = ROOT / "data/parquet"
    parquet_compression: str = "zstd"
    partition_prices_by: tuple[str, ...] = ("trade_year",)
    partition_news_by: tuple[str, ...] = ("published_year", "published_month")
    dual_write_enabled: bool = False
    shadow_compare_enabled: bool = False
    fail_on_shadow_difference: bool = False
    fallback_to_legacy_csv: bool = True
    point_in_time_enabled: bool = True
    strict_availability_dates: bool = True
    allow_missing_available_from: bool = False
    use_latest_vintage_only_for_live_runs: bool = True
    preserve_all_vintages: bool = True
    fail_on_duplicate_primary_keys: bool = True
    fail_on_future_available_from: bool = True
    fail_on_invalid_currency: bool = True
    fail_on_negative_prices: bool = True
    maximum_missing_price_fraction: float = 0.05
    absolute_tolerance: float = 1.0e-8
    relative_tolerance: float = 1.0e-6
    weight_absolute_tolerance: float = 1.0e-6
    compare_column_order: bool = False
    preserve_raw_payload_metadata: bool = True
    store_raw_payload_in_database: bool = False
    raw_archive_root: Path = ROOT / "data/raw_archive"
    register_ingestion_runs: bool = True
    register_model_runs: bool = True
    calculate_config_hash: bool = True
    calculate_input_snapshot_hash: bool = True
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def mode(self) -> DataMode:
        return self.backend

    @property
    def dual_write_duckdb(self) -> bool:
        return self.dual_write_enabled

    @property
    def shadow_compare(self) -> bool:
        return self.shadow_compare_enabled

    @property
    def duckdb_path(self) -> Path:
        return self.duckdb_database_path

    @property
    def numeric_tolerance(self) -> float:
        return self.relative_tolerance

    @property
    def row_count_tolerance(self) -> int:
        return 0

    @property
    def fail_on_difference(self) -> bool:
        return self.fail_on_shadow_difference


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def load_data_config(path: str | Path = "configs/data.yaml") -> DataLayerConfig:
    """Load backend migration settings without changing model behaviour."""
    loaded = load_yaml(path)
    raw = loaded.get("data", loaded)
    duckdb_cfg = raw.get("duckdb", {})
    parquet_cfg = raw.get("parquet", {})
    migration_cfg = raw.get("migration", {})
    point_in_time_cfg = raw.get("point_in_time", {})
    validation_cfg = raw.get("validation", {})
    comparison_cfg = raw.get("comparison", {})
    retention_cfg = raw.get("retention", {})
    audit_cfg = raw.get("audit", {})
    backend = str(raw.get("backend", raw.get("mode", "legacy_csv")))
    if backend not in {"legacy_csv", "duckdb", "shadow"}:
        raise ValueError(f"Unsupported data backend: {backend}")
    return DataLayerConfig(
        backend=backend,  # type: ignore[arg-type]
        duckdb_enabled=bool(duckdb_cfg.get("enabled", True)),
        duckdb_database_path=_resolve(duckdb_cfg.get("database_path", "data/database/wolf.duckdb")),
        duckdb_read_only_for_models=bool(duckdb_cfg.get("read_only_for_models", True)),
        duckdb_threads=int(duckdb_cfg.get("threads", 4)),
        duckdb_memory_limit=str(duckdb_cfg.get("memory_limit", "4GB")),
        migrations_path=_resolve(duckdb_cfg.get("migrations_path", "sql/migrations")),
        views_path=_resolve(duckdb_cfg.get("views_path", "sql/views")),
        parquet_root=_resolve(parquet_cfg.get("root_path", "data/parquet")),
        parquet_compression=str(parquet_cfg.get("compression", "zstd")),
        partition_prices_by=tuple(parquet_cfg.get("partition_prices_by", ["trade_year"])),
        partition_news_by=tuple(parquet_cfg.get("partition_news_by", ["published_year", "published_month"])),
        dual_write_enabled=bool(migration_cfg.get("dual_write_enabled", raw.get("dual_write_duckdb", False))),
        shadow_compare_enabled=bool(migration_cfg.get("shadow_compare_enabled", raw.get("shadow_compare", False))),
        fail_on_shadow_difference=bool(migration_cfg.get("fail_on_shadow_difference", False)),
        fallback_to_legacy_csv=bool(migration_cfg.get("fallback_to_legacy_csv", True)),
        point_in_time_enabled=bool(point_in_time_cfg.get("enabled", True)),
        strict_availability_dates=bool(point_in_time_cfg.get("strict_availability_dates", True)),
        allow_missing_available_from=bool(point_in_time_cfg.get("allow_missing_available_from", False)),
        use_latest_vintage_only_for_live_runs=bool(point_in_time_cfg.get("use_latest_vintage_only_for_live_runs", True)),
        preserve_all_vintages=bool(point_in_time_cfg.get("preserve_all_vintages", True)),
        fail_on_duplicate_primary_keys=bool(validation_cfg.get("fail_on_duplicate_primary_keys", True)),
        fail_on_future_available_from=bool(validation_cfg.get("fail_on_future_available_from", True)),
        fail_on_invalid_currency=bool(validation_cfg.get("fail_on_invalid_currency", True)),
        fail_on_negative_prices=bool(validation_cfg.get("fail_on_negative_prices", True)),
        maximum_missing_price_fraction=float(validation_cfg.get("maximum_missing_price_fraction", 0.05)),
        absolute_tolerance=float(comparison_cfg.get("absolute_tolerance", 1.0e-8)),
        relative_tolerance=float(comparison_cfg.get("relative_tolerance", 1.0e-6)),
        weight_absolute_tolerance=float(comparison_cfg.get("weight_absolute_tolerance", 1.0e-6)),
        compare_column_order=bool(comparison_cfg.get("compare_column_order", False)),
        preserve_raw_payload_metadata=bool(retention_cfg.get("preserve_raw_payload_metadata", True)),
        store_raw_payload_in_database=bool(retention_cfg.get("store_raw_payload_in_database", False)),
        raw_archive_root=_resolve(retention_cfg.get("raw_archive_path", "data/raw_archive")),
        register_ingestion_runs=bool(audit_cfg.get("register_ingestion_runs", True)),
        register_model_runs=bool(audit_cfg.get("register_model_runs", True)),
        calculate_config_hash=bool(audit_cfg.get("calculate_config_hash", True)),
        calculate_input_snapshot_hash=bool(audit_cfg.get("calculate_input_snapshot_hash", True)),
        extra={key: value for key, value in raw.items() if key not in {"backend", "mode", "duckdb", "parquet", "migration", "point_in_time", "validation", "comparison", "retention", "audit"}},
    )
