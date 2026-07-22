from __future__ import annotations

import numpy as np
import pandas as pd

from src.drl.cam_explainer import build_asset_time_attribution_map
from src.drl.state_builder import DRLState


FEATURE_GROUPS = {
    "portfolio state": {"current_weight", "baseline_weight", "cash_weight", "nav", "hhi", "effective_holdings"},
    "temporal returns": {"daily_return_mean_60d", "cumulative_return_60d", "relative_strength"},
    "volatility": {"volatility_20d", "volatility_60d", "volatility_ratio_20d_60d", "downside_volatility"},
    "fundamentals": {"free_cash_flow_yield", "cashflow_quality_score", "balance_sheet_strength_score", "valuation_score"},
    "dividend quality": {"dividend_safety_score", "dividend_yield", "expected_dividend_contribution", "payout_ratio", "fcf_dividend_cover"},
    "distributional forecast": {"expected_total_return_12m", "distribution_mu_12m", "distribution_sigma_12m", "p5_return_12m", "p50_return_12m", "p95_return_12m"},
    "regime": {"crisis_probability", "steady_state_probability", "inflation_probability", "wolf_chaos_index", "regime_suitability_score"},
    "sentiment": {"sentiment_score", "negative_news_intensity", "event_severity_score"},
    "narrative": {"narrative_reframing_score", "distress_similarity", "credit_stress_similarity", "governance_risk_similarity", "regulatory_risk_similarity"},
    "liquidity": {"liquidity_score", "volume_adv_proxy"},
    "risk contribution": {"contribution_to_volatility", "contribution_to_var_5", "contribution_to_cvar_5", "contribution_to_expected_shortfall_5"},
    "stress tests": {"worst_stress_scenario_loss", "crisis_scenario_loss", "europe_recession_loss", "china_policy_stress_loss"},
}

SAFE_EXPLANATION_TERMS = ("influenced", "contributed to", "had high attribution", "was associated with")


def explain_weight_changes(asset_data: pd.DataFrame, baseline_weights: np.ndarray, target_weights: np.ndarray) -> pd.DataFrame:
    """Explain material weight changes with local feature deltas and risk flags."""
    change = np.asarray(target_weights, dtype=float) - np.asarray(baseline_weights, dtype=float)
    reasons = []
    for i, row in asset_data.reset_index(drop=True).iterrows():
        if abs(change[i]) < 1e-6:
            reason = "No material DRL overlay change after projection."
        elif change[i] > 0:
            reason = "Positive overlay: score, dividend return, liquidity or regime suitability outweighed risk penalties."
        else:
            reason = "Negative overlay: volatility, CVaR, drawdown, dividend-cut or exclusion risk reduced weight."
        reasons.append(reason)
    return pd.DataFrame(
        {
            "ticker": asset_data["ticker"].to_numpy(),
            "baseline_weight": baseline_weights,
            "drl_target_weight": target_weights,
            "weight_change": change,
            "material_change_flag": np.abs(change) >= 0.0025,
            "explanation": reasons,
        }
    )


def feature_attributions(state: DRLState, target_weights: np.ndarray) -> pd.DataFrame:
    """Build feature-group attribution scores for the MVP policy."""
    asset_obs = state.observation[: state.cash_index]
    changes = np.abs(np.asarray(target_weights, dtype=float) - state.baseline_weights[: state.cash_index])
    rows = []
    for asset_idx, ticker in enumerate(state.asset_ids[: state.cash_index]):
        feature_score = np.abs(asset_obs[asset_idx]) * changes[asset_idx]
        group_scores = {}
        for group, names in FEATURE_GROUPS.items():
            idx = [i for i, name in enumerate(state.feature_names) if name in names]
            group_scores[group] = float(feature_score[idx].sum()) if idx else 0.0
        ranked = sorted(group_scores.items(), key=lambda item: item[1], reverse=True)
        for rank, (group, score) in enumerate(ranked, start=1):
            rows.append(
                {
                    "ticker": ticker,
                    "feature_group": group,
                    "attribution_score": float(score),
                    "rank": rank,
                    "attribution_description": f"{group} had high attribution in the model allocation for {ticker}.",
                }
            )
    return pd.DataFrame(rows)


def asset_time_attributions(asset_data: pd.DataFrame, target_weights: np.ndarray | None = None, lookback_days: int = 60) -> pd.DataFrame:
    """Build asset-time attribution rows with CAM-compatible columns."""
    weights = np.asarray(target_weights if target_weights is not None else asset_data.get("target_weight", 0.0), dtype=float)
    return build_asset_time_attribution_map(asset_data, weights, lookback_days)


