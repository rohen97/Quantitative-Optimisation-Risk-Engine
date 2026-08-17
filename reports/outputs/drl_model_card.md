# DRL Allocation Engine Model Card

## Role

The DRL engine is a residual overlay and challenger to the selected constrained optimiser. It proposes bounded active-weight changes relative to the baseline optimiser; it does not replace the optimiser by default and cannot bypass hard constraints.

The baseline optimiser remains the primary portfolio because it is deterministic, auditable and directly tied to explicit risk, liquidity, concentration and mandate controls. DRL is allowed to contribute only through a capped blend unless the acceptance gate explicitly permits challenger status.

## Runtime Mode

- Mode: `historical_walk_forward`
- Seeds: 11, 23, 37, 53, 71
- Default deployment: maximum 10% DRL blend, baseline optimiser dominant.
- Full DRL replacement: disabled unless explicitly configured and accepted.

## State Design

The point-in-time state contains deterministic feature ordering across portfolio state, temporal returns, volatility, fundamentals, dividend quality, distributional forecasts, regime, sentiment, narrative, liquidity, risk contribution, stress tests and hard eligibility masks. Cash is included as an explicit asset. Future target or realised-label columns are excluded.

## Action Design

The action is a residual weight adjustment. Monthly deltas are clipped to the configured maximum and applied to the baseline optimiser weights. The action space is long-only after projection, cash-inclusive, unlevered and does not permit shorting.

## Constraint Projection

Every proposed action is projected to the feasible set after masking excluded assets. The projection enforces non-negative weights, sum-to-one weights including cash, single-name caps, sector/country/region/currency caps, liquidity limits, turnover caps and cash floors. Infeasible projections fall back to the baseline optimiser.

## Transaction-Cost Model

Transaction costs include commission, half-spread/slippage, nonlinear market impact based on participation rate, currency conversion placeholders and optional transaction-tax placeholders. Costs are deducted from reward and included in benchmark net metrics.

## Reward

The historical regional PPO reward is benchmark-relative and net of costs. It rewards active return over the dated regional benchmark and explicitly penalises transaction costs, turnover, drawdown beyond the configured threshold, realised tail loss, expected CVaR excess and volatility. The live security-level overlay retains the broader decomposed reward used for projection diagnostics.

Differential Sharpe is updated online from exponentially smoothed first and second moments, keeping the reward focused on risk-adjusted incremental performance rather than raw return alone.

## Regime And Specialist Policies

The Wolf Chaos risk throttle scales or blocks actions as chaos and crisis probabilities rise. Severe chaos can force baseline fallback. Specialist agents are blended probabilistically rather than hard switched: the stable low-chaos specialist emphasises return, dividends, quality and low turnover; the crisis high-chaos specialist emphasises CVaR, Expected Shortfall, drawdown control, liquidity, cash and dividend safety. Inflation, regional-stress and credit-stress specialists are future-ready placeholders.

## Algorithms

Production research mode trains Stable-Baselines3 PPO policies with continuous regional residual actions, deterministic evaluation and five independent seeds. A ridge contextual bandit and convex residual allocator are evaluated on the same frozen split as lower-variance challengers. The pipeline fails closed when historical evidence or the PPO dependency is unavailable.

The TCN/GAP encoder is optional and dependency-light. When PyTorch is available, it supports causal dilated convolutions, residual blocks, Global Average Pooling, cross-asset layers and a cash logit. It is not a hard dependency.

## Explainability

Outputs include constraint traces, feature-group attributions, asset-time attributions and human-readable explanations. CAM/Grad-CAM is future-ready for the TCN path. Explanations describe model attributions and avoid causal claims.

## Validation And Benchmarks

Validation uses chronological walk-forward splits, train-only scaling, an embargo between train/validation/test windows, multiple seeds and validation-only model selection. Benchmark comparisons are labelled as fair information-set comparisons or full Wolf comparisons so DRL is not credited for richer input data without disclosure.
Benchmark success rate across windows: 0.00%

Ablation tests compare regime/no-regime, distributional/no-distributional, sentiment/narrative variants, reward variants, transaction-cost assumptions, universal versus specialist policies, MLP versus optional TCN/GAP and no-throttle versus Wolf Chaos throttle.

## Acceptance And Rejection

The DRL allocation is rejected and replaced with the baseline optimiser for hard constraint violations, infeasible projection, missing eligibility masks, non-finite or negative weights, weight-sum errors, CVaR/Expected Shortfall/stress breaches, turnover or liquidity failures, severe throttle fallback, low confidence, excessive seed instability, validation underperformance or test leakage.

## Current Limitations

- Exact panel dates, hashes, embargoes and locked evaluation dates are written to `drl_split_manifest.csv`.
- The 2025-06 through 2026-05 OOS window is now a legacy locked record; deployment requires three genuinely prospective monthly shadow cycles beginning after the policy freeze.
- Bloomberg ingestion is paused. Existing licensed local aggregates remain available, but no new Bloomberg requests are part of this run.
- The action space is regional; security selection remains with the constrained optimiser.
- Current five-seed validation information ratios are negative, so the validation guard retains the baseline optimiser.
- TCN/GAP and CAM paths are interfaces, not yet a fully validated production policy.
- The contextual-bandit and convex-residual challengers also underperform the baseline on the legacy locked OOS period.
- Outputs are research and decision-support artifacts, not trade execution instructions.

## Future Research

- full TCN + GAP PPO policy
- robust CAM / Grad-CAM attribution
- additional offline-RL challengers after prospective evidence exists
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