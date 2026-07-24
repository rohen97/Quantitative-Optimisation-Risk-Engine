from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class GovernanceDecision:
    score: float
    status: str
    critical_failures: tuple[str, ...]
    warnings: tuple[str, ...]


def make_governance_decision(
    component_scores: dict[str, float],
    critical_failures: list[str],
    warnings: list[str],
    approval_threshold: float = 70.0,
    conditional_threshold: float = 60.0,
    insufficient_components: list[str] | None = None,
) -> GovernanceDecision:
    score = float(sum(value for value in component_scores.values() if pd.notna(value)))
    if critical_failures:
        status = "REJECTED"
    elif insufficient_components:
        status = "INSUFFICIENT_DATA"
    elif score >= approval_threshold:
        status = "APPROVED"
    elif score >= conditional_threshold:
        status = "CONDITIONALLY_APPROVED"
    else:
        status = "REJECTED"
    return GovernanceDecision(score, status, tuple(critical_failures), tuple(warnings))


def component_approval_table(scorecard: pd.DataFrame) -> pd.DataFrame:
    result = scorecard.copy()
    result["approval_status"] = result["status"].map({"PASS": "APPROVED", "WARNING": "CONDITIONALLY_APPROVED", "FAIL": "REJECTED", "NOT_EVALUATED": "INSUFFICIENT_DATA"})
    result["critical_failures"] = ""
    result["warnings"] = ""
    result["approved_version"] = None
    return result
