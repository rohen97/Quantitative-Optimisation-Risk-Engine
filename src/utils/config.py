from __future__ import annotations

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
    output_dir = (config or {}).get("output_dir", "reports/outputs")
    path = ROOT / output_dir
    path.mkdir(parents=True, exist_ok=True)
    return path
