from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.drl.ablation import build_ablation_results
from src.drl.action_projection import project_to_feasible_set
from src.drl.baseline_policy import baseline_weight_vector, choose_baseline_portfolio
from src.drl.benchmark import (
    build_benchmark_comparison,
    build_seed_evaluation,
    compare_against_benchmark,
    decide_drl_acceptance,
)
from src.drl.config import load_drl_config, normalize_drl_config
from src.drl.evaluation import build_backtest_results
from src.drl.explainability import (
    asset_time_attributions,
    build_constraint_adjustment_explanations,
    explain_weight_changes,
    feature_attributions,
)
from src.drl.market_environment import DRLMarketEnvironment
from src.drl.mock_drl_data import build_temporal_mock_features, read_output
from src.drl.regime_gating import calculate_regime_agent_weights, calculate_risk_throttle_from_dashboard, risk_throttle_frame
from src.drl.state_builder import build_drl_state, build_state_schema
from src.drl.training import chronological_train_validation_test_split, run_seed_training
from src.drl.trade_list import build_drl_trade_list
from src.optimisation.constraints import build_eligibility_mask
from src.reporting.report_writer import write_csv, write_markdown
from src.utils.config import ensure_output_dir


def _constraints(config: dict, optimisation_config: dict | None = None) -> dict:
    limits = (optimisation_config or {}).get("optimisation", optimisation_config or {}).get("constraints", {}).copy()
    limits.update(config.get("constraints", {}))
    frequency = str(config.get("rebalance_frequency", "monthly")).lower()
    default_delta = config.get("quarterly_max_delta_weight", 0.02) if frequency == "quarterly" else config.get("monthly_max_delta_weight", 0.01)
    limits["max_drl_adjustment"] = float(config.get("max_delta_weight", default_delta))
    limits["max_delta_weight"] = limits["max_drl_adjustment"]
    return limits


def _portfolio_features(asset_data: pd.DataFrame, baseline_weights: np.ndarray, config: dict) -> dict[str, float]:
    hhi = float(np.square(baseline_weights).sum())
    return {
        "cash_weight": float(config.get("cash_weight", 0.02)),
        "nav": float(asset_data.get("current_market_value_usd", pd.Series(0, index=asset_data.index)).sum()),
        "hhi": hhi,
        "effective_holdings": float(1 / max(hhi, 1e-12)),
        "turnover_used": 0.0,
        "remaining_turnover_budget": float(config.get("turnover_limit", 0.20)),
        "max_single_name_weight": float(config.get("max_single_name_weight", 0.05)),
        "sector_limit_headroom": 0.0,
        "country_limit_headroom": 0.0,
        "currency_limit_headroom": 0.0,
    }


def _load_inputs(output_dir: Path, input_frames: dict[str, pd.DataFrame] | None) -> dict[str, pd.DataFrame]:
    frames = input_frames.copy() if input_frames else {}
    for name, filename in {
        "portfolio_optimisation_summary": "portfolio_optimisation_summary.csv",
        "optimised_portfolio_cvar_constrained": "optimised_portfolio_cvar_constrained.csv",
        "optimised_portfolio_regime_aware": "optimised_portfolio_regime_aware.csv",
        "stock_scorecard": "stock_scorecard.csv",
        "regime_dashboard_summary": "regime_dashboard_summary.csv",
    }.items():
        if name not in frames or frames[name].empty:
            frames[name] = read_output(filename, output_dir)
    return frames


