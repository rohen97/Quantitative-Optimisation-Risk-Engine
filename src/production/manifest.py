from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import ProductionRunContext, ProductionRunResult


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_outputs(output_directory: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(output_directory.rglob("*")):
        if path.is_file() and path.name != "production_manifest.json":
            hashes[str(path.relative_to(output_directory))] = sha256_file(path)
    return hashes


def build_manifest(context: ProductionRunContext, result: ProductionRunResult, pointer_updates: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "production_run_id": context.production_run_id,
        "run_mode": context.mode,
        "validation_mode": context.validation_mode,
        "started_at_utc": context.started_at.isoformat(),
        "completed_at_utc": result.completed_at.isoformat(),
        "as_of_date_utc": context.as_of_date.isoformat(),
        "git_commit": context.git_commit_hash,
        "git_is_dirty": context.git_is_dirty,
        "configuration_hash": context.config_hash,
        "input_snapshot_hash": None,
        "model_run_id": None,
        "validation_run_id": None,
        "ic_report_run_id": None,
        "source_manifests": [],
        "step_log_hashes": {
            step.name: {
                "stdout": sha256_file(step.stdout_path) if step.stdout_path.exists() else None,
                "stderr": sha256_file(step.stderr_path) if step.stderr_path.exists() else None,
            }
            for step in result.step_results
        },
        "output_hashes": hash_outputs(context.output_directory),
        "approval_status": result.approval_status,
        "run_status": result.status,
        "alerts": [alert.__dict__ for alert in result.alerts],
        "incidents": [],
        "latest_pointer_update_result": pointer_updates or {},
    }


def write_manifest(context: ProductionRunContext, result: ProductionRunResult, pointer_updates: dict[str, Any] | None = None) -> Path:
    path = context.output_directory / "production_manifest.json"
    path.write_text(json.dumps(build_manifest(context, result, pointer_updates), indent=2, default=str, sort_keys=True), encoding="utf-8")
    return path
