from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import HealthCheckResult


FRESHNESS_TARGETS = {
    "current_portfolio": ("current_portfolio_enriched.csv", "current_portfolio_max_age_hours", "hours"),
    "regime_output": ("regime_features.csv", "regime_output_max_age_hours", "hours"),
    "forecast_output": ("return_distribution_forecasts.csv", "forecast_output_max_age_days", "days"),
    "risk_output": ("portfolio_risk_report.csv", "risk_output_max_age_days", "days"),
    "ic_report": ("ic/latest/investment_committee_report.html", "ic_report_max_age_hours", "hours"),
}


def _age_hours(path: Path, now: datetime) -> float:
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (now - modified).total_seconds() / 3600.0


def run_freshness_checks(repository_root: Path, production_config: dict, now: datetime | None = None) -> list[HealthCheckResult]:
    now = now or datetime.now(timezone.utc)
    output_root = repository_root / "reports" / "outputs"
    freshness_config = production_config.get("freshness", {})
    results: list[HealthCheckResult] = []
    for name, (relative_path, threshold_key, units) in FRESHNESS_TARGETS.items():
        path = output_root / relative_path
        threshold = float(freshness_config.get(threshold_key, 36))
        threshold_hours = threshold * 24.0 if units == "days" else threshold
        if not path.exists():
            results.append(HealthCheckResult(f"freshness_{name}", "FAIL", "WARNING", f"{relative_path} is missing.", None, None, threshold_hours))
            continue
        age_hours = _age_hours(path, now)
        status = "PASS" if age_hours <= threshold_hours else "FAIL"
        severity = "INFO" if status == "PASS" else "WARNING"
        results.append(
            HealthCheckResult(
                f"freshness_{name}",
                status,
                severity,
                f"{relative_path} age is {age_hours:.2f} hours.",
                age_hours,
                "hours",
                threshold_hours,
            )
        )
    return results