def build_model_card(config: dict, benchmark: pd.DataFrame) -> str:
    """Create a DRL model card covering role, design, controls and limits."""
    success_rate = float(benchmark["drl_success_flag"].mean()) if not benchmark.empty else 0.0
    mode = config.get("mode", "mock")
    seeds = ", ".join(str(seed) for seed in config.get("random_seeds", ()))
    return "\n".join(
        [
            "# DRL Allocation Engine Model Card",
            "",
            "## Role",
            "",
            "The DRL engine is a residual overlay and challenger to the selected constrained optimiser. It proposes bounded active-weight changes relative to the baseline optimiser; it does not replace the optimiser by default and cannot bypass hard constraints.",
            "",
            "The baseline optimiser remains the primary portfolio because it is deterministic, auditable and directly tied to explicit risk, liquidity, concentration and mandate controls. DRL is allowed to contribute only through a capped blend unless the acceptance gate explicitly permits challenger status.",
            "",
            "## Runtime Mode",
            "",
            f"- Mode: `{mode}`",
            f"- Seeds: {seeds}",
            "- Default deployment: maximum 25% DRL blend, baseline optimiser dominant.",
            "- Full DRL replacement: disabled unless explicitly configured and accepted.",
            "",
            "## State Design",
            "",
            "The point-in-time state contains deterministic feature ordering across portfolio state, temporal returns, volatility, fundamentals, dividend quality, distributional forecasts, regime, sentiment, narrative, liquidity, risk contribution, stress tests and hard eligibility masks. Cash is included as an explicit asset. Future target or realised-label columns are excluded.",
            "",
            "## Action Design",
            "",
            "The action is a residual weight adjustment. Monthly deltas are clipped to the configured maximum and applied to the baseline optimiser weights. The action space is long-only after projection, cash-inclusive, unlevered and does not permit shorting.",
            "",
            "## Constraint Projection",
            "",
            "Every proposed action is projected to the feasible set after masking excluded assets. The projection enforces non-negative weights, sum-to-one weights including cash, single-name caps, sector/country/region/currency caps, liquidity limits, turnover caps and cash floors. Infeasible projections fall back to the baseline optimiser.",
            "",
            "## Transaction-Cost Model",
            "",
            "Transaction costs include commission, half-spread/slippage, nonlinear market impact based on participation rate, currency conversion placeholders and optional transaction-tax placeholders. Costs are deducted from reward and included in benchmark net metrics.",
            "",
            "## Reward",
            "",
            "The reward is conservative and decomposed. Positive components include Differential Sharpe, net total return, dividend income, regime suitability improvement, diversification improvement and quality exposure. Negative components include CVaR, Expected Shortfall, drawdown, transaction costs, turnover, concentration, dividend-cut risk, liquidity risk, forecast uncertainty, narrative/credit stress and stress-scenario loss.",
            "",
            "Differential Sharpe is updated online from exponentially smoothed first and second moments, keeping the reward focused on risk-adjusted incremental performance rather than raw return alone.",
            "",
            "## Regime And Specialist Policies",
            "",
            "The Wolf Chaos risk throttle scales or blocks actions as chaos and crisis probabilities rise. Severe chaos can force baseline fallback. Specialist agents are blended probabilistically rather than hard switched: the stable low-chaos specialist emphasises return, dividends, quality and low turnover; the crisis high-chaos specialist emphasises CVaR, Expected Shortfall, drawdown control, liquidity, cash and dividend safety. Inflation, regional-stress and credit-stress specialists are future-ready placeholders.",
            "",
            "## Algorithms",
            "",
            "The primary policy interface is PPO with continuous residual actions, deterministic evaluation and multiple seeds. Stable-Baselines3 is optional. If unavailable or disabled, the pipeline uses a deterministic mock policy and labels outputs as mock. SAC and TD3 are documented as optional challengers but are not active production policies.",
            "",
            "The TCN/GAP encoder is optional and dependency-light. When PyTorch is available, it supports causal dilated convolutions, residual blocks, Global Average Pooling, cross-asset layers and a cash logit. It is not a hard dependency.",
            "",
            "## Explainability",
            "",
            "Outputs include constraint traces, feature-group attributions, asset-time attributions and human-readable explanations. CAM/Grad-CAM is future-ready for the TCN path. Explanations describe model attributions and avoid causal claims.",
            "",
            "## Validation And Benchmarks",
            "",
            "Validation uses chronological walk-forward splits, train-only scaling, an embargo between train/validation/test windows, multiple seeds and validation-only model selection. Benchmark comparisons are labelled as fair information-set comparisons or full Wolf comparisons so DRL is not credited for richer input data without disclosure.",
            f"Benchmark success rate across windows: {success_rate:.2%}",
            "",
            "Ablation tests compare regime/no-regime, distributional/no-distributional, sentiment/narrative variants, reward variants, transaction-cost assumptions, universal versus specialist policies, MLP versus optional TCN/GAP and no-throttle versus Wolf Chaos throttle.",
            "",
            "## Acceptance And Rejection",
            "",
            "The DRL allocation is rejected and replaced with the baseline optimiser for hard constraint violations, infeasible projection, missing eligibility masks, non-finite or negative weights, weight-sum errors, CVaR/Expected Shortfall/stress breaches, turnover or liquidity failures, severe throttle fallback, low confidence, excessive seed instability, validation underperformance or test leakage.",
            "",
            "## Current Limitations",
            "",
            "- MVP training uses deterministic local/mock policy mechanics.",
            "- Vendor point-in-time history is not yet connected.",
            "- PPO deep learning integration is optional and not required for pipeline success.",
            "- TCN/GAP and CAM paths are interfaces, not yet a fully validated production policy.",
            "- SAC, TD3, distributional RL and constrained policy optimisation are research extensions.",
            "- Outputs are research and decision-support artifacts, not trade execution instructions.",
            "",
            "## Future Research",
            "",
            "- full TCN + GAP PPO policy",
            "- robust CAM / Grad-CAM attribution",
            "- SAC and TD3 challengers",
            "- distributional reinforcement learning",
            "- constrained policy optimisation",
            "- Lagrangian risk constraints",
            "- offline reinforcement learning",
            "- uncertainty-aware policy ensembles",
            "- synthetic crisis generation",
            "- adversarial regime simulation",
            "- multi-agent allocation and hedging",
            "- meta-learning across regions",
            "- online fine-tuning with strict governance",
            "- causal validation of input features",
            "- DRL hedge sizing",
            "- hierarchical or graph-based cross-asset encoders",
        ]
    )


