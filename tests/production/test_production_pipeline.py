from __future__ import annotations

from src.production.config import resolve_schedule_mode, resolve_validation_mode


def test_production_mode_selection_defaults_daily():
    config = {"execution": {"default_mode": "daily"}, "schedules": {"daily": {"validation_mode": "smoke"}}}
    assert resolve_schedule_mode(None, config) == "daily"
    assert resolve_validation_mode("daily", config) == "smoke"
