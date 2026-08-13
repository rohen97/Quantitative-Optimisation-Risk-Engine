from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import ctypes
import hashlib
import json
import locale
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Callable, Iterator, Mapping, Sequence
from uuid import uuid4

from src.production.run_lock import ProductionRunLock


LOGGER = logging.getLogger(__name__)
RETRYABLE_EXTERNAL_EXIT = 75
MEMORY_PRESSURE_EXIT = 137
TIMEOUT_EXIT = 124


@dataclass(frozen=True)
class MemoryPolicy:
    minimum_available_gb: float = 2.0
    minimum_available_percent: float = 10.0
    consecutive_low_samples: int = 3
    poll_seconds: float = 2.0


@dataclass(frozen=True)
class MemorySample:
    total_bytes: int
    available_bytes: int

    @property
    def available_percent(self) -> float:
        if self.total_bytes <= 0:
            return 100.0
        return 100.0 * self.available_bytes / self.total_bytes


@dataclass(frozen=True)
class OvernightStep:
    name: str
    command: tuple[str, ...]
    required: bool
    external: bool
    resource_group: str | None
    timeout_seconds: int
    max_attempts: int
    retry_exit_codes: tuple[int, ...]
    retry_delay_seconds: int
    defer_seconds: int
    environment: Mapping[str, str]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> 'OvernightStep':
        timeout_minutes = max(float(payload.get('timeout_minutes', 180)), 0.1)
        return cls(
            name=str(payload['name']),
            command=tuple(str(item) for item in payload['command']),
            required=bool(payload.get('required', True)),
            external=bool(payload.get('external', False)),
            resource_group=(
                str(payload['resource_group'])
                if payload.get('resource_group')
                else None
            ),
            timeout_seconds=int(timeout_minutes * 60),
            max_attempts=max(int(payload.get('max_attempts', 2)), 1),
            retry_exit_codes=tuple(
                int(value) for value in payload.get('retry_exit_codes', [75, 111, 124, 137])
            ),
            retry_delay_seconds=max(int(payload.get('retry_delay_seconds', 30)), 0),
            defer_seconds=max(int(payload.get('defer_minutes', 240)) * 60, 60),
            environment={
                str(key): str(value)
                for key, value in dict(payload.get('environment', {})).items()
            },
        )

    @property
    def signature(self) -> str:
        serialised = json.dumps(
            {
                'command': self.command,
                'environment': dict(self.environment),
                'required': self.required,
                'external': self.external,
                'resource_group': self.resource_group,
            },
            sort_keys=True,
        )
        return hashlib.sha256(serialised.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class StepResult:
    exit_code: int
    started_at: str
    completed_at: str
    duration_seconds: float
    stdout_path: Path
    stderr_path: Path
    minimum_available_gb: float
    minimum_available_percent: float
    detail: str


class OvernightCheckpoint:
    def __init__(self, path: Path, config_hash: str, resume: bool = True) -> None:
        self.path = path
        self.config_hash = config_hash
        self.payload: dict[str, object] = {
            'version': 1,
            'config_hash': config_hash,
            'created_at': _utc_now(),
            'updated_at': _utc_now(),
            'steps': {},
            'resource_cooldowns': {},
        }
        if resume and path.exists():
            try:
                loaded = json.loads(path.read_text(encoding='utf-8-sig'))
                if loaded.get('config_hash') == config_hash:
                    self.payload = loaded
            except (OSError, json.JSONDecodeError):
                LOGGER.warning('Ignoring unreadable overnight checkpoint %s.', path)

    @property
    def steps(self) -> dict[str, dict[str, object]]:
        return self.payload.setdefault('steps', {})  # type: ignore[return-value]

    @property
    def resource_cooldowns(self) -> dict[str, str]:
        return self.payload.setdefault('resource_cooldowns', {})  # type: ignore[return-value]

    def save(self) -> None:
        self.payload['updated_at'] = _utc_now()
        _atomic_json(self.path, self.payload)

    def update_step(self, name: str, **values: object) -> None:
        state = dict(self.steps.get(name, {}))
        state.update(values)
        self.steps[name] = state
        self.save()

    def is_complete(self, step: OvernightStep) -> bool:
        state = self.steps.get(step.name, {})
        return state.get('status') == 'completed' and state.get('signature') == step.signature

    def invalidate_after(self, steps: Sequence[OvernightStep], position: int) -> None:
        for downstream in steps[position + 1 :]:
            state = self.steps.get(downstream.name)
            if state and state.get('status') == 'completed':
                state['status'] = 'pending'
                state['invalidated_by'] = steps[position].name
        self.save()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    temporary.replace(path)


def _config_hash(payload: Mapping[str, object]) -> str:
    serialised = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode('utf-8')).hexdigest()


