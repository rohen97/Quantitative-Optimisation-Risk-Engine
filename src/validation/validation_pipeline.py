from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from src.utils.config import ROOT
from src.validation.ablation import build_ablation_report
from src.validation.config import ValidationConfig, load_validation_config
from src.validation.constraint_validation import validate_portfolio_frame
from src.validation.data_loader import load_validation_data
from src.validation.distribution_calibration import quantile_crossing_count
from src.validation.drl_validation import validate_seed_stability
from src.validation.governance import component_approval_table, make_governance_decision
from src.validation.historical_evaluation import (
    HistoricalEvaluation,
    evaluate_historical_evidence,
)
from src.validation.leakage import leakage_report, validate_point_in_time
from src.validation.models import ValidationPipelineResult
from src.validation.regime_validation import validate_regime_probabilities
from src.validation.report_builder import build_validation_reports
from src.validation.scorecard import build_validation_scorecard


LOGGER = logging.getLogger(__name__)

OUTPUT_FILES = (
    "model_validation_scorecard.csv", "data_leakage_report.csv", "point_in_time_validation.csv",
    "data_provenance_validation.csv",
    "forecast_accuracy_report.csv", "forecast_calibration_report.csv", "distribution_coverage_report.csv",
    "binary_probability_calibration.csv", "risk_backtesting_report.csv", "portfolio_strategy_comparison.csv",
    "portfolio_performance_by_period.csv", "regime_performance_report.csv", "regional_performance_report.csv",
    "transaction_cost_validation.csv", "constraint_compliance_report.csv", "drl_governance_validation.csv",
    "drl_seed_stability.csv", "sensitivity_analysis.csv", "ablation_analysis.csv",
    "benchmark_significance_report.csv", "model_component_approval.csv",
)


def _status_frame(component: str, status: str, commentary: str, observations: int = 0) -> pd.DataFrame:
    return pd.DataFrame([{"component": component, "status": status, "observation_count": observations, "commentary": commentary}])


def _copy_latest(run_directory: Path, latest_directory: Path) -> None:
    unique_suffix = uuid4().hex[:8]
    tmp_directory = latest_directory.with_name(f"{latest_directory.name}.tmp-{unique_suffix}")
    old_directory = latest_directory.with_name(f"{latest_directory.name}.old-{unique_suffix}")
    shutil.copytree(run_directory, tmp_directory)
    for attempt in range(3):
        try:
            if latest_directory.exists():
                latest_directory.rename(old_directory)
            tmp_directory.rename(latest_directory)
            if old_directory.exists():
                shutil.rmtree(old_directory, ignore_errors=True)
            return
        except PermissionError as error:
            LOGGER.warning(
                "Could not atomically replace validation latest directory on attempt %s: %s",
                attempt + 1,
                error,
            )
            time.sleep(0.5 * (attempt + 1))
    LOGGER.warning(
        "Validation latest pointer was not updated because Windows denied directory replacement. Immutable run remains at %s.",
        run_directory,
    )
    shutil.rmtree(tmp_directory, ignore_errors=True)


def _input_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        if path.exists() and path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _weight_column(frame: pd.DataFrame) -> str | None:
    for candidate in (
        "final_selected_weight",
        "final_weight",
        "accepted_target_weight",
        "target_weight",
        "projected_drl_weight",
        "weight",
    ):
        if candidate in frame:
            return candidate
    return None


def _register_validation_run(
    validation_run_id: str,
    timestamp: pd.Timestamp,
    mode: str,
    backend: str,
    run_directory: Path,
    config_hash: str,
    input_snapshot_hash: str,
    status: str,
) -> None:
    try:
        from src.data.config import load_data_config
        from src.data.repository.duckdb_repository import DUCKDB_AVAILABLE, DuckDBRepository

        if not DUCKDB_AVAILABLE:
            return
        data_config = load_data_config()
        repository = DuckDBRepository(data_config.duckdb_path, read_only=False)
        repository.execute_migrations(data_config.migrations_path)
        repository.register_model_run(
            {
                "model_run_id": validation_run_id,
                "model_name": "wolf_quant_model_validation",
                "model_version": "1.0",
                "backend": backend,
                "mode": mode,
                "as_of_date": timestamp,
                "started_at": timestamp,
                "completed_at": pd.Timestamp(datetime.now(UTC)).tz_localize(None),
                "status": status.lower(),
                "config_hash": config_hash,
                "input_snapshot_hash": input_snapshot_hash,
                "output_path": str(run_directory),
            }
        )
    except Exception as exc:  # pragma: no cover - filesystem report remains canonical
        LOGGER.warning("Could not register validation run in DuckDB: %s", exc)


