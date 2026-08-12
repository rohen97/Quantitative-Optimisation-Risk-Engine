from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class PortfolioSpec:
    key: str
    label: str
    holdings: pd.DataFrame
    initial_capital_usd: float
    capital_source: str
    evidence_type: str
    source_files: tuple[Path, ...] = field(default_factory=tuple)
    description: str = ''


@dataclass(frozen=True)
class MarketDataBundle:
    prices_usd: pd.DataFrame
    volume_usd: pd.DataFrame
    cash_returns: pd.Series
    benchmark_prices_usd: pd.DataFrame
    benchmark_metadata: pd.DataFrame
    data_coverage: pd.DataFrame
    source_manifest: dict
    price_adjustments: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass(frozen=True)
class ReplayResult:
    strategy: str
    label: str
    monthly: pd.DataFrame
    initial_capital_usd: float
    capital_source: str
    evidence_type: str
    full_investment_start: pd.Timestamp | None
    source_files: tuple[Path, ...] = field(default_factory=tuple)
