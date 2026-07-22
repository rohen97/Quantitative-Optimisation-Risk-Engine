# Sprint Timeline - The Wolf Quant Model

## Current MVP Note

A runnable mock-data MVP has been scaffolded ahead of the full roadmap. Treat it as the baseline for Sprint 1/Sprint 2 validation and iterate issue-by-issue from here.

## Sprint Overview

| Sprint | Weeks | Month | Focus | Release Tag |
|---|---:|---|---|---|
| Sprint 1 | Weeks 1-2 | Month 1 | Repo, architecture, GitHub Project setup | v0.1-foundation |
| Sprint 2 | Weeks 3-4 | Month 1 | Database schema and current portfolio diagnostics | v0.2-portfolio-baseline |
| Sprint 3 | Weeks 5-6 | Month 2 | Universe, price, fundamentals and dividend ingestion | v0.3-data-ingestion |
| Sprint 4 | Weeks 7-8 | Month 2 | Feature store and conservative scorecard | v0.4-scorecard |
| Sprint 5 | Weeks 9-10 | Month 3 | Sentiment and alternative-data ingestion | v0.5-sentiment |
| Sprint 6 | Weeks 11-12 | Month 3 | Regime engine and score integration | v0.6-regime |
| Sprint 7 | Weeks 13-14 | Month 4 | ML forecasting and quantile outputs | v0.7-ml-forecasting |
| Sprint 8 | Weeks 15-16 | Month 4 | Optimisation, DRL prototype and backtesting | v0.8-feature-freeze |
| Sprint 9 | Weeks 17-18 | Month 5 | Full integration and validation | v0.9-integration |
| Sprint 10 | Weeks 19-20 | Month 5 | Risk, stress tests, hedging and debugging | v0.9-rc1 |
| Sprint 11 | Weeks 21-22 | Month 6 | Dashboard and production hardening | v0.9-rc2 |
| Sprint 12 | Weeks 23-24 | Month 6 | Final docs, final debugging and v1.0 release | v1.0.0 |

## Sprint 1 - Repo, Architecture and Project Setup

Deliverables:
- Repo skeleton.
- README.
- Architecture document.
- Project plan.
- Data dictionary skeleton.
- GitHub Project setup guide.
- Basic CI structure.

Acceptance criteria:
- Project opens cleanly in VS Code.
- Folder structure exists.
- Documentation explains the intended engine architecture.

## Sprint 2 - Database Schema and Current Portfolio Diagnostics

Deliverables:
- Current portfolio ingestion.
- Portfolio diagnostics.
- HHI, effective holdings and concentration metrics.
- Sector, country and currency exposure.
- Database schema v0.

Acceptance criteria:
- A CSV/Excel current portfolio file can be loaded.
- Diagnostics outputs are generated in `reports/outputs/`.

## Sprint 3 - Universe and Data Ingestion

Deliverables:
- DACH, EU ex-DACH, UK, US, Shanghai/China and Hong Kong universe engine.
- Security master.
- Price ingestion.
- Fundamental ingestion.
- Dividend ingestion.

Acceptance criteria:
- Initial universe loads successfully.
- Price/fundamental/dividend tables can be created or mocked.

## Sprint 4 - Feature Store and Conservative Scorecard

Deliverables:
- Feature store v0.
- Dividend safety score.
- Cash-flow quality score.
- Balance-sheet score.
- Valuation score.
- Liquidity score.
- Final conservative scorecard v0.

Acceptance criteria:
- Ranked stock scorecard is generated.
- Hard filters remove unsafe or insufficient-quality equities.

## Sprint 5 - Sentiment and Alternative Data Ingestion

Deliverables:
- Text ingestion module.
- Entity mapping.
- Sentiment analyser v0.
- Alternative-data event schema.
- Event classifier v0.

Acceptance criteria:
- Text documents can be mapped to securities.
- Sentiment and event signals are generated.

## Sprint 6 - Regime Engine and Score Integration

Deliverables:
- Regime variables.
- Rule-based regime engine v0.
- Optional HMM prototype.
- Regime suitability score.
- Updated scorecard v1 with sentiment and regime features.

Acceptance criteria:
- Each stock has regime and sentiment-adjusted scores.

## Sprint 7 - ML Forecasting and Quantile Outputs

Deliverables:
- Forward return target generator.
- Ridge/Elastic Net baseline.
- Random Forest / XGBoost or LightGBM model.
- Quantile return model.
- VaR/CVaR forecast outputs.
- Walk-forward validation.

Acceptance criteria:
- 3M/6M/9M/12M forecasts are produced.
- P5/P50/P95 expected return is produced per stock.

## Sprint 8 - Optimisation, DRL Prototype and Feature Freeze

Deliverables:
- Portfolio-aware ranking.
- Equal-weight baseline.
- HRP optimiser.
- Mean-variance optimiser.
- CVaR-constrained optimiser.
- DRL environment skeleton.
- Backtesting engine v0.

Acceptance criteria:
- Model outputs target weights.
- DRL output is compared against simpler baselines.
- Feature freeze is declared.

## Sprint 9 - Full Integration and Validation

Deliverables:
- End-to-end pipeline script.
- Config system.
- Data quality checks.
- Point-in-time leakage checks.
- Model comparison report.

Acceptance criteria:
- `scripts/run_full_pipeline.py` works without manual notebook edits.

## Sprint 10 - Risk, Stress Tests, Hedging and Debugging

Deliverables:
- Risk engine v1.
- Stress-test engine v1.
- Hedge recommendation engine v1.
- Bug bash board.
- Model validation report v1.

Acceptance criteria:
- Stress tests and hedge recommendations are produced for current and recommended portfolios.

## Sprint 11 - Dashboard and Production Hardening

Deliverables:
- Dashboard v1.
- Executive summary page.
- Recommendation page.
- Risk/stress page.
- Hedge book page.
- Full CI checks.

Acceptance criteria:
- Dashboard can be run locally and produces key IC-ready views.

## Sprint 12 - Final Docs, Final Debugging and v1.0 Release

Deliverables:
- Final documentation.
- Final user guide.
- Final validation report.
- Investment committee pack.
- v1.0.0 release.

Acceptance criteria:
- P0/P1 bugs are closed.
- Project is reproducible from a fresh clone.
- Final outputs are ready for presentation.
