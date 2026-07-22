from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DRLState:
    observation: np.ndarray
    asset_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    eligibility_mask: np.ndarray
    baseline_weights: np.ndarray
    current_weights: np.ndarray
    cash_index: int


BASE_FEATURES = [
    "current_weight",
    "baseline_weight",
    "cash_weight",
    "nav",
    "sector_exposure",
    "country_exposure",
    "region_exposure",
    "currency_exposure",
    "hhi",
    "effective_holdings",
    "turnover_used",
    "remaining_turnover_budget",
    "max_name_headroom",
    "sector_limit_headroom",
    "country_limit_headroom",
    "currency_limit_headroom",
    "daily_return_mean_60d",
    "cumulative_return_60d",
    "volatility_20d",
    "volatility_60d",
    "volatility_ratio_20d_60d",
    "rolling_drawdown",
    "downside_volatility",
    "relative_strength",
    "volume_adv_proxy",
    "liquidity_score",
    "rolling_corr_portfolio",
    "rolling_corr_change",
    "final_recommendation_score",
    "dividend_safety_score",
    "dividend_yield",
    "free_cash_flow_yield",
    "cashflow_quality_score",
    "balance_sheet_strength_score",
    "valuation_score",
    "portfolio_fit_score",
    "expected_dividend_contribution",
    "payout_ratio",
    "fcf_dividend_cover",
    "leverage_metric",
    "interest_coverage",
    "expected_total_return_12m",
    "expected_dividend_return_12m",
    "distribution_mu_12m",
    "distribution_sigma_12m",
    "distribution_nu_12m",
    "distribution_xi_12m",
    "p5_return_12m",
    "p50_return_12m",
    "p95_return_12m",
    "var_5_12m",
    "cvar_5_12m",
    "expected_shortfall_5_12m",
    "dividend_cut_probability",
    "large_drawdown_probability_12m",
    "forecast_uncertainty_score",
    "tail_risk_score",
    "skewness_risk_score",
    "crisis_probability",
    "steady_state_probability",
    "inflation_probability",
    "walking_on_ice_probability",
    "low_chaos_probability",
    "intermediate_chaos_probability",
    "high_chaos_probability",
    "wolf_chaos_index",
    "regime_deterioration_probability",
    "regime_suitability_score",
    "sentiment_score",
    "narrative_reframing_score",
    "distress_similarity",
    "credit_stress_similarity",
    "governance_risk_similarity",
    "regulatory_risk_similarity",
    "negative_news_intensity",
    "event_severity_score",
    "contribution_to_volatility",
    "contribution_to_var_5",
    "contribution_to_cvar_5",
    "contribution_to_expected_shortfall_5",
    "contribution_to_drawdown_risk",
    "worst_stress_scenario_loss",
    "crisis_scenario_loss",
    "europe_recession_loss",
    "china_policy_stress_loss",
    "uk_rate_shock_loss",
    "credit_stress_loss",
    "dividend_cut_shock_loss",
    "liquidity_shock_loss",
    "hard_eligibility_mask",
    "review_required_flag",
    "exclusion_flag",
]


