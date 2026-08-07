from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_env_file(path: str | Path = ".env") -> dict[str, str]:
    """Load simple KEY=value pairs from a local env file without overriding os.environ."""
    env_path = ROOT / path if not Path(path).is_absolute() else Path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = os.environ.get(key, value)
    return values


def get_env(name: str, default: str | None = None) -> str | None:
    """Read an environment variable, falling back to local env files."""
    if name in os.environ:
        return os.environ[name]
    values = load_env_file()
    if name in values:
        return values[name]
    example_values = load_env_file(".env.example")
    return example_values.get(name, default)


def env_flag(name: str, default: bool = False) -> bool:
    """Return a boolean environment flag from common true/false strings."""
    value = get_env(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
