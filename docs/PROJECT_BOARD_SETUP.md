# GitHub Projects Setup - The Wolf Quant Model

## Recommended GitHub Project

Create a GitHub Project called:

```text
The Wolf Quant Model
```

Use it to manage the 6-month build across 12 two-week sprints.

## Views

| View | Purpose |
|---|---|
| Roadmap | Month 1 to Month 6 timeline |
| Sprint Board | Active sprint execution |
| Module Board | Workstream view by system module |
| Validation Board | Backtests, leakage checks, risk tests and model validation |
| Bug Bash | Month 5 and Month 6 debugging |
| Release Board | v0.1 to v1.0 release tracking |

## Fields

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

## Suggested Status Flow

```text
Backlog -> Ready -> In Progress -> Review -> Done
```

Use `Blocked` only when a task is waiting on missing data, unavailable APIs, broken dependencies, or unresolved design decisions.

## Issue Hierarchy

Use this hierarchy:

```text
Monthly epic issue
    |
Sprint issue
    |
Module task issue
    |
PR / commit
```

## Seed Epics

- Current portfolio engine.
- Database and security master.
- Universe and data ingestion.
- Feature store.
- Conservative scorecard.
- Sentiment and alternative-data engine.
- Regime engine.
- ML forecasting.
- Portfolio optimisation.
- DRL overlay prototype.
- Risk, stress testing and hedging.
- Reporting and dashboard.

## Feature Freeze

Feature freeze happens at the end of Month 4 / Sprint 8.

Month 5 and Month 6 should be reserved for:

- Integration
- Debugging
- Validation
- Backtesting
- Risk checks
- Stress testing
- Dashboard hardening
- Documentation
- Final investment committee outputs
