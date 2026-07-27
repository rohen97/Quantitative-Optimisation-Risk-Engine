from __future__ import annotations

from .models import ApprovalGateResult


def evaluate_approval_gate(
    required_steps_passed: bool,
    validation_passed: bool,
    point_in_time_passed: bool,
    constraints_passed: bool,
    final_weights_valid: bool,
    ic_report_exists: bool,
    drl_governance_consistent: bool,
    critical_health_failures: list[str],
    warnings: list[str],
) -> ApprovalGateResult:
    critical_failures: list[str] = []
    if not required_steps_passed:
        critical_failures.append("One or more required production steps failed.")
    if not validation_passed:
        critical_failures.append("Configured model validation did not pass.")
    if not point_in_time_passed:
        critical_failures.append("Point-in-time validation failed.")
    if not constraints_passed:
        critical_failures.append("Hard portfolio constraints failed.")
    if not final_weights_valid:
        critical_failures.append("Final portfolio weights are invalid.")
    if not ic_report_exists:
        critical_failures.append("Investment Committee report is missing.")
    if not drl_governance_consistent:
        critical_failures.append("DRL governance decision is inconsistent with the final selected portfolio.")
    critical_failures.extend(critical_health_failures)
    if critical_failures:
        return ApprovalGateResult(False, "BLOCKED", tuple(critical_failures), tuple(warnings))
    status = "APPROVED_WITH_WARNINGS" if warnings else "APPROVED"
    return ApprovalGateResult(True, status, (), tuple(warnings))
