from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DRLAcceptanceDecision:
    accepted: bool
    selected_weights_source: str
    rejection_reasons: tuple[str, ...]
    blend_weight_drl: float
    blend_weight_baseline: float


BENCHMARK_NAMES = [
    "current_portfolio",
    "cash",
    "buy_and_hold",
    "equal_weight_eligible",
    "score_weighted",
    "risk_parity",
    "mean_variance",
    "cvar_constrained",
    "dividend_income_constrained",
    "regime_aware_constrained",
    "selected_recommended_optimiser",
    "constrained_regime_gated_drl",
]


def _column(data: pd.DataFrame, column: str, default: float) -> pd.Series:
    if column in data:
        return pd.to_numeric(data[column], errors="coerce").fillna(default)
    return pd.Series(default, index=data.index, dtype=float)


def _normalise(weights: np.ndarray) -> np.ndarray:
    w = np.nan_to_num(np.asarray(weights, dtype=float), nan=0.0, posinf=0.0, neginf=0.0).clip(min=0.0)
    total = float(w.sum())
    return w / total if total > 0 else w


def _strategy_weights(asset_data: pd.DataFrame, baseline_weights: np.ndarray, drl_weights: np.ndarray, name: str) -> np.ndarray:
    n = len(asset_data)
    eligible = asset_data.get("eligible_for_drl", asset_data.get("eligible_for_optimisation", pd.Series(True, index=asset_data.index)))
    eligible = eligible.fillna(False).astype(bool).to_numpy() if hasattr(eligible, "fillna") else np.ones(n, dtype=bool)
    if name == "cash":
        return np.zeros(n)
    if name in {"current_portfolio", "buy_and_hold"}:
        return _normalise(_column(asset_data, "current_weight", 0.0).to_numpy(dtype=float))
    if name == "equal_weight_eligible":
        return _normalise(np.where(eligible, 1.0, 0.0))
    if name == "score_weighted":
        return _normalise(np.where(eligible, _column(asset_data, "final_recommendation_score", 50).clip(lower=0), 0.0))
    if name == "risk_parity":
        vol = _column(asset_data, "expected_volatility_12m", 0.20).clip(lower=0.03)
        return _normalise(np.where(eligible, 1 / vol, 0.0))
    if name == "mean_variance":
        score = _column(asset_data, "expected_total_return_12m", 0.05) - 5.0 * np.square(_column(asset_data, "expected_volatility_12m", 0.20))
        return _normalise(np.where(eligible, score.clip(lower=0), 0.0))
    if name == "cvar_constrained":
        return _normalise(np.where(eligible, 1 / _column(asset_data, "cvar_5_12m", -0.25).abs().clip(lower=0.05), 0.0))
    if name == "dividend_income_constrained":
        return _normalise(np.where(eligible, _column(asset_data, "expected_dividend_return_12m", 0.03).clip(lower=0), 0.0))
    if name == "regime_aware_constrained":
        return _normalise(np.where(eligible, _column(asset_data, "regime_suitability_score", 50).clip(lower=0), 0.0))
    if name == "constrained_regime_gated_drl":
        return _normalise(drl_weights)
    return _normalise(baseline_weights)


