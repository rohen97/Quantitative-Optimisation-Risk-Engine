from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd


DEFAULT_SIGNAL_WEIGHTS = {
    "benchmark_relative_expected_return_12m": 0.30,
    "momentum_6m": 0.15,
    "valuation_score": 0.15,
    "cash_flow_quality_score": 0.12,
    "balance_sheet_strength_score": 0.08,
    "dividend_safety_score": 0.08,
    "expected_volatility_12m": -0.06,
    "cvar_5_12m": 0.06,
}


@dataclass(frozen=True)
class RegionalAlphaSettings:
    signal_weights: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_SIGNAL_WEIGHTS)
    )
    regional_rank_weight: float = 0.70
    sector_rank_weight: float = 0.30
    minimum_peer_count: int = 5
    base_cost_bps: float = 17.5
    currency_conversion_bps: float = 2.0
    impact_coefficient_bps: float = 10.0
    maximum_participation_rate: float = 0.05
    assumed_position_weight: float = 0.05
    portfolio_nav_usd: float = 100_000_000.0
    retention_bonus_points: float = 3.0
    cost_penalty_points_per_portfolio_bp: float = 1.5

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object] | None,
        *,
        portfolio_nav_usd: float | None = None,
    ) -> "RegionalAlphaSettings":
        raw = dict(values or {})
        weights = {
            **DEFAULT_SIGNAL_WEIGHTS,
            **{
                str(key): float(value)
                for key, value in dict(raw.get("signal_weights", {})).items()
            },
        }
        return cls(
            signal_weights=weights,
            regional_rank_weight=float(raw.get("regional_rank_weight", 0.70)),
            sector_rank_weight=float(raw.get("sector_rank_weight", 0.30)),
            minimum_peer_count=max(int(raw.get("minimum_peer_count", 5)), 2),
            base_cost_bps=float(raw.get("base_cost_bps", 17.5)),
            currency_conversion_bps=float(
                raw.get("currency_conversion_bps", 2.0)
            ),
            impact_coefficient_bps=float(
                raw.get("impact_coefficient_bps", 10.0)
            ),
            maximum_participation_rate=max(
                float(raw.get("maximum_participation_rate", 0.05)), 1.0e-6
            ),
            assumed_position_weight=float(
                raw.get("assumed_position_weight", 0.05)
            ),
            portfolio_nav_usd=float(
                portfolio_nav_usd
                if portfolio_nav_usd is not None
                else raw.get("portfolio_nav_usd", 100_000_000.0)
            ),
            retention_bonus_points=float(raw.get("retention_bonus_points", 3.0)),
            cost_penalty_points_per_portfolio_bp=float(
                raw.get("cost_penalty_points_per_portfolio_bp", 1.5)
            ),
        )


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    values = frame[column] if column in frame else pd.Series(default, index=frame.index)
    return pd.to_numeric(values, errors="coerce").fillna(default)


def _weighted_group_mean(
    values: pd.Series,
    weights: pd.Series,
    groups: pd.Series,
) -> pd.Series:
    valid_weights = weights.clip(lower=0.0).where(values.notna(), 0.0)
    numerator = (values.fillna(0.0) * valid_weights).groupby(groups).transform("sum")
    denominator = valid_weights.groupby(groups).transform("sum")
    fallback = values.groupby(groups).transform("median")
    return (numerator / denominator.replace(0.0, np.nan)).fillna(fallback)


def _peer_rank(
    values: pd.Series,
    region: pd.Series,
    sector: pd.Series,
    settings: RegionalAlphaSettings,
) -> pd.Series:
    regional = values.groupby(region, dropna=False).rank(pct=True, method="average")
    peer_keys = pd.MultiIndex.from_arrays([region, sector])
    peer_count = values.groupby(peer_keys, dropna=False).transform("count")
    sector_rank = values.groupby(peer_keys, dropna=False).rank(
        pct=True,
        method="average",
    )
    sector_rank = sector_rank.where(
        peer_count.ge(settings.minimum_peer_count),
        regional,
    )
    total_weight = settings.regional_rank_weight + settings.sector_rank_weight
    if total_weight <= 0:
        return regional.fillna(0.5)
    blended = (
        settings.regional_rank_weight * regional
        + settings.sector_rank_weight * sector_rank
    ) / total_weight
    return blended.fillna(0.5).clip(0.0, 1.0)


