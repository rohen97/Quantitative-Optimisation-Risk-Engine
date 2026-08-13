import numpy as np
import pandas as pd

from src.drl.benchmark import (
    DRLAcceptanceDecision,
    build_benchmark_comparison,
    build_seed_evaluation,
    compare_against_benchmark,
    decide_drl_acceptance,
)
from src.drl.evaluation import build_backtest_results
from src.drl.regime_gating import calculate_risk_throttle


def test_drl_benchmark_comparison_has_success_flag():
    data = pd.DataFrame(
        {
            "expected_total_return_12m": [0.08, 0.04],
            "expected_dividend_return_12m": [0.03, 0.02],
            "expected_volatility_12m": [0.18, 0.22],
            "cvar_5_12m": [-0.20, -0.25],
            "expected_shortfall_5_12m": [-0.21, -0.26],
            "large_drawdown_probability_12m": [0.2, 0.25],
            "dividend_cut_probability": [0.1, 0.2],
        }
    )
    backtest = build_backtest_results(data, np.array([0.5, 0.5]), np.array([0.6, 0.4]))
    comparison = compare_against_benchmark(backtest)
    assert "drl_success_flag" in comparison
    assert set(comparison["window"]) == {"train", "validation", "test", "worst_window"}


def test_full_drl_benchmark_comparison_labels_information_sets_and_metrics():
    data = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "eligible_for_drl": [True, True],
            "current_weight": [0.4, 0.6],
            "final_recommendation_score": [80, 50],
            "expected_total_return_12m": [0.08, 0.04],
            "expected_dividend_return_12m": [0.03, 0.02],
            "expected_volatility_12m": [0.18, 0.22],
            "var_5_12m": [-0.15, -0.20],
            "cvar_5_12m": [-0.20, -0.25],
            "expected_shortfall_5_12m": [-0.21, -0.26],
            "large_drawdown_probability_12m": [0.2, 0.25],
            "dividend_cut_probability": [0.1, 0.2],
            "p95_return_12m": [0.20, 0.15],
            "p5_return_12m": [-0.15, -0.20],
        }
    )
    comparison = build_benchmark_comparison(data, np.array([0.5, 0.5]), np.array([0.6, 0.4]))
    required = {
        "annualised_net_return",
        "annualised_volatility",
        "sharpe",
        "sortino",
        "calmar",
        "maximum_drawdown",
        "var",
        "cvar",
        "expected_shortfall",
        "omega_ratio",
        "tail_ratio",
        "portfolio_dividend_yield",
        "dividend_income",
        "dividend_cut_risk",
        "turnover",
        "estimated_transaction_cost",
        "hhi",
        "effective_holdings",
        "worst_stress_loss",
        "constraint_violations",
        "average_weight_change",
        "weight_stability",
        "worst_rolling_12m_return",
    }
    assert required.issubset(comparison.columns)
    assert {"fair_information_set", "full_wolf"} == set(comparison["comparison_type"])
    assert "selected_recommended_optimiser" in set(comparison["benchmark"])
    assert comparison["estimated_transaction_cost"].ge(0).all()
    assert comparison["annualised_net_return"].notna().all()
    assert comparison[comparison["comparison_type"].eq("full_wolf")]["richer_state_than_mvo"].any()


def test_seed_evaluation_reports_all_seeds_and_summary():
    seed_results = pd.DataFrame(
        {
            "seed": [1, 2, 3, 4, 5],
            "test_reward": [0.01, 0.02, 0.0, 0.03, 0.015],
            "cvar_penalty": [0.1] * 5,
            "expected_shortfall_penalty": [0.12] * 5,
            "drawdown_penalty": [0.05] * 5,
            "turnover_penalty": [0.01] * 5,
        }
    )
    report = build_seed_evaluation(seed_results)
    assert (report["row_type"].eq("seed")).sum() == 5
    assert {"mean", "median", "standard_deviation", "best_seed", "worst_seed", "interquartile_range"}.issubset(set(report["row_type"]))
    summary = report[report["row_type"].isin(["mean", "median", "standard_deviation", "interquartile_range"])]
    for column in [
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
    ]:
        assert summary[column].notna().all()


def test_drl_acceptance_rejects_throttle_fallback_and_defaults_to_blend():
    benchmark = pd.DataFrame(
        [
            {
                "benchmark": "constrained_regime_gated_drl",
                "comparison_type": "full_wolf",
                "cvar": -0.20,
                "expected_shortfall": -0.20,
                "worst_stress_loss": -0.20,
                "turnover": 0.10,
            }
        ]
    )
    throttle = calculate_risk_throttle(10, 0.1, 0.1, 0.1, 0.1)
    decision = decide_drl_acceptance(
        np.array([0.5, 0.5]),
        np.array([0.5, 0.5]),
        benchmark,
        throttle,
        {},
        {"deployment_mode": "blend"},
        eligibility_mask=np.array([True, True]),
    )
    assert isinstance(decision, DRLAcceptanceDecision)
    assert decision.accepted
    assert decision.blend_weight_drl == 0.25
    fallback = calculate_risk_throttle(90, 0.1, 0.1, 0.1, 0.1)
    rejected = decide_drl_acceptance(
        np.array([0.5, 0.5]),
        np.array([0.5, 0.5]),
        benchmark,
        fallback,
        {},
        {},
        eligibility_mask=np.array([True, True]),
    )
    assert not rejected.accepted
    assert "regime_risk_throttle_requires_fallback" in rejected.rejection_reasons