def calculate_benchmark_metrics(
    asset_data: pd.DataFrame,
    weights: np.ndarray,
    benchmark_name: str,
    comparison_type: str,
    information_set: str,
    pre_trade_weights: np.ndarray | None = None,
) -> dict[str, float | str | bool]:
    """Calculate benchmark metrics under an explicitly labelled information set."""
    w = _normalise(weights)
    previous = _normalise(pre_trade_weights) if pre_trade_weights is not None and np.asarray(pre_trade_weights).sum() > 0 else np.zeros_like(w)
    expected_return = float((w * _column(asset_data, "expected_total_return_12m", 0.0)).sum())
    volatility = float((w * _column(asset_data, "expected_volatility_12m", 0.20)).sum())
    dividend_yield = float((w * _column(asset_data, "expected_dividend_return_12m", _column(asset_data, "dividend_yield", 0.03))).sum())
    cvar = float((w * _column(asset_data, "cvar_5_12m", -0.25)).sum())
    es = float((w * _column(asset_data, "expected_shortfall_5_12m", -0.25)).sum())
    var = float((w * _column(asset_data, "var_5_12m", -0.15)).sum())
    drawdown = float((w * _column(asset_data, "large_drawdown_probability_12m", 0.20)).sum())
    turnover = float(np.abs(w - previous).sum())
    hhi = float(np.square(w).sum())
    transaction_cost = turnover * 0.0017
    net_return = expected_return + dividend_yield - transaction_cost
    downside = max(abs(var), 1e-8)
    return {
        "comparison_type": comparison_type,
        "information_set": information_set,
        "benchmark": benchmark_name,
        "annualised_net_return": net_return,
        "annualised_volatility": volatility,
        "sharpe": net_return / max(volatility, 1e-8),
        "sortino": net_return / max(abs(es), 1e-8),
        "calmar": net_return / max(drawdown, 1e-8),
        "maximum_drawdown": -drawdown,
        "var": var,
        "cvar": cvar,
        "expected_shortfall": es,
        "omega_ratio": max(net_return, 0.0) / max(abs(min(net_return, 0.0)) + downside, 1e-8),
        "tail_ratio": abs(float((w * _column(asset_data, "p95_return_12m", 0.20)).sum())) / max(abs(float((w * _column(asset_data, "p5_return_12m", -0.20)).sum())), 1e-8),
        "portfolio_dividend_yield": dividend_yield,
        "dividend_income": dividend_yield,
        "dividend_cut_risk": float((w * _column(asset_data, "dividend_cut_probability", 0.10)).sum()),
        "turnover": turnover,
        "estimated_transaction_cost": transaction_cost,
        "hhi": hhi,
        "effective_holdings": 1 / max(hhi, 1e-12),
        "worst_stress_loss": float((w * _column(asset_data, "worst_stress_scenario_loss", _column(asset_data, "cvar_5_12m", -0.25))).sum()),
        "constraint_violations": 0,
        "average_weight_change": float(np.abs(w - previous).mean()),
        "weight_stability": 1.0 / (1.0 + float(np.abs(w - previous).sum())),
        "worst_rolling_12m_return": min(net_return, var, cvar),
        "richer_state_than_mvo": comparison_type == "full_wolf" and benchmark_name == "constrained_regime_gated_drl",
    }


def build_benchmark_comparison(asset_data: pd.DataFrame, baseline_weights: np.ndarray, drl_weights: np.ndarray) -> pd.DataFrame:
    """Compare DRL against classical benchmarks under fair and full-Wolf labels."""
    rows = []
    current = _column(asset_data, "current_weight", 0.0).to_numpy(dtype=float)
    for comparison_type, information_set in [
        ("fair_information_set", "returns, volatility, covariance, current weights, cash"),
        ("full_wolf", "scorecard, distributional forecasts, regime, sentiment, narrative, risk, stress, liquidity"),
    ]:
        for name in BENCHMARK_NAMES:
            weights = _strategy_weights(asset_data, baseline_weights, drl_weights, name)
            rows.append(calculate_benchmark_metrics(asset_data, weights, name, comparison_type, information_set, current))
    return pd.DataFrame(rows)


