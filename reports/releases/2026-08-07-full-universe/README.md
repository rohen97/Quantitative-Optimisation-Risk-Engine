# Full-Universe Model Evidence

Validation run: `validation-20260812T110002-75367a51`

## Decision

- Governance status: **CONDITIONALLY_APPROVED**
- Overall score: **80.0/100**
- Critical failures: **0**
- Active universe: **55,504** of **112,570** listed and historical securities
- Walk-forward evidence: **156,764** forecasts and **156,312** aligned outcomes
- Portfolio: **60** monthly decisions, **13.7%** annualised net return, **1.16** Sharpe

The result is capped at conditional approval because the free-source history reconstructs filing availability and does not provide immutable historical universe, volume, sentiment, narrative, or regime vintages.

## Scorecard

| component | score | status |
| --- | --- | --- |
| data_integrity | 20.0/20 | PASS |
| point_in_time | 7.5/15 | WARNING |
| forecast_performance | 15.0/15 | PASS |
| distribution_calibration | 10.0/10 | PASS |
| risk_backtesting | 7.5/15 | WARNING |
| portfolio_net_of_costs | 5.0/10 | WARNING |
| constraint_compliance | 10.0/10 | PASS |
| stability_sensitivity | 5.0/5 | PASS |

![Validation scorecard](plots/validation_scorecard.png)

## Forecasts

The point-forecast component is **PASS** and the distribution-calibration component is **PASS** under the configured gates.

![Forecast quality](plots/forecast_quality.png)

![Distribution coverage](plots/distribution_coverage.png)

## Portfolio And Risk

The constrained Wolf portfolio is **WARNING** on the net-of-cost gate: annual turnover is 2.11x and annualised cost drag is 2.35%. It returned -1.18% per year relative to equal weight over this short sample; the paired test p-value is 0.741. Hard-constraint compliance is **PASS** and the daily EWMA VaR backtest is **WARNING**.

![Cumulative returns](plots/cumulative_returns.png)

![Portfolio comparison](plots/portfolio_comparison.png)

![VaR backtest](plots/risk_backtest.png)

![Final exposures](plots/final_portfolio_exposures.png)

![Regional rank IC](plots/regional_rank_ic.png)

## Package Contents

- `validation/`: complete governance output, including HTML and Markdown reports.
- `validation/portfolio_monthly_returns.csv`: all dated Wolf, equal-weight, and cap-weight control returns.
- `investment_committee/`: complete IC report bundle, PDF, data tables, and charts.
- `final_portfolio_weights.csv`: resolved 20-name final portfolio.
- `universe_summary.csv`: compact active and delisted security coverage by region.
- `walk_forward_manifest.json`: source profile, chronology checks, limitations, and evidence counts.
- `manifest.json`: SHA-256 checksum and byte size for every release artifact.

Research output only. Conditional approval is not authorization for unattended live trading.

## Investment Committee Briefing

The current evidence, target holdings, portfolio comparisons, risks and
proposed live-pilot gates are published in the
[PowerPoint briefing](../../presentations/wolf_investment_principal/wolf_quant_model_ic_briefing.pptx),
[rendered PDF](../../presentations/wolf_investment_principal/wolf_quant_model_ic_briefing_2026-08-13.pdf),
and [investment principal report](../../presentations/wolf_investment_principal/investment_principal_report.md).
