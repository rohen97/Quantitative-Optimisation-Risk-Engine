from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import subprocess


@dataclass(frozen=True)
class ModelRunMetadata:
    model_run_id: str
    model_name: str
    model_version: str
    git_commit_hash: str | None
    git_is_dirty: bool
    backend: str
    mode: str
    as_of_date: str
    started_at: str
    config_hash: str
    input_snapshot_hash: str | None
    random_seed: int | None
    status: str = "running"
    completed_at: str | None = None
    train_start: str | None = None
    train_end: str | None = None
    validation_start: str | None = None
    validation_end: str | None = None
    test_start: str | None = None
    test_end: str | None = None
    output_path: str | None = None
    error_message: str | None = None
    runtime_seconds: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


ModelRunLineage = ModelRunMetadata


def calculate_json_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_git_metadata(repository_root: Path) -> tuple[str | None, bool]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repository_root, text=True)
        return commit, bool(status.strip())
    except Exception:
        return None, False


def new_model_run_metadata(
    model_name: str,
    model_version: str,
    backend: str,
    mode: str,
    config: dict[str, object] | None = None,
    input_snapshot_hash: str | None = None,
    random_seed: int | None = None,
    repository_root: str | Path = ".",
) -> ModelRunMetadata:
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    commit, dirty = get_git_metadata(Path(repository_root))
    return ModelRunMetadata(
        model_run_id=str(uuid4()),
        model_name=model_name,
        model_version=model_version,
        git_commit_hash=commit,
        git_is_dirty=dirty,
        backend=backend,
        mode=mode,
        as_of_date=now,
        started_at=now,
        config_hash=calculate_json_hash(config or {}),
        input_snapshot_hash=input_snapshot_hash,
        random_seed=random_seed,
    )


def new_model_run_lineage(
    backend_mode: str,
    code_version: str = "local",
    config_hash: str = "",
    input_snapshot_id: str = "",
    notes: str = "",
) -> ModelRunLineage:
    now = datetime.now(UTC).replace(tzinfo=None).isoformat()
    commit, dirty = get_git_metadata(Path("."))
    return ModelRunLineage(
        model_run_id=str(uuid4()),
        model_name=notes or "wolf_quant_model",
        model_version=code_version,
        git_commit_hash=commit or code_version,
        git_is_dirty=dirty,
        backend=backend_mode,
        mode=backend_mode,
        as_of_date=now,
        started_at=now,
        completed_at=None,
        status="completed",
        config_hash=config_hash,
        input_snapshot_hash=input_snapshot_id,
        random_seed=None,
    )
