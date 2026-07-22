from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def read_output(filename: str, output_dir: str | Path = "reports/outputs") -> pd.DataFrame:
    """Read a local pipeline output or return an empty frame."""
    path = Path(output_dir) / filename
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def build_temporal_mock_features(asset_data: pd.DataFrame, lookback_days: int = 60) -> pd.DataFrame:
    """Build deterministic temporal market features when price history is unavailable."""
    rows = []
    for idx, row in asset_data.reset_index(drop=True).iterrows():
        vol = float(row.get("expected_volatility_12m", 0.20))
        ret = float(row.get("expected_total_return_12m", 0.05))
        liquidity = float(row.get("liquidity_score", 50))
        rows.append(
            {
                "ticker": row["ticker"],
                "daily_return_mean_60d": ret / 252,
                "cumulative_return_60d": ret * lookback_days / 252,
                "volatility_20d": vol * (0.85 + 0.01 * (idx % 5)),
                "volatility_60d": vol,
                "volatility_ratio_20d_60d": 0.85 + 0.01 * (idx % 5),
                "rolling_drawdown": -abs(float(row.get("large_drawdown_probability_12m", 0.20))) * 0.20,
                "downside_volatility": vol * 0.65,
                "relative_strength": ret / max(vol, 1e-6),
                "volume_adv_proxy": liquidity * 100_000,
                "liquidity_score": liquidity,
                "rolling_corr_portfolio": 0.25 + 0.01 * (idx % 10),
                "rolling_corr_change": 0.01 * np.sin(idx),
            }
        )
    return pd.DataFrame(rows)
