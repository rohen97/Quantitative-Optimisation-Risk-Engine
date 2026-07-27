from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.config import ROOT, load_yaml


VALID_PRODUCTION_MODES = {"daily", "weekly", "monthly", "release_candidate"}


def load_production_config(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load production configuration from central settings or YAML."""
    if settings and isinstance(settings.get("production"), dict):
        return settings["production"]
    return load_yaml("configs/production.yaml").get("production", {})


def repository_root_from_settings(settings: dict[str, Any] | None = None) -> Path:
    root = (settings or {}).get("repository_root")
    return Path(root).resolve() if root else ROOT.resolve()


def resolve_schedule_mode(mode: str | None, production_config: dict[str, Any]) -> str:
    selected = mode or production_config.get("execution", {}).get("default_mode", "daily")
    if selected not in VALID_PRODUCTION_MODES:
        raise ValueError(f"Unsupported production mode: {selected}")
    return selected


def resolve_validation_mode(mode: str, production_config: dict[str, Any]) -> str:
    schedule = production_config.get("schedules", {}).get(mode, {})
    return schedule.get("validation_mode", "release_candidate" if mode == "release_candidate" else "smoke")


def timeout_seconds_for_mode(mode: str, production_config: dict[str, Any]) -> int:
    minutes = production_config.get("pipeline", {}).get("timeout_minutes", {}).get(mode, 180)
    return int(minutes) * 60
