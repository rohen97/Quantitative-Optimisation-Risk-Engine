from __future__ import annotations

import pytest

from src.production.config import resolve_schedule_mode


def test_invalid_schedule_mode_raises():
    with pytest.raises(ValueError):
        resolve_schedule_mode("hourly", {})
