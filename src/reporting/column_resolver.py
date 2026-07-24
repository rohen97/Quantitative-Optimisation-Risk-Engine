from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "security_id": ("security_id", "asset_id", "instrument_id"),
    "ticker": ("ticker", "symbol"),
    "company_name": ("company_name", "name", "security_name"),
    "current_weight": ("current_weight", "portfolio_weight", "existing_weight"),
    "target_weight": ("target_weight", "final_weight", "recommended_weight", "weight", "final_selected_weight"),
    "market_value_usd": ("market_value_usd", "current_market_value_usd", "position_value_usd"),
    "expected_total_return_12m": ("expected_total_return_12m", "predicted_total_return", "expected_return_12m"),
    "dividend_yield": ("dividend_yield", "expected_dividend_yield"),
    "recommendation": ("final_recommendation", "recommendation", "trade_action"),
}


@dataclass(frozen=True)
class ColumnResolution:
    canonical_name: str
    resolved_name: str | None
    available: bool


def resolve_column(data: pd.DataFrame, canonical_name: str, required: bool = False) -> str | None:
    candidates = COLUMN_ALIASES.get(canonical_name, (canonical_name,))
    for candidate in candidates:
        if candidate in data.columns:
            return candidate
    if required:
        raise KeyError(
            f"Unable to resolve required column {canonical_name!r}. "
            f"Available columns: {sorted(data.columns)}"
        )
    return None


def canonicalise_dataframe(data: pd.DataFrame, canonical_names: tuple[str, ...] | None = None) -> pd.DataFrame:
    result = data.copy()
    names = canonical_names or tuple(COLUMN_ALIASES)
    rename_map: dict[str, str] = {}
    for canonical_name in names:
        resolved = resolve_column(result, canonical_name)
        if resolved is not None and resolved != canonical_name and canonical_name not in result.columns:
            rename_map[resolved] = canonical_name
    return result.rename(columns=rename_map)


def first_existing(columns: list[str] | tuple[str, ...], frame: pd.DataFrame, default: str | None = None) -> str | None:
    for column in columns:
        if column in frame.columns:
            return column
    return default


def require_any(frame: pd.DataFrame, candidates: list[str] | tuple[str, ...], purpose: str) -> str:
    column = first_existing(candidates, frame)
    if column is None:
        raise ValueError(f"Missing column for {purpose}; expected one of {list(candidates)}")
    return column


def safe_numeric(frame: pd.DataFrame, column: str | None, default: float = 0.0) -> pd.Series:
    if column is None or column not in frame:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)
