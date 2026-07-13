from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_HOLDING_COLUMNS = {
    "ticker",
    "company_name",
    "country",
    "region",
    "currency",
    "sector",
    "shares",
    "current_price",
    "market_value_usd",
}


def load_current_portfolio(path: str | Path | None = None, mock_portfolio: pd.DataFrame | None = None) -> pd.DataFrame:
    if path and Path(path).exists():
        path = Path(path)
        frame = pd.read_excel(path) if path.suffix.lower() in {".xls", ".xlsx"} else pd.read_csv(path)
    elif mock_portfolio is not None:
        frame = mock_portfolio.copy()
    else:
        raise FileNotFoundError("Provide a holdings file or mock_portfolio.")
    missing = REQUIRED_HOLDING_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Portfolio missing required columns: {sorted(missing)}")
    frame["market_value_usd"] = frame["market_value_usd"].astype(float)
    total_nav = frame["market_value_usd"].sum()
    frame["weight"] = frame["market_value_usd"] / total_nav if total_nav else 0.0
    return frame
