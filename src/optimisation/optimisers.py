from __future__ import annotations

import numpy as np
import pandas as pd

from src.optimisation.constraints import (
    apply_diversification_caps,
    build_eligibility_mask,
    build_fallback_eligibility_mask,
    build_retention_eligibility_mask,
)
from src.optimisation.objectives import (
    cvar_expected_shortfall_objective,
    dividend_income_objective,
    regime_aware_objective,
    risk_adjusted_return_objective,
    score_weighted_objective,
)


def _normalise_scores(scores: pd.Series) -> pd.Series:
    scores = pd.Series(scores).fillna(0).clip(lower=0)
    return scores / scores.sum() if scores.sum() > 0 else scores


def _apply_turnover_limit(
    target_weights: pd.Series,
    data: pd.DataFrame,
    eligible: pd.Series,
    limits: dict,
) -> pd.Series:
    '''Project a feasible target toward a fully invested feasible current portfolio.'''
    status = dict(target_weights.attrs)
    target = pd.Series(target_weights, index=data.index, dtype=float).fillna(0.0)
    current = pd.to_numeric(
        data.get('current_weight', pd.Series(0.0, index=data.index)),
        errors='coerce',
    ).fillna(0.0).clip(lower=0.0)
    maximum_turnover = float(limits.get('maximum_turnover', 1.0))
    unconstrained_turnover = float(0.5 * (target - current).abs().sum())
    fully_invested_current = abs(float(current.sum()) - 1.0) <= 1.0e-6
    retention_eligible = build_retention_eligibility_mask(data, limits)
    hard_exit_required = bool(
        current.where(~retention_eligible, 0.0).gt(1.0e-12).any()
    )
    current_feasible = bool(
        current.max() <= float(limits.get('max_single_name_weight', 1.0)) + 1.0e-10
    )
    for column, key in (
        ('sector', 'max_sector_weight'),
        ('country', 'max_country_weight'),
        ('region', 'max_region_weight'),
        ('currency', 'max_currency_weight'),
    ):
        if column in data:
            maximum_exposure = float(
                pd.DataFrame({column: data[column], '_weight': current})
                .groupby(column, dropna=False)['_weight']
                .sum()
                .max()
            )
            current_feasible &= maximum_exposure <= float(limits.get(key, 1.0)) + 1.0e-10
    minimum_rebalance = float(limits.get('minimum_rebalance_turnover', 0.0))
    applied = False
    no_trade_band_applied = False
    if (
        fully_invested_current
        and current_feasible
        and not hard_exit_required
        and unconstrained_turnover <= minimum_rebalance
    ):
        target = current.copy()
        no_trade_band_applied = True
    if (
        fully_invested_current
        and current_feasible
        and not hard_exit_required
        and 0.0 <= maximum_turnover < unconstrained_turnover
        and not no_trade_band_applied
    ):
        scale = maximum_turnover / unconstrained_turnover
        target = current + scale * (target - current)
        target = target.clip(lower=0.0)
        target /= target.sum()
        applied = True
    status.update(
        {
            'unconstrained_turnover': unconstrained_turnover,
            'turnover_constraint_applied': applied,
            'no_trade_band_applied': no_trade_band_applied,
            'turnover_constraint_skipped_for_hard_exit': hard_exit_required,
            'turnover_constraint_skipped_for_infeasible_current': (
                fully_invested_current and not current_feasible
            ),
            'projected_turnover': float(0.5 * (target - current).abs().sum()),
        }
    )
    target.attrs.update(status)
    return target


