from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import csr_matrix


UNKNOWN_LABELS = {"", "unknown", "nan", "none", "n/a", "<na>"}
GROUP_CAPS = (
    ("sector", "max_sector_weight"),
    ("country", "max_country_weight"),
    ("region", "max_region_weight"),
    ("currency", "max_currency_weight"),
)


def _series(data: pd.DataFrame, column: str, default) -> pd.Series:
    if column in data:
        return data[column]
    return pd.Series(default, index=data.index)


def _known(values: pd.Series) -> pd.Series:
    return ~values.fillna("Unknown").astype(str).str.strip().str.lower().isin(UNKNOWN_LABELS)


def build_eligibility_mask(data: pd.DataFrame, constraints: dict | None = None) -> pd.Series:
    """Apply hard optimiser exclusions. Hard constraints must not be bypassed."""
    limits = constraints or {}
    recommendation = _series(data, "final_recommendation", "Avoid").astype(str).str.lower()
    mask = (
        _series(data, "instrument_type", "Equity").fillna("Equity").eq("Equity")
        & _series(data, "listing_status", "Active").fillna("Active").eq("Active")
        & ~recommendation.str.contains("exclude|avoid", na=False)
        & recommendation.str.contains("buy|hold|watchlist|accumulate|core income", na=False)
        & (pd.to_numeric(_series(data, "liquidity_score", np.nan), errors="coerce") >= limits.get("minimum_liquidity_score", 40))
        & (
            pd.to_numeric(_series(data, "average_daily_value_usd", np.nan), errors="coerce")
            >= limits.get("minimum_average_daily_value_usd", 5_000_000)
        )
        & (pd.to_numeric(_series(data, "dividend_cut_probability", np.nan), errors="coerce") <= limits.get("maximum_dividend_cut_probability", 0.35))
        & (
            pd.to_numeric(_series(data, "large_drawdown_probability_12m", np.nan), errors="coerce")
            <= limits.get("maximum_large_drawdown_probability", 0.35)
        )
        & (
            pd.to_numeric(_series(data, "forecast_uncertainty_score", np.nan), errors="coerce")
            <= limits.get("maximum_forecast_uncertainty_score", 80)
        )
        & (pd.to_numeric(_series(data, "tail_risk_score", np.nan), errors="coerce") <= limits.get("maximum_tail_risk_score", 80))
        & ~_series(data, "regime_exclusion_flag", False).fillna(False).astype(bool)
        & ~_series(data, "reframing_exclusion_flag", False).fillna(False).astype(bool)
        & ~_series(data, "alt_data_exclusion_flag", False).fillna(False).astype(bool)
        & ~_series(data, "price_data_exclusion_flag", False).fillna(False).astype(bool)
    )
    for column, key in GROUP_CAPS:
        if float(limits.get(key, 1.0)) < 1.0 and column in data:
            mask &= _known(data[column])
    if not bool(limits.get("allow_synthetic_data", False)):
        mask &= ~_series(data, "is_synthetic_data", False).fillna(False).astype(bool)
        mask &= ~_series(data, "is_synthetic_fundamentals", False).fillna(False).astype(bool)
    if "liquidity_observation_count" in data:
        observations = pd.to_numeric(data["liquidity_observation_count"], errors="coerce").fillna(0)
        observation_ok = observations.ge(int(limits.get("minimum_liquidity_observations", 20)))
        if bool(limits.get("allow_synthetic_data", False)):
            observation_ok |= _series(data, "is_synthetic_data", False).fillna(False).astype(bool)
        mask &= observation_ok
    return mask


def build_retention_eligibility_mask(
    data: pd.DataFrame,
    constraints: dict | None = None,
) -> pd.Series:
    """Use hysteresis for held names while preserving non-negotiable exclusions."""

    limits = constraints or {}
    entry = build_eligibility_mask(data, limits)
    current = pd.to_numeric(
        _series(data, "current_weight", 0.0), errors="coerce"
    ).fillna(0.0).gt(1.0e-12)
    recommendation = _series(data, "final_recommendation", "Avoid").astype(str).str.lower()
    allowed_recommendation = (
        ~recommendation.str.contains("exclude|avoid", na=False)
        & recommendation.str.contains(
            "buy|hold|watchlist|accumulate|core income", na=False
        )
    )
    hard_safe = (
        _series(data, "instrument_type", "Equity").fillna("Equity").eq("Equity")
        & _series(data, "listing_status", "Active").fillna("Active").eq("Active")
        & allowed_recommendation
        & ~_series(data, "regime_exclusion_flag", False).fillna(False).astype(bool)
        & ~_series(data, "reframing_exclusion_flag", False).fillna(False).astype(bool)
        & ~_series(data, "alt_data_exclusion_flag", False).fillna(False).astype(bool)
        & ~_series(data, "price_data_exclusion_flag", False).fillna(False).astype(bool)
    )
    for column, key in GROUP_CAPS:
        if float(limits.get(key, 1.0)) < 1.0 and column in data:
            hard_safe &= _known(data[column])
    if not bool(limits.get("allow_synthetic_data", False)):
        hard_safe &= ~_series(data, "is_synthetic_data", False).fillna(False).astype(bool)
        hard_safe &= ~_series(data, "is_synthetic_fundamentals", False).fillna(False).astype(bool)

    minimum_factor = float(limits.get("retention_minimum_factor", 0.80))
    maximum_factor = float(limits.get("retention_maximum_factor", 1.15))
    buffered = (
        pd.to_numeric(_series(data, "liquidity_score", np.nan), errors="coerce")
        >= float(limits.get("minimum_liquidity_score", 40)) * minimum_factor
    ) & (
        pd.to_numeric(
            _series(data, "average_daily_value_usd", np.nan), errors="coerce"
        )
        >= float(limits.get("minimum_average_daily_value_usd", 5_000_000))
        * minimum_factor
    ) & (
        pd.to_numeric(
            _series(data, "dividend_cut_probability", np.nan), errors="coerce"
        )
        <= min(
            float(limits.get("maximum_dividend_cut_probability", 0.35))
            * maximum_factor,
            1.0,
        )
    ) & (
        pd.to_numeric(
            _series(data, "large_drawdown_probability_12m", np.nan),
            errors="coerce",
        )
        <= min(
            float(limits.get("maximum_large_drawdown_probability", 0.35))
            * maximum_factor,
            1.0,
        )
    ) & (
        pd.to_numeric(
            _series(data, "forecast_uncertainty_score", np.nan), errors="coerce"
        )
        <= min(
            float(limits.get("maximum_forecast_uncertainty_score", 80))
            * maximum_factor,
            100.0,
        )
    ) & (
        pd.to_numeric(_series(data, "tail_risk_score", np.nan), errors="coerce")
        <= min(
            float(limits.get("maximum_tail_risk_score", 80)) * maximum_factor,
            100.0,
        )
    )
    if "liquidity_observation_count" in data:
        buffered &= pd.to_numeric(
            data["liquidity_observation_count"], errors="coerce"
        ).fillna(0).ge(
            int(limits.get("minimum_liquidity_observations", 20))
            * minimum_factor
        )
    return entry | (current & hard_safe & buffered)


