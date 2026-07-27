# Architecture

The repository is organised as a modular quant platform, with production logic in `src/` and scripts as thin entry points.

For visual pipeline diagrams, data-flow graphs and stage-by-stage diagnostic checks, see `docs/ARCHITECTURE_DIAGRAMS.md`.

- `data`: backend configuration, schemas, validators, normalisers, lineage, point-in-time views, snapshot building, CSV/DuckDB repositories, ingestion helpers and shadow comparison utilities.
- `data_ingestion`: universe, mock data, yfinance price ingestion, Alpaca integration and vendor adapter interfaces.
- `branches`: portfolio-aware quant, clean-sheet quant, mock LLM analyst benchmark and branch comparison engines.
- `portfolio`: current holdings loading, exposure and concentration diagnostics.
- `features`: financial, dividend, valuation, liquidity, risk and portfolio-fit features.
- `sentiment` and `alternative_data`: mock/local text ingestion, entity mapping, rule-based sentiment, event classification, rolling alternative-data features and risk overlays.
- `narrative`: financial concept extraction, occurrence/reoccurrence tracking, narrative frame construction, mock embeddings, semantic distance, temporal reframing and Markov transition analysis.
- `regime`: factor-regime lens, Wolf Chaos Index, informational regime drivers, fused dashboard, transition matrix and stock-level regime suitability scoring.
- `models`: conservative scorecard, ML forecasting, distributional risk forecasts, probabilistic validation, VaR/ES backtesting and walk-forward interfaces.
- `optimisation`: score-weighted, risk-parity, mean-variance, CVaR/ES, dividend-income and regime-aware portfolio construction, trade-list generation and constraint reporting.
- `risk`: VaR, CVaR, Expected Shortfall, drawdown, risk contributions, scenario library, risk reports and stress tests.
- `hedging`: equity-only hedges, optional institutional hedge placeholders and defensive substitution recommendations.
- `drl`: constrained PPO-style allocation overlay, regime-gated specialist policies, projection to hard optimiser constraints, benchmark comparison and explanation reports.
- `reporting`: canonical IC data loading, final portfolio resolution, deterministic narratives, static charts, HTML/Markdown/PDF rendering, source lineage, governance bundles and dashboard inputs.

## Active Universe

The active listed-equity universe covers DACH, EU ex-DACH, UK, US, Mainland China and Hong Kong. India is no longer part of the active stock-selection universe.

## Data Foundation

The persistence layer is additive and does not change model math. API and Python-library data is normalised in Python, written to DuckDB structured tables and optionally archived to Parquet for large datasets. Point-in-time SQL views expose latest-available prices, fundamentals, macro vintages and FX rates. Model runs and outputs can be written back to DuckDB for auditability.

Migration is configuration controlled through `configs/data.yaml`. `legacy_csv` remains the default. `shadow` mode supports dual-writing and comparing DuckDB snapshots against legacy CSV outputs before any production read switch. `duckdb` mode is reserved for validated point-in-time reads.

The data foundation has three layers. The raw layer stores retrieval metadata in DuckDB and keeps large payloads under `data/raw_archive/`. The clean layer contains typed, deduplicated tables such as `securities`, `security_identifiers`, `prices_daily`, `fundamentals_reported`, `dividends`, `fx_rates`, `macro_observations`, `news_documents` and `news_security_map`. The model-ready layer contains point-in-time snapshots for features, regimes, forecasts, scorecards, portfolios, optimisation, risk, stress tests, hedges, DRL and final recommendations.

The external-provider boundary is defined in `configs/data_sources.yaml` and implemented under `src/data_ingestion/`. Provider adapters normalise data before it reaches persistence or model code. The price router can query all credentialed sources, compare overlapping closes and select observations by explicit provider priority. Macro adapters retain source, retrieval time, availability date and vintage date so revisions are inserted as new point-in-time records. Current coverage combines yfinance, Alpaca, EODHD, Finnhub, iTick, Frankfurter, FRED, ECB, ONS, Bank of England, China Data and HKMA across every active region.

## Branching Pipeline

The pipeline runs three deterministic MVP branches before final optimisation/risk/stress/hedge outputs:

1. Portfolio-Aware Quant Model: prioritises current-portfolio improvement, dividend income, diversification and incremental risk.
2. Clean-Sheet Quant Model: ranks what the model would own from cash without existing holdings.
3. OpenAI / Claude Analyst Benchmark Model: mock structured analyst output for future provider integration.

The branch comparison engine flags agreement, disagreement and final review requirements. LLM agreement can increase confidence, but LLM output cannot override quant hard filters.

## Feature Store

The feature store converts mock or future vendor data into stock-level monthly features. Current modules cover dividend quality, cash-flow quality, balance-sheet strength, valuation, risk, liquidity, sentiment/narrative overlays, regime suitability and portfolio fit.

The output is `reports/outputs/features_monthly.csv`. Missing ML, regime and sentiment production signals use neutral placeholder scores until those engines are implemented.

## Conservative Scorecard

