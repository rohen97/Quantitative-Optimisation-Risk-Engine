import pandas as pd

from src.drl.drl_pipeline import run_drl_pipeline


def test_drl_pipeline_generates_required_outputs(tmp_path):
    baseline = pd.DataFrame(
        {
            "security_id": ["A", "B", "C"],
            "ticker": ["AAA", "BBB", "CCC"],
            "company_name": ["A", "B", "C"],
            "sector": ["Tech", "Health", "Utilities"],
            "country": ["DE", "FR", "GB"],
            "region": ["DACH", "EU", "UK"],
            "currency": ["EUR", "EUR", "GBP"],
            "current_weight": [0.2, 0.2, 0.2],
            "current_market_value_usd": [20, 20, 20],
            "target_weight": [0.34, 0.33, 0.33],
            "portfolio_method": ["cvar_constrained"] * 3,
            "eligible_for_optimisation": [True, True, False],
            "expected_total_return_12m": [0.08, 0.05, 0.02],
            "expected_dividend_return_12m": [0.03, 0.04, 0.01],
            "expected_volatility_12m": [0.18, 0.20, 0.25],
            "p5_return_12m": [-0.15, -0.18, -0.30],
            "var_5_12m": [-0.15, -0.18, -0.30],
            "cvar_5_12m": [-0.20, -0.22, -0.35],
            "expected_shortfall_5_12m": [-0.21, -0.23, -0.36],
            "dividend_cut_probability": [0.1, 0.1, 0.4],
            "large_drawdown_probability_12m": [0.2, 0.2, 0.5],
            "tail_risk_score": [30, 40, 90],
            "liquidity_score": [70, 65, 45],
            "final_recommendation_score": [80, 70, 30],
            "dividend_safety_score": [80, 75, 20],
            "dividend_yield": [0.03, 0.04, 0.01],
            "regime_suitability_score": [80, 70, 20],
            "portfolio_fit_score": [60, 65, 20],
        }
    )
    outputs = run_drl_pipeline(
        tmp_path,
        input_frames={
            "recommended_optimised_portfolio": baseline,
            "portfolio_optimisation_summary": pd.DataFrame(
                [{"portfolio_method": "cvar_constrained", "selected_recommended_portfolio": True}]
            ),
            "regime_dashboard_summary": pd.DataFrame([{"crisis_probability": 0.2, "high_chaos_probability": 0.2}]),
        },
        drl_config={"random_seeds": (1, 2), "max_adjustment": 0.01, "cash_weight": 0.02, "lookback_days": 5, "train_fraction": 0.6, "validation_fraction": 0.2},
        optimisation_config={"optimisation": {"constraints": {"max_single_name_weight": 0.70}}},
    )
    assert outputs["drl_target_weights"].loc[2, "target_weight"] == 0
    assert "accepted_target_weight" in outputs["drl_target_weights"].columns
    assert (tmp_path / "drl_target_weights.csv").exists()
    assert (tmp_path / "drl_risk_throttle.csv").exists()
    assert "drl_acceptance_decision" in outputs
    assert {
        "raw_drl_weight",
        "projected_drl_weight",
        "accepted_blended_weight",
        "trade_action",
        "acceptance_status",
        "commentary",
    }.issubset(outputs["drl_trade_list"].columns)
    assert {"comparison_type", "benchmark", "annualised_net_return", "sharpe", "cvar"}.issubset(
        outputs["drl_benchmark_comparison"].columns
    )
    assert {"row_type", "seed", "total_net_return", "policy_weight_stability"}.issubset(outputs["drl_seed_results"].columns)
    assert {
        "seed",
        "train_start",
        "train_end",
        "validation_start",
        "validation_end",
        "test_start",
        "test_end",
        "hyperparameters",
        "best_validation_score",
        "test_metrics",
        "constraint_violations",
        "model_mode",
        "dependency_mode",
        "runtime_seconds",
        "random_split_used",
        "test_period_model_selection_used",
    }.issubset(outputs["drl_training_summary"].columns)
    assert len(outputs["drl_training_summary"]) >= 5
    assert not outputs["drl_training_summary"]["random_split_used"].any()
    assert not outputs["drl_training_summary"]["test_period_model_selection_used"].any()
    assert "drl_model_card" in outputs
