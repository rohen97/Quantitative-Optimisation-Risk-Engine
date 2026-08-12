from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_complete_month_end(now: pd.Timestamp | None = None) -> pd.Timestamp:
    reference = pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    if reference.tzinfo is not None:
        reference = reference.tz_convert(None)
    return reference.normalize().replace(day=1) - pd.Timedelta(days=1)


def load_backtest_config(path: str | Path | None = None) -> dict[str, Any]:
    root = repository_root()
    config_path = Path(path) if path is not None else root / 'configs' / 'backtest.yaml'
    if not config_path.is_absolute():
        config_path = root / config_path
    with config_path.open('r', encoding='utf-8') as handle:
        payload = yaml.safe_load(handle) or {}
    config = deepcopy(payload)
    values = config.setdefault('backtest', {})
    values['start_date'] = pd.Timestamp(values.get('start_date', '1997-01-01')).normalize()
    configured_end = values.get('end_date')
    values['end_date'] = (
        pd.Timestamp(configured_end).normalize()
        if configured_end
        else latest_complete_month_end()
    )
    for key in ('current_portfolio_file', 'output_directory', 'cache_directory'):
        value = Path(values[key])
        values[key] = value if value.is_absolute() else root / value
    config['_meta'] = {
        'repository_root': root,
        'config_path': config_path,
    }
    return config
