# The Wolf Quant Model - 6-Month Project Management Plan

## Current MVP Status

The repository now contains a runnable mock-data MVP scaffold. It includes modular source packages, configs, scripts, pytest coverage, generated sample outputs, and a basic dashboard skeleton.

Validated commands:

```bash
python scripts/run_full_pipeline.py
pytest
```

The next engineering issue should replace mock data with point-in-time CSV/vendor fixtures and validation tests.

## Project Objective

Build a portfolio-aware quant equity selection engine for listed equities in DACH, Shanghai/China, Hong Kong and India. The model will recommend conservative dividend and cash-flow equities after accounting for the current portfolio, regime analysis, sentiment/alternative data, ML forecasts, DRL portfolio optimisation, VaR/CVaR, stress tests and hedge requirements.

## Operating Model

- **GitHub Issues**: source of truth for tasks, epics and sprint work.
- **GitHub Projects**: roadmap, sprint board and execution tracker.
- **VS Code + Codex**: development environment.
- **Git branches**: one branch per module or issue.
- **Pull Requests**: review checkpoint before merging to `main`.
- **Month 5 onwards**: feature freeze, finalisation, debugging, validation and documentation.

## GitHub Project Setup

Create a GitHub Project called:

```text
The Wolf Quant Model
```

Recommended project views:

| View | Purpose |
|---|---|
| Roadmap | Month 1 to Month 6 timeline |
| Sprint Board | Current 2-week sprint execution |
| Module Board | Data, features, sentiment, regime, ML, DRL, risk, dashboard |
| Validation Board | Backtests, leakage checks, risk tests and model validation |
| Bug Bash | Month 5 and Month 6 debugging |
| Release Board | v0.1 to v1.0 release tracking |

Recommended custom fields:

| Field | Type | Values |
|---|---|---|
| Status | Single select | Backlog, Ready, In Progress, Review, Blocked, Done |
| Month | Single select | Month 1, Month 2, Month 3, Month 4, Month 5, Month 6 |
| Sprint | Iteration | Sprint 1 to Sprint 12 |
| Workstream | Single select | Data, Database, Features, Sentiment, Alternative Data, Regime, ML, DRL, Optimisation, Risk, Hedging, Dashboard, DevOps, Docs |
| Priority | Single select | P0, P1, P2, P3 |
| Deliverable Type | Single select | Code, Research, Model, Data, Dashboard, Report, Test, Documentation |
| Acceptance Status | Single select | Not Started, Partial, Passed, Failed |
| Target Date | Date | Due date |
| Estimate | Number | Story points or days |

## Branching Workflow

```text
main
  protected stable branch

develop
  integration branch

feature/<issue-number>-short-name
  feature branches

bugfix/<issue-number>-short-name
  debugging branches

release/v0.x
  release stabilisation branches
```

Example workflow:

```bash
git checkout main
git pull origin main
git checkout -b feature/portfolio-ingestion
git add .
git commit -m "Build current portfolio ingestion module"
git push origin feature/portfolio-ingestion
```

Then open a pull request into `main` or `develop`, depending on whether a `develop` branch is being used.

## Timeline Summary

| Month | Focus | Output |
|---|---|---|
| Month 1 | Foundation, database and current portfolio engine | Repo structure, current portfolio ingestion, diagnostics, database schema v0 |
| Month 2 | Feature store and conservative scorecard | Universe engine, price/fundamental/dividend ingestion, stock scorecard v0 |
| Month 3 | Sentiment, alternative data and regime engine | Sentiment analyser, alt-data event detection, regime engine, scorecard v1 |
| Month 4 | ML forecasting, portfolio optimisation and DRL prototype | Return/risk forecasts, quantile outputs, HRP/MVO/CVaR optimiser, DRL prototype |
| Month 5 | Finalisation, integration and debugging I | Full pipeline, validation checks, risk engine, stress tests, hedge recommender |
| Month 6 | Final debugging, deployment and IC pack | Dashboard, documentation, final validation, investment committee report, v1.0 release |

## Sprint Plan

| Sprint | Weeks | Focus | Release Tag |
|---|---:|---|---|
| Sprint 1 | Weeks 1-2 | Repo, architecture, GitHub Project setup | v0.1-foundation |
| Sprint 2 | Weeks 3-4 | Database schema and current portfolio diagnostics | v0.2-portfolio-baseline |
| Sprint 3 | Weeks 5-6 | Universe, price, fundamentals and dividend ingestion | v0.3-data-ingestion |
| Sprint 4 | Weeks 7-8 | Feature store and conservative scorecard | v0.4-scorecard |
| Sprint 5 | Weeks 9-10 | Sentiment and alternative-data ingestion | v0.5-sentiment |
| Sprint 6 | Weeks 11-12 | Regime engine and score integration | v0.6-regime |
| Sprint 7 | Weeks 13-14 | ML forecasting and quantile outputs | v0.7-ml-forecasting |
| Sprint 8 | Weeks 15-16 | Optimisation, DRL prototype and backtesting | v0.8-feature-freeze |
| Sprint 9 | Weeks 17-18 | Full integration and validation | v0.9-integration |
| Sprint 10 | Weeks 19-20 | Risk, stress tests, hedging and debugging | v0.9-rc1 |
| Sprint 11 | Weeks 21-22 | Dashboard and production hardening | v0.9-rc2 |
| Sprint 12 | Weeks 23-24 | Final docs, final debugging and v1.0 release | v1.0.0 |

