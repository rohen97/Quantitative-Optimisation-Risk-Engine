# Changelog

## 1.7.0rc1 - 2026-08-12 - Portfolio Backtest Evidence Release Candidate

### Added

- A 1997-present monthly replay for all 13 investable portfolio outputs, with capital rules derived from the current portfolio and independent research allocations.
- S&P 500, SPY adjusted-close, six regional indices, equal-region, and portfolio-specific regional benchmark comparisons in USD.
- Standalone Dow Jones, Nasdaq, Russell 2000, FTSE 250, CAC 40, EURO STOXX 50, Nikkei 225, Swiss Market, MSCI EAFE proxy, and MSCI ACWI proxy paths.
- Lagged interest-rate level/direction and market-regime analysis, retrospective NBER recession splits, and 13 source-backed macro-event windows through the 2026 US-Iran war.
- A 25 bp annual bank AUM charge, reconciled to USD 465,151.305 at USD 186,060,522 reference AUM, with gross, pre-fee, and fully net wealth accounting.
- A lagged trend and volatility-controlled regional-index challenger with point-in-time signals.
- Circular moving-block resampling and correlated Student-t AR(1)/EWMA Monte Carlo evidence.
- PSR, Minimum Track Record Length, Lo-adjusted Sharpe, Sidak family-wise control, correlation-clustered trial counts, and Deflated Sharpe Ratios.
- Finnhub and Eastmoney historical-fundamentals adapters with observed or conservatively reconstructed filing availability for US, Mainland China, and Hong Kong equities.
- Rendered HTML and 42-page PDF reports, 17 publication plots, plain-language interpretation for every table, compact CSV evidence, a source manifest, and SHA-256 checksums.

### Changed

- Enforced a hard 5% ADV trade cap in historical replay; unfilled allocations now remain in cash and are reported.
- Updated current-derived starting capital from USD 80,540 to the supplied USD 186,060,522 AUM; independent optimiser, clean-sheet, LLM, and index paths remain at USD 100,000.
- Converted non-USD holdings and benchmarks with historical FRED FX and assigned pre-listing cash to 3-month Treasury bills.
- Added explicit, auditable adjusted-price spike and persistent-level-shift repairs.
- Extended the separate reconstructed point-in-time model record from 25 to 60 monthly decisions without splicing it into the retrospective holdings replay.
- Added an exact cardinality fallback with a bounded cash sleeve for sparse early-region anchors while preserving every equity concentration cap.

### Validation

- All requested market symbols have cached price histories from 1997 through the latest complete month where listed.
- The common 80%-investable comparison window begins in September 2013.
- Raw daily adjusted-close moves over 50% are reduced from seven to zero through six logged repair events.
- 322 automated tests pass in deterministic mock mode, including historical-provider parsing, exchange-holiday alignment, constrained cash, and current-artifact precedence tests.
- The reconstructed walk-forward contains 156,764 forecasts, 156,312 aligned outcomes, 60 monthly portfolio decisions, and 1,141 daily risk observations.
- Governance is `CONDITIONALLY_APPROVED` at 80.0/100 with zero critical failures, zero chronology violations, and zero hard-constraint breaches.
- Point-in-time alpha is not statistically significant against either equal-weight or cap-weight eligible controls; deployable alpha remains `NOT_ESTABLISHED`.
- The annual reference charge reconciles to the cent; external benchmark paths remain uncharged.
- The rendered report contains 19 standalone benchmark paths and all 13 configured event windows.
- Long-history holdings results are labeled for critical selection look-ahead and survivorship limitations and are not presented as historical model-selection skill.

## 1.6.0rc1 - 2026-08-07 - Full-Universe Validation Release Candidate

### Added

- Resumable free-data enrichment for security reference data and reported annual fundamentals.
- TickDB market-data integration for Mainland China and Hong Kong equities.
- Continuous and batched price-backfill runners with provider fallback and progress accounting.
- A two-phase observed-data pipeline that computes regional intermediates before one global ranking, optimisation, risk, DRL, and reporting pass.
- Reconstructed point-in-time walk-forward evidence across 25 monthly anchors.
- Historical forecast, calibration, portfolio, transaction-cost, regional, regime, sensitivity, constraint, and benchmark evaluation.
- Daily RiskMetrics EWMA VaR and Expected Shortfall forecasts with prior-day-only updates.
- A compact, checksummed GitHub evidence package containing the complete validation and investment-committee reports and publication plots.

### Changed

- Expanded the active universe to DACH, EU ex-DACH, UK, US, Mainland China, and Hong Kong.
- Switched the configured model backend to DuckDB while retaining explicit mock/CSV fallback for tests.
- Hardened global portfolio constraints, feasibility reporting, branch resolution, DRL gating, data-quality checks, and reporting diagnostics.
- Updated documentation from the mock scaffold to the observed full-universe release workflow.

### Validation

- 112,570 active and delisted securities in the security master; 55,504 are active.
- 73,524 historical forecasts and 73,072 aligned realised outcomes.
- 25 monthly portfolio decisions and 494 daily risk observations.
- Governance score 87.5/100 with zero critical failures and zero hard-constraint breaches.
- Point forecasts pass at 3M, 6M, 9M, and 12M.
- Daily EWMA VaR backtests pass at 95% and 99% confidence.
- 288 automated tests pass with deterministic mock inputs.

### Known Limitations

- Approval remains `CONDITIONALLY_APPROVED` because filing availability is partly reconstructed.
- Current universe and reference metadata introduce survivorship and historical-reference bias.
- Historical traded volume and immutable sentiment, narrative, and regime vintages are unavailable.
- Distribution calibration remains a warning at 9M and 12M.
- Credentials previously present in repository history must be rotated and history remediation coordinated separately.
