from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.production.overnight import (
    MemoryPolicy,
    _blocked_cooldown_wake_at,
    _config_hash,
    _last_log_line,
    OvernightCheckpoint,
    OvernightStep,
    run_monitored_step,
    run_overnight_plan,
)


def _step(name: str = 'probe') -> OvernightStep:
    return OvernightStep.from_mapping(
        {
            'name': name,
            'command': ['{python}', '-c', 'print("ok")'],
            'timeout_minutes': 1,
            'max_attempts': 1,
        }
    )


def test_checkpoint_resumes_matching_steps_and_invalidates_downstream(tmp_path: Path):
    first = _step('first')
    second = _step('second')
    path = tmp_path / 'checkpoint.json'
    checkpoint = OvernightCheckpoint(path, 'config', resume=True)
    checkpoint.update_step('first', status='completed', signature=first.signature)
    checkpoint.update_step('second', status='completed', signature=second.signature)

    resumed = OvernightCheckpoint(path, 'config', resume=True)
    assert resumed.is_complete(first)
    resumed.invalidate_after([first, second], 0)
    assert resumed.steps['second']['status'] == 'pending'


def test_monitored_step_applies_environment_bounds(tmp_path: Path, monkeypatch):
    monkeypatch.setenv('REMOVE_FROM_CHILD', 'secret')
    step = OvernightStep.from_mapping(
        {
            'name': 'environment_probe',
            'command': [
                '{python}',
                '-c',
                'import os; print(os.getenv("BOUND")); print(os.getenv("REMOVE_FROM_CHILD", "missing"))',
            ],
            'timeout_minutes': 1,
            'max_attempts': 1,
        }
    )
    result = run_monitored_step(
        step,
        tmp_path,
        tmp_path / 'logs',
        1,
        MemoryPolicy(poll_seconds=0.05),
        {'BOUND': '1'},
        ['REMOVE_FROM_CHILD'],
    )
    assert result.exit_code == 0
    assert result.stdout_path.read_text(encoding='utf-8').splitlines() == ['1', 'missing']


def test_overnight_plan_writes_report_and_skips_completed_step(tmp_path: Path):
    config = {
        'overnight': {
            'max_hours': 0.01,
            'disabled_resource_groups': ['bloomberg'],
            'checkpoint_path': 'data/locks/test_checkpoint.json',
            'output_directory': 'reports/outputs/overnight',
            'log_directory': 'reports/logs/overnight',
            'memory': {'poll_seconds': 0.05},
            'steps': [
                {
                    'name': 'probe',
                    'command': ['{python}', '-c', 'print("complete")'],
                    'timeout_minutes': 1,
                    'max_attempts': 1,
                }
            ],
        }
    }
    assert run_overnight_plan(config, tmp_path) == 0
    checkpoint_path = tmp_path / 'data/locks/test_checkpoint.json'
    first = json.loads(checkpoint_path.read_text(encoding='utf-8'))
    assert first['steps']['probe']['attempts'] == 1

    assert run_overnight_plan(config, tmp_path) == 0
    second = json.loads(checkpoint_path.read_text(encoding='utf-8'))
    assert second['steps']['probe']['attempts'] == 1
    report_root = tmp_path / 'reports/outputs/overnight'
    report = json.loads(
        (report_root / 'overnight_execution_report.json').read_text(
            encoding='utf-8'
        )
    )
    markdown = (report_root / 'overnight_execution_report.md').read_text(
        encoding='utf-8'
    )
    assert report['disabled_resource_groups'] == ['bloomberg']
    assert 'Disabled resource groups: `bloomberg`' in markdown


def test_pending_steps_can_share_one_external_cooldown(tmp_path: Path):
    priority = OvernightStep.from_mapping(
        {
            'name': 'priority',
            'command': ['{python}', '-c', 'raise SystemExit(75)'],
            'external': True,
            'resource_group': 'bloomberg',
        }
    )
    full = OvernightStep.from_mapping(
        {
            'name': 'full',
            'command': ['{python}', '-c', 'raise SystemExit(75)'],
            'external': True,
            'resource_group': 'bloomberg',
        }
    )
    checkpoint = OvernightCheckpoint(
        tmp_path / 'checkpoint.json', 'config', resume=False
    )
    now = datetime.now(timezone.utc)
    retry_at = now + timedelta(hours=1)
    checkpoint.resource_cooldowns['bloomberg'] = retry_at.isoformat()
    checkpoint.update_step('priority', status='deferred')

    assert _blocked_cooldown_wake_at(
        [priority, full], checkpoint, now
    ) == retry_at
    assert _blocked_cooldown_wake_at(
        [full, _step('local')], checkpoint, now
    ) is None


def test_last_log_line_accepts_windows_console_encoding(tmp_path: Path):
    path = tmp_path / 'pytest.log'
    path.write_bytes(b'Expected: 0.25 \xb1 2.5e-07\n')

    assert _last_log_line(path) == 'Expected: 0.25 \u00b1 2.5e-07'


def test_external_partial_exit_invalidates_downstream(tmp_path: Path):
    settings = {
        'max_hours': 0.05,
        'checkpoint_path': 'data/locks/test_checkpoint.json',
        'output_directory': 'reports/outputs/overnight',
        'log_directory': 'reports/logs/overnight',
        'memory': {'poll_seconds': 0.05},
        'steps': [
            {
                'name': 'external',
                'command': ['{python}', '-c', 'raise SystemExit(75)'],
                'external': True,
                'required': False,
                'resource_group': 'vendor',
                'max_attempts': 1,
            },
            {
                'name': 'downstream',
                'command': ['{python}', '-c', 'print("fresh")'],
                'max_attempts': 1,
            },
        ],
    }
    steps = [
        OvernightStep.from_mapping(payload) for payload in settings['steps']
    ]
    checkpoint = OvernightCheckpoint(
        tmp_path / settings['checkpoint_path'],
        _config_hash(settings),
        resume=False,
    )
    checkpoint.update_step(
        'downstream',
        status='completed',
        attempts=1,
        signature=steps[1].signature,
    )

    assert run_overnight_plan({'overnight': settings}, tmp_path) == 0
    resumed = OvernightCheckpoint(
        tmp_path / settings['checkpoint_path'],
        _config_hash(settings),
    )
    assert resumed.steps['external']['status'] == 'failed_optional'
    assert resumed.steps['downstream']['status'] == 'completed'
    assert resumed.steps['downstream']['attempts'] == 2
    assert resumed.steps['downstream']['invalidated_by'] == 'external'
    status = json.loads(
        (tmp_path / 'reports/outputs/overnight/latest_status.json').read_text(
            encoding='utf-8'
        )
    )
    assert status['status'] == 'completed_with_external_limits'
