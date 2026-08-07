from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = ROOT / path if not Path(path).is_absolute() else Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def ensure_output_dir(config: dict[str, Any] | None = None) -> Path:
    output_dir = os.environ.get("PIPELINE_OUTPUT_DIR") or (config or {}).get(
        "output_dir",
        "reports/outputs",
    )
    path = Path(output_dir)
    if not path.is_absolute():
        path = ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_settings() -> dict[str, Any]:
    """Load central project settings, including the data backend layer."""
    settings = load_yaml("configs/base.yaml")
    settings["data"] = load_yaml("configs/data.yaml").get("data", {})
    settings["data_sources"] = load_yaml("configs/data_sources.yaml").get("data_sources", {})
    settings["validation"] = load_yaml("configs/validation.yaml").get("validation", {})
    settings["production"] = load_yaml("configs/production.yaml").get("production", {})
    settings["repository_root"] = str(ROOT)
    return settings