def _blocked_cooldown_wake_at(
    steps: Sequence[OvernightStep],
    checkpoint: OvernightCheckpoint,
    now: datetime,
) -> datetime | None:
    """Return the next retry when every incomplete step is cooldown-blocked."""
    if not steps:
        return None
    wake_times: list[datetime] = []
    for step in steps:
        if not step.resource_group:
            return None
        raw = checkpoint.resource_cooldowns.get(step.resource_group)
        cooldown = datetime.fromisoformat(raw) if raw else None
        if cooldown is None or cooldown <= now:
            return None
        wake_times.append(cooldown)
    return min(wake_times)


def _wait_for_external_retry(
    wake_at: datetime,
    deadline: datetime,
    heartbeat: Callable[[Mapping[str, object]], None],
) -> None:
    """Sleep without spinning while keeping unattended status observable."""
    while True:
        now = datetime.now(timezone.utc)
        remaining = min(
            max((wake_at - now).total_seconds(), 0),
            max((deadline - now).total_seconds(), 0),
        )
        if remaining <= 0:
            return
        sample = system_memory()
        heartbeat(
            {
                'status': 'waiting_external',
                'retry_at': wake_at.isoformat(),
                'seconds_remaining': round(remaining, 1),
                'available_memory_gb': round(
                    sample.available_bytes / 1024**3, 2
                ),
                'updated_at': _utc_now(),
            }
        )
        time.sleep(min(remaining, 15.0))


