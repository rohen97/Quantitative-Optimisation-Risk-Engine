from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_SEVERITIES = {"INFO", "WARNING", "CRITICAL"}
VALID_RUN_STATUSES = {
    "PENDING",
    "RUNNING",
    "SUCCEEDED",
    "SUCCEEDED_WITH_WARNINGS",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
}


@dataclass(frozen=True)
class ProductionAlert:
    alert_id: str
    production_run_id: str | None
    created_at: datetime
    severity: str
    component: str
    alert_type: str
    title: str
    message: str
    fingerprint: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HealthCheckResult:
    check_name: str
    status: str
    severity: str
    message: str
    metric_value: float | None = None
    metric_text: str | None = None
    threshold_value: float | None = None


@dataclass(frozen=True)
class DriftCheckResult:
    drift_type: str
    segment: str
    metric_name: str
    metric_value: float | None
    warning_threshold: float | None
    critical_threshold: float | None
    status: str
    sample_size: int
    notes: str | None = None


@dataclass(frozen=True)
class StepDefinition:
    name: str
    order: int
    required: bool
    command: tuple[str, ...]
    timeout_seconds: int
    retryable: bool = True


@dataclass(frozen=True)
class StepExecutionResult:
    name: str
    status: str
    required: bool
    attempt_count: int
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    exit_code: int | None
    stdout_path: Path
    stderr_path: Path
    error_message: str | None = None


@dataclass(frozen=True)
class ApprovalGateResult:
    approved: bool
    status: str
    critical_failures: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass
class ProductionRunResult:
    production_run_id: str
    mode: str
    status: str
    approval_status: str
    output_directory: Path
    started_at: datetime
    completed_at: datetime
    step_results: list[StepExecutionResult]
    health_checks: list[HealthCheckResult]
    drift_checks: list[DriftCheckResult]
    alerts: list[ProductionAlert]
    critical_failures: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ProductionRunContext:
    production_run_id: str
    mode: str
    validation_mode: str
    as_of_date: datetime
    started_at: datetime
    repository_root: Path
    output_directory: Path
    log_directory: Path
    config_hash: str
    git_commit_hash: str | None
    git_is_dirty: bool
    host_name: str
    process_id: int