def add_regional_alpha_signals(
    scorecard: pd.DataFrame,
    settings: RegionalAlphaSettings | Mapping[str, object] | None = None,
) -> pd.DataFrame:
    """Add cross-sectionally neutral, cost-aware signals using only dated inputs."""

    config = (
        settings
        if isinstance(settings, RegionalAlphaSettings)
        else RegionalAlphaSettings.from_mapping(settings)
    )
    data = scorecard.copy()
    region = data.get("region", pd.Series("Unknown", index=data.index)).fillna(
        "Unknown"
    ).astype(str)
    sector = data.get("sector", pd.Series("Unknown", index=data.index)).fillna(
        "Unknown"
    ).astype(str)
    expected_return = _numeric(data, "expected_total_return_12m", 0.0)
    market_cap = _numeric(data, "market_cap_usd", 0.0)
    data["regional_benchmark_expected_return_12m"] = _weighted_group_mean(
        expected_return,
        market_cap,
        region,
    )
    data["benchmark_relative_expected_return_12m"] = (
        expected_return - data["regional_benchmark_expected_return_12m"]
    )

    composite = pd.Series(0.0, index=data.index, dtype=float)
    absolute_weight = 0.0
    for column, signed_weight in config.signal_weights.items():
        values = _numeric(data, column, 0.0)
        rank = _peer_rank(values, region, sector, config)
        direction = 1.0 if signed_weight >= 0 else -1.0
        data[f"regional_rank_{column}"] = rank
        composite += abs(float(signed_weight)) * direction * (2.0 * rank - 1.0)
        absolute_weight += abs(float(signed_weight))
    if absolute_weight > 0:
        composite /= absolute_weight
    data["regional_alpha_composite"] = composite.clip(-1.0, 1.0)
    data["regional_alpha_score"] = (50.0 + 50.0 * composite).clip(0.0, 100.0)

    current_weight = _numeric(data, "current_weight", 0.0).clip(lower=0.0)
    trade_weight = (config.assumed_position_weight - current_weight).clip(lower=0.0)
    adv = _numeric(data, "average_daily_value_usd", 0.0).clip(lower=1.0)
    participation = (
        trade_weight * config.portfolio_nav_usd / (21.0 * adv)
    ).clip(lower=0.0, upper=config.maximum_participation_rate)
    impact_bps = config.impact_coefficient_bps * np.sqrt(
        participation / config.maximum_participation_rate
    )
    currency = data.get("currency", pd.Series("USD", index=data.index)).fillna(
        "USD"
    ).astype(str)
    total_bps = (
        config.base_cost_bps
        + impact_bps
        + currency.ne("USD").astype(float) * config.currency_conversion_bps
    )
    data["estimated_entry_trade_weight"] = trade_weight
    data["estimated_entry_cost_bps"] = total_bps
    data["estimated_entry_cost_fraction"] = trade_weight * total_bps / 10_000.0
    data["cost_adjusted_benchmark_relative_return_12m"] = (
        data["benchmark_relative_expected_return_12m"]
        - data["estimated_entry_cost_fraction"]
    )
    net_return_rank = _peer_rank(
        data["cost_adjusted_benchmark_relative_return_12m"],
        region,
        sector,
        config,
    )
    recommendation = _numeric(data, "final_recommendation_score", 50.0).clip(
        0.0,
        100.0,
    )
    portfolio_cost_bps = data["estimated_entry_cost_fraction"] * 10_000.0
    retention_bonus = current_weight.gt(0.0).astype(float) * config.retention_bonus_points
    utility = (
        0.65 * data["regional_alpha_score"]
        + 0.20 * (100.0 * net_return_rank)
        + 0.15 * recommendation
        + retention_bonus
        - config.cost_penalty_points_per_portfolio_bp * portfolio_cost_bps
    )
    data["regional_alpha_selection_utility"] = utility.clip(0.0, 100.0)
    data["regional_alpha_retention_bonus"] = retention_bonus
    return data
