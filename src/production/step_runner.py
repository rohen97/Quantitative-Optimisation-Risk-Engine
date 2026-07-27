from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .models import StepDefinition, StepExecutionResult
from .retry import RetryPolicy, run_with_retry


def _single_attempt(step: StepDefinition, repository_root: Path, log_directory: Path, attempt: int) -> StepExecutionResult:
    started = datetime.now(timezone.utc)
    start_clock = time.perf_counter()
    stdout_path = log_directory / f"{step.order:02d}_{step.name}_attempt{attempt}.out.log"
    stderr_path = log_directory / f"{step.order:02d}_{step.name}_attempt{attempt}.err.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
        try:
            completed_process = subprocess.run(
                list(step.command),
                cwd=repository_root,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                timeout=step.timeout_seconds,
                check=False,
            )
            exit_code = completed_process.returncode
            error_message = None if exit_code == 0 else f"Exit code {exit_code}"
        except subprocess.TimeoutExpired:
            exit_code = 124
            error_message = f"Timed out after {step.timeout_seconds} seconds"
    completed = datetime.now(timezone.utc)
    status = "SUCCEEDED" if exit_code == 0 else "FAILED"
    return StepExecutionResult(
        name=step.name,
        status=status,
        required=step.required,
        attempt_count=attempt,
        started_at=started,
        completed_at=completed,
        duration_seconds=time.perf_counter() - start_clock,
        exit_code=exit_code,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        error_message=error_message,
    )


def run_step(step: StepDefinition, repository_root: Path, log_directory: Path, retry_policy: RetryPolicy) -> StepExecutionResult:
    attempts = {"count": 0}

    def operation() -> StepExecutionResult:
        attempts["count"] += 1
        return _single_attempt(step, repository_root, log_directory, attempts["count"])

    def retryable(result: StepExecutionResult) -> bool:
        return bool(
            step.retryable
            and result.exit_code is not None
            and result.exit_code in retry_policy.retryable_exit_codes
        )

    result, attempt_count = run_with_retry(operation, retryable, retry_policy)
    return StepExecutionResult(
        name=result.name,
        status=result.status,
        required=result.required,
        attempt_count=attempt_count,
        started_at=result.started_at,
        completed_at=result.completed_at,
        duration_seconds=result.duration_seconds,
        exit_code=result.exit_code,
        stdout_path=result.stdout_path,
        stderr_path=result.stderr_path,
        error_message=result.error_message,
    )


def build_step_definitions(mode: str, validation_mode: str, production_config: dict, python_executable: str) -> list[StepDefinition]:
    timeout_minutes = production_config.get("pipeline", {}).get("timeout_minutes", {}).get(mode, 180)
    timeout_seconds = int(timeout_minutes) * 60
    validation_command = (
        python_executable,
        "scripts/run_model_validation.py",
        "--mode",
        validation_mode,
    )
    if mode in {"daily", "weekly"}:
        validation_command = (python_executable, "scripts/run_model_validation.py", "--mode", validation_mode)
    return [
        StepDefinition("full_model_pipeline", 1, True, (python_executable, "scripts/run_full_pipeline.py"), timeout_seconds),
        StepDefinition("configured_validation", 2, True, validation_command, timeout_seconds),
    ]
