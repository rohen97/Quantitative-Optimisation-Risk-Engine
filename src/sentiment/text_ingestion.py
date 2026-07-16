from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.alternative_data.mock_alt_data import generate_mock_text_documents


def load_text_documents(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_or_generate_text_documents(universe: pd.DataFrame, path: str | Path | None = None, use_mock: bool = True) -> pd.DataFrame:
    """Load local text documents or generate mock active-universe documents."""
    if path is not None and Path(path).exists():
        return load_text_documents(path)
    if use_mock:
        return generate_mock_text_documents(universe)
    raise FileNotFoundError("No text document file supplied and mock mode is disabled.")