def test_drl_acceptance_rejects_missing_mask_projection_failure_and_unstable_seeds():
    benchmark = pd.DataFrame(
        [
            {
                "benchmark": "constrained_regime_gated_drl",
                "comparison_type": "full_wolf",
                "cvar": -0.20,
                "expected_shortfall": -0.20,
                "worst_stress_loss": -0.20,
                "turnover": 0.10,
                "constraint_violations": 0,
            }
        ]
    )
    throttle = calculate_risk_throttle(10, 0.1, 0.1, 0.1, 0.1)
    projection_report = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "projected_weight": [0.0],
            "eligible_for_drl": [True],
            "feasible": [False],
            "fallback_used": [True],
        }
    )
    seed_results = pd.DataFrame({"seed": [1, 2, 3, 4, 5], "validation_reward": [0.10, -0.10, 0.12, -0.11, 0.0]})

    decision = decide_drl_acceptance(
        np.array([1.0]),
        np.array([1.0]),
        benchmark,
        throttle,
        {},
        {"maximum_seed_instability_ratio": 0.10},
        projection_report=projection_report,
        seed_results=seed_results,
    )

    assert not decision.accepted
    assert "missing_required_eligibility_mask" in decision.rejection_reasons
    assert "infeasible_projected_action" in decision.rejection_reasons
    assert "excessive_seed_instability" in decision.rejection_reasons
    assert decision.blend_weight_drl == 0.0
    assert decision.blend_weight_baseline == 1.0


def test_drl_acceptance_rejects_threshold_breaches_and_masked_weights():
    benchmark = pd.DataFrame(
        [
            {
                "benchmark": "constrained_regime_gated_drl",
                "comparison_type": "full_wolf",
                "cvar": -0.35,
                "expected_shortfall": -0.40,
                "worst_stress_loss": -0.45,
                "turnover": 0.50,
                "constraint_violations": 1,
                "liquidity_requirement_failed": True,
            }
        ]
    )
    throttle = calculate_risk_throttle(10, 0.1, 0.1, 0.1, 0.1)
    decision = decide_drl_acceptance(
        np.array([0.95, 0.05]),
        np.array([1.0, 0.0]),
        benchmark,
        throttle,
        {
            "maximum_portfolio_cvar_5": -0.25,
            "maximum_portfolio_expected_shortfall_5": -0.25,
            "maximum_stress_loss": -0.30,
            "maximum_turnover": 0.35,
        },
        {"model_confidence": 0.30, "minimum_model_confidence": 0.50, "test_leakage_detected": True},
        eligibility_mask=np.array([True, False]),
    )

    assert not decision.accepted
    assert {
        "hard_constraint_violation",
        "portfolio_cvar_exceeds_configured_limit",
        "expected_shortfall_exceeds_configured_limit",
        "stress_test_loss_exceeds_severe_loss_limit",
        "liquidity_requirement_fails",
        "model_confidence_below_threshold",
        "test_leakage_detected",
    }.issubset(set(decision.rejection_reasons))
    assert "turnover_exceeds_hard_limit" not in decision.rejection_reasons


def test_drl_acceptance_modes_cap_dry_run_blend_and_allow_explicit_challenger():
    benchmark = pd.DataFrame(
        [
            {
                "benchmark": "constrained_regime_gated_drl",
                "comparison_type": "full_wolf",
                "cvar": -0.20,
                "expected_shortfall": -0.20,
                "worst_stress_loss": -0.20,
                "turnover": 0.10,
            }
        ]
    )
    throttle = calculate_risk_throttle(10, 0.1, 0.1, 0.1, 0.1)
    dry_run = decide_drl_acceptance(
        np.array([0.5, 0.5]),
        np.array([0.5, 0.5]),
        benchmark,
        throttle,
        {},
        {"deployment_mode": "blend", "maximum_drl_blend": 0.25, "blend_weight_drl": 0.90},
        eligibility_mask=np.array([True, True]),
    )
    assert dry_run.accepted
    assert dry_run.selected_weights_source == "baseline_drl_blend"
    assert dry_run.blend_weight_drl == 0.25
    assert dry_run.blend_weight_baseline == 0.75

    lower_confidence = decide_drl_acceptance(
        np.array([0.5, 0.5]),
        np.array([0.5, 0.5]),
        benchmark,
        throttle,
        {},
        {"deployment_mode": "blend", "maximum_drl_blend": 0.25, "blend_weight_drl": 0.10, "model_confidence": 0.60, "minimum_model_confidence": 0.50},
        eligibility_mask=np.array([True, True]),
    )
    assert lower_confidence.accepted
    assert lower_confidence.blend_weight_drl == 0.10

    challenger = decide_drl_acceptance(
        np.array([0.5, 0.5]),
        np.array([0.5, 0.5]),
        benchmark,
        throttle,
        {},
        {"deployment_mode": "accept challenger", "allow_full_drl_replacement": True},
        eligibility_mask=np.array([True, True]),
    )
    assert challenger.accepted
    assert challenger.selected_weights_source == "drl_challenger"
    assert challenger.blend_weight_drl == 1.0
