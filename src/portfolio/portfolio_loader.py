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
    "dividend_yield",
    "beta",
    "volatility",
}

NUMERIC_HOLDING_COLUMNS = {
    "shares",
    "current_price",
    "market_value_usd",
    "dividend_yield",
    "beta",
    "volatility",
}


def read_portfolio_file(path: str | Path) -> pd.DataFrame:
    """Read a current portfolio file from CSV or Excel."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Current portfolio file does not exist: {file_path}")
    if file_path.suffix.lower() == ".csv":
        return pd.read_csv(file_path)
    if file_path.suffix.lower() in {".xls", ".xlsx"}:
        return pd.read_excel(file_path)
    raise ValueError("Current portfolio input must be a CSV or Excel file.")


def validate_current_portfolio(frame: pd.DataFrame) -> None:
    """Validate required columns and basic numeric constraints."""
    missing = REQUIRED_HOLDING_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Portfolio missing required columns: {sorted(missing)}")


def enrich_current_portfolio(frame: pd.DataFrame) -> pd.DataFrame:
    """Add weights, dividend income and weighted risk columns to holdings."""
    validate_current_portfolio(frame)
    data = frame.copy()
    for column in NUMERIC_HOLDING_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="raise")
    if (data["market_value_usd"] < 0).any():
        raise ValueError("market_value_usd cannot be negative.")
    if (data["shares"] < 0).any():
        raise ValueError("shares cannot be negative.")
    total_nav = data["market_value_usd"].sum()
    if total_nav <= 0:
        raise ValueError("Portfolio total NAV must be greater than zero.")
    data["weight"] = data["market_value_usd"] / total_nav
    data["dividend_income_usd"] = data["market_value_usd"] * data["dividend_yield"]
    data["weighted_dividend_yield"] = data["weight"] * data["dividend_yield"]
    data["weighted_beta"] = data["weight"] * data["beta"]
    data["weighted_volatility"] = data["weight"] * data["volatility"]
    return data


def load_current_portfolio(path: str | Path) -> pd.DataFrame:
    """Load and enrich current holdings from a CSV or Excel file."""
    return enrich_current_portfolio(read_portfolio_file(path))