def _candidate_mask(
    data: pd.DataFrame,
    eligible: pd.Series,
    scores: pd.Series,
    maximum_candidates: int,
) -> pd.Series:
    """Deduplicate issuers and retain a region-sector-balanced shortlist."""
    candidates = data.loc[eligible].copy()
    if candidates.empty:
        return pd.Series(False, index=data.index)
    candidates["_objective_score"] = pd.to_numeric(scores.loc[candidates.index], errors="coerce").fillna(0.0)
    issuer_fallback = (
        candidates.get("company_name", candidates.get("ticker", candidates.index.to_series()))
        .astype(str)
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "", regex=True)
        .radd("NAME:")
    )
    candidates["_issuer_key"] = candidates.get("issuer_id", issuer_fallback).fillna(issuer_fallback).astype(str)
    candidates["_ticker_key"] = candidates.get("ticker", candidates.index.to_series()).astype(str)
    ranked = candidates.sort_values(
        ["_objective_score", "_ticker_key"],
        ascending=[False, True],
        kind="stable",
    ).drop_duplicates("_issuer_key", keep="first")
    if maximum_candidates > 0 and len(ranked) > maximum_candidates:
        group_columns = [column for column in ("region", "sector") if column in ranked]
        if group_columns:
            group_count = max(int(ranked.groupby(group_columns, dropna=False).ngroups), 1)
            quota = max(maximum_candidates // group_count, 1)
            diversified = ranked.groupby(group_columns, dropna=False, sort=False).head(quota)
            remaining = ranked.loc[~ranked.index.isin(diversified.index)]
            ranked = pd.concat(
                [diversified, remaining.head(maximum_candidates - len(diversified))],
                axis=0,
            ).head(maximum_candidates)
        else:
            ranked = ranked.head(maximum_candidates)
    mask = pd.Series(False, index=data.index)
    mask.loc[ranked.index] = True
    return mask


def _portfolio_from_scores(data: pd.DataFrame, scores: pd.Series, constraints: dict | None, method: str) -> pd.DataFrame:
    limits = constraints or {}
    eligible = build_eligibility_mask(data, limits)
    fallback_used = False
    if eligible.sum() == 0:
        eligible = build_fallback_eligibility_mask(data, limits)
        fallback_used = True
    candidate_mask = _candidate_mask(
        data,
        eligible,
        scores,
        int(limits.get("maximum_candidates", 2000)),
    )
    eligible_scores = scores.where(candidate_mask, 0)
    if eligible_scores.sum() <= 0 and eligible.sum() > 0:
        eligible_scores = pd.Series(1.0, index=data.index).where(candidate_mask, 0)
    elif candidate_mask.sum() > 0:
        eligible_scores = eligible_scores + candidate_mask.astype(float) * max(float(eligible_scores.max()), 1.0) * 0.01
    raw = _normalise_scores(eligible_scores)
    weights = apply_diversification_caps(raw, data, limits)
    weights = _apply_turnover_limit(weights, data, eligible, limits)
    feasible = bool(weights.attrs.get("feasible", False))
    status = str(weights.attrs.get("status", "unknown"))
    retained = candidate_mask | pd.to_numeric(data.get("current_weight", 0.0), errors="coerce").fillna(0.0).gt(0)
    weights = weights.where(retained, 0.0)
    portfolio = data.loc[retained].copy()
    portfolio["target_weight"] = weights.loc[portfolio.index].to_numpy()
    portfolio["portfolio_method"] = method
    portfolio["eligible_for_optimisation"] = candidate_mask.loc[portfolio.index].to_numpy()
    portfolio["fallback_eligibility_used"] = fallback_used
    portfolio["optimisation_feasible"] = feasible
    portfolio["optimisation_status"] = status
    portfolio["eligible_security_count"] = int(eligible.sum())
    portfolio["candidate_security_count"] = int(candidate_mask.sum())
    portfolio['unconstrained_turnover'] = float(
        weights.attrs.get('unconstrained_turnover', 0.0)
    )
    portfolio['projected_turnover'] = float(
        weights.attrs.get('projected_turnover', 0.0)
    )
    portfolio['turnover_constraint_applied'] = bool(
        weights.attrs.get('turnover_constraint_applied', False)
    )
    portfolio['no_trade_band_applied'] = bool(
        weights.attrs.get('no_trade_band_applied', False)
    )
    portfolio['retention_eligible'] = build_retention_eligibility_mask(
        data, limits
    ).loc[portfolio.index].to_numpy()
    portfolio['turnover_constraint_skipped_for_hard_exit'] = bool(
        weights.attrs.get('turnover_constraint_skipped_for_hard_exit', False)
    )
    portfolio['turnover_constraint_skipped_for_infeasible_current'] = bool(
        weights.attrs.get('turnover_constraint_skipped_for_infeasible_current', False)
    )
    return portfolio.reset_index(drop=True)


def equal_weight_eligible_portfolio(data: pd.DataFrame, constraints: dict | None = None) -> pd.DataFrame:
    eligible = build_eligibility_mask(data, constraints)
    scores = pd.Series(1.0, index=data.index).where(eligible, 0)
    return _portfolio_from_scores(data, scores, constraints, "equal_weight")


def score_weighted_portfolio(data: pd.DataFrame, constraints: dict | None = None) -> pd.DataFrame:
    return _portfolio_from_scores(data, score_weighted_objective(data), constraints, "score_weighted")


def risk_parity_portfolio(data: pd.DataFrame, constraints: dict | None = None) -> pd.DataFrame:
    inv_vol = 1 / data["expected_volatility_12m"].fillna(0.20).clip(lower=0.03)
    scores = inv_vol * build_eligibility_mask(data, constraints).astype(float)
    return _portfolio_from_scores(data, scores, constraints, "risk_parity")


def mean_variance_portfolio(data: pd.DataFrame, constraints: dict | None = None, risk_aversion_lambda: float = 5.0) -> pd.DataFrame:
    score = (
        data["expected_total_return_12m"].fillna(0.05)
        - risk_aversion_lambda * np.square(data["expected_volatility_12m"].fillna(0.20))
        + 0.01 * data["final_recommendation_score"].fillna(50)
    )
    return _portfolio_from_scores(data, score.clip(lower=0), constraints, "mean_variance")


def cvar_constrained_portfolio(data: pd.DataFrame, constraints: dict | None = None) -> pd.DataFrame:
    return _portfolio_from_scores(data, cvar_expected_shortfall_objective(data), constraints, "cvar_constrained")


def dividend_income_portfolio(data: pd.DataFrame, constraints: dict | None = None) -> pd.DataFrame:
    scores = dividend_income_objective(data)
    scores = scores.where(data["dividend_cut_probability"].fillna(0.10) <= (constraints or {}).get("maximum_dividend_cut_probability", 0.35), 0)
    return _portfolio_from_scores(data, scores, constraints, "dividend_income")


def regime_aware_portfolio(data: pd.DataFrame, constraints: dict | None = None, dominant_regime: str = "steady_state_low_chaos") -> pd.DataFrame:
    return _portfolio_from_scores(data, regime_aware_objective(data, dominant_regime), constraints, "regime_aware")


def run_all_optimisers(data: pd.DataFrame, optimisation_config: dict | None = None, dominant_regime: str = "steady_state_low_chaos") -> dict[str, pd.DataFrame]:
    config = (optimisation_config or {}).get("optimisation", optimisation_config or {})
    constraints = {
        **config.get("constraints", {}),
        "maximum_candidates": int(config.get("maximum_candidates", 2000)),
        "allow_synthetic_data": str(config.get("mode", "")).lower() == "mock",
    }
    methods = config.get("methods", {})
    outputs = {}
    if methods.get("equal_weight", {}).get("enabled", True):
        outputs["optimised_portfolio_equal_weight"] = equal_weight_eligible_portfolio(data, constraints)
    if methods.get("score_weighted", {}).get("enabled", True):
        outputs["optimised_portfolio_score_weighted"] = score_weighted_portfolio(data, constraints)
    if methods.get("risk_parity", {}).get("enabled", True):
        outputs["optimised_portfolio_risk_parity"] = risk_parity_portfolio(data, constraints)
    if methods.get("mean_variance", {}).get("enabled", True):
        outputs["optimised_portfolio_mean_variance"] = mean_variance_portfolio(
            data, constraints, methods.get("mean_variance", {}).get("risk_aversion_lambda", 5.0)
        )
    if methods.get("cvar_constrained", {}).get("enabled", True):
        outputs["optimised_portfolio_cvar_constrained"] = cvar_constrained_portfolio(data, constraints)
    if methods.get("dividend_income", {}).get("enabled", True):
        outputs["optimised_portfolio_dividend_income"] = dividend_income_portfolio(data, constraints)
    if methods.get("regime_aware", {}).get("enabled", True):
        outputs["optimised_portfolio_regime_aware"] = regime_aware_portfolio(data, constraints, dominant_regime)
    return outputs


def equal_weight(candidates: pd.DataFrame, max_weight: float = 0.05) -> pd.Series:
    weight = min(max_weight, 1 / len(candidates)) if len(candidates) else 0
    return pd.Series(weight, index=candidates.index)