def build_seed_evaluation(seed_results: pd.DataFrame) -> pd.DataFrame:
    """Report every seed plus distribution summary; never only the best seed."""
    rows = []
    for _, row in seed_results.iterrows():
        seed = int(row["seed"])
        if str(row.get("model_mode", "")).lower() == "real":
            turnover = float(row.get("annualised_incremental_turnover", 0.0))
            rows.append(
                {
                    "row_type": "seed",
                    "seed": seed,
                    "total_net_return": float(row.get("test_total_net_return", 0.0)),
                    "sharpe": float(row.get("test_net_sharpe", 0.0)),
                    "information_ratio": float(row.get("test_information_ratio", 0.0)),
                    "cvar": float(row.get("test_cvar", 0.0)),
                    "expected_shortfall": float(row.get("test_expected_shortfall", row.get("test_cvar", 0.0))),
                    "maximum_drawdown": float(row.get("test_maximum_drawdown", 0.0)),
                    "turnover": turnover,
                    "dividend_yield": 0.0,
                    "transaction_costs": float(row.get("transaction_costs", 0.0)),
                    "constraint_violations": int(row.get("constraint_violations", 0)),
                    "policy_weight_stability": 1.0 / (1.0 + turnover),
                    "oos_observations": int(row.get("test_observations", 0)),
                    "active_return_ci_lower_95": float(row.get("active_return_ci_lower_95", 0.0)),
                }
            )
            continue
        total = float(row.get("test_reward", row.get("total_reward", 0.0)))
        cvar = -abs(float(row.get("cvar_penalty", row.get("risk_penalty", 0.0))))
        es = -abs(float(row.get("expected_shortfall_penalty", row.get("risk_penalty", 0.0))))
        drawdown = -abs(float(row.get("drawdown_penalty", 0.0)))
        turnover = float(row.get("turnover_penalty", 0.0)) / 0.05 if float(row.get("turnover_penalty", 0.0)) else 0.0
        rows.append(
            {
                "row_type": "seed",
                "seed": seed,
                "total_net_return": total,
                "sharpe": total / max(abs(cvar), 1e-8),
                "cvar": cvar,
                "expected_shortfall": es,
                "maximum_drawdown": drawdown,
                "turnover": turnover,
                "dividend_yield": float(row.get("dividend_component", row.get("dividend_income_component", 0.0))),
                "transaction_costs": float(row.get("transaction_cost_penalty", row.get("transaction_cost", 0.0))),
                "constraint_violations": int(row.get("constraint_violations", 0)),
                "policy_weight_stability": 1.0 / (1.0 + turnover),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    metrics = [
        "total_net_return",
        "sharpe",
        "cvar",
        "expected_shortfall",
        "maximum_drawdown",
        "turnover",
        "dividend_yield",
        "transaction_costs",
        "constraint_violations",
        "policy_weight_stability",
    ]
    metrics.extend(
        column
        for column in ("information_ratio", "oos_observations", "active_return_ci_lower_95")
        if column in frame
    )
    summary_rows = []
    for label in ["mean", "median", "standard_deviation", "interquartile_range"]:
        summary = {"row_type": label, "seed": np.nan}
        for metric in metrics:
            series = pd.to_numeric(frame[metric], errors="coerce")
            if label == "mean":
                value = series.mean()
            elif label == "median":
                value = series.median()
            elif label == "standard_deviation":
                value = series.std(ddof=0)
            else:
                value = series.quantile(0.75) - series.quantile(0.25)
            summary[metric] = float(value)
        summary_rows.append(summary)
    metric = "total_net_return"
    best = frame.loc[frame[metric].idxmax()].copy()
    best["row_type"] = "best_seed"
    worst = frame.loc[frame[metric].idxmin()].copy()
    worst["row_type"] = "worst_seed"
    return pd.concat([frame, pd.DataFrame(summary_rows), pd.DataFrame([best, worst])], ignore_index=True)


def decide_drl_acceptance(
    weights: np.ndarray,
    baseline_weights: np.ndarray,
    benchmark: pd.DataFrame,
    throttle,
    constraints: dict | None = None,
    config: dict | None = None,
    projection_report: pd.DataFrame | None = None,
    eligibility_mask: np.ndarray | None = None,
    seed_results: pd.DataFrame | None = None,
) -> DRLAcceptanceDecision:
    """Apply conservative acceptance/rejection rules before deployment."""
    cfg = config or {}
    limits = constraints or {}
    reasons: list[str] = []
    w = np.asarray(weights, dtype=float)
    baseline = np.asarray(baseline_weights, dtype=float)
    tolerance = float(cfg.get("weight_sum_tolerance", 1e-4))

    def add_reason(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    if w.size == 0 or not np.isfinite(w).all():
        add_reason("non_finite_weights")
    if np.any(w < -1e-10):
        add_reason("negative_long_only_weight")
    if abs(float(w.sum()) - 1.0) > tolerance:
        add_reason("weights_do_not_sum_to_one")
    if baseline.size != w.size or not np.isfinite(baseline).all():
        add_reason("invalid_baseline_weights")
    elif baseline.size == w.size:
        incremental_turnover = 0.5 * float(np.abs(w - baseline).sum())
        if incremental_turnover > float(limits.get("maximum_turnover", 1.0)):
            add_reason("incremental_overlay_turnover_exceeds_hard_limit")
    if eligibility_mask is None:
        add_reason("missing_required_eligibility_mask")
    else:
        mask = np.asarray(eligibility_mask, dtype=bool)
        equity_weights = w[: mask.size]
        if mask.size == 0 or equity_weights.size != mask.size:
            add_reason("missing_required_eligibility_mask")
        elif np.any((~mask) & (equity_weights > tolerance)):
            add_reason("hard_constraint_violation")
    if projection_report is not None and not projection_report.empty:
        if "feasible" in projection_report and not bool(projection_report["feasible"].fillna(False).all()):
            add_reason("infeasible_projected_action")
        if "fallback_used" in projection_report and bool(projection_report["fallback_used"].fillna(False).any()):
            add_reason("infeasible_projected_action")
        if "eligible_for_drl" in projection_report and "projected_weight" in projection_report:
            projected = pd.to_numeric(projection_report["projected_weight"], errors="coerce").fillna(0.0)
            eligible = projection_report["eligible_for_drl"].fillna(False).astype(bool)
            if bool(((~eligible) & (projected > tolerance)).any()):
                add_reason("hard_constraint_violation")
        if "liquidity_requirement_failed" in projection_report and bool(projection_report["liquidity_requirement_failed"].fillna(False).any()):
            add_reason("liquidity_requirement_fails")
    if getattr(throttle, "fallback_to_baseline", False):
        add_reason("regime_risk_throttle_requires_fallback")
    drl_rows = benchmark[(benchmark["benchmark"].eq("constrained_regime_gated_drl")) & (benchmark["comparison_type"].eq("full_wolf"))]
    if not drl_rows.empty:
        row = drl_rows.iloc[0]
        if float(row.get("constraint_violations", 0)) > 0:
            add_reason("hard_constraint_violation")
        if row["cvar"] < float(limits.get("maximum_portfolio_cvar_5", -1.0)):
            add_reason("portfolio_cvar_exceeds_configured_limit")
        if row["expected_shortfall"] < float(limits.get("maximum_portfolio_expected_shortfall_5", -1.0)):
            add_reason("expected_shortfall_exceeds_configured_limit")
        stress_limit = float(limits.get("maximum_stress_loss", limits.get("maximum_severe_stress_loss", -1.0)))
        if row["worst_stress_loss"] < stress_limit:
            add_reason("stress_test_loss_exceeds_severe_loss_limit")
        if bool(row.get("liquidity_requirement_failed", False)):
            add_reason("liquidity_requirement_fails")
    if float(cfg.get("model_confidence", 1.0)) < float(cfg.get("minimum_model_confidence", 0.50)):
        add_reason("model_confidence_below_threshold")
    if seed_results is not None and not seed_results.empty:
        score_column = "validation_reward" if "validation_reward" in seed_results else "test_reward"
        scores = pd.to_numeric(seed_results.get(score_column, pd.Series(dtype=float)), errors="coerce").dropna()
        if not scores.empty:
            mean_score = float(scores.mean())
            std_score = float(scores.std(ddof=0))
            max_seed_instability = float(cfg.get("maximum_seed_instability_ratio", 0.50))
            minimum_scale = float(cfg.get("minimum_seed_stability_scale", 1e-8))
            real_results = bool(
                "model_mode" in seed_results
                and seed_results["model_mode"].astype(str).str.lower().eq("real").all()
            )
            instability_limit = (
                max_seed_instability
                if real_results
                else max(abs(mean_score) * max_seed_instability, minimum_scale)
            )
            if std_score > instability_limit:
                add_reason("excessive_seed_instability")
            baseline_validation = cfg.get("baseline_validation_score")
            if baseline_validation is not None:
                tolerance_underperformance = float(cfg.get("validation_underperformance_tolerance", 0.0))
                if float(scores.max()) < float(baseline_validation) - tolerance_underperformance:
                    add_reason("validation_underperformance_beyond_tolerance")
        if "model_mode" in seed_results and seed_results["model_mode"].astype(str).str.lower().eq("real").all():
            selected = seed_results.loc[
                seed_results.get(
                    "selected_by_validation",
                    pd.Series(False, index=seed_results.index),
                ).fillna(False).astype(bool)
            ]
            if selected.empty and "validation_reward" in seed_results:
                selected = seed_results.loc[[seed_results["validation_reward"].astype(float).idxmax()]]
            if not selected.empty:
                selected_row = selected.iloc[0]
                if int(selected_row.get("test_observations", 0)) < int(
                    cfg.get("minimum_oos_observations", 12)
                ):
                    add_reason("insufficient_independent_oos_observations")
                if float(selected_row.get("test_net_sharpe", -np.inf)) <= float(
                    selected_row.get("baseline_test_sharpe", np.inf)
                ) + float(cfg.get("minimum_oos_sharpe_improvement", 0.0)):
                    add_reason("drl_did_not_improve_oos_net_sharpe")
                if float(selected_row.get("test_maximum_drawdown", -np.inf)) < float(
                    selected_row.get("baseline_test_maximum_drawdown", -np.inf)
                ) - float(cfg.get("oos_tail_risk_tolerance", 0.0)):
                    add_reason("drl_worsened_oos_drawdown")
                if float(selected_row.get("test_cvar", -np.inf)) < float(
                    selected_row.get("baseline_test_cvar", -np.inf)
                ) - float(cfg.get("oos_tail_risk_tolerance", 0.0)):
                    add_reason("drl_worsened_oos_cvar")
                if bool(cfg.get("require_positive_active_return_ci", True)) and float(
                    selected_row.get("active_return_ci_lower_95", -np.inf)
                ) <= 0.0:
                    add_reason("oos_active_return_not_statistically_positive")
                if float(selected_row.get("annualised_incremental_turnover", np.inf)) > float(
                    limits.get("annual_turnover_limit", cfg.get("annual_turnover_limit", 0.35))
                ):
                    add_reason("annual_incremental_overlay_turnover_exceeds_limit")
    if bool(cfg.get("test_leakage_detected", False)):
        add_reason("test_leakage_detected")
    if bool(cfg.get("historical_validation_guard_triggered", False)):
        add_reason("all_ppo_seeds_failed_validation_guard")
    required_shadow_cycles = int(cfg.get("required_prospective_shadow_cycles", 0))
    completed_shadow_cycles = int(cfg.get("prospective_shadow_cycles_completed", 0))
    if completed_shadow_cycles < required_shadow_cycles:
        add_reason("insufficient_prospective_shadow_cycles")
    if bool(cfg.get("hard_constraint_violation", False)):
        add_reason("hard_constraint_violation")
    if bool(cfg.get("liquidity_requirement_failed", False)):
        add_reason("liquidity_requirement_fails")

    mode = str(cfg.get("deployment_mode", "blend")).lower().replace(" ", "_").replace("-", "_")
    max_blend = max(0.0, min(float(cfg.get("maximum_drl_blend", 0.25)), 0.49))
    full_replacement = bool(cfg.get("allow_full_drl_replacement", False))
    if reasons or mode == "reject":
        return DRLAcceptanceDecision(False, "baseline_optimiser", tuple(reasons or ["deployment_mode_reject"]), 0.0, 1.0)
    if mode == "accept_challenger" and full_replacement:
        return DRLAcceptanceDecision(True, "drl_challenger", tuple(), 1.0, 0.0)
    blend = max(0.0, min(max_blend, float(cfg.get("blend_weight_drl", max_blend))))
    selected_source = "drl_challenger_blend" if mode == "accept_challenger" else "baseline_drl_blend"
    return DRLAcceptanceDecision(True, selected_source, tuple(), blend, 1.0 - blend)


def compare_against_benchmark(backtest_results: pd.DataFrame) -> pd.DataFrame:
    """Compare DRL overlay against the selected classical optimiser."""
    baseline = backtest_results[backtest_results["portfolio"].eq("baseline_classical_optimiser")]
    drl = backtest_results[backtest_results["portfolio"].eq("constrained_regime_gated_drl")]
    rows = []
    for window in sorted(set(backtest_results["window"])):
        b = baseline[baseline["window"].eq(window)].iloc[0]
        d = drl[drl["window"].eq(window)].iloc[0]
        rows.append(
            {
                "window": window,
                "net_risk_adjusted_return_delta": d["net_risk_adjusted_return"] - b["net_risk_adjusted_return"],
                "expected_return_delta": d["expected_total_return"] - b["expected_total_return"],
                "cvar_delta": d["cvar_5"] - b["cvar_5"],
                "drawdown_probability_delta": d["drawdown_probability"] - b["drawdown_probability"],
                "dividend_yield_delta": d["expected_dividend_yield"] - b["expected_dividend_yield"],
                "drl_success_flag": bool(
                    d["net_risk_adjusted_return"] >= b["net_risk_adjusted_return"]
                    and d["cvar_5"] >= b["cvar_5"]
                    and d["drawdown_probability"] <= b["drawdown_probability"] + 0.02
                ),
            }
        )
    return pd.DataFrame(rows)
