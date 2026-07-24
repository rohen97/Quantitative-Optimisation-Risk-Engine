from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config import ROOT, load_yaml


@dataclass(frozen=True)
class ValidationConfig:
    raw: dict[str, Any]

    @property
    def output_root(self) -> Path:
        return ROOT / self.raw["output"]["root"]

    @property
    def latest_directory(self) -> Path:
        return ROOT / self.raw["output"]["latest_directory"]

    def section(self, name: str) -> dict[str, Any]:
        return dict(self.raw.get(name, {}))


def load_validation_config(path: str | Path = "configs/validation.yaml") -> ValidationConfig:
    raw = load_yaml(path).get("validation", {})
    if not raw:
        raise ValueError(f"Validation configuration is empty: {path}")
    return ValidationConfig(raw=raw)
