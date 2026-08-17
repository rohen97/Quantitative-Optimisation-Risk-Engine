from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sys
from pathlib import Path
from uuid import uuid4

import pandas as pd

from .alerts.console import ConsoleAlertSink
from .alerts.router import AlertRouter
from .approval_gate import evaluate_approval_gate
from .config import load_production_config, repository_root_from_settings, resolve_schedule_mode, resolve_validation_mode
from .drift import run_drift_checks
from .freshness import run_freshness_checks
from .health import run_health_checks
from .incidents import IncidentStore
from .manifest import write_manifest
from .models import ProductionAlert, ProductionRunResult
from .paths import atomic_copy_directory, ensure_directory, resolve_repo_path
from .retry import RetryPolicy
from .run_context import create_run_context
from .run_lock import ProductionRunAlreadyActive, ProductionRunLock
from .run_registry import ProductionRunRegistry
from .shadow_operation import run_shadow_operation_from_outputs
from .status_report import write_global_status, write_run_status_reports
from .step_runner import build_step_definitions, run_step


LOGGER = logging.getLogger(__name__)


def _alert(run_id: str | None, severity: str, component: str, alert_type: str, title: str, message: str) -> ProductionAlert:
    fingerprint = f"{component}:{alert_type}:{title}".lower().replace(" ", "_")
    return ProductionAlert(f"alert-{uuid4().hex[:12]}", run_id, datetime.now(timezone.utc), severity, component, alert_type, title, message, fingerprint)


def _critical_health_failures(health_checks) -> list[str]:
    return [check.message for check in health_checks if check.status == "FAIL" and check.severity == "CRITICAL"]


def _warnings(health_checks, drift_checks) -> list[str]:
    warnings = [check.message for check in health_checks if check.severity == "WARNING" or check.status in {"WARNING", "NOT_EVALUATED"}]
    warnings.extend(check.notes or f"{check.drift_type}.{check.metric_name}={check.status}" for check in drift_checks if check.status in {"WARNING", "NOT_EVALUATED"})
    return warnings


def _latest_validation_status(repository_root: Path) -> tuple[str | None, list[str]]:
    manifest = repository_root / "reports" / "outputs" / "validation" / "latest" / "validation_manifest.json"
    if not manifest.exists():
        return None, ["Validation manifest is missing."]
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as error:
        return None, [f"Validation manifest could not be read: {type(error).__name__}"]
    warnings = [str(item) for item in payload.get("warnings", [])]
    warnings.extend(str(item) for item in payload.get("critical_failures", []))
    return payload.get("approval_status"), warnings


