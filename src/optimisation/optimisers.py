from __future__ import annotations

import numpy as np
import pandas as pd

from src.optimisation.constraints import apply_diversification_caps, build_eligibility_mask, build_fallback_eligibility_mask
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


def _portfolio_from_scores(data: pd.DataFrame, scores: pd.Series, constraints: dict | None, method: str) -> pd.DataFrame:
    eligible = build_eligibility_mask(data, constraints)
    fallback_used = False
    if eligible.sum() == 0:
        eligible = build_fallback_eligibility_mask(data, constraints)
        fallback_used = True
    eligible_scores = scores.where(eligible, 0)
    if eligible_scores.sum() <= 0 and eligible.sum() > 0:
        eligible_scores = pd.Series(1.0, index=data.index).where(eligible, 0)
    elif eligible.sum() > 0:
        eligible_scores = eligible_scores + eligible.astype(float) * max(float(eligible_scores.max()), 1.0) * 0.01
    raw = _normalise_scores(eligible_scores)
    weights = apply_diversification_caps(raw, data, constraints)
    weights = weights.where(eligible, 0)
    weights = apply_diversification_caps(weights, data, constraints)
    portfolio = data.copy()
    portfolio["target_weight"] = weights
    portfolio["portfolio_method"] = method
    portfolio["eligible_for_optimisation"] = eligible
    portfolio["fallback_eligibility_used"] = fallback_used
    return portfolio


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
    constraints = config.get("constraints", {})
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