def system_memory() -> MemorySample:
    if os.name == 'nt':
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ('length', ctypes.c_ulong),
                ('memory_load', ctypes.c_ulong),
                ('total_physical', ctypes.c_ulonglong),
                ('available_physical', ctypes.c_ulonglong),
                ('total_page_file', ctypes.c_ulonglong),
                ('available_page_file', ctypes.c_ulonglong),
                ('total_virtual', ctypes.c_ulonglong),
                ('available_virtual', ctypes.c_ulonglong),
                ('available_extended_virtual', ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.length = ctypes.sizeof(MemoryStatusEx)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return MemorySample(
                int(status.total_physical),
                int(status.available_physical),
            )
    meminfo = Path('/proc/meminfo')
    if meminfo.exists():
        values = {}
        for line in meminfo.read_text(encoding='utf-8').splitlines():
            name, raw = line.split(':', 1)
            values[name] = int(raw.strip().split()[0]) * 1024
        return MemorySample(values.get('MemTotal', 0), values.get('MemAvailable', 0))
    return MemorySample(0, 0)


@contextmanager
def prevent_system_sleep() -> Iterator[None]:
    if os.name != 'nt':
        yield
        return
    execution_state_continuous = 0x80000000
    execution_state_system_required = 0x00000001
    kernel32 = ctypes.windll.kernel32
    result = kernel32.SetThreadExecutionState(
        execution_state_continuous | execution_state_system_required
    )
    if result == 0:
        LOGGER.warning('Windows rejected the prevent-sleep request.')
    try:
        yield
    finally:
        kernel32.SetThreadExecutionState(execution_state_continuous)


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(
            ['taskkill', '/PID', str(process.pid), '/T', '/F'],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()


def _last_log_line(*paths: Path) -> str:
    for path in paths:
        try:
            raw = path.read_bytes()
            encodings = dict.fromkeys(
                ('utf-8', locale.getpreferredencoding(False), 'cp1252')
            )
            for encoding in encodings:
                try:
                    text = raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                text = raw.decode('utf-8', errors='replace')
            lines = [line.strip() for line in text.splitlines()]
        except OSError:
            continue
        for line in reversed(lines):
            if line:
                return line[-500:]
    return ''


def _resolve_command(command: Sequence[str], repository_root: Path) -> list[str]:
    replacements = {'{python}': sys.executable, '{repo}': str(repository_root)}
    return [replacements.get(token, token.replace('{repo}', str(repository_root))) for token in command]


def run_monitored_step(
    step: OvernightStep,
    repository_root: Path,
    log_directory: Path,
    attempt: int,
    memory_policy: MemoryPolicy,
    base_environment: Mapping[str, str],
    unset_environment: Sequence[str] = (),
    heartbeat: Callable[[Mapping[str, object]], None] | None = None,
) -> StepResult:
    log_directory.mkdir(parents=True, exist_ok=True)
    stdout_path = log_directory / f'{step.name}.attempt{attempt}.out.log'
    stderr_path = log_directory / f'{step.name}.attempt{attempt}.err.log'
    environment = os.environ.copy()
    for name in unset_environment:
        environment.pop(str(name), None)
    environment.update({str(key): str(value) for key, value in base_environment.items()})
    environment.update({str(key): str(value) for key, value in step.environment.items()})
    environment['PYTHONUNBUFFERED'] = '1'
    command = _resolve_command(step.command, repository_root)
    started = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    low_samples = 0
    minimum_available_bytes: int | None = None
    minimum_available_percent = 100.0
    forced_exit: int | None = None
    forced_detail = ''
    creation_flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) if os.name == 'nt' else 0
    with stdout_path.open('w', encoding='utf-8') as stdout_handle, stderr_path.open(
        'w', encoding='utf-8'
    ) as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=repository_root,
            env=environment,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            creationflags=creation_flags,
            start_new_session=os.name != 'nt',
        )
        LOGGER.info('Overnight step %s attempt %s started as PID %s.', step.name, attempt, process.pid)
        last_heartbeat = 0.0
        try:
            while process.poll() is None:
                elapsed = time.perf_counter() - started_clock
                sample = system_memory()
                minimum_available_bytes = (
                    sample.available_bytes
                    if minimum_available_bytes is None
                    else min(minimum_available_bytes, sample.available_bytes)
                )
                minimum_available_percent = min(
                    minimum_available_percent,
                    sample.available_percent,
                )
                below_limit = sample.total_bytes > 0 and (
                    sample.available_bytes < memory_policy.minimum_available_gb * 1024**3
                    or sample.available_percent < memory_policy.minimum_available_percent
                )
                low_samples = low_samples + 1 if below_limit else 0
                if low_samples >= memory_policy.consecutive_low_samples:
                    forced_exit = MEMORY_PRESSURE_EXIT
                    forced_detail = (
                        f'Available memory remained below guardrail: '
                        f'{sample.available_bytes / 1024**3:.2f} GB '
                        f'({sample.available_percent:.1f}%).'
                    )
                    _terminate_process_tree(process)
                    break
                if elapsed >= step.timeout_seconds:
                    forced_exit = TIMEOUT_EXIT
                    forced_detail = f'Timed out after {step.timeout_seconds} seconds.'
                    _terminate_process_tree(process)
                    break
                if heartbeat and elapsed - last_heartbeat >= 15:
                    heartbeat(
                        {
                            'status': 'running',
                            'step': step.name,
                            'attempt': attempt,
                            'pid': process.pid,
                            'elapsed_seconds': round(elapsed, 1),
                            'available_memory_gb': round(sample.available_bytes / 1024**3, 2),
                            'available_memory_percent': round(sample.available_percent, 1),
                            'updated_at': _utc_now(),
                        }
                    )
                    last_heartbeat = elapsed
                time.sleep(memory_policy.poll_seconds)
        except BaseException:
            _terminate_process_tree(process)
            raise
        exit_code = forced_exit if forced_exit is not None else int(process.wait())

    completed = datetime.now(timezone.utc)
    minimum_bytes = minimum_available_bytes or 0
    detail = forced_detail or _last_log_line(stderr_path, stdout_path)
    return StepResult(
        exit_code=exit_code,
        started_at=started.isoformat(),
        completed_at=completed.isoformat(),
        duration_seconds=time.perf_counter() - started_clock,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        minimum_available_gb=minimum_bytes / 1024**3,
        minimum_available_percent=minimum_available_percent,
        detail=detail,
    )


