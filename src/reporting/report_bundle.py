from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import json
import os
from pathlib import Path
import shutil
import stat
import time
from typing import Any

import numpy as np
import pandas as pd


def _handle_remove_error(function, path: str, _exc_info) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
        function(path)
    except PermissionError:
        time.sleep(0.25)
        function(path)


def _remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, onerror=_handle_remove_error)


def prepare_report_directory(archive_root: Path, latest_dir: Path, model_run_id: str) -> Path:
    report_dir = archive_root / model_run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    _remove_tree(latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def copy_to_latest(report_dir: Path, latest_dir: Path) -> None:
    _remove_tree(latest_dir)
    shutil.copytree(report_dir, latest_dir)


def to_json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if is_dataclass(value):
        return to_json_safe(asdict(value))
    if isinstance(value, pd.DataFrame):
        return [{key: to_json_safe(item) for key, item in record.items()} for record in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return {str(key): to_json_safe(item) for key, item in value.to_dict().items()}
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def write_report_bundle(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")
    return path
