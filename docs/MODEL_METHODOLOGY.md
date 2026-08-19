# Model Methodology

The MVP ranks listed equities with conservative hard filters, modular feature engineering, weighted quality scores, portfolio-fit features, branch comparison, risk checks, stress tests and hedge recommendations.

## Data Foundation Methodology

The DuckDB + Parquet data foundation is designed for persistence, reproducibility, point-in-time accuracy, lineage, duplicate handling, vintage tracking, API caching and model-run auditability. It is an additive backend beneath the existing Python model and does not alter scoring, optimisation, risk, DRL reward or recommendation logic.

Backend modes are controlled by `configs/data.yaml`:

- `legacy_csv`: existing CSV/mock reads remain active.
- `shadow`: write/read DuckDB snapshots and compare them to legacy outputs while continuing to rely on legacy outputs if differences exceed tolerance.
- `duckdb`: read from DuckDB point-in-time views after validation.

Data is normalised in Python, persisted in DuckDB structured tables, optionally exported to Parquet and exposed through SQL views for point-in-time prices, fundamentals, macro vintages and FX rates. Model feature snapshots, model runs and model outputs are stored with run identifiers so outputs can be traced back to backend mode, code version, config hash and input snapshot.

## Feature Store

The feature store creates stock-level monthly features from mock or future vendor inputs.

Feature groups:

- Dividend: yield, trailing DPS, 3Y/5Y growth, payout ratio, cut flag, stability, safety, FCF cover and dividend income.
- Cash-flow and quality: operating cash flow, capex, free cash flow, FCF yield, margins, CFO/net income, revenue growth, ROE, ROIC, earnings stability and cash-flow quality.
- Balance sheet: debt, cash, net debt, equity, net debt/EBITDA, debt/equity, interest coverage and sector-specific financial placeholders.
- Valuation: market cap, enterprise value, PE, PB, EV/EBITDA, FCF yield, dividend yield spread and cross-sectional valuation percentile.
- Risk: daily return, annualised volatility, beta placeholders, max drawdown, downside volatility, VaR, CVaR, Sharpe proxy, Sortino proxy and risk score.
- Liquidity: average daily value, average volume, turnover, days to liquidate 1% NAV, liquidity score and liquidity stress.
- Portfolio fit: correlation fallback, incremental exposures, incremental dividend income, concentration impact, diversification benefit and portfolio fit score.
- Sentiment and alternative data: rolling news sentiment, controversy, dividend risk, cash-flow deterioration, management confidence, regulatory risk, litigation risk, governance flags, credit stress, abnormal attention and event severity.
- Narrative reframing: financial concept extraction, first occurrence/reoccurrence tracking, frame construction, semantic drift, risk-anchor similarity, temporal narrative states and Markov transition probabilities.
- Regime analysis: factor-regime probabilities, Wolf Chaos Index, informational regime drivers, fused market-state dashboard, transition matrix and stock-level regime suitability.
- Distributional ML forecasting: expected total return, volatility, dividend-cut probability, drawdown probability, Normal/Student-t/skewed Student-t parameters, VaR, CVaR, Expected Shortfall, tail risk and skewness risk.

Output:

- `reports/outputs/features_monthly.csv`

## Conservative Scorecard

Hard filters are applied before scoring:

- Instrument type must be Equity.
- Listing status must be Active.
- Market cap and average daily value must clear configured minimums.
- Dividend yield must clear the configured minimum unless later overridden.
- Free cash flow must be positive where available.
- Payout ratio and non-financial leverage must stay below configured maximums.
- Liquidity score must clear the configured minimum.
- Severe regulatory, governance, credit or CVaR flags are excluded where available.

Weighted score:

- 18% Dividend Safety
- 18% Cash Flow Quality
- 14% Balance Sheet Strength
- 10% Valuation
- 10% Regime Suitability
- 10% ML Expected Risk-Adjusted Return
- 8% Portfolio Diversification Benefit
- 5% Liquidity
- 7% Sentiment / Alternative Data Signal

Production ML and real vendor ingestion are not built yet. Missing signals use neutral placeholder scores so the interface remains stable.

## Sentiment + Alternative Data Methodology