def run_production_pipeline(
    settings,
    mode: str = "daily",
    as_of_date: datetime | None = None,
    backend_override: str | None = None,
    force_stale_lock_recovery: bool = True,
) -> ProductionRunResult:
    repository_root = repository_root_from_settings(settings)
    production_config = load_production_config(settings)
    mode = resolve_schedule_mode(mode, production_config)
    validation_mode = resolve_validation_mode(mode, production_config)
    context = create_run_context(
        repository_root=repository_root,
        mode=mode,
        validation_mode=validation_mode,
        as_of_date=as_of_date or datetime.now(timezone.utc),
        production_settings=production_config,
    )
    paths = production_config.get("paths", {})
    output_root = ensure_directory(resolve_repo_path(repository_root, paths.get("output_root", "reports/outputs/production")))
    lock_path = resolve_repo_path(repository_root, paths.get("lock_directory", "data/locks")) / "wolf_production.lock"
    run_lock = ProductionRunLock(lock_path, context.production_run_id, int(production_config.get("execution", {}).get("stale_lock_minutes", 360)) * 60)
    registry = ProductionRunRegistry(context.output_directory / "production_registry.jsonl")
    alert_log_path = resolve_repo_path(repository_root, production_config.get("alerts", {}).get("file", {}).get("path", "reports/outputs/production/alerts.jsonl"))
    incident_store = IncidentStore(output_root / "incidents.json")
    router = AlertRouter(
        alert_log_path=alert_log_path,
        sinks=[(ConsoleAlertSink(), production_config.get("alerts", {}).get("minimum_console_severity", "INFO"))],
        deduplication_window_minutes=int(production_config.get("alerts", {}).get("deduplication_window_minutes", 120)),
        incident_store=incident_store,
    )
    step_results = []
    health_checks = []
    drift_checks = []
    alerts: list[ProductionAlert] = []
    critical_failures: list[str] = []
    warnings: list[str] = []
    final_status = "FAILED"
    approval_status = "BLOCKED"
    pointer_updates: dict[str, str | bool | None] = {}
    try:
        run_lock.acquire(force_stale_recovery=force_stale_lock_recovery)
        backend = backend_override or production_config.get("pipeline", {}).get("model_backend", "duckdb")
        registry.register_run(context, backend)
        health_checks.extend(run_health_checks(repository_root, production_config, mode=mode))
        critical_failures.extend(_critical_health_failures(health_checks))
        if critical_failures:
            final_status = "BLOCKED"
        else:
            retry_policy = RetryPolicy.from_config(production_config.get("retries", {}))
            non_retryable = set(production_config.get("retries", {}).get("non_retryable_steps", []))
            steps = build_step_definitions(mode, validation_mode, production_config, sys.executable)
            for step in steps:
                step = type(step)(
                    step.name,
                    step.order,
                    step.required,
                    step.command,
                    step.timeout_seconds,
                    step.retryable and step.name not in non_retryable,
                )
                result = run_step(step, repository_root, context.log_directory, retry_policy)
                step_results.append(result)
                registry.record_step(context.production_run_id, result)
                if result.required and result.status != "SUCCEEDED" and production_config.get("execution", {}).get("stop_on_required_step_failure", True):
                    critical_failures.append(f"Required step failed: {result.name}")
                    break
            health_checks.extend(run_freshness_checks(repository_root, production_config))
            drift_checks.extend(run_drift_checks(repository_root, production_config))
            required_steps_passed = all(result.status == "SUCCEEDED" for result in step_results if result.required) and len(step_results) >= 2
            validation_exit_passed = any(result.name == "configured_validation" and result.status == "SUCCEEDED" for result in step_results)
            validation_status, validation_warnings = _latest_validation_status(repository_root)
            validation_passed = validation_exit_passed and validation_status in {"APPROVED", "APPROVED_WITH_WARNINGS", "CONDITIONALLY_APPROVED"}
            ic_report_exists = (repository_root / "reports" / "outputs" / "ic" / "latest" / "investment_committee_report.html").exists()
            warnings.extend(_warnings(health_checks, drift_checks))
            warnings.extend(validation_warnings)
            gate = evaluate_approval_gate(
                required_steps_passed=required_steps_passed,
                validation_passed=validation_passed,
                point_in_time_passed=True,
                constraints_passed=True,
                final_weights_valid=(repository_root / "reports" / "outputs" / "final_recommendations.csv").exists(),
                ic_report_exists=ic_report_exists,
                drl_governance_consistent=True,
                critical_health_failures=_critical_health_failures(health_checks),
                warnings=warnings,
            )
            approval_status = gate.status
            critical_failures.extend(gate.critical_failures)
            final_status = "SUCCEEDED_WITH_WARNINGS" if gate.approved and gate.warnings else ("SUCCEEDED" if gate.approved else "BLOCKED")
            shadow_config = production_config.get("shadow_operation", {}) or {}
            shadow_enabled = bool(shadow_config.get("enabled", False))
            shadow_schedule_allowed = (
                not bool(shadow_config.get("monthly_only", True))
                or mode in {"monthly", "release_candidate"}
            )
            if shadow_enabled and shadow_schedule_allowed and required_steps_passed:
                try:
                    cycle_id = run_shadow_operation_from_outputs(
                        repository_root=repository_root,
                        as_of_date=pd.Timestamp(context.as_of_date),
                        production_run_id=context.production_run_id,
                        governance_status=approval_status,
                        maximum_recording_lag_days=int(
                            shadow_config.get("maximum_recording_lag_days", 7)
                        ),
                        required_cycles=int(
                            shadow_config.get("required_prospective_cycles", 3)
                        ),
                        prospective_start_date=shadow_config.get(
                            "prospective_start_date"
                        ),
                    )
                    LOGGER.info("Monthly shadow cycle recorded: %s", cycle_id)
                except Exception as error:
                    LOGGER.exception("Monthly shadow-cycle recording failed.")
                    warnings.append(
                        f"Shadow-cycle recording failed: {type(error).__name__}"
                    )
                    if final_status == "SUCCEEDED":
                        final_status = "SUCCEEDED_WITH_WARNINGS"
    except ProductionRunAlreadyActive as error:
        final_status = "BLOCKED"
        approval_status = "BLOCKED"
        critical_failures.append(str(error))
    except Exception as error:
        LOGGER.exception("Production pipeline failed.")
        final_status = "FAILED"
        approval_status = "BLOCKED"
        critical_failures.append(f"{type(error).__name__}: {error}")
    finally:
        run_lock.release()

    completed_at = datetime.now(timezone.utc)
    if critical_failures:
        alert = _alert(context.production_run_id, "CRITICAL", "production_orchestrator", "run_blocked", "Production run blocked", critical_failures[0])
        alerts.append(alert)
        router.route(alert)
    result = ProductionRunResult(
        production_run_id=context.production_run_id,
        mode=mode,
        status=final_status,
        approval_status=approval_status,
        output_directory=context.output_directory,
        started_at=context.started_at,
        completed_at=completed_at,
        step_results=step_results,
        health_checks=health_checks,
        drift_checks=drift_checks,
        alerts=alerts,
        critical_failures=tuple(critical_failures),
        warnings=tuple(warnings),
    )
    write_run_status_reports(result)
    manifest_path = write_manifest(context, result, pointer_updates)
    latest_successful = None
    latest_approved = None
    try:
        if final_status in {"SUCCEEDED", "SUCCEEDED_WITH_WARNINGS"} and production_config.get("execution", {}).get("update_latest_successful", True):
            atomic_copy_directory(context.output_directory, resolve_repo_path(repository_root, paths.get("latest_successful", "reports/outputs/production/latest_successful")))
            latest_successful = context.production_run_id
            pointer_updates["latest_successful"] = True
        if approval_status in {"APPROVED", "APPROVED_WITH_WARNINGS"} and production_config.get("execution", {}).get("update_latest_approved_only_on_pass", True):
            atomic_copy_directory(context.output_directory, resolve_repo_path(repository_root, paths.get("latest_approved", "reports/outputs/production/latest_approved")))
            latest_approved = context.production_run_id
            pointer_updates["latest_approved"] = True
    except Exception as error:
        warnings.append(f"Latest pointer update failed: {type(error).__name__}")
        pointer_updates["error"] = type(error).__name__
        write_manifest(context, result, pointer_updates)
    write_global_status(output_root, result, latest_successful, latest_approved)
    registry.complete_run(context.production_run_id, final_status, approval_status, error_message="; ".join(critical_failures) if critical_failures else None)
    if manifest_path.exists():
        LOGGER.info("Production manifest written to %s", manifest_path)
    return result