The scorecard applies hard filters before scoring. Filters cover equity instrument type, active listing status, market cap, liquidity, dividend yield, positive free cash flow, payout ratio, leverage, severe risk flags and incremental CVaR where available.

Scoring weights are configured around dividend safety, cash-flow quality, balance-sheet strength, valuation, regime suitability, ML expected risk-adjusted return, portfolio diversification benefit, liquidity and sentiment/alternative-data signal.

## ML Forecasting And Distributional Risk

The ML engine forecasts conditional return distributions rather than only point returns. In mock mode it estimates expected total return, volatility, dividend-cut probability, large-drawdown probability and distribution parameters for Normal, Student-t and an upgradeable skewed Student-t placeholder.

Inspired by distributional deep-learning research, the architecture is designed for future CNN, LSTM, Transformer and xLSTM forecasters that output `mu`, `sigma`, `nu` and `xi`. The current implementation does not add TensorFlow or PyTorch and does not train deep models. It derives P5/P50/P95, VaR, CVaR, Expected Shortfall, tail-risk scores, skewness-risk scores, PIT/LPS/CRPS-style validation proxies and VaR/ES backtest reports from deterministic mock inputs.

Research-only extension outputs cover sensitivity analysis, additional asset-class hooks, quantile-forecasting placeholders and distribution-driven trading signal scaffolding. These are not execution instructions and do not override hard filters.

## Portfolio Optimisation And Constraints

The optimiser converts scorecard, distributional forecasts, regime suitability, narrative risk, alternative-data risk and current holdings into target weights and trade actions. It runs equal-weight fallback, score-weighted, risk-parity, mean-variance, CVaR/Expected Shortfall constrained, dividend-income and regime-aware constructors.

Hard constraints cover long-only weights, single-name caps, liquidity, active equity status and exclusion flags. Soft constraints report portfolio dividend yield, volatility, VaR, CVaR, Expected Shortfall, turnover, HHI, effective holdings and concentration exposures. The final trade list translates current weight versus target weight into Buy, Increase, Reduce, Sell, Hold or Avoid actions with risk flags and rationale.

## Risk, Stress Testing And Hedges

The risk engine evaluates the recommended optimised portfolio using distributional forecasts, VaR, CVaR, Expected Shortfall, dividend-cut risk, drawdown probability, tail risk, skewness risk, liquidity, regime, narrative and alternative-data risk. It produces portfolio-level metrics and stock-level risk contribution ranks.

The stress engine applies deterministic mock scenarios including global risk-off, crisis/high-chaos, Europe recession, China policy stress, UK rate shock, inflation shock, credit stress, dividend-cut shock, liquidity shock, FX shock, correlation spike and Meta Wolf shock. It reports scenario losses and stock-level loss contributors.

The hedge engine separates equity-only recommendations from optional institutional hedges. It also suggests defensive substitutions for high-risk holdings. Optional institutional hedges are placeholders only and are not executable without mandate, pricing and market data.

## DRL Allocation Overlay

The DRL engine is a bounded challenger model layered on top of the selected classical optimiser. It follows the equation `w_drl = Projection_C(w_base + delta_w_agent)`: the PPO-style policy proposes small active-weight adjustments, regime-gated low-volatility and defensive specialists modify the action, then the final weights are projected through the existing hard exclusions, long-only rules and diversification caps.

The engine is cash-inclusive, long-only and mock/local by default. It includes transaction-cost, slippage, liquidity, risk-aversion and drawdown reward components, chronological train/validation/test split metadata, multiple random seeds, benchmark comparison, ablations and explanation outputs. TCN/GAP/CAM interfaces are present for future deep policy and asset-time attribution work, but the MVP policy does not call live APIs or execute trades.

The optimiser remains the primary allocator because it is deterministic and directly governed by explicit risk, concentration, liquidity and mandate constraints. DRL is a residual overlay: it receives point-in-time state features, emits bounded residual weight adjustments, passes through regime gating and the Wolf Chaos throttle, and is projected to the hard feasible set before any benchmark or trade-list output is written. If projection fails, risk limits breach, seed instability is excessive, confidence is too low or leakage is detected, the acceptance gate selects the baseline optimiser.

The DRL state combines portfolio weights, cash, temporal returns, volatility, fundamentals, dividend quality, distributional forecasts, regime, sentiment, narrative, liquidity, risk contribution, stress tests and eligibility masks. The action design is monthly or quarterly residual weight deltas, with no leverage, no shorting and cash included. Transaction costs cover commissions, half-spread/slippage, nonlinear market impact, currency conversion placeholders and optional tax placeholders.

Reward design uses Differential Sharpe plus net return, dividend income, regime suitability, diversification and quality components, then subtracts CVaR, Expected Shortfall, drawdown, transaction cost, turnover, dividend-risk, liquidity, narrative/credit and stress penalties. Specialist agents are blended probabilistically between stable low-chaos and crisis high-chaos policies, with inflation, regional-stress and credit-stress specialists left future-ready.