The sentiment engine is designed as an early-warning risk overlay. It currently runs in mock mode and supports the following source types by design: news, exchange announcements, annual/interim reports, earnings transcripts, analyst commentary, regulatory filings, social media, search trends, ownership/flow data and credit signals.

The mock pipeline:

1. Generates local text documents for active-universe companies.
2. Maps documents to securities using ticker and company-name mentions.
3. Scores text with rule-based financial sentiment dictionaries.
4. Classifies events such as dividend cuts, profit warnings, buybacks, regulatory probes, credit stress and litigation.
5. Aggregates rolling stock-level alternative-data features.
6. Produces risk flags for scorecard and risk-engine consumption.

Sentiment can reduce confidence, trigger review, cap target weights or exclude severe-risk names through hard risk overlays. It cannot override failed quant filters and cannot turn a weak quant name into a final buy by itself.

## Financial Narrative Reframing Methodology

The Financial Narrative Reframing Engine adapts protocol-framing ideas to financial text. It is more than sentiment analysis: it measures whether the company story is shifting from one frame to another over time.

Current mock-mode process:

1. Generate local financial documents for active-universe companies.
2. Extract concepts such as dividend, cash flow, margin pressure, credit stress, regulation, governance and distress.
3. Track first occurrence, reoccurrence, recurring risk concepts and concept acceleration.
4. Construct narrative frames from co-occurring concepts.
5. Generate deterministic mock embeddings for frame text.
6. Measure cosine distance to company history and anchors such as positive quality, distress, dividend risk, credit stress, governance risk and regulatory risk.
7. Classify temporal states such as positive stable, negative deteriorating, dividend risk, credit stress, regulatory overhang and distress.
8. Estimate first-order and second-order Markov transition probabilities between narrative states.
9. Aggregate final narrative reframing features for the scorecard and risk overlays.

Narrative outputs can trigger review, cap weights or exclude severe-risk names. They cannot override hard quant filters or act as standalone buy signals.

Future upgrades can add FinBERT, Sentence-BERT, OpenAI embeddings, Claude/OpenAI analyst benchmark integration and real vendor documents.

Known-scenario fixtures in `tests/fixtures/` validate that a timeline can move from a positive quality frame into governance risk, distress and credit stress, with expected Markov transitions.

## Regime Analysis Methodology

The Regime Analysis and Market State Engine is a deterministic mock-mode overlay inspired by factor-regime modeling and chaos/systemic-risk indicators. It does not fetch real macro, market or paid data yet.

Current process:

1. Build a regional factor lens for Global, DACH, EU ex-DACH, UK, US, Mainland China and Hong Kong.
2. Standardise factor returns and estimate crisis, steady-state, inflation and walking-on-ice probabilities with a GMM when available, falling back to rules.
3. Calculate the Wolf Chaos Index from cross-sectional dispersion, pairwise correlation, correlation instability, largest eigenvalue, effective bets, breadth, volatility-of-volatility and drawdown breadth.
4. Estimate informational regime deterioration using alternative-data and narrative proxies.
5. Fuse factor, chaos and informational signals into a dominant regime such as steady-state low chaos, crisis high chaos, inflation pressure, Europe recession, China policy stress, UK rate pressure, credit stress or mixed transition.
6. Build a transition matrix and stock-level regime suitability scores.
7. Feed suitability, review/exclusion flags and target-weight adjustments into the scorecard, branches, stress tests and hedge recommendations.

Regime output is a risk and sizing overlay. It can reduce exposure, add reviews or exclude severe mismatch names, but it cannot override hard filters.

## ML Forecasting And Distributional Risk Methodology

The ML layer follows the paper-inspired idea that financial models should forecast return distributions rather than only point estimates. In the current mock implementation, the engine estimates distribution parameters:

- Normal: `mu`, `sigma`
- Student-t: `mu`, `sigma`, `nu`
- Skewed Student-t placeholder: `mu`, `sigma`, `nu`, `xi`

`mu` is conditional expected total return, `sigma` is conditional volatility, `nu` controls tail thickness and `xi` controls skewness. The current skewed Student-t implementation is documented as an approximation: it widens downside or upside tails around a Student-t base and is designed to be replaced later with a full implementation.

