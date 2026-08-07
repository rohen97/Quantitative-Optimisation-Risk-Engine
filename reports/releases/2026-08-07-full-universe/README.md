# Full-Universe Model Evidence

Validation run: `validation-20260807T092326-e5e0e476`

## Decision

- Governance status: **CONDITIONALLY_APPROVED**
- Overall score: **87.5/100**
- Critical failures: **0**
- Active universe: **55,504** of **112,570** listed and historical securities
- Walk-forward evidence: **73,524** forecasts and **73,072** aligned outcomes
- Portfolio: **25** monthly decisions, **18.9%** annualised net return, **1.75** Sharpe

The result is capped at conditional approval because the free-source history reconstructs filing availability and does not provide immutable historical universe, volume, sentiment, narrative, or regime vintages.

## Scorecard

| component | score | status |
| --- | --- | --- |
| data_integrity | 20.0/20 | PASS |
| point_in_time | 7.5/15 | WARNING |
| forecast_performance | 15.0/15 | PASS |
| distribution_calibration | 5.0/10 | WARNING |
| risk_backtesting | 15.0/15 | PASS |
| portfolio_net_of_costs | 10.0/10 | PASS |
| constraint_compliance | 10.0/10 | PASS |
| stability_sensitivity | 5.0/5 | PASS |

![Validation scorecard](plots/validation_scorecard.png)

## Forecasts

All point-forecast horizons passed the configured directional-accuracy, rank-IC, and normalized-RMSE gates. Distribution coverage passes at 3M and 6M and remains a warning at 9M and 12M.

![Forecast quality](plots/forecast_quality.png)

![Distribution coverage](plots/distribution_coverage.png)

## Portfolio And Risk

The constrained Wolf portfolio passes net-of-cost, turnover, drawdown, hard-constraint, and daily EWMA VaR backtests. Equal weight outperformed over this short sample, but the difference was not statistically significant.

![Cumulative returns](plots/cumulative_returns.png)

![Portfolio comparison](plots/portfolio_comparison.png)

![VaR backtest](plots/risk_backtest.png)

![Final exposures](plots/final_portfolio_exposures.png)

![Regional rank IC](plots/regional_rank_ic.png)

## Package Contents

- `validation/`: complete governance output, including HTML and Markdown reports.
- `investment_committee/`: complete IC report bundle, PDF, data tables, and charts.
- `final_portfolio_weights.csv`: resolved 20-name final portfolio.
- `universe_summary.csv`: compact active and delisted security coverage by region.
- `walk_forward_manifest.json`: source profile, chronology checks, limitations, and evidence counts.
- `manifest.json`: SHA-256 checksum and byte size for every release artifact.

Research output only. Conditional approval is not authorization for unattended live trading.
