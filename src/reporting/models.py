from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ReportSource:
    name: str
    path: Path | None
    available: bool
    row_count: int
    modified_at: datetime | None
    source_hash: str | None
    warning: str | None = None


@dataclass(frozen=True)
class DataQualityFlag:
    severity: str
    section: str
    rule: str
    message: str


@dataclass
class ICDataPackage:
    model_run_id: str
    as_of_date: pd.Timestamp
    current_portfolio: pd.DataFrame = field(default_factory=pd.DataFrame)
    final_portfolio: pd.DataFrame = field(default_factory=pd.DataFrame)
    final_trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    portfolio_aware: pd.DataFrame = field(default_factory=pd.DataFrame)
    clean_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)
    optimiser_candidates: dict[str, pd.DataFrame] = field(default_factory=dict)
    forecasts: dict[str, pd.DataFrame] = field(default_factory=dict)
    risk_report: pd.DataFrame = field(default_factory=pd.DataFrame)
    risk_contributions: pd.DataFrame = field(default_factory=pd.DataFrame)
    stress_report: pd.DataFrame = field(default_factory=pd.DataFrame)
    stress_contributions: pd.DataFrame = field(default_factory=pd.DataFrame)
    regime_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    regime_suitability: pd.DataFrame = field(default_factory=pd.DataFrame)
    hedge_recommendations: pd.DataFrame = field(default_factory=pd.DataFrame)
    defensive_substitutions: pd.DataFrame = field(default_factory=pd.DataFrame)
    drl_outputs: dict[str, pd.DataFrame] = field(default_factory=dict)
    sources: list[ReportSource] = field(default_factory=list)
    quality_flags: list[DataQualityFlag] = field(default_factory=list)
    markdown: dict[str, str] = field(default_factory=dict)
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    source_root: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutiveSummary:
    model_run_id: str
    as_of_date: str
    decision_readiness_status: str
    current_nav_usd: float | None
    selected_portfolio_source: str
    dominant_regime: str | None
    wolf_chaos_index: float | None
    expected_total_return_12m: float | None
    expected_dividend_yield: float | None
    p5_return_12m: float | None
    p50_return_12m: float | None
    p95_return_12m: float | None
    portfolio_var_5: float | None
    portfolio_cvar_5: float | None
    portfolio_expected_shortfall_5: float | None
    worst_stress_scenario: str | None
    worst_stress_loss: float | None
    drl_status: str | None
    maximum_single_name_weight: float | None
    effective_number_of_holdings: float | None
    top_actions: tuple[str, ...]
    critical_warnings: tuple[str, ...]


class ICDataBundle(ICDataPackage):
    def __init__(
        self,
        frames: dict[str, pd.DataFrame],
        markdown: dict[str, str] | None = None,
        source_root: Path | None = None,
        sources: list[ReportSource] | None = None,
        quality_flags: list[DataQualityFlag] | None = None,
        model_run_id: str = "unknown",
        as_of_date: pd.Timestamp | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            model_run_id=model_run_id,
            as_of_date=as_of_date or pd.Timestamp.now('UTC'),
            current_portfolio=frames.get("current_portfolio", pd.DataFrame()),
            final_portfolio=frames.get("final_recommendations", frames.get("final_portfolio_weights", pd.DataFrame())),
            final_trades=frames.get("portfolio_trade_list", pd.DataFrame()),
            portfolio_aware=frames.get("recommendations_portfolio_aware", pd.DataFrame()),
            clean_sheet=frames.get("recommendations_clean_sheet", pd.DataFrame()),
            optimiser_candidates={
                key: value
                for key, value in frames.items()
                if key.startswith("optimised_portfolio_")
            },
            forecasts={
                key: value
                for key, value in frames.items()
                if key.startswith("ml_forecasts_") or key in {"return_distribution_forecasts", "dividend_cut_probability", "drawdown_probability"}
            },
            risk_report=frames.get("risk_report", pd.DataFrame()),
            risk_contributions=frames.get("risk_contribution", pd.DataFrame()),
            stress_report=frames.get("stress_report", pd.DataFrame()),
            stress_contributions=frames.get("stress_contribution", pd.DataFrame()),
            regime_summary=frames.get("regime_summary", pd.DataFrame()),
            regime_suitability=frames.get("regime_suitability", pd.DataFrame()),
            hedge_recommendations=frames.get("hedges", pd.DataFrame()),
            defensive_substitutions=frames.get("defensive_substitutions", pd.DataFrame()),
            drl_outputs={key: value for key, value in frames.items() if key.startswith("drl_")},
            sources=sources or [],
            quality_flags=quality_flags or [],
            markdown=markdown or {},
            frames=frames,
            source_root=source_root,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class ICReportBundle:
    model_run_id: str
    report_dir: Path
    latest_dir: Path
    html_path: Path
    markdown_path: Path
    manifest_path: Path
    chart_paths: dict[str, Path]
    validation_path: Path
    pdf_path: Path | None = None
    bundle_path: Path | None = None
    report_manifest_path: Path | None = None
    readiness_status: str = "UNKNOWN"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ICReportingResult:
    model_run_id: str
    output_directory: Path
    html_path: Path
    markdown_path: Path
    pdf_path: Path | None
    bundle_path: Path
    manifest_path: Path
    readiness_status: str
    warnings: tuple[str, ...]
