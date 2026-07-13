from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_text_documents(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)
