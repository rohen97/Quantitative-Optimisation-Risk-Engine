from __future__ import annotations

import pandas as pd


def build_eligibility_mask(data: pd.DataFrame, constraints: dict | None = None) -> pd.Series:
    """Apply hard optimiser exclusions. Hard constraints must not be bypassed."""
    limits = constraints or {}
    recommendation = data["final_recommendation"].astype(str).str.lower()
    mask = (
        data["instrument_type"].fillna("Equity").eq("Equity")
        & data["listing_status"].fillna("Active").eq("Active")
        & ~recommendation.str.contains("exclude|avoid", na=False)
        & (data["liquidity_score"].fillna(50) >= limits.get("minimum_liquidity_score", 40))
        & (data["average_daily_value_usd"].fillna(5_000_000) >= limits.get("minimum_average_daily_value_usd", 5_000_000))
        & (data["dividend_cut_probability"].fillna(0.10) <= limits.get("maximum_dividend_cut_probability", 0.35))
        & (data["large_drawdown_probability_12m"].fillna(0.20) <= limits.get("maximum_large_drawdown_probability", 0.35))
        & (data["forecast_uncertainty_score"].fillna(50) <= limits.get("maximum_forecast_uncertainty_score", 80))
        & (data["tail_risk_score"].fillna(50) <= limits.get("maximum_tail_risk_score", 80))
        & ~data["regime_exclusion_flag"].fillna(False).astype(bool)
        & ~data["reframing_exclusion_flag"].fillna(False).astype(bool)
        & ~data["alt_data_exclusion_flag"].fillna(False).astype(bool)
    )
    return mask


def build_fallback_eligibility_mask(data: pd.DataFrame, constraints: dict | None = None, min_names: int = 20) -> pd.Series:
    """Dry-run fallback when every name is excluded by mock upstream flags."""
    limits = constraints or {}
    base = (
        data["instrument_type"].fillna("Equity").eq("Equity")
        & data["listing_status"].fillna("Active").eq("Active")
        & (data["liquidity_score"].fillna(50) >= limits.get("minimum_liquidity_score", 40))
        & (data["average_daily_value_usd"].fillna(5_000_000) >= limits.get("minimum_average_daily_value_usd", 5_000_000))
        & ~data["regime_exclusion_flag"].fillna(False).astype(bool)
        & ~data["alt_data_exclusion_flag"].fillna(False).astype(bool)
    )
    if base.sum() == 0:
        base = data["instrument_type"].fillna("Equity").eq("Equity") & data["listing_status"].fillna("Active").eq("Active")
    ranking = (
        data["final_recommendation_score"].fillna(50)
        + data["liquidity_score"].fillna(50)
        + data["regime_suitability_score"].fillna(50)
        - 100 * data["dividend_cut_probability"].fillna(0.10)
        - 80 * data["large_drawdown_probability_12m"].fillna(0.20)
        - data["tail_risk_score"].fillna(50)
    )
    selected = ranking.where(base, -1e9).sort_values(ascending=False).head(min_names).index
    mask = pd.Series(False, index=data.index)
    mask.loc[selected] = True
    return mask


def cap_and_renormalise_weights(
    weights: pd.Series,
    data: pd.DataFrame,
    constraints: dict | None = None,
    max_iterations: int = 20,
) -> pd.Series:
    """Apply long-only single-name caps and renormalise without violating hard exclusions."""
    limits = constraints or {}
    raw = pd.Series(weights, index=data.index).fillna(0).clip(lower=0)
    max_weight = float(limits.get("max_single_name_weight", 0.05))
    if raw.sum() <= 0:
        return raw
    weights_out = pd.Series(0.0, index=raw.index)
    remaining = raw / raw.sum()
    available = remaining[remaining > 0].index
    for _ in range(max_iterations):
        if len(available) == 0:
            break
        allocation_pool = 1.0 - weights_out.sum()
        if allocation_pool <= 1e-12:
            break
        proportional = remaining.loc[available] / remaining.loc[available].sum() * allocation_pool
        capped_now = proportional.clip(upper=max_weight - weights_out.loc[available])
        weights_out.loc[available] += capped_now
        available = weights_out.loc[available][weights_out.loc[available] < max_weight - 1e-12].index
        if abs(weights_out.sum() - 1.0) < 1e-10 or capped_now.sum() <= 1e-12:
            break
    return weights_out.clip(lower=0, upper=max_weight)


def apply_group_cap(weights: pd.Series, data: pd.DataFrame, group_col: str, max_group_weight: float) -> pd.Series:
    """Scale groups above cap and renormalise the freed weight across uncapped names."""
    adjusted = pd.Series(weights, index=data.index).fillna(0).clip(lower=0)
    for _, idx in data.groupby(group_col).groups.items():
        group_weight = adjusted.loc[idx].sum()
        if group_weight > max_group_weight and group_weight > 0:
            adjusted.loc[idx] *= max_group_weight / group_weight
    total = adjusted.sum()
    return adjusted / total if total > 0 else adjusted


def apply_diversification_caps(weights: pd.Series, data: pd.DataFrame, constraints: dict | None = None) -> pd.Series:
    limits = constraints or {}
    adjusted = cap_and_renormalise_weights(weights, data, limits)
    for column, key in [
        ("sector", "max_sector_weight"),
        ("country", "max_country_weight"),
        ("region", "max_region_weight"),
        ("currency", "max_currency_weight"),
    ]:
        adjusted = apply_group_cap(adjusted, data, column, float(limits.get(key, 1.0)))
        adjusted = cap_and_renormalise_weights(adjusted, data, limits)
    return adjusted


def check_weight_caps(portfolio: pd.DataFrame, max_weight: float = 0.05) -> bool:
    return bool((portfolio["target_weight"] <= max_weight + 1e-12).all())