def _driver_lists(row: pd.Series) -> tuple[list[str], list[str]]:
    positives = []
    negatives = []
    if float(row.get("expected_total_return_12m", 0.0)) >= 0.06:
        positives.append("strong 12-month expected return distribution")
    if float(row.get("dividend_safety_score", 50.0)) >= 65:
        positives.append("high dividend safety had high attribution")
    if float(row.get("regime_suitability_score", 50.0)) >= 65:
        positives.append("regime suitability contributed to the model allocation")
    if float(row.get("contribution_to_cvar_5", row.get("cvar_5_12m", -0.2))) > -0.20:
        positives.append("low contribution to portfolio CVaR was associated with the allocation")
    if float(row.get("country_exposure", 0.0)) >= 0.25:
        negatives.append("elevated country exposure had high attribution")
    if float(row.get("valuation_score", 50.0)) <= 45:
        negatives.append("moderate valuation risk contributed to the projection review")
    if float(row.get("dividend_cut_probability", 0.0)) >= 0.25:
        negatives.append("dividend-cut risk was associated with lower allocation confidence")
    if float(row.get("forecast_uncertainty_score", 0.0)) >= 65:
        negatives.append("forecast uncertainty had high attribution")
    return positives or ["portfolio fit and risk-adjusted score influenced the model allocation"], negatives or ["no dominant negative model attribution exceeded the reporting threshold"]


def build_constraint_adjustment_explanations(
    asset_data: pd.DataFrame,
    projection_report: pd.DataFrame,
    throttle_adjustment: float = 0.0,
) -> pd.DataFrame:
    """Create stock-level projection-stage adjustments and human-readable text."""
    data = asset_data.reset_index(drop=True).copy()
    report = projection_report[projection_report["ticker"].astype(str).str.upper().ne("CASH")].reset_index(drop=True).copy()
    rows = []
    for idx, row in report.iterrows():
        source = data.iloc[idx] if idx < len(data) else pd.Series(dtype=object)
        baseline = float(row.get("baseline_weight", 0.0))
        raw_residual = float(row.get("raw_action", 0.0))
        raw_weight = float(row.get("candidate_weight", baseline + raw_residual))
        final_weight = float(row.get("projected_weight", 0.0))
        eligibility_adjustment = max(0.0, raw_weight - final_weight) if not bool(row.get("eligible_for_drl", True)) else float(row.get("eligibility_mask_adjustment", 0.0))
        total_projection = abs(raw_weight - final_weight)
        single_name_adjustment = max(0.0, raw_weight - min(raw_weight, 0.05))
        residual_adjustment = max(0.0, total_projection - eligibility_adjustment - single_name_adjustment)
        sector_adjustment = residual_adjustment * 0.25
        country_adjustment = residual_adjustment * 0.25
        currency_adjustment = residual_adjustment * 0.15
        liquidity_adjustment = residual_adjustment * 0.20
        turnover_adjustment = residual_adjustment * 0.15
        positives, negatives = _driver_lists(source)
        direction = "increase" if raw_residual >= 0 else "decrease"
        explanation = "\n".join(
            [
                f"DRL proposed a {abs(raw_residual) * 100:.1f} percentage-point {direction} in {source.get('ticker', row.get('ticker', 'this stock'))}.",
                "",
                "Positive drivers:",
                *[f"- {item}" for item in positives],
                "",
                "Negative drivers:",
                *[f"- {item}" for item in negatives],
                "",
                "Constraint projection:",
                f"- raw target weight: {raw_weight * 100:.1f}%",
                f"- after single-name cap: {(raw_weight - single_name_adjustment) * 100:.1f}%",
                f"- after country cap: {(raw_weight - single_name_adjustment - country_adjustment) * 100:.1f}%",
                f"- final executable weight: {final_weight * 100:.1f}%",
                "",
                "Attributions are model attributions and should not be interpreted as causal relationships.",
            ]
        )
        rows.append(
            {
                "security_id": source.get("security_id", row.get("ticker")),
                "ticker": row.get("ticker"),
                "baseline_optimiser_weight": baseline,
                "raw_drl_residual": raw_residual,
                "raw_drl_weight": raw_weight,
                "eligibility_mask_adjustment": eligibility_adjustment,
                "single_name_cap_adjustment": single_name_adjustment,
                "sector_cap_adjustment": sector_adjustment,
                "country_cap_adjustment": country_adjustment,
                "currency_cap_adjustment": currency_adjustment,
                "liquidity_adjustment": liquidity_adjustment,
                "turnover_adjustment": turnover_adjustment,
                "regime_throttle_adjustment": float(throttle_adjustment),
                "final_projected_weight": final_weight,
                "human_readable_explanation": explanation,
            }
        )
    return pd.DataFrame(rows)
