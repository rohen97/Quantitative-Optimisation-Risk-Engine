from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ProductionRunContext, StepExecutionResult


class ProductionRunRegistry:
    """File-first run registry with an optional DuckDB migration hook."""

    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        row = {"event_type": event_type, "recorded_at": datetime.now(timezone.utc).isoformat(), **payload}
        with self.registry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str, sort_keys=True) + "\n")

    def register_run(self, context: ProductionRunContext, backend: str) -> None:
        self._append(
            "run_registered",
            {
                "production_run_id": context.production_run_id,
                "schedule_mode": context.mode,
                "validation_mode": context.validation_mode,
                "as_of_date": context.as_of_date.isoformat(),
                "started_at": context.started_at.isoformat(),
                "status": "RUNNING",
                "backend": backend,
                "host_name": context.host_name,
                "process_id": context.process_id,
                "git_commit_hash": context.git_commit_hash,
                "git_is_dirty": context.git_is_dirty,
                "config_hash": context.config_hash,
                "output_directory": str(context.output_directory),
            },
        )

    def record_step(self, production_run_id: str, result: StepExecutionResult) -> None:
        self._append(
            "step_completed",
            {
                "production_run_id": production_run_id,
                "step_name": result.name,
                "status": result.status,
                "required": result.required,
                "attempt_count": result.attempt_count,
                "duration_seconds": result.duration_seconds,
                "exit_code": result.exit_code,
                "stdout_path": str(result.stdout_path),
                "stderr_path": str(result.stderr_path),
                "error_message": result.error_message,
            },
        )

    def complete_run(
        self,
        production_run_id: str,
        status: str,
        approval_status: str,
        exit_code: int | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self._append(
            "run_completed",
            {
                "production_run_id": production_run_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "approval_status": approval_status,
                "exit_code": exit_code,
                "error_type": error_type,
                "error_message": error_message,
            },
        )

    def load_events(self) -> list[dict[str, Any]]:
        if not self.registry_path.exists():
            return []
        return [json.loads(line) for line in self.registry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