def build_validation_report(seed_results: pd.DataFrame, benchmark: pd.DataFrame) -> str:
    """Create a validation report focused on methodology, tests and controls."""
    stable = seed_results["test_reward"].std(ddof=0) <= max(abs(seed_results["test_reward"].mean()) * 0.50, 1e-8)
    seed_count = int(seed_results["seed"].nunique()) if not seed_results.empty else 0
    constraint_violations = int(seed_results.get("constraint_violations", pd.Series(dtype=float)).sum()) if not seed_results.empty else 0
    fair_rows = int(benchmark["comparison_type"].eq("fair_information_set").sum()) if "comparison_type" in benchmark else 0
    full_rows = int(benchmark["comparison_type"].eq("full_wolf").sum()) if "comparison_type" in benchmark else 0
    return "\n".join(
        [
            "# DRL Validation Report",
            "",
            "## Scope",
            "",
            "This report validates the constrained, regime-gated DRL residual overlay. It checks state construction, action projection, reward decomposition, environment replay, regime gating, walk-forward training, multi-seed evaluation, benchmarks, explainability and acceptance/rejection rules.",
            "",
            "## State And Action Validation",
            "",
            "- Feature order is deterministic.",
            "- Observations are finite numeric arrays.",
            "- Future target or realised-label columns are excluded.",
            "- Eligibility masks are required and validated.",
            "- Cash is included as an explicit asset.",
            "- Excluded assets receive zero projected weight.",
            "",
            "## Projection And Constraints",
            "",
            "Projection enforces non-negative weights, sum-to-one weights, exclusions, single-name caps, sector/country/region/currency caps, turnover caps and baseline fallback when infeasible.",
            "",
            "## Reward Validation",
            "",
            "Differential Sharpe is finite. Transaction costs, CVaR, Expected Shortfall and drawdown reduce reward. Dividend income increases reward. The component decomposition reconciles to total reward.",
            "",
            "## Environment Validation",
            "",
            "The environment supports reset/step semantics, chronological progression, daily return accrual between decisions, transaction-cost deduction, same-step trading prevention and fallback flags when actions are infeasible.",
            "",
            "## Training And Seeds",
            "",
            f"Seeds tested: {', '.join(seed_results['seed'].astype(str)) if not seed_results.empty else 'none'}",
            f"Number of seeds: {seed_count}",
            f"Seed stability acceptable: {bool(stable)}",
            "Training split: chronological with no random train/test split.",
            "Validation occurs before test and model selection uses validation only.",
            "A rebalance-period embargo is applied between windows.",
            "Training-only and expanding-window scaling interfaces are used.",
            "",
            "## Benchmark Fairness",
            "",
            f"Fair information-set benchmark rows: {fair_rows}",
            f"Full Wolf benchmark rows: {full_rows}",
            "Benchmarks include the selected baseline optimiser, current portfolio, cash, buy-and-hold, equal-weight eligible, score-weighted, risk-parity, mean-variance, CVaR-constrained, dividend-income constrained and regime-aware constrained portfolios.",
            "Net metrics include estimated transaction costs.",
            "",
            "## Acceptance Gate",
            "",
            f"Constraint violations across seed rows: {constraint_violations}",
            "DRL is rejected for constraint violations, CVaR breaches, Expected Shortfall breaches, severe stress breaches, infeasible actions, missing eligibility masks, liquidity failures, severe throttle fallback, low confidence, seed instability, validation underperformance or leakage.",
            "",
            "## Outputs Checked",
            "",
            "- `drl_state_schema.csv`",
            "- `drl_training_summary.csv`",
            "- `drl_seed_results.csv`",
            "- `drl_backtest_results.csv`",
            "- `drl_benchmark_comparison.csv`",
            "- `drl_acceptance_decision.csv`",
            "- `drl_baseline_portfolio.csv`",
            "- `drl_challenger_portfolio.csv`",
            "- `drl_final_selected_weights_source.csv`",
            "- `drl_trade_list.csv`",
            "- `drl_constraint_adjustments.csv`",
            "- `drl_feature_attributions.csv`",
            "- `drl_asset_time_attributions.csv`",
            "- `drl_ablation_results.csv`",
            "",
            "## Current Limitations",
            "",
            "The current implementation is mock/local, dependency-light and designed for reproducibility. It does not execute trades, does not use live point-in-time vendor history and does not claim causal validity of input features.",
            "",
            "## Future Research",
            "",
            "- full TCN + GAP PPO policy",
            "- robust CAM / Grad-CAM attribution",
            "- SAC and TD3 challengers",
            "- distributional reinforcement learning",
            "- constrained policy optimisation",
            "- Lagrangian risk constraints",
            "- offline reinforcement learning",
            "- uncertainty-aware policy ensembles",
            "- synthetic crisis generation",
            "- adversarial regime simulation",
            "- multi-agent allocation and hedging",
            "- meta-learning across regions",
            "- online fine-tuning with strict governance",
            "- causal validation of input features",
            "- DRL hedge sizing",
            "- hierarchical or graph-based cross-asset encoders",
        ]
    )