The engine derives P5/P50/P95, VaR 5%, VaR 1%, CVaR, Expected Shortfall, tail-risk score, skewness-risk score, forecast uncertainty and distribution model confidence. Probabilistic validation includes Log Predictive Score, CRPS approximation, PIT diagnostics, quantile coverage and calibration error. VaR/ES backtesting includes exceedance rates plus Kupiec coverage and Christoffersen independence tests. The production risk stack compares DCC-IGARCH Student-t, filtered historical simulation, EWMA Normal and EWMA Student-t forecasts using trailing information only. Its scale and causal post-exception buffer are selected by three blocked development folds and then locked for the chronological holdout. Overall rows remain diagnostics; when the minimum holdout exists, the explicitly labelled chronological holdout is the governance gate.

Future research hooks are present but disabled or research-only: additional asset classes, Transformer/xLSTM/CNN/LSTM distributional forecasters, quantile-based forecasting, conformal prediction and distribution-derived trading signal research. DRL is enabled only as a bounded, multi-seed PPO challenger with a deterministic fallback and an explicit rejection gate; it cannot authorize automated trading or override the classical portfolio and governance controls.

## Portfolio Optimisation Methodology

The Portfolio Optimisation and Constraint Engine turns model outputs into target weights and trade recommendations. It consumes current holdings, scorecard scores, portfolio-fit features, sentiment and narrative risk flags, regime suitability and distributional ML forecasts including expected return, volatility, VaR, CVaR, Expected Shortfall, dividend-cut probability, drawdown probability, tail risk and skewness risk.

Implemented constructors:

- Equal-weight eligible fallback.
- Score-weighted portfolio.
- Risk-parity portfolio using volatility proxies.
- Mean-variance baseline using expected return and variance penalty.
- CVaR / Expected Shortfall constrained portfolio.
- Regional benchmark-relative, cost-aware stock-selection portfolio.
- Dividend-income constrained portfolio.
- Regime-aware portfolio.

Hard constraints include long-only weights, single-name caps, liquidity, active equity status and exclusion flags. Soft constraints include dividend yield, volatility, VaR, CVaR, Expected Shortfall, turnover, HHI, effective holdings and concentration limits. The constraint report records breaches rather than hiding them.

For reconstructed point-in-time validation, the optimiser receives the prior
month's weights and projects each otherwise feasible target onto a 10% one-way
monthly turnover budget. The projection is a convex blend, so a feasible prior
portfolio and feasible target retain their diversification caps. Mandatory hard
exits override the budget and are disclosed rather than delayed. This control is
operationally specified before evaluation and is not fitted to realised returns.

The regional-alpha challenger ranks each security against its dated regional
and sector peers. The objective combines benchmark-relative expected return,
momentum, valuation, cash-flow quality, balance-sheet strength, dividend safety,
volatility and tail risk. Estimated spread, FX and participation-based impact
costs reduce selection utility, while a fixed retention bonus discourages
unnecessary replacement of existing holdings. Signal weights are fixed in
configuration before evaluation.

The trade list compares current and target weights and assigns Buy, Increase, Reduce, Sell, Hold or Avoid actions. Optimisation cannot override hard exclusions or use high expected return alone to justify high-risk names. Future upgrades can add Hierarchical Risk Parity, Black-Litterman, transaction-cost models, tax constraints, robust covariance estimation, robust optimisation and a DRL allocation overlay.

## Supervised Benchmark-Relative Alpha Methodology

The supervised alpha layer is a governed challenger to the regional-alpha
optimiser, not an automatic replacement. It trains OLS after train-only
Fama-MacBeth feature screening, Ridge, ElasticNet, SGD Huber, Random Forest,
Extra Trees, histogram gradient boosting, XGBoost regression and XGBoost
ranking models. Fixed, deliberately small parameter grids limit search degrees
of freedom. One positive-validation model from each of the linear, tree and
ranking categories may enter an equal-weight ensemble.