def build_fallback_eligibility_mask(data: pd.DataFrame, constraints: dict | None = None, min_names: int = 20) -> pd.Series:
    """Select a ranked subset without relaxing any hard eligibility rule."""
    base = build_eligibility_mask(data, constraints)
    if not bool(base.any()):
        return base
    ranking = (
        pd.to_numeric(_series(data, "final_recommendation_score", 50), errors="coerce").fillna(50)
        + pd.to_numeric(_series(data, "liquidity_score", 50), errors="coerce").fillna(50)
        + pd.to_numeric(_series(data, "regime_suitability_score", 50), errors="coerce").fillna(50)
        - 100 * pd.to_numeric(_series(data, "dividend_cut_probability", 0.10), errors="coerce").fillna(0.10)
        - 80 * pd.to_numeric(_series(data, "large_drawdown_probability_12m", 0.20), errors="coerce").fillna(0.20)
        - pd.to_numeric(_series(data, "tail_risk_score", 50), errors="coerce").fillna(50)
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
    """Solve the long-only cap system exactly with a sparse linear programme."""
    limits = constraints or {}
    raw = pd.Series(weights, index=data.index, dtype=float).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    active_positions = np.flatnonzero(raw.to_numpy() > 0)
    output = pd.Series(0.0, index=data.index)
    if len(active_positions) == 0:
        output.attrs.update(feasible=False, status="no_positive_candidate_weights")
        return output

    active = data.iloc[active_positions].reset_index(drop=True)
    preference = raw.iloc[active_positions].to_numpy(dtype=float, copy=True)
    preference /= max(float(preference.max()), 1.0)
    preference += np.linspace(1e-12, 0.0, len(preference), endpoint=False)
    max_weight = float(limits.get("max_single_name_weight", 0.05))
    if len(active) * max_weight < 1.0 - 1e-10:
        partial = np.minimum(raw.iloc[active_positions].to_numpy(dtype=float), max_weight)
        output.iloc[active_positions] = partial
        output.attrs.update(feasible=False, status="insufficient_single_name_capacity")
        return output

    row_indices: list[int] = []
    column_indices: list[int] = []
    values: list[float] = []
    upper_bounds: list[float] = []
    constraint_row = 0
    for column, key in GROUP_CAPS:
        cap = float(limits.get(key, 1.0))
        if cap >= 1.0 or column not in active:
            continue
        for _, positions in active.groupby(column, sort=False).indices.items():
            local_positions = np.asarray(positions, dtype=int)
            row_indices.extend([constraint_row] * len(local_positions))
            column_indices.extend(local_positions.tolist())
            values.extend([1.0] * len(local_positions))
            upper_bounds.append(cap)
            constraint_row += 1
    a_ub = (
        csr_matrix((values, (row_indices, column_indices)), shape=(constraint_row, len(active)))
        if constraint_row
        else None
    )
    result = linprog(
        c=-preference,
        A_ub=a_ub,
        b_ub=np.asarray(upper_bounds, dtype=float) if upper_bounds else None,
        A_eq=np.ones((1, len(active)), dtype=float),
        b_eq=np.array([1.0]),
        bounds=[(0.0, max_weight)] * len(active),
        method="highs",
    )
    if not result.success:
        output.attrs.update(feasible=False, status=f"infeasible:{result.message}")
        return output
    solved = np.where(np.asarray(result.x) > 1e-10, np.asarray(result.x), 0.0)
    solved /= solved.sum()
    output.iloc[active_positions] = solved
    output.attrs.update(feasible=True, status="optimal")
    return output


def check_weight_caps(portfolio: pd.DataFrame, max_weight: float = 0.05) -> bool:
    return bool((portfolio["target_weight"] <= max_weight + 1e-12).all())