def run_validation_pipeline(
    settings: dict[str, Any] | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    model_run_id: str | None = None,
    backend_override: str | None = None,
    strict: bool = False,
    run_sensitivity: bool = True,
    run_ablation: bool = True,
    bootstrap_samples_override: int | None = None,
    output_root: str | Path | None = None,
    execution_mode: str | None = None,
) -> ValidationPipelineResult:
    del settings, strict
    config: ValidationConfig = load_validation_config()
    mode = execution_mode or str(config.raw.get("execution_mode", "smoke"))
    if mode not in {"smoke", "standard", "full", "release_candidate"}:
        raise ValueError(f"Unsupported validation execution mode: {mode}")
    timestamp = pd.Timestamp(as_of_date) if as_of_date is not None else pd.Timestamp(datetime.now(UTC)).tz_localize(None)
    validation_run_id = f"validation-{timestamp.strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
    root = Path(output_root) if output_root else config.output_root
    root = root if root.is_absolute() else ROOT / root
    latest = root / "latest" if output_root else config.latest_directory
    run_directory = root / validation_run_id
    if run_directory.exists():
        raise FileExistsError(f"Validation run already exists: {run_directory}")
    run_directory.mkdir(parents=True)
    package = load_validation_data(validation_run_id, timestamp)
    historical_evaluation: HistoricalEvaluation | None = None
    if package.evidence_manifest and package.evidence_mode != 'current_snapshot':
        historical_evaluation = evaluate_historical_evidence(package, config.raw)

    features = pd.read_csv(ROOT / "reports" / "outputs" / "features_monthly.csv")
    leakage = leakage_report(features)
    point_in_time = validate_point_in_time(features)
    if historical_evaluation is not None:
        chronology_rows = []
        for check_name, failure_count in package.evidence_manifest.get(
            'chronology_checks',
            {},
        ).items():
            failures = int(failure_count)
            chronology_rows.append(
                {
                    'check_name': f'walk_forward_{check_name}',
                    'status': 'PASS' if failures == 0 else 'FAIL',
                    'failures': failures,
                    'commentary': 'Reconstructed walk-forward chronology invariant.',
                }
            )
        point_in_time = pd.concat(
            [point_in_time, pd.DataFrame(chronology_rows)],
            ignore_index=True,
            sort=False,
        )
    india_rows = int(features.get("country", pd.Series(dtype=str)).astype(str).str.contains("India", case=False, na=False).sum())
    leakage = pd.concat([leakage, pd.DataFrame([{"check_name": "india_excluded_from_active_universe", "status": "PASS" if india_rows == 0 else "FAIL", "failure_count": india_rows, "details": "", "critical": True}])], ignore_index=True)

    aligned_observations = 0
    forecast_rows = []
    distribution_rows = []
    for horizon, forecast in package.forecasts.items():
        crossing = quantile_crossing_count(forecast.get("p5_return", pd.Series(dtype=float)), forecast.get("p50_return", pd.Series(dtype=float)), forecast.get("p95_return", pd.Series(dtype=float)))
        forecast_rows.append({"horizon": horizon, "status": "NOT_EVALUATED", "observation_count": 0, "commentary": "No aligned point-in-time realised outcomes for this horizon."})
        distribution_rows.append({"horizon": horizon, "status": "NOT_EVALUATED", "observation_count": 0, "quantile_crossing_count": crossing, "commentary": "Forecast ordering checked; realised coverage unavailable."})
    forecast_accuracy = pd.DataFrame(forecast_rows) if forecast_rows else _status_frame("forecast", "NOT_EVALUATED", "No forecast snapshots available.")
    forecast_calibration = forecast_accuracy.copy()
    distribution = pd.DataFrame(distribution_rows) if distribution_rows else _status_frame("distribution", "NOT_EVALUATED", "No distribution snapshots available.")
    binary = _status_frame("binary_probability_calibration", "NOT_EVALUATED", "No point-in-time realised dividend-cut or drawdown events.")
    risk = _status_frame("risk_backtesting", "NOT_EVALUATED", "No aligned realised portfolio loss series and historical VaR forecasts.")

    benchmark = package.drl_benchmark_results.copy()
    if benchmark.empty:
        benchmark = _status_frame("portfolio_strategy_comparison", "NOT_EVALUATED", "No strategy benchmark output.")
    else:
        benchmark["validation_status"] = "NOT_EVALUATED"
        benchmark["evidence_mode"] = "model_proxy_not_realised_backtest"
    period_performance = _status_frame("portfolio_performance", "NOT_EVALUATED", "Minimum 24 months of realised net returns are unavailable.")
    regional = _status_frame("regional_performance", "NOT_EVALUATED", "No aligned regional realised-return history.")
    transaction = _status_frame("transaction_cost_validation", "NOT_EVALUATED", "Current cost estimates exist, but realised gross alpha history is unavailable.")

    factor_columns = [column for column in ("crisis_probability", "steady_state_probability", "inflation_probability", "walking_on_ice_probability") if column in package.regime_history]
    regime = validate_regime_probabilities(package.regime_history, factor_columns, config.section("regime").get("probability_sum_tolerance", 0.001)) if factor_columns else _status_frame("regime", "NOT_EVALUATED", "Regime probability history unavailable.")

    if historical_evaluation is not None:
        aligned_observations = historical_evaluation.aligned_observations
        forecast_accuracy = historical_evaluation.forecast_accuracy
        forecast_calibration = historical_evaluation.forecast_calibration
        distribution = historical_evaluation.distribution_coverage
        binary = historical_evaluation.binary_calibration
        risk = historical_evaluation.risk_backtesting
        benchmark = historical_evaluation.benchmark_comparison
        period_performance = historical_evaluation.period_performance
        regional = historical_evaluation.regional_performance
        transaction = historical_evaluation.transaction_costs
        if not historical_evaluation.regime_performance.empty:
            regime = historical_evaluation.regime_performance

    constraint_rows = []
    hard_breaches = 0
    for name, report in package.constraint_reports.items():
        if report.empty:
            continue
        raw = report.get("breach_flag", pd.Series(False, index=report.index))
        breach = raw.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
        hard = report.get("constraint_type", pd.Series("", index=report.index)).astype(str).str.lower().eq("hard")
        hard_breaches += int((breach & hard).sum())
        constraint_rows.append(report.assign(portfolio=name))
    for name, portfolio in package.portfolio_weights.items():
        weight_column = _weight_column(portfolio)
        if weight_column:
            maximum = 1.0 if name == "current_portfolio" else 0.05
            checks = validate_portfolio_frame(portfolio, weight_column, maximum)
            checks["portfolio"] = name
            if name in {"selected_classical", "final_portfolio"}:
                hard_breaches += int(checks["status"].eq("FAIL").sum())
            constraint_rows.append(checks)
    constraints = pd.concat(constraint_rows, ignore_index=True, sort=False) if constraint_rows else _status_frame("constraints", "FAIL", "No reproducible portfolio constraint evidence.")

    drl_seed = validate_seed_stability(
        package.drl_seed_results,
        config.section("drl").get("minimum_seeds", 5),
        config.section("drl").get("maximum_seed_sharpe_std", 0.35),
        config.section("drl").get("maximum_seed_return_std", 0.10),
    )
    drl_governance = _status_frame("drl_governance", "FAIL" if drl_seed.iloc[0]["status"] == "FAIL" else "WARNING", "DRL remains a challenger and cannot be promoted without realised out-of-sample comparison.", len(package.drl_seed_results))

    sensitivity = _status_frame("sensitivity", "NOT_EVALUATED", "Sensitivity requires a full historical validation dataset.") if run_sensitivity and mode in {"full", "release_candidate"} else _status_frame("sensitivity", "NOT_EVALUATED", f"Skipped in {mode} mode.")
    existing_ablation = pd.read_csv(ROOT / "reports" / "outputs" / "drl_ablation_results.csv") if (ROOT / "reports" / "outputs" / "drl_ablation_results.csv").exists() else pd.DataFrame()
    ablation = existing_ablation.assign(validation_status="PROXY_ONLY") if run_ablation and mode in {"full", "release_candidate"} and not existing_ablation.empty else build_ablation_report({}, {})
    stability = _status_frame("stability", "NOT_EVALUATED", "Leave-one-period and leave-one-region tests require realised history.")
    significance = _status_frame("benchmark_significance", "NOT_EVALUATED", "Block-bootstrap significance requires aligned realised strategy returns.")

    integrity_errors = [issue for issue in package.issues if issue.severity.lower() == "error"]
    if historical_evaluation is not None:
        sensitivity = historical_evaluation.sensitivity
        stability = historical_evaluation.stability
        significance = historical_evaluation.significance

    data_integrity_status = (
        "PASS"
        if not package.lineage.empty and india_rows == 0 and not integrity_errors
        else "FAIL"
    )
    pit_status = "FAIL" if leakage["status"].eq("FAIL").any() or point_in_time["status"].eq("FAIL").any() else "WARNING"
    statuses = {
        "data_integrity": data_integrity_status,
        "point_in_time": pit_status,
        "forecast_performance": "NOT_EVALUATED",
        "distribution_calibration": "NOT_EVALUATED",
        "risk_backtesting": "NOT_EVALUATED",
        "portfolio_net_of_costs": "NOT_EVALUATED",
        "constraint_compliance": "FAIL" if hard_breaches else "PASS",
        "stability_sensitivity": "NOT_EVALUATED",
    }
    if historical_evaluation is not None:
        statuses.update(historical_evaluation.statuses)
    scorecard = build_validation_scorecard(statuses)
    critical_failures = []
    if package.lineage.empty:
        critical_failures.append("Missing model-run lineage.")
    critical_failures.extend(issue.message for issue in integrity_errors)
    if leakage["status"].eq("FAIL").any():
        critical_failures.append("Look-ahead or target leakage check failed.")
    if point_in_time["status"].eq("FAIL").any():
        critical_failures.append("Point-in-time validation failed.")
    if hard_breaches:
        critical_failures.append(f"{hard_breaches} unresolved hard portfolio constraint breach(es).")
    warnings = [issue.message for issue in package.issues]
    warnings.extend(["Historical forecast calibration, risk backtesting, and net-of-cost strategy validation are not evaluable from the current stored outcomes."])
    insufficient = scorecard.loc[scorecard["status"].eq("NOT_EVALUATED"), "component"].tolist()
    governance = config.section("governance")
    if historical_evaluation is not None:
        warnings = [issue.message for issue in package.issues]
        warnings.append(
            'Validation uses reconstructed point-in-time evidence and remains capped at conditional approval.'
        )
    decision = make_governance_decision(
        dict(zip(scorecard["component"], scorecard["score"])),
        critical_failures,
        warnings,
        governance.get("minimum_overall_score", 70),
        governance.get("conditional_approval_score", 60),
        insufficient,
        maximum_status=package.evidence_manifest.get('release_approval_cap'),
    )
    approvals = component_approval_table(scorecard)

    outputs = {
        "model_validation_scorecard.csv": scorecard,
        "data_provenance_validation.csv": pd.DataFrame(
            [
                {
                    "component": issue.component,
                    "severity": issue.severity,
                    "rule": issue.rule,
                    "message": issue.message,
                    "affected_observations": issue.affected_observations,
                }
                for issue in package.issues
                if issue.component == "data_integrity"
            ]
        ),
        "data_leakage_report.csv": leakage,
        "point_in_time_validation.csv": point_in_time,
        "forecast_accuracy_report.csv": forecast_accuracy,
        "forecast_calibration_report.csv": forecast_calibration,
        "distribution_coverage_report.csv": distribution,
        "binary_probability_calibration.csv": binary,
        "risk_backtesting_report.csv": risk,
        "portfolio_strategy_comparison.csv": benchmark,
        "portfolio_performance_by_period.csv": period_performance,
        "regime_performance_report.csv": regime,
        "regional_performance_report.csv": regional,
        "transaction_cost_validation.csv": transaction,
        "constraint_compliance_report.csv": constraints,
        "drl_governance_validation.csv": drl_governance,
        "drl_seed_stability.csv": drl_seed,
        "sensitivity_analysis.csv": sensitivity,
        "ablation_analysis.csv": ablation,
        "benchmark_significance_report.csv": significance,
        "model_component_approval.csv": approvals,
    }
    for filename, frame in outputs.items():
        frame.to_csv(run_directory / filename, index=False)

    limitations = [
        "Current stored forecasts are predominantly single-date cross-sectional outputs.",
        "Available price history does not provide aligned realised outcomes for the active Wolf securities and all required horizons.",
        "Existing DRL benchmark files are model proxies and are not credited as realised out-of-sample evidence.",
        "Small or unavailable samples are not treated as statistical evidence.",
    ]
    remediation = [
        "Accumulate immutable point-in-time forecast vintages and realised 3M, 6M, 9M and 12M outcomes.",
        "Resolve every hard portfolio constraint breach, including the current liquidity breach.",
        "Run walk-forward risk and strategy validation on at least 24 months of realised net returns.",
        "Re-evaluate DRL only after the selected classical optimiser passes governance.",
    ]
    if historical_evaluation is not None:
        limitations = [
            str(value)
            for value in package.evidence_manifest.get('limitations', [])
        ]
        remediation = [
            'Replace reconstructed filing lags with exchange or regulator filing timestamps.',
            'Add delisted constituents and historical security metadata to remove survivorship bias.',
            'Repair and repopulate historical volume, then remove the static ADV proxy.',
            'Archive immutable sentiment, narrative, and regime vintages for future walk-forward runs.',
            'Continue storing live forecast vintages until native out-of-sample evidence supersedes this proxy.',
        ]
    section_frames = {
        "data_integrity": _status_frame(
            "data_integrity",
            data_integrity_status,
            "Lineage, active-universe, metadata provenance, and final-selection checks.",
        ),
        "leakage": leakage,
        "forecast": forecast_accuracy,
        "distribution": distribution,
        "binary": binary,
        "risk": risk,
        "portfolio": period_performance,
        "costs": transaction,
        "benchmarks": benchmark.head(20),
        "regime": regime,
        "regional": regional,
        "constraints": constraints,
        "drl": drl_governance,
        "sensitivity": sensitivity,
        "ablation": ablation.head(20),
        "stability": stability,
        "statistics": significance,
    }
    markdown_path, html_path = build_validation_reports(
        run_directory, validation_run_id, timestamp, mode, decision.status, decision.score,
        decision.critical_failures, approvals, section_frames, limitations, remediation,
    )
    source_paths = [ROOT / "configs" / "validation.yaml", ROOT / "reports" / "outputs" / "model_run_lineage.csv"]
    if historical_evaluation is not None:
        source_paths.append(
            ROOT
            / 'reports'
            / 'outputs'
            / 'walk_forward'
            / 'walk_forward_manifest.json'
        )
    manifest = {
        "validation_run_id": validation_run_id,
        "source_model_run_id": model_run_id,
        "as_of_date": timestamp.isoformat(),
        "backend": backend_override or "configured",
        "execution_mode": mode,
        "approval_status": decision.status,
        "overall_score": decision.score,
        "critical_failures": decision.critical_failures,
        "warnings": decision.warnings,
        "aligned_realised_observations": aligned_observations,
        "bootstrap_samples": bootstrap_samples_override or config.section("bootstrap").get("samples", 1000),
        "config_hash": _input_hash([source_paths[0]]),
        "input_snapshot_hash": _input_hash(source_paths),
        "generated_files": sorted([*OUTPUT_FILES, markdown_path.name, html_path.name]),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    manifest_path = run_directory / "validation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    if historical_evaluation is not None:
        manifest.update(
            {
                'evidence_mode': package.evidence_mode,
                'evidence_approval_cap': package.evidence_manifest.get(
                    'release_approval_cap'
                ),
                'walk_forward_artifact_version': package.evidence_manifest.get(
                    'artifact_version'
                ),
            }
        )
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str),
            encoding='utf-8',
        )
    if output_root is None:
        _register_validation_run(
            validation_run_id,
            timestamp,
            mode,
            str(manifest["backend"]),
            run_directory,
            str(manifest["config_hash"]),
            str(manifest["input_snapshot_hash"]),
            decision.status,
        )
    _copy_latest(run_directory, latest)
    LOGGER.info("Validation run %s completed with status=%s score=%.1f", validation_run_id, decision.status, decision.score)
    return ValidationPipelineResult(validation_run_id, run_directory, decision.score, decision.status, decision.critical_failures, decision.warnings)
