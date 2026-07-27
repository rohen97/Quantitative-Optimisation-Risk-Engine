from __future__ import annotations

import sys

from src.production.models import StepDefinition
from src.production.orchestrator import run_production_pipeline


def test_orchestrator_runs_mock_steps(monkeypatch, tmp_path):
    config = {
        "execution": {"stale_lock_minutes": 60, "stop_on_required_step_failure": True},
        "paths": {
            "output_root": str(tmp_path / "outputs"),
            "lock_directory": str(tmp_path / "locks"),
            "log_directory": str(tmp_path / "logs"),
            "database_path": str(tmp_path / "wolf.duckdb"),
            "latest_successful": str(tmp_path / "latest_successful"),
            "latest_approved": str(tmp_path / "latest_approved"),
        },
        "schedules": {"daily": {"validation_mode": "smoke"}},
        "pipeline": {"timeout_minutes": {"daily": 1}, "model_backend": "legacy_csv"},
        "retries": {"enabled": False},
        "health": {"database_connection_required": False, "minimum_free_disk_gb": 0},
        "freshness": {},
        "drift": {"enabled": False},
        "alerts": {"file": {"path": str(tmp_path / "alerts.jsonl")}, "minimum_console_severity": "CRITICAL"},
    }

    def fake_steps(mode, validation_mode, production_config, python_executable):
        return [
            StepDefinition("full_model_pipeline", 1, True, (sys.executable, "-c", "print('model')"), 30),
            StepDefinition("configured_validation", 2, True, (sys.executable, "-c", "print('validation')"), 30),
        ]

    monkeypatch.setattr("src.production.orchestrator.build_step_definitions", fake_steps)
    (tmp_path / "reports" / "outputs" / "ic" / "latest").mkdir(parents=True)
    (tmp_path / "reports" / "outputs" / "ic" / "latest" / "investment_committee_report.html").write_text("ok", encoding="utf-8")
    (tmp_path / "reports" / "outputs" / "validation" / "latest").mkdir(parents=True)
    (tmp_path / "reports" / "outputs" / "validation" / "latest" / "validation_manifest.json").write_text(
        '{"approval_status": "APPROVED", "warnings": [], "critical_failures": []}',
        encoding="utf-8",
    )
    (tmp_path / "reports" / "outputs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / "outputs" / "final_recommendations.csv").write_text("ticker,final_weight\nA,1\n", encoding="utf-8")
    result = run_production_pipeline({"repository_root": str(tmp_path), "production": config}, "daily")
    assert result.status in {"SUCCEEDED", "SUCCEEDED_WITH_WARNINGS"}
    assert (result.output_directory / "production_manifest.json").exists()