def _column(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column in frame:
        return pd.to_numeric(frame[column], errors="coerce").fillna(default)
    return pd.Series(default, index=frame.index, dtype=float)


def _map_by_asset(features: pd.DataFrame, asset_ids: Sequence[str]) -> pd.DataFrame:
    if features is None or features.empty:
        return pd.DataFrame(index=list(asset_ids))
    key = "ticker" if "ticker" in features else "security_id" if "security_id" in features else None
    if key is None:
        return features.reindex(range(len(asset_ids))).reset_index(drop=True)
    return features.drop_duplicates(key).set_index(key).reindex(asset_ids).reset_index()


def build_state_schema(feature_names: Sequence[str]) -> pd.DataFrame:
    """Return deterministic schema metadata for reports/outputs."""
    return pd.DataFrame(
        {
            "feature_order": range(len(feature_names)),
            "feature_name": list(feature_names),
            "feature_group": [
                "portfolio"
                if idx < 16
                else "temporal"
                if idx < 28
                else "fundamental_scorecard"
                if idx < 41
                else "distributional_forecast"
                if idx < 57
                else "regime_information"
                if idx < 76
                else "risk_stress_constraint"
                for idx, _ in enumerate(feature_names)
            ],
        }
    )


def build_drl_state(
    as_of_date: pd.Timestamp,
    asset_ids: Sequence[str],
    current_weights: np.ndarray,
    baseline_weights: np.ndarray,
    temporal_features: pd.DataFrame,
    cross_sectional_features: pd.DataFrame,
    portfolio_features: dict[str, float],
    eligibility_mask: np.ndarray,
) -> DRLState:
    """Build a point-in-time observation with deterministic feature order."""
    del as_of_date
    asset_ids = tuple(str(asset) for asset in asset_ids)
    cross = _map_by_asset(cross_sectional_features, asset_ids)
    temporal = _map_by_asset(temporal_features, asset_ids)
    current = np.asarray(current_weights, dtype=float)
    baseline = np.asarray(baseline_weights, dtype=float)
    eligible = np.asarray(eligibility_mask, dtype=bool)
    rows: list[list[float]] = []
    for i, _asset in enumerate(asset_ids):
        row = {
            "current_weight": current[i],
            "baseline_weight": baseline[i],
            "cash_weight": float(portfolio_features.get("cash_weight", 0.0)),
            "nav": float(portfolio_features.get("nav", 0.0)),
            "sector_exposure": float(portfolio_features.get("sector_exposure", 0.0)),
            "country_exposure": float(portfolio_features.get("country_exposure", 0.0)),
            "region_exposure": float(portfolio_features.get("region_exposure", 0.0)),
            "currency_exposure": float(portfolio_features.get("currency_exposure", 0.0)),
            "hhi": float(portfolio_features.get("hhi", float(np.square(baseline).sum()))),
            "effective_holdings": float(portfolio_features.get("effective_holdings", 1 / max(np.square(baseline).sum(), 1e-12))),
            "turnover_used": float(portfolio_features.get("turnover_used", 0.0)),
            "remaining_turnover_budget": float(portfolio_features.get("remaining_turnover_budget", 0.0)),
            "max_name_headroom": max(0.0, float(portfolio_features.get("max_single_name_weight", 0.05)) - baseline[i]),
            "sector_limit_headroom": float(portfolio_features.get("sector_limit_headroom", 0.0)),
            "country_limit_headroom": float(portfolio_features.get("country_limit_headroom", 0.0)),
            "currency_limit_headroom": float(portfolio_features.get("currency_limit_headroom", 0.0)),
            "hard_eligibility_mask": float(eligible[i]),
            "review_required_flag": float(bool(cross.get("regime_review_required_flag", pd.Series(False, index=cross.index)).iloc[i])),
            "exclusion_flag": float(not eligible[i]),
        }
        for feature in BASE_FEATURES:
            if feature not in row:
                value = _column(cross, feature, np.nan).iloc[i]
                if pd.isna(value):
                    value = _column(temporal, feature, 0.0).iloc[i]
                row[feature] = float(0.0 if pd.isna(value) else value)
        rows.append([row[name] for name in BASE_FEATURES])
    cash_row = [0.0 for _ in BASE_FEATURES]
    cash_row[BASE_FEATURES.index("cash_weight")] = float(portfolio_features.get("cash_weight", 0.0))
    cash_row[BASE_FEATURES.index("hard_eligibility_mask")] = 1.0
    observation = np.asarray(rows + [cash_row], dtype=float)
    observation = np.nan_to_num(observation, nan=0.0, posinf=0.0, neginf=0.0)
    return DRLState(
        observation=observation,
        asset_ids=asset_ids + ("CASH",),
        feature_names=tuple(BASE_FEATURES),
        eligibility_mask=np.concatenate([eligible, np.array([True])]),
        baseline_weights=np.concatenate([baseline, np.array([float(portfolio_features.get("cash_weight", 0.0))])]),
        current_weights=np.concatenate([current, np.array([0.0])]),
        cash_index=len(asset_ids),
    )