Features are reconstructed at monthly decision dates. Fundamental availability
and price-feature timestamps must not exceed the decision date. Targets are
realised returns relative to contemporaneous regional and sufficiently broad
sector peers. Every expanding-window training fold is purged so its labels
mature before the next validation block. In addition, all labels used for model
or family selection must mature before the legacy OOS calendar begins. Numeric
imputation, missing indicators, clipping, scaling, categorical encoding and OLS
screening are fitted separately inside each training fold.

Candidate scores combine rank information coefficient, net active cohort
return, turnover and risk. Ensemble component outputs are converted to
within-region percentile ranks before averaging, avoiding invalid combinations
of arbitrary ranker scores and return forecasts. Portfolio evaluation selects
the strongest cost-adjusted fraction in each represented region, penalises
expensive entrants and grants a fixed retention bonus to reduce replacement.
Spread, FX and square-root participation impact estimates are charged on
weight changes. The recurring cost report excludes initial funding and adds the
separate 25bp annual bank fee. Decision dates with less than 90% realised
cross-section coverage are excluded so terminal data truncation cannot create
forced sales. Desired portfolios are transitioned through a 1.5x annual
turnover budget using a convex blend fixed before outcomes are scored;
unavoidable exits are identified separately. Quantile gradient-boosting models separately estimate the 5th,
50th and 95th percentile benchmark-relative outcomes. They train before a
purged 12-date calibration block; date-block conformal correction uses a
conservative 95% calibration target around the published central 90% interval.

Forward-return windows overlap, so monthly decision scores are not called
independent observations. Governance counts a deterministic non-overlapping
subset. Formal annualised return, Sharpe, Newey-West statistics and block
bootstrap intervals are suppressed until 12 independent cohorts exist. The current
3-month legacy record contains 11 monthly scores but four independent cohorts;
longer horizons contain two, one and one. Validation-to-legacy-OOS rank IC does
not deteriorate in the observed sample, but that cannot disprove overfitting:
the holdout has already informed research iteration and all historical features
are labelled `reconstructed_pit_proxy`.

Deployment therefore fails closed. The optimiser blend remains zero until a
new prospective shadow record supplies at least 12 independent cohorts using
native point-in-time evidence, with positive net active return and confidence
bound, a significant independent sign test, rank IC above threshold and annual
turnover no greater than 1.5x. Code cannot manufacture that evidence. The
remaining external requirements are future outcomes, original filing/vintage
timestamps, historical membership and inactive-security mappings, broader
historical fundamentals and observed execution fills.

## Constrained Regime-Gated DRL Methodology

The DRL allocation engine is implemented as a bounded residual overlay and challenger to the selected classical optimiser. The central allocation equation is `raw_candidate_weights = baseline_optimiser_weights + bounded_drl_adjustments`, followed by projection to the feasible constraint set. DRL does not replace the optimiser by default because the optimiser is deterministic, auditable and directly controlled by explicit risk, concentration, liquidity and mandate constraints.

State design is point-in-time and deterministic. The state includes current weights, baseline weights, cash, concentration, turnover budget, temporal return features, volatility, fundamentals, dividend quality, distributional forecasts, regime probabilities, Wolf Chaos Index, sentiment, narrative reframing, liquidity, risk contributions, stress losses and hard eligibility masks. Future target, realised-return or label columns are excluded from the observation.

Action design is a residual weight adjustment. Monthly action deltas default to 1% per asset and quarterly deltas default to 2%. The action is not a direct target portfolio: it is clipped, added to the baseline, masked for eligibility and projected. The MVP is cash-inclusive, long-only, unlevered and does not permit shorting.

Constraint projection is mandatory. Excluded stocks receive zero weight. The projection enforces non-negative weights, weights summing to one, single-name caps, sector/country/region/currency caps, liquidity limits, turnover caps and cash floors. If a projected action is infeasible, the engine falls back to the baseline optimiser.

The transaction-cost model estimates commission, half-spread/slippage, nonlinear market impact using participation rate, currency conversion placeholders and optional country transaction-tax placeholders. Costs reduce reward and are included in net benchmark metrics.

