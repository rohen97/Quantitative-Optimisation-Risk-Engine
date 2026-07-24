from __future__ import annotations

import pandas as pd

from src.reporting.models import ICDataBundle


def build_drl_governance(bundle: ICDataBundle) -> dict[str, pd.DataFrame]:
    return {
        "acceptance": bundle.frames.get("drl_acceptance", pd.DataFrame()),
        "constraints": bundle.frames.get("drl_constraints", pd.DataFrame()),
        "trade_list": bundle.frames.get("drl_trade_list", pd.DataFrame()),
    }


def build_drl_governance_outputs(bundle: ICDataBundle) -> dict[str, pd.DataFrame]:
    acceptance = bundle.frames.get("drl_acceptance", pd.DataFrame()).copy()
    constraints = bundle.frames.get("drl_constraints", pd.DataFrame()).copy()
    seed = bundle.frames.get("drl_seed_results", pd.DataFrame()).copy()
    trade = bundle.frames.get("drl_trade_list", pd.DataFrame()).copy()
    benchmark = bundle.frames.get("drl_benchmark_comparison", pd.DataFrame()).copy()
    reward = bundle.frames.get("drl_reward_decomposition", pd.DataFrame()).copy()
    regime = bundle.frames.get("drl_regime_agent_weights", pd.DataFrame()).copy()
    features = bundle.frames.get("drl_feature_attributions", pd.DataFrame()).copy()
    asset_time = bundle.frames.get("drl_asset_time_attributions", pd.DataFrame()).copy()
    summary_rows = []
    status = "Unavailable"
    rejection = ""
    blend = pd.NA
    if not acceptance.empty:
        row = acceptance.iloc[-1]
        status = str(row.get("selected_weights_source", row.get("acceptance_status", row.get("accepted", "Unavailable"))))
        rejection = str(row.get("rejection_reasons", row.get("drl_rejection_reasons", "")))
        blend = row.get("blend_weight_drl", row.get("maximum_drl_blend_weight", pd.NA))
    summary_rows.append(
        {
            "drl_acceptance_status": status,
            "rejection_reasons": rejection,
            "blend_percentage": blend,
            "rejected_proposals_visible": True,
            "seed_stability_rows": len(seed),
            "walk_forward_performance_available": not bundle.frames.get("drl_training_summary", pd.DataFrame()).empty,
            "benchmark_performance_available": not benchmark.empty,
            "reward_decomposition_available": not reward.empty,
            "regime_specialist_blend_available": not regime.empty,
            "top_feature_attributions_available": not features.empty,
            "top_asset_time_attributions_available": not asset_time.empty,
            "attribution_language": "model attribution, not causality",
        }
    )
    constraint_trace = constraints.copy()
    if not trade.empty:
        keep = [column for column in ("security_id", "ticker", "baseline_weight", "raw_drl_weight", "projected_drl_weight", "accepted_blended_weight", "acceptance_status") if column in trade]
        if keep:
            constraint_trace = trade[keep].merge(constraint_trace, on=[column for column in ("security_id", "ticker") if column in keep and column in constraint_trace], how="left") if not constraint_trace.empty else trade[keep]
    return {
        "drl_governance_summary": pd.DataFrame(summary_rows),
        "drl_constraint_trace": constraint_trace,
        "drl_seed_summary": seed,
    }
