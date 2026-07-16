from __future__ import annotations

import pandas as pd

from src.regime.mock_regime_data import FACTOR_COLUMNS, build_mock_factor_lens


def calculate_factor_returns(factor_lens: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return factor returns from supplied or mock factor lens data."""
    return build_mock_factor_lens() if factor_lens is None else factor_lens.copy()


def standardise_factor_features(factor_returns: pd.DataFrame) -> pd.DataFrame:
    """Standardise factor features cross-sectionally for regime modeling."""
    data = factor_returns.copy()
    for column in FACTOR_COLUMNS:
        std = data[column].std()
        data[column] = (data[column] - data[column].mean()) / (std if std else 1)
    return data