PPO is the primary policy interface with deterministic evaluation and multi-seed validation. Stable-Baselines3 is optional; mock fallback keeps the pipeline runnable. SAC and TD3 are documented challengers. TCN/GAP and CAM/Grad-CAM paths are optional architecture hooks rather than hard dependencies. Benchmarking is explicitly labelled as fair information-set or full Wolf so richer DRL inputs are not compared unfairly against simpler optimisers.

Acceptance outputs separate the baseline portfolio, DRL challenger portfolio, accepted/rejected/blended decision and final selected weights source. The DRL step does not silently overwrite the selected baseline optimiser portfolio.

## Sentiment And Alternative Data

The sentiment and alternative-data engine is a risk overlay, not a standalone buy signal. In mock mode it generates active-universe text documents, maps them to securities, scores sentiment with rule-based financial keyword dictionaries, classifies events and aggregates rolling monthly features.

Outputs include text documents, entity mentions, sentiment scores, event signals and `alt_features_monthly.csv`. The scorecard consumes sentiment/alt-data score, dividend risk, regulatory risk, governance red-flag count, credit stress and review/exclusion flags.

## Financial Narrative Reframing

The narrative engine looks beyond sentiment to detect how the equity story is being framed and reframed over time. It extracts financial concepts, tracks first occurrences and reoccurrences, builds co-occurring concept frames, embeds frames with a deterministic mock provider, measures semantic distance to risk/quality anchors, classifies temporal narrative states and estimates Markov transition probabilities.

Narrative features feed the scorecard as risk overlays: high risk reframing, dividend-risk similarity, credit-stress similarity, governance/regulatory similarity or negative-to-distress transition probability can trigger review, cap weights or exclude names. Narrative output cannot override hard quant risk controls.

## Regime Analysis And Market State

The regime engine is a market-state overlay that runs in deterministic mock mode. It builds a factor lens across Global, DACH, EU ex-DACH, UK, US, Mainland China and Hong Kong, estimates factor-regime probabilities, calculates a FCIX-lite Wolf Chaos Index, models informational deterioration drivers from alternative data and narrative features, fuses the signals into a dominant market regime and scores every stock for suitability under that regime.

Regime outputs feed the scorecard, portfolio-aware branch, clean-sheet branch, mock analyst benchmark, stress tests and hedge recommendations. The engine can reduce weights, trigger review/exclusion flags and add regime-conditioned stress/hedge overlays, but it cannot override hard quant controls.

## Investment Committee Reporting

The Investment Committee reporting layer is a read-only consumer of precomputed model artifacts. It loads current portfolio, scorecard, branch comparison, final recommendation, optimiser, risk, stress, hedge, regime, DRL and data-quality outputs from the configured data backend, resolves changing column names through a reporting column resolver and renders a deterministic report bundle.

The reporting pipeline is intentionally downstream of the model stack:

1. load precomputed outputs
2. validate availability and schema quality
3. resolve selected baseline and DRL challenger portfolios
4. summarise exposures, forecasts, branch agreement, risk, stress, hedges and DRL governance
5. generate charts and non-causal narrative
6. render HTML and optional PDF
7. write an immutable bundle plus a copied `latest` view

Opening the dashboard or rendering a report does not rerun forecasts, optimisation, risk, stress tests, DRL policies or external data ingestion. The report preserves the final selected weights source and keeps baseline optimiser, DRL challenger and accepted/rejected/blended status separate.

Final portfolio resolution follows explicit final weights, accepted/blended DRL, selected constrained optimiser, CVaR-constrained, regime-aware, score-weighted and equal-weight fallback order. Invalid, negative or non-unit-sum weights are rejected. HTML and the JSON bundle are required pipeline artifacts; PDF and dashboard dependencies are optional.

## Validation And Governance

`src/validation/` consumes immutable model artifacts after IC reporting. Its layers are:

1. evidence loading and forecast/outcome alignment by security, origin, horizon and realisation date
2. point-in-time, chronology, purge/embargo and leakage controls
3. point, distribution, binary-event and tail-risk calibration
4. realised portfolio, cost, benchmark, regime and regional validation
5. hard-constraint, DRL, sensitivity, ablation and concentration controls
6. statistical confidence, component scoring and production governance
7. immutable Markdown/HTML report bundles plus DuckDB lineage registration

Daily pipeline runs use smoke mode. Full and release-candidate modes are explicit because historical bootstrap, sensitivity and ablation work can be expensive. Validation never promotes DRL when the constrained classical baseline fails governance.

## Production Monitoring And Operations

`src/production/` operationalises the existing stack without changing model math. It adds operating modes, production run locks, preflight and post-run health checks, freshness checks, lightweight drift monitoring, approval gates, alert routing, incident tracking, immutable production manifests and copied latest-successful/latest-approved pointers.

The scheduler boundary is outside Python. Windows Task Scheduler scripts live under `scripts/windows/`, and Linux cron examples live under `scripts/linux/`. All persisted timestamps are UTC; human-facing schedules are configured for Asia/Singapore.
