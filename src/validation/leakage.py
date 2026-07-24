from __future__ import annotations

import pandas as pd

from src.validation.models import ValidationIssue

TARGET_PATTERNS = ("forward_", "future_", "target_", "realised_", "realized_")


def check_availability_dates(
    data: pd.DataFrame,
    decision_column: str,
    availability_column: str,
    component: str,
) -> list[ValidationIssue]:
    if data.empty:
        return [ValidationIssue(component, "warning", "missing_data", "No data available for leakage check.")]
    if decision_column not in data or availability_column not in data:
        return [ValidationIssue(component, "warning", "missing_columns", f"Missing {decision_column} or {availability_column}.")]
    decision = pd.to_datetime(data[decision_column], errors="coerce", utc=True)
    available = pd.to_datetime(data[availability_column], errors="coerce", utc=True)
    invalid = available.isna() | decision.isna() | (available > decision)
    count = int(invalid.sum())
    if count == 0:
        return []
    return [ValidationIssue(component, "critical", "future_information", f"{count} observations became available after the model decision timestamp.", count)]


def check_split_overlap(splits: pd.DataFrame) -> list[ValidationIssue]:
    if splits.empty:
        return [ValidationIssue("chronology", "warning", "missing_splits", "No chronological split metadata was available.")]
    issues: list[ValidationIssue] = []
    for _, row in splits.iterrows():
        if pd.Timestamp(row["train_end"]) >= pd.Timestamp(row["validation_start"]):
            issues.append(ValidationIssue("chronology", "critical", "training_validation_overlap", "Training and validation periods overlap.", 1))
        if pd.Timestamp(row["validation_end"]) >= pd.Timestamp(row["test_start"]):
            issues.append(ValidationIssue("chronology", "critical", "validation_test_overlap", "Validation and test periods overlap.", 1))
    return issues


def detect_target_columns(columns: list[str] | pd.Index) -> list[str]:
    return sorted(column for column in map(str, columns) if column.lower().startswith(TARGET_PATTERNS))


def validate_point_in_time(data: pd.DataFrame, decision_date_column: str = "as_of_date") -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if decision_date_column not in data:
        return pd.DataFrame([{"check_name": "decision_date_present", "status": "FAIL", "failures": len(data), "commentary": f"Missing {decision_date_column}."}])
    decision_dates = pd.to_datetime(data[decision_date_column], errors="coerce")
    rows.append({"check_name": "decision_date_parseable", "status": "PASS" if decision_dates.notna().all() else "FAIL", "failures": int(decision_dates.isna().sum()), "commentary": ""})
    for column in ("available_from", "retrieved_at", "filing_date", "published_at"):
        if column not in data:
            continue
        availability = pd.to_datetime(data[column], errors="coerce")
        failures = int((availability > decision_dates).fillna(False).sum())
        rows.append({"check_name": f"{column}_not_after_decision", "status": "PASS" if failures == 0 else "FAIL", "failures": failures, "commentary": "Availability must not be later than the historical decision date."})
    return pd.DataFrame(rows)


def leakage_report(features: pd.DataFrame, splits: pd.DataFrame | None = None) -> pd.DataFrame:
    targets = detect_target_columns(features.columns)
    rows = [{
        "check_name": "future_target_columns_absent",
        "status": "PASS" if not targets else "FAIL",
        "failure_count": len(targets),
        "details": ", ".join(targets),
        "critical": True,
    }]
    if splits is not None and not splits.empty:
        random_split = bool(splits.get("random_split_used", pd.Series(False)).fillna(False).astype(bool).any())
        rows.append({"check_name": "random_time_split_absent", "status": "FAIL" if random_split else "PASS", "failure_count": int(random_split), "details": "", "critical": True})
    return pd.DataFrame(rows)
