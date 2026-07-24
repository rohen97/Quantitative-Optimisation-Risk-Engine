from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess

from src.reporting.config import ReportingConfig
from src.reporting.models import ICDataBundle


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(args: list[str]) -> str | None:
    try:
        result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    except OSError:
        return None
    value = result.stdout.strip()
    return value or None


def git_commit_hash() -> str | None:
    return _git_value(["rev-parse", "HEAD"])


def git_dirty_status() -> str:
    status = _git_value(["status", "--short"])
    return "dirty" if status else "clean"


def write_manifest(manifest: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return output_path


def build_report_manifest(
    *,
    report_run_id: str,
    bundle: ICDataBundle,
    config: ReportingConfig,
    output_files: list[Path],
    pdf_rendered: bool,
    readiness_status: str,
    warnings: tuple[str, ...],
) -> dict[str, object]:
    existing_outputs = [path for path in output_files if path.exists()]
    return {
        "report_run_id": report_run_id,
        "source_model_run_id": bundle.model_run_id,
        "as_of_date": str(bundle.as_of_date),
        "report_generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit_hash": git_commit_hash(),
        "dirty_git_status": git_dirty_status(),
        "backend": "legacy_csv",
        "configuration_hash": hashlib.sha256(json.dumps(config.__dict__, default=str, sort_keys=True).encode("utf-8")).hexdigest(),
        "input_source_hashes": {source.name: source.source_hash for source in bundle.sources if source.source_hash},
        "output_file_hashes": {path.name: hash_file(path) for path in existing_outputs},
        "missing_sources": [source.name for source in bundle.sources if not source.available],
        "warnings": list(warnings),
        "pdf_rendering_status": "rendered" if pdf_rendered else "not_rendered",
        "decision_readiness_status": readiness_status,
    }
