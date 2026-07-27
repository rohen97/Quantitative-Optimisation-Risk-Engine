from __future__ import annotations

import shutil
from pathlib import Path


def resolve_repo_path(repository_root: Path, path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else repository_root / path


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_copy_directory(source: Path, destination: Path) -> None:
    """Copy a directory through a temporary location before replacing the pointer."""
    if not source.exists():
        raise FileNotFoundError(source)
    tmp_destination = destination.with_name(f"{destination.name}.tmp")
    old_destination = destination.with_name(f"{destination.name}.old")
    if tmp_destination.exists():
        shutil.rmtree(tmp_destination)
    shutil.copytree(source, tmp_destination)
    manifest = tmp_destination / "production_manifest.json"
    if not manifest.exists():
        raise FileNotFoundError("Copied production bundle is missing production_manifest.json")
    if old_destination.exists():
        shutil.rmtree(old_destination)
    if destination.exists():
        destination.rename(old_destination)
    tmp_destination.rename(destination)
    if old_destination.exists():
        shutil.rmtree(old_destination)