## Month 1 - Foundation, Database and Current Portfolio Engine

### Goal

Set up the project properly and make the system understand the current portfolio before recommending any new stocks.

### Deliverables

- GitHub repo structure.
- Documentation skeleton.
- Database schema v0.
- Current portfolio ingestion module.
- Portfolio diagnostics module.
- Basic CI/test structure.

### Acceptance Criteria

- The repo has a clean folder structure.
- A current portfolio CSV/Excel file can be loaded.
- The system calculates portfolio weights, HHI, effective holdings, top holdings, sector exposure, country exposure and currency exposure.
- Outputs are saved to `reports/outputs/`.

## Month 2 - Feature Store and Conservative Stock Scorecard

### Goal

Build the core conservative equity selection layer using dividends, cash flow, balance sheet strength, valuation, liquidity and risk.

### Deliverables

- Equity universe engine for DACH, Shanghai/China, Hong Kong and India.
- Security master.
- Price ingestion.
- Fundamental ingestion.
- Dividend ingestion.
- Feature store v0.
- Conservative scorecard v0.

### Acceptance Criteria

- The model produces a ranked stock universe.
- Each stock has dividend yield, FCF yield, payout ratio, ROE/ROIC, leverage, volatility, beta and liquidity features.
- Conservative hard filters are applied before scoring.

## Month 3 - Sentiment, Alternative Data and Regime Engine

### Goal

Add an early-warning layer that detects sentiment deterioration, dividend risk, regulatory risk, credit stress and macro/market regimes.

### Deliverables

- Text ingestion pipeline.
- Company entity mapping.
- Sentiment scoring.
- Event detection.
- Alternative-data feature tables.
- Regime engine v0.
- Sentiment/regime-adjusted stock scorecard.

### Acceptance Criteria

- Each stock has rolling 30d/90d sentiment features.
- Event flags exist for dividend cuts, profit warnings, buybacks, management changes, capital raises and regulatory probes.
- Regime suitability is included in the final stock score.

## Month 4 - ML Forecasting, Portfolio Optimisation and DRL Prototype

### Goal

Build the main forecasting and allocation layer. This is the last month for new features.

### Deliverables

- 3M/6M/9M/12M forward return target generator.
- Volatility, VaR and CVaR targets.
- ML forecasting models.
- Quantile return outputs: P5, P50, P95.
- Portfolio-aware ranking.
- HRP, MVO and CVaR optimisers.
- DRL environment prototype.
- Backtesting engine v0.

### Acceptance Criteria

- The model outputs risk-adjusted recommendations across 3M, 6M, 9M and 12M horizons.
- Each candidate stock has expected return, VaR, CVaR, P5/P50/P95 return and portfolio fit score.
- DRL is treated as an overlay and compared against simpler baselines.
- Feature freeze is declared at the end of Month 4.

## Month 5 - Finalisation, Integration and Debugging I

### Goal

No major new features. Stabilise the system and validate it.

### Deliverables

- End-to-end pipeline run.
- Integrated config system.
- Data quality checks.
- Point-in-time leakage checks.
- Final VaR/CVaR risk engine.
- Stress-test engine.
- Hedge recommendation engine.
- Model validation report v1.

### Acceptance Criteria

- `scripts/run_full_pipeline.py` works without manual notebook edits.
- P0 data and model validation checks pass.
- Stress tests are generated for current and recommended portfolios.
- Hedge recommendations are generated.
- P0/P1 bugs are tracked and actively resolved.

## Month 6 - Final Debugging, Deployment and Investment Committee Pack

### Goal

Make the project presentable, reproducible and usable.

### Deliverables

- Final dashboard.
- Final documentation.
- Final user guide.
- Final model validation report.
- Investment committee report.
- Final GitHub release v1.0.0.

### Acceptance Criteria

- P0/P1 bugs are closed.
- Dashboard produces recommendation, risk, stress and hedge outputs.
- The project is reproducible from a fresh clone.
- Documentation explains methodology, assumptions and limitations.

## Definition of Done

Every issue is only done when it has:

- Working code.
- Unit tests.
- Integration test where relevant.
- Example output.
- Documentation.
- Logged assumptions.
- Known limitations.
- GitHub issue closed through a commit or PR.

Model-related issues also need:

- Backtest or validation output.
- Leakage check.
- Feature importance or explanation output where relevant.
- Risk/stress-test behaviour.

## Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Data coverage is weak for China/HK/India | High | High | Use vendor adapters and fallback sources |
| Fundamentals introduce look-ahead bias | Medium | Very High | Use filing dates and point-in-time checks |
| Sentiment data is noisy | Medium | Medium | Use as a risk overlay, not sole buy signal |
| DRL overfits | High | High | Compare against HRP/MVO/CVaR and restrict with hard risk limits |
| Model recommends yield traps | Medium | High | Use FCF cover, payout safety and dividend-risk overrides |
| Pipeline becomes too complex | Medium | High | Feature freeze at end of Month 4 |
| Debugging overruns | Medium | High | Reserve Month 5 and Month 6 for finalisation/debugging |

## Codex Development Rule

Codex should be used issue-by-issue. Do not ask Codex to build the whole model at once.

Recommended prompt format:

```text
Work on GitHub Issue #[number].
Build only the module described in the issue.
Do not modify files outside this repository.
Do not add unrelated features.
Add tests and update documentation.
```
