from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_csv(frame: pd.DataFrame, output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    frame.to_csv(path, index=False)
    return path


def write_markdown(text: str, output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(text, encoding="utf-8")
    return path
