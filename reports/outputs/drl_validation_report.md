# DRL Validation Report

## Scope

This report validates the constrained, regime-gated DRL residual overlay. It checks state construction, action projection, reward decomposition, environment replay, regime gating, walk-forward training, multi-seed evaluation, benchmarks, explainability and acceptance/rejection rules.

## State And Action Validation

- Feature order is deterministic.
- Observations are finite numeric arrays.
- Future target or realised-label columns are excluded.
- Eligibility masks are required and validated.
- Cash is included as an explicit asset.
- Excluded assets receive zero projected weight.

## Projection And Constraints

Projection enforces non-negative weights, sum-to-one weights, exclusions, single-name caps, sector/country/region/currency caps, turnover caps and baseline fallback when infeasible.

## Reward Validation

Differential Sharpe is finite. Transaction costs, CVaR, Expected Shortfall and drawdown reduce reward. Dividend income increases reward. The component decomposition reconciles to total reward.

## Environment Validation

The environment supports reset/step semantics, chronological progression, daily return accrual between decisions, transaction-cost deduction, same-step trading prevention and fallback flags when actions are infeasible.

## Training And Seeds

Seeds tested: 11, 23, 37, 53, 71
Number of seeds: 5
Seed stability acceptable: True
Training split: chronological with no random train/test split.
Validation occurs before test and model selection uses validation only.
A rebalance-period embargo is applied between windows.
Training-only and expanding-window scaling interfaces are used.

## Benchmark Fairness

Fair information-set benchmark rows: 12
Full Wolf benchmark rows: 12
Benchmarks include the selected baseline optimiser, current portfolio, cash, buy-and-hold, equal-weight eligible, score-weighted, risk-parity, mean-variance, CVaR-constrained, dividend-income constrained and regime-aware constrained portfolios.
Net metrics include estimated transaction costs.

## Acceptance Gate

Constraint violations across seed rows: 0
DRL is rejected for constraint violations, CVaR breaches, Expected Shortfall breaches, severe stress breaches, infeasible actions, missing eligibility masks, liquidity failures, severe throttle fallback, low confidence, seed instability, validation underperformance or leakage.

## Outputs Checked

- `drl_state_schema.csv`
- `drl_training_summary.csv`
- `drl_split_manifest.csv`
- `drl_seed_results.csv`
- `drl_simple_challenger_comparison.csv`
- `drl_simple_challenger_oos_paths.csv`
- `drl_backtest_results.csv`
- `drl_benchmark_comparison.csv`
- `drl_acceptance_decision.csv`
- `drl_baseline_portfolio.csv`
- `drl_challenger_portfolio.csv`
- `drl_final_selected_weights_source.csv`
- `drl_trade_list.csv`
- `drl_constraint_adjustments.csv`
- `drl_feature_attributions.csv`
- `drl_asset_time_attributions.csv`
- `drl_ablation_results.csv`

## Current Limitations

Production research evaluation uses Stable-Baselines3 PPO over a frozen chronological regional panel with train-only scaling, embargoes and validation-only selection. The June 2025 through May 2026 window is a legacy locked OOS record that has already been observed once, so it is not described as untouched. Deployment evidence must come from the prospective monthly shadow record beginning after the policy freeze. The current policy is rejected because validation and legacy-OOS active performance do not beat the optimiser.

## Future Research

- full TCN + GAP PPO policy
- robust CAM / Grad-CAM attribution
- additional low-variance challengers after prospective evidence exists
- distributional reinforcement learning
- constrained policy optimisation
- Lagrangian risk constraints
- offline reinforcement learning
- uncertainty-aware policy ensembles
- synthetic crisis generation
- adversarial regime simulation
- multi-agent allocation and hedging
- meta-learning across regions
- online fine-tuning with strict governance
- causal validation of input features
- DRL hedge sizing
- hierarchical or graph-based cross-asset encoders