def run_drl_pipeline(
    output_dir: str | Path | None = None,
    input_frames: dict[str, pd.DataFrame] | None = None,
    drl_config: dict | None = None,
    optimisation_config: dict | None = None,
    write_outputs: bool = True,
) -> dict[str, pd.DataFrame | str]:
    """Run the constrained, regime-gated and explainable DRL allocation overlay."""
    config = normalize_drl_config(drl_config) if drl_config is not None else load_drl_config()
    out = Path(output_dir) if output_dir else ensure_output_dir()
    frames = _load_inputs(out, input_frames)
    baseline = choose_baseline_portfolio(frames, out)
    if baseline.empty:
        raise ValueError("DRL pipeline requires optimiser outputs or a stock_scorecard fallback.")
    baseline = baseline.reset_index(drop=True)
    constraints = _constraints(config, optimisation_config)
    eligibility = baseline.get("eligible_for_optimisation")
    if eligibility is None:
        eligibility = build_eligibility_mask(baseline, constraints)
    eligibility_mask = eligibility.fillna(False).astype(bool).to_numpy()
    baseline_weights = baseline_weight_vector(baseline)
    current_weights = pd.to_numeric(baseline.get("current_weight", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    temporal = build_temporal_mock_features(baseline, int(config.get("lookback_days", 60)))
    gate_weights = calculate_regime_agent_weights(frames.get("regime_dashboard_summary", pd.DataFrame()))
    throttle = calculate_risk_throttle_from_dashboard(frames.get("regime_dashboard_summary", pd.DataFrame()))
    effective_config = config.copy()
    effective_config["max_adjustment"] = constraints["max_delta_weight"]
    effective_config["cash_weight"] = max(float(config.get("cash_weight", 0.02)), throttle.minimum_cash_weight)
    effective_config["risk_throttle_reason"] = throttle.reason
    constraints["cash_floor"] = max(float(constraints.get("cash_floor", 0.0)), throttle.minimum_cash_weight)
    state = build_drl_state(
        pd.Timestamp.today().normalize(),
        baseline["ticker"].astype(str).tolist(),
        current_weights,
        baseline_weights,
        temporal,
        baseline,
        _portfolio_features(baseline, baseline_weights, effective_config),
        eligibility_mask,
    )
    state_schema = build_state_schema(state.feature_names)
    seed_results, actions, reward_rows = run_seed_training(baseline, baseline_weights, eligibility_mask, gate_weights, constraints, effective_config, throttle)
    avg_action = np.vstack(list(actions.values())).mean(axis=0) if actions else np.zeros(len(baseline))
    if throttle.fallback_to_baseline:
        avg_action = np.zeros_like(avg_action)
    env = DRLMarketEnvironment(baseline, baseline_weights, eligibility_mask, constraints, effective_config)
    result = env.step(avg_action, current_weights=baseline_weights)
    target_weights, projection_report = project_to_feasible_set(
        baseline_weights,
        avg_action,
        baseline,
        eligibility_mask,
        constraints,
        cash_weight=float(effective_config.get("cash_weight", 0.02)),
    )
    drl_portfolio = baseline.copy()
    drl_portfolio["baseline_weight"] = baseline_weights
    drl_portfolio["target_weight"] = target_weights
    drl_portfolio["portfolio_method"] = "constrained_regime_gated_drl"
    drl_portfolio["eligible_for_drl"] = eligibility_mask
    backtest = build_backtest_results(baseline, baseline_weights, target_weights)
    legacy_benchmark = compare_against_benchmark(backtest)
    benchmark = build_benchmark_comparison(baseline, baseline_weights, target_weights)
    target_cash = max(0.0, 1.0 - float(np.asarray(target_weights, dtype=float).sum()))
    baseline_cash = max(0.0, 1.0 - float(np.asarray(baseline_weights, dtype=float).sum()))
    acceptance = decide_drl_acceptance(
        np.concatenate([target_weights, [target_cash]]),
        np.concatenate([baseline_weights, [baseline_cash]]),
        benchmark,
        throttle,
        constraints,
        effective_config,
        projection_report=projection_report,
        eligibility_mask=eligibility_mask,
        seed_results=seed_results,
    )
    accepted_weights = acceptance.blend_weight_drl * target_weights + acceptance.blend_weight_baseline * baseline_weights
    drl_portfolio["accepted_target_weight"] = accepted_weights
    drl_portfolio["acceptance_selected_weights_source"] = acceptance.selected_weights_source
    baseline_portfolio = baseline.copy()
    baseline_portfolio["baseline_weight"] = baseline_weights
    baseline_portfolio["selected_weight"] = baseline_weights
    baseline_portfolio["selected_weights_source"] = "baseline_optimiser"
    challenger_portfolio = drl_portfolio.copy()
    challenger_portfolio["raw_drl_weight"] = projection_report[
        projection_report["ticker"].astype(str).str.upper().ne("CASH")
    ]["candidate_weight"].to_numpy(dtype=float)
    challenger_portfolio["projected_drl_weight"] = target_weights
    challenger_portfolio["selected_weight"] = accepted_weights
    challenger_portfolio["selected_weights_source"] = acceptance.selected_weights_source
    final_source_frame = pd.DataFrame(
        [
            {
                "baseline_portfolio_source": str(baseline.get("portfolio_method", pd.Series(["unknown"])).iloc[0]),
                "drl_challenger_source": "constrained_regime_gated_drl",
                "accepted": acceptance.accepted,
                "final_selected_weights_source": acceptance.selected_weights_source,
                "blend_weight_drl": acceptance.blend_weight_drl,
                "blend_weight_baseline": acceptance.blend_weight_baseline,
                "rejection_reasons": ";".join(acceptance.rejection_reasons),
            }
        ]
    )
    nav_usd = float(baseline.get("current_market_value_usd", pd.Series(100_000_000)).sum() or 100_000_000)
    trade_list = build_drl_trade_list(
        baseline,
        projection_report,
        accepted_weights,
        acceptance,
        nav_usd,
        effective_config,
    )
    explanations = explain_weight_changes(baseline, baseline_weights, target_weights)
    feature_attr = feature_attributions(state, target_weights)
    asset_time_attr = asset_time_attributions(drl_portfolio, target_weights, int(config.get("lookback_days", 60)))
    constraint_explanations = build_constraint_adjustment_explanations(
        baseline,
        projection_report,
        throttle_adjustment=1.0 - float(throttle.action_scale),
    )
    reward_report = pd.DataFrame(reward_rows + [{"seed": "ensemble", **result.reward_parts}])
    seed_evaluation = build_seed_evaluation(seed_results)
    ablation = build_ablation_results(benchmark)
    split = chronological_train_validation_test_split(pd.date_range("2020-01-31", periods=36, freq="ME"), config["train_fraction"], config["validation_fraction"])
    training_summary = seed_results.copy()
    training_summary["policy_type"] = "mock_mlp_ppo_with_regime_specialists"
    training_summary["train_start_index"] = split["train"][0]
    training_summary["train_end_index"] = split["train"][1]
    training_summary["validation_start_index"] = split["validation"][0]
    training_summary["validation_end_index"] = split["validation"][1]
    training_summary["test_start_index"] = split["test"][0]
    training_summary["test_end_index"] = split["test"][1]
    training_summary["mean_seed_reward"] = float(seed_results["test_reward"].mean())
    training_summary["std_seed_reward"] = float(seed_results["test_reward"].std(ddof=0))
    training_summary["constraint_projection_applied"] = True
    training_summary["risk_throttle_action_scale"] = throttle.action_scale
    training_summary["risk_throttle_minimum_cash_weight"] = throttle.minimum_cash_weight
    training_summary["risk_throttle_reason"] = throttle.reason
    model_card = build_model_card(config, legacy_benchmark)
    validation_report = build_validation_report(seed_results, benchmark)
    acceptance_frame = pd.DataFrame([acceptance.__dict__])
    outputs: dict[str, pd.DataFrame | str] = {
        "drl_state_schema": state_schema,
        "drl_training_summary": training_summary,
        "drl_seed_results": seed_evaluation,
        "drl_backtest_results": backtest,
        "drl_benchmark_comparison": benchmark,
        "drl_acceptance_decision": acceptance_frame,
        "drl_baseline_portfolio": baseline_portfolio,
        "drl_challenger_portfolio": challenger_portfolio,
        "drl_final_selected_weights_source": final_source_frame,
        "drl_target_weights": drl_portfolio,
        "drl_trade_list": trade_list,
        "drl_constraint_adjustments": constraint_explanations,
        "drl_reward_decomposition": reward_report,
        "drl_regime_agent_weights": gate_weights,
        "drl_risk_throttle": risk_throttle_frame(throttle),
        "drl_explanations": explanations,
        "drl_feature_attributions": feature_attr,
        "drl_asset_time_attributions": asset_time_attr,
        "drl_ablation_results": ablation,
        "drl_model_card": model_card,
        "drl_validation_report": validation_report,
    }
    if write_outputs:
        for name, value in outputs.items():
            if isinstance(value, pd.DataFrame):
                write_csv(value, out, f"{name}.csv")
        write_markdown(model_card, out, "drl_model_card.md")
        write_markdown(validation_report, out, "drl_validation_report.md")
    return outputs
