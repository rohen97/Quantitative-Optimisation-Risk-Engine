from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import HealthCheckResult
from .paths import resolve_repo_path


def _result(name: str, status: str, severity: str, message: str, value: float | None = None, threshold: float | None = None) -> HealthCheckResult:
    return HealthCheckResult(name, status, severity, message, metric_value=value, threshold_value=threshold)


def run_health_checks(repository_root: Path, production_config: dict, mode: str = "daily") -> list[HealthCheckResult]:
    config = production_config.get("health", {})
    paths = production_config.get("paths", {})
    checks: list[HealthCheckResult] = []
    minimum_free_gb = float(config.get("minimum_free_disk_gb", 10))
    usage = shutil.disk_usage(repository_root)
    free_gb = usage.free / (1024**3)
    checks.append(
        _result(
            "disk_free_space",
            "PASS" if free_gb >= minimum_free_gb else "FAIL",
            "INFO" if free_gb >= minimum_free_gb else "CRITICAL",
            f"Free disk space is {free_gb:.2f} GB.",
            free_gb,
            minimum_free_gb,
        )
    )
    write_probe = repository_root / ".production_write_probe"
    try:
        write_probe.write_text("ok", encoding="utf-8")
        write_probe.unlink()
        checks.append(_result("repository_write", "PASS", "INFO", "Repository write check passed."))
    except Exception as exc:
        checks.append(_result("repository_write", "FAIL", "CRITICAL", f"Repository write check failed: {type(exc).__name__}"))
    database_path = resolve_repo_path(repository_root, paths.get("database_path", "data/database/wolf.duckdb"))
    if config.get("database_connection_required", True):
        try:
            import duckdb  # type: ignore

            database_path.parent.mkdir(parents=True, exist_ok=True)
            connection = duckdb.connect(str(database_path))
            connection.execute("SELECT 1")
            connection.close()
            checks.append(_result("database_connection", "PASS", "INFO", "DuckDB connection check passed."))
        except Exception as exc:
            checks.append(_result("database_connection", "FAIL", "CRITICAL", f"DuckDB connection check failed: {type(exc).__name__}"))
    maximum_database_size_gb = float(config.get("maximum_database_size_gb", 50))
    if database_path.exists():
        size_gb = database_path.stat().st_size / (1024**3)
        checks.append(
            _result(
                "database_size",
                "PASS" if size_gb <= maximum_database_size_gb else "FAIL",
                "INFO" if size_gb <= maximum_database_size_gb else "WARNING",
                f"Database size is {size_gb:.3f} GB.",
                size_gb,
                maximum_database_size_gb,
            )
        )
    if config.get("git_required", False) or mode == "release_candidate":
        result = subprocess.run(["git", "--version"], cwd=repository_root, capture_output=True, text=True, check=False)
        checks.append(_result("git_available", "PASS" if result.returncode == 0 else "FAIL", "INFO" if result.returncode == 0 else "CRITICAL", "Git availability checked."))
    return checks
