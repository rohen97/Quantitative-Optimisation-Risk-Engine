from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd


class ValidationStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONALLY_APPROVED"
    REJECTED = "REJECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ValidationIssue:
    component: str
    severity: str
    rule: str
    message: str
    affected_observations: int = 0


@dataclass(frozen=True)
class ValidationMetric:
    component: str
    metric_name: str
    metric_value: float | None
    threshold: float | None
    passed: bool | None
    sample_size: int
    segment: str = "overall"
    notes: str | None = None


@dataclass
class ValidationDataPackage:
    validation_run_id: str
    as_of_date: pd.Timestamp
    forecasts: dict[str, pd.DataFrame] = field(default_factory=dict)
    realised_returns: pd.DataFrame = field(default_factory=pd.DataFrame)
    realised_dividend_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    realised_drawdowns: pd.DataFrame = field(default_factory=pd.DataFrame)
    risk_forecasts: pd.DataFrame = field(default_factory=pd.DataFrame)
    portfolio_weights: dict[str, pd.DataFrame] = field(default_factory=dict)
    portfolio_returns: pd.DataFrame = field(default_factory=pd.DataFrame)
    transaction_costs: pd.DataFrame = field(default_factory=pd.DataFrame)
    regime_history: pd.DataFrame = field(default_factory=pd.DataFrame)
    drl_seed_results: pd.DataFrame = field(default_factory=pd.DataFrame)
    drl_benchmark_results: pd.DataFrame = field(default_factory=pd.DataFrame)
    constraint_reports: dict[str, pd.DataFrame] = field(default_factory=dict)
    lineage: pd.DataFrame = field(default_factory=pd.DataFrame)
    historical_portfolio_weights: pd.DataFrame = field(default_factory=pd.DataFrame)
    evidence_mode: str = 'current_snapshot'
    evidence_manifest: dict[str, Any] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass(frozen=True)
class ComponentApproval:
    component: str
    score: float
    status: str
    critical_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    approved_version: str | None


@dataclass(frozen=True)
class ValidationPipelineResult:
    validation_run_id: str
    output_directory: Path
    overall_score: float
    approval_status: str
    critical_failures: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ValidationCheck:
    component: str
    check_name: str
    status: ValidationStatus
    score: float
    critical: bool
    observation_count: int
    metric_value: float | None = None
    threshold: float | None = None
    commentary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationBundle:
    validation_run_id: str
    run_directory: Path
    latest_directory: Path
    approval: ApprovalDecision
    overall_score: float
    manifest_path: Path
    markdown_path: Path
    html_path: Path
