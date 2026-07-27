from __future__ import annotations

import sys

from src.production.models import StepDefinition
from src.production.retry import RetryPolicy
from src.production.step_runner import run_step


def test_step_runner_executes_successful_command(tmp_path):
    step = StepDefinition("ok", 1, True, (sys.executable, "-c", "print('ok')"), 30)
    result = run_step(step, tmp_path, tmp_path / "logs", RetryPolicy(enabled=False))
    assert result.status == "SUCCEEDED"
    assert result.exit_code == 0
    assert result.stdout_path.exists()