The historical regional PPO reward is benchmark-relative and net of costs. It
rewards return above the dated regional benchmark and penalises transaction
costs, incremental turnover, drawdown above 10%, realised absolute and active
tail losses, expected CVaR excess and volatility. Every component is emitted in
the reward decomposition. The live security-level projection retains the wider
quality, dividend, regime, liquidity and stress diagnostics; raw return alone is
never the objective.

The Wolf Chaos risk throttle scales actions during elevated chaos, blocks additions during high stress and can force a baseline fallback under severe chaos. Specialist agents are blended probabilistically rather than switched by a hard rule. The stable low-chaos specialist emphasises total return, dividend income, quality, cash flow, diversification and low turnover. The crisis high-chaos specialist emphasises CVaR, Expected Shortfall, drawdown control, liquidity, cash, defensive sectors, low leverage, dividend safety and reduced turnover. Inflation, regional-stress and credit-stress specialists are future-ready.

PPO is the primary policy interface with continuous residual actions,
deterministic evaluation and at least five seeds. A train-only ridge contextual
bandit and a convex residual allocator are lower-variance challengers. Their
hyperparameters are selected on validation data only, then frozen before the
legacy OOS evaluation. Historical mode fails closed if Stable-Baselines3 or the
required dated panel is unavailable; deterministic mock fallback is restricted
to explicit mock runs.

The optional TCN/GAP policy encoder is available only when PyTorch is present. It uses asset-independent temporal streams, shared parameters, causal dilated convolutions, residual blocks, Global Average Pooling, a cross-asset fully connected layer, cash logit and softmax portfolio weights. CAM/Grad-CAM explainability is future-ready for that path. Current explainability outputs include constraint traces, feature-group attribution, asset-time attribution and human-readable explanations that describe model attributions rather than causal relationships.

Training uses a frozen chronological split whose dates and SHA-256 panel hash are
saved in `drl_split_manifest.csv`. Public regional benchmarks and point-in-time
macro releases extend the common six-region panel to July 1997. The current
evidence has 268 train months through October 2019, a one-month embargo, 65
validation months through April 2025, a second one-month embargo and a 12-month
legacy locked OOS record from June 2025 through May 2026. Four bounded
environments per seed sample contiguous 24-month blocks from training dates only;
validation and OOS dates are never bootstrap candidates. Scaling is fit on
training data only and model selection uses validation only. The legacy OOS
window has already been observed once and is not called untouched. New deployment
evidence begins with prospective monthly shadow decisions after the policy freeze.

Benchmarking is labelled by information set. Fair comparisons give DRL and classical optimisers the same return, volatility, covariance, current-weight and cash inputs. Full Wolf comparisons allow richer scorecard, distributional, regime, sentiment, narrative, risk, stress and liquidity features. The model does not claim DRL beats MVO when DRL is using a richer state unless the comparison is clearly labelled.

Ablation tests compare regime/no-regime, distributional/no-distributional, sentiment/narrative variants, Differential Sharpe only versus full conservative reward, no transaction costs versus realistic costs, universal agent versus regime-specialist blend, MLP versus optional TCN/GAP and no throttle versus Wolf Chaos throttle.

The acceptance gate rejects DRL and selects the baseline optimiser when there is a hard constraint violation, infeasible projected action, missing eligibility mask, non-finite weight, negative weight, weight-sum error, CVaR breach, Expected Shortfall breach, severe stress breach, turnover breach, liquidity failure, throttle fallback, low confidence, excessive seed instability, validation underperformance or test leakage. In dry-run mode the DRL blend is capped at 25% and full replacement is disabled.

Current limitations:

- All five PPO seeds and both simpler challengers have negative validation
  information ratios. No challenger establishes positive active return in the
  legacy locked OOS diagnostic, so the optimiser retains 100% weight.
- Bloomberg ingestion is paused; existing licensed local aggregates are not
  redistributed.
- Historical membership, mappable inactive securities, observed volume and
  filing-acceptance coverage remain incomplete.
- Three completed prospective monthly shadow outcomes are required before any
  deployment reconsideration.
- TCN/GAP and CAM are research interfaces, not fully validated production policy explanations.
- Outputs are decision-support artifacts and not execution instructions.

Future research:

- full TCN + GAP PPO policy
- robust CAM / Grad-CAM attribution
- additional low-variance and offline-RL challengers after prospective evidence exists
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

