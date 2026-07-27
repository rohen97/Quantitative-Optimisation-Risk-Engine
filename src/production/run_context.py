from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ProductionRunContext
from .paths import ensure_directory, resolve_repo_path
from .secrets import redact_mapping


def _stable_json_hash(payload: dict[str, Any]) -> str:
    clean_payload = redact_mapping(payload)
    encoded = json.dumps(clean_payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_output(repository_root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repository_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=15,
        )
    except Exception:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def current_git_state(repository_root: Path) -> tuple[str | None, bool]:
    commit = _git_output(repository_root, ["rev-parse", "HEAD"])
    status = _git_output(repository_root, ["status", "--porcelain"])
    return commit, bool(status)


def create_run_context(
    repository_root: Path,
    mode: str,
    validation_mode: str,
    as_of_date: datetime,
    production_settings: dict[str, Any],
) -> ProductionRunContext:
    started_at = datetime.now(timezone.utc)
    if as_of_date.tzinfo is None:
        as_of_date = as_of_date.replace(tzinfo=timezone.utc)
    run_id = f"prod-{mode}-{started_at.strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    paths = production_settings.get("paths", {})
    output_root = ensure_directory(resolve_repo_path(repository_root, paths.get("output_root", "reports/outputs/production")))
    log_root = ensure_directory(resolve_repo_path(repository_root, paths.get("log_directory", "logs/production")))
    output_directory = ensure_directory(output_root / run_id)
    log_directory = ensure_directory(log_root / run_id)
    git_commit_hash, git_is_dirty = current_git_state(repository_root)
    return ProductionRunContext(
        production_run_id=run_id,
        mode=mode,
        validation_mode=validation_mode,
        as_of_date=as_of_date.astimezone(timezone.utc),
        started_at=started_at,
        repository_root=repository_root,
        output_directory=output_directory,
        log_directory=log_directory,
        config_hash=_stable_json_hash(production_settings),
        git_commit_hash=git_commit_hash,
        git_is_dirty=git_is_dirty,
        host_name=socket.gethostname(),
        process_id=os.getpid(),
    )
