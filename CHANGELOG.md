# Changelog

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