## Risk, Stress Testing And Hedge Methodology

The Risk, Stress Testing and Hedge Recommendation Engine evaluates what can break the recommended optimised portfolio. Portfolio risk metrics include expected return, dividend yield, volatility, VaR, CVaR, Expected Shortfall, drawdown probability, dividend-cut risk, tail risk, skewness risk, liquidity risk, regime risk, narrative risk, HHI and effective holdings.

Risk contributions allocate expected return, dividend income, volatility, VaR, CVaR, Expected Shortfall, drawdown risk, dividend-cut risk, tail risk, liquidity risk, regime risk, narrative risk and alternative-data risk to individual holdings.

Stress testing uses a deterministic scenario library covering global risk-off, crisis/high-chaos, Europe recession, China policy stress, UK rate shock, inflation shock, credit stress, dividend-cut shock, liquidity shock, Meta Wolf shock, FX shock and correlation spike. Each scenario produces portfolio-level losses and stock-level contribution rows.

Hedge recommendations are split into equity-only actions and optional institutional placeholders. Defensive substitutions identify safer equity replacements by balance-sheet quality, dividend safety, CVaR/ES, regime suitability, narrative risk and liquidity. Optional institutional hedges are not executable without real pricing, liquidity and mandate data.

Output:

- `reports/outputs/stock_scorecard.csv`

## Investment Committee Reporting Methodology

The Investment Committee report is a presentation and governance layer. It consumes saved pipeline artifacts and keeps the model stack authoritative for calculations. Risk metrics, stress losses, optimiser weights, DRL acceptance decisions and final recommendations are displayed from their source outputs rather than recalculated inside the dashboard.

The report bundle combines executive summary, portfolio exposures, forecast diagnostics, branch comparison, risk, stress testing, hedge recommendations, DRL governance, data quality and narrative commentary. Narrative text describes signals as model attributions or associations and avoids causal language.

The immutable bundle layout supports auditability: each run is saved under `reports/outputs/ic/<model_run_id>/`, with manifest metadata, source file references, charts, HTML and optional PDF. The `latest` folder is a copied convenience view and does not replace the run-specific bundle.

Current limitations:

- The report quality depends on the completeness of upstream outputs.
- PDF rendering is optional and dependency-gated.
- The dashboard is optional and dependency-gated.
- The report does not validate live trading readiness or vendor data entitlements.
- Deterministic narrative is not a substitute for analyst review.
- Optional hedge concepts require execution review.
- Forecast and stress outputs remain model estimates.
- Model attribution describes association, not causality.
- The dashboard is read-only and does not execute trades.

## Validation Methodology

Validation is chronological: training precedes calibration/validation, which
precedes a locked evaluation period. Purge and embargo gaps reduce label overlap.
Scaling, imputation and covariance estimation use prior training data only. A
test period that has already been inspected is labelled legacy OOS rather than
untouched; future claims require a new prospective shadow record.

Point forecasts use MAE, RMSE, normalised RMSE, bias, directional accuracy and
rank IC by horizon and segment. Distribution validation measures P5/P50/P95
coverage, pinball loss, interval coverage and quantile crossing. Binary drawdown
risk compares raw, isotonic, Platt and beta calibration. Calibrators fit on the
training segment, method selection uses validation only, a 12-month embargo
separates labels, and the selected method is reported on the locked holdout.
Small samples remain explicitly insufficient.

Risk backtesting converts return-side negative VaR values to positive losses before Kupiec and Christoffersen tests. Expected Shortfall is the average positive loss beyond VaR. CVaR and Expected Shortfall at the same confidence level are reported without being double-counted in governance.

Portfolio validation applies weights after decision timestamps, drifts pre-trade weights, calculates half-turnover and deducts commissions, spread, slippage and square-root market impact. Missing returns are never silently replaced with zero. Benchmark comparisons use aligned periods and moving-block bootstrap confidence intervals.

DRL remains a challenger. It requires at least five stable seeds, compliant projected weights, net-of-cost classical outperformance, and no deterioration in drawdown or Expected Shortfall. Any accepted blend remains capped at 25%. Attribution is not causality.