def _step_result_payload(result: StepResult, step: OvernightStep) -> dict[str, object]:
    return {
        'signature': step.signature,
        'exit_code': result.exit_code,
        'started_at': result.started_at,
        'completed_at': result.completed_at,
        'duration_seconds': round(result.duration_seconds, 3),
        'stdout_path': str(result.stdout_path),
        'stderr_path': str(result.stderr_path),
        'minimum_available_gb': round(result.minimum_available_gb, 3),
        'minimum_available_percent': round(result.minimum_available_percent, 2),
        'detail': result.detail,
    }


def _write_report(
    output_directory: Path,
    checkpoint: OvernightCheckpoint,
    steps: Sequence[OvernightStep],
    status: str,
    started_at: datetime,
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    completed_at = datetime.now(timezone.utc)
    rows = []
    for step in steps:
        state = checkpoint.steps.get(step.name, {})
        rows.append(
            {
                'step': step.name,
                'required': step.required,
                'external': step.external,
                'status': state.get('status', 'pending'),
                'attempts': state.get('attempts', 0),
                'exit_code': state.get('exit_code'),
                'duration_seconds': state.get('duration_seconds'),
                'minimum_available_gb': state.get('minimum_available_gb'),
                'detail': state.get('detail', ''),
                'stdout_path': state.get('stdout_path'),
                'stderr_path': state.get('stderr_path'),
            }
        )
    payload = {
        'status': status,
        'started_at': started_at.isoformat(),
        'completed_at': completed_at.isoformat(),
        'duration_seconds': (completed_at - started_at).total_seconds(),
        'config_hash': checkpoint.config_hash,
        'steps': rows,
    }
    json_path = output_directory / 'overnight_execution_report.json'
    markdown_path = output_directory / 'overnight_execution_report.md'
    _atomic_json(json_path, payload)
    lines = [
        '# Overnight Execution Report',
        '',
        f'- Status: **{status}**',
        f'- Started (UTC): `{payload["started_at"]}`',
        f'- Completed (UTC): `{payload["completed_at"]}`',
        f'- Runtime: `{payload["duration_seconds"]:.1f}` seconds',
        '',
        '| Step | Required | External | Status | Attempts | Exit | Seconds | Min free GB |',
        '|---|---:|---:|---|---:|---:|---:|---:|',
    ]
    for row in rows:
        lines.append(
            f'| {row["step"]} | {row["required"]} | {row["external"]} | '
            f'{row["status"]} | {row["attempts"]} | {row["exit_code"]} | '
            f'{row["duration_seconds"]} | {row["minimum_available_gb"]} |'
        )
    lines.extend(['', '## Evidence', ''])
    for row in rows:
        detail = str(row['detail']).replace('\n', ' ').strip() or 'No error detail.'
        lines.append(f'- **{row["step"]}**: {detail}')
    markdown_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return json_path, markdown_path


def run_overnight_plan(
    config: Mapping[str, object],
    repository_root: Path,
    *,
    resume: bool = True,
    max_hours: float | None = None,
) -> int:
    settings = dict(config.get('overnight', config))
    steps = [OvernightStep.from_mapping(item) for item in settings.get('steps', [])]
    if not steps:
        raise ValueError('Overnight plan contains no steps.')
    configured_hours = float(settings.get('max_hours', 12))
    deadline_hours = configured_hours if max_hours is None else max(float(max_hours), 0.01)
    started_at = datetime.now(timezone.utc)
    deadline = started_at + timedelta(hours=deadline_hours)
    run_id = f'overnight-{uuid4().hex[:12]}'
    checkpoint_path = repository_root / str(
        settings.get('checkpoint_path', 'data/locks/overnight_checkpoint.json')
    )
    output_directory = repository_root / str(
        settings.get('output_directory', 'reports/outputs/overnight')
    )
    log_directory = repository_root / str(
        settings.get('log_directory', 'reports/logs/overnight')
    )
    heartbeat_path = output_directory / 'latest_status.json'
    checkpoint = OvernightCheckpoint(checkpoint_path, _config_hash(settings), resume=resume)
    memory_settings = dict(settings.get('memory', {}))
    memory_policy = MemoryPolicy(
        minimum_available_gb=float(memory_settings.get('minimum_available_gb', 2)),
        minimum_available_percent=float(memory_settings.get('minimum_available_percent', 10)),
        consecutive_low_samples=max(int(memory_settings.get('consecutive_low_samples', 3)), 1),
        poll_seconds=max(float(memory_settings.get('poll_seconds', 2)), 0.1),
    )
    base_environment = {
        str(key): str(value)
        for key, value in dict(settings.get('environment', {})).items()
    }
    unset_environment = tuple(
        str(value) for value in settings.get('unset_environment', [])
    )
    lock = ProductionRunLock(
        repository_root / 'data/locks/wolf_overnight.lock',
        run_id,
        stale_after_seconds=int(deadline_hours * 3600 + 3600),
    )
    status = 'running'
    required_failure = False

    def heartbeat(payload: Mapping[str, object]) -> None:
        _atomic_json(heartbeat_path, payload)

    try:
        lock.acquire(force_stale_recovery=True)
        with prevent_system_sleep():
            while datetime.now(timezone.utc) < deadline:
                runnable = False
                deferred = False
                for position, step in enumerate(steps):
                    if checkpoint.is_complete(step):
                        continue
                    state_before = dict(checkpoint.steps.get(step.name, {}))
                    existing_status = state_before.get('status')
                    attempts = int(state_before.get('attempts', 0))
                    if existing_status == 'failed_optional':
                        continue
                    if existing_status == 'deferred' and attempts >= step.max_attempts:
                        failure_status = (
                            'failed' if step.required else 'failed_optional'
                        )
                        checkpoint.update_step(
                            step.name,
                            status=failure_status,
                            attempts=attempts,
                        )
                        checkpoint.invalidate_after(steps, position)
                        if step.required:
                            required_failure = True
                            break
                        continue
                    now = datetime.now(timezone.utc)
                    if step.resource_group:
                        cooldown_raw = checkpoint.resource_cooldowns.get(step.resource_group)
                        cooldown = datetime.fromisoformat(cooldown_raw) if cooldown_raw else None
                        if cooldown and cooldown > now:
                            deferred = True
                            continue
                    cycle_attempts = 0
                    runnable = True
                    result: StepResult | None = None
                    while cycle_attempts < step.max_attempts and datetime.now(timezone.utc) < deadline:
                        attempts += 1
                        cycle_attempts += 1
                        checkpoint.update_step(
                            step.name,
                            status='running',
                            attempts=attempts,
                            signature=step.signature,
                        )
                        result = run_monitored_step(
                            step,
                            repository_root,
                            log_directory,
                            attempts,
                            memory_policy,
                            base_environment,
                            unset_environment,
                            heartbeat,
                        )
                        result_payload = _step_result_payload(result, step)
                        if result.exit_code == 0:
                            checkpoint.update_step(step.name, status='completed', attempts=attempts, **result_payload)
                            if state_before.get('status') == 'deferred':
                                checkpoint.invalidate_after(steps, position)
                            if step.resource_group:
                                checkpoint.resource_cooldowns.pop(step.resource_group, None)
                                checkpoint.save()
                            LOGGER.info('Overnight step %s completed in %.1fs.', step.name, result.duration_seconds)
                            break
                        if step.external and result.exit_code == RETRYABLE_EXTERNAL_EXIT:
                            checkpoint.invalidate_after(steps, position)
                            if attempts >= step.max_attempts:
                                break
                            retry_at = datetime.now(timezone.utc) + timedelta(
                                seconds=step.defer_seconds
                            )
                            checkpoint.update_step(
                                step.name,
                                status='deferred',
                                attempts=attempts,
                                retry_at=retry_at.isoformat(),
                                **result_payload,
                            )
                            if step.resource_group:
                                checkpoint.resource_cooldowns[step.resource_group] = retry_at.isoformat()
                                checkpoint.save()
                            deferred = True
                            break
                        if (
                            result.exit_code not in step.retry_exit_codes
                            or cycle_attempts >= step.max_attempts
                        ):
                            break
                        delay = step.retry_delay_seconds * (2 ** (attempts - 1))
                        time.sleep(min(delay, max((deadline - datetime.now(timezone.utc)).total_seconds(), 0)))

                    if result is not None and result.exit_code != 0:
                        current = checkpoint.steps.get(step.name, {})
                        if current.get('status') != 'deferred':
                            failure_status = 'failed' if step.required else 'failed_optional'
                            checkpoint.update_step(
                                step.name,
                                status=failure_status,
                                attempts=attempts,
                                **_step_result_payload(result, step),
                            )
                            if step.required:
                                required_failure = True
                                break
                if required_failure:
                    break
                incomplete = [
                    step
                    for step in steps
                    if not checkpoint.is_complete(step)
                    and checkpoint.steps.get(step.name, {}).get('status') != 'failed_optional'
                ]
                if not incomplete:
                    break
                if not deferred and not runnable:
                    break
                now = datetime.now(timezone.utc)
                wake_at = (
                    _blocked_cooldown_wake_at(incomplete, checkpoint, now)
                    if deferred and not runnable
                    else None
                )
                if wake_at is not None:
                    remaining = min(
                        max((wake_at - now).total_seconds(), 0),
                        max((deadline - now).total_seconds(), 0),
                    )
                    LOGGER.info(
                        'All remaining work is externally blocked; '
                        'retry in %.0fs.',
                        remaining,
                    )
                    _wait_for_external_retry(wake_at, deadline, heartbeat)
            unresolved_external = any(
                checkpoint.steps.get(step.name, {}).get('status') == 'deferred'
                for step in steps
            )
            optional_failures = any(
                checkpoint.steps.get(step.name, {}).get('status') == 'failed_optional'
                for step in steps
            )
            external_limits = unresolved_external or any(
                step.external
                and checkpoint.steps.get(step.name, {}).get('status')
                == 'failed_optional'
                for step in steps
            )
            status = (
                'failed'
                if required_failure
                else 'completed_with_external_limits'
                if external_limits
                else 'completed_with_warnings'
                if optional_failures
                else 'completed'
            )
    except KeyboardInterrupt:
        status = 'interrupted'
        raise
    except Exception:
        status = 'failed'
        raise
    finally:
        lock.release()
        report_json, report_markdown = _write_report(
            output_directory,
            checkpoint,
            steps,
            status,
            started_at,
        )
        heartbeat(
            {
                'status': status,
                'report_json': str(report_json),
                'report_markdown': str(report_markdown),
                'updated_at': _utc_now(),
            }
        )
    return 1 if required_failure else 0
