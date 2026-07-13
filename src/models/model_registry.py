from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelRegistryEntry:
    name: str
    version: str
    description: str
