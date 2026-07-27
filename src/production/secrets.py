from __future__ import annotations

import os
from typing import Iterable


SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "WEBHOOK", "AUTH")


def get_secret_from_env(name: str) -> str | None:
    return os.environ.get(name) or None


def redact_secret(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 8:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def redact_mapping(values: dict) -> dict:
    redacted = {}
    for key, value in values.items():
        if any(marker in str(key).upper() for marker in SECRET_MARKERS):
            redacted[key] = redact_secret(str(value)) if value is not None else None
        else:
            redacted[key] = value
    return redacted


def present_secret_names(names: Iterable[str]) -> list[str]:
    return [name for name in names if os.environ.get(name)]
