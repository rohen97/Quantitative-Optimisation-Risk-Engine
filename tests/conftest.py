from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_live_data_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic even when the local .env enables live data."""
    monkeypatch.setenv('USE_MOCK_DATA', 'true')
    monkeypatch.setenv('PIPELINE_INPUT_SOURCE', '')
    monkeypatch.setenv('PIPELINE_MAX_SECURITIES', '24')
