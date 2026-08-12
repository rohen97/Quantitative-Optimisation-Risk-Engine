# Portfolio Backtest Evidence: 1997 to 2026

This package compares every investable portfolio output currently produced by the repository. Current-derived allocations start with the observed current NAV of $80,540; independent clean-sheet, optimiser, and LLM portfolios start with $100,000.

> **Interpretation boundary:** the long history is a retrospective replay of today's selected holdings and weights. It contains selection look-ahead and survivorship bias and is not a 1997 point-in-time model backtest. The shorter reconstructed point-in-time model evidence is reported separately.

## Requested Window

| Portfolio | Start | CAGR | Sharpe | Max drawdown | Ending value | PnL |
|---|---:|---:|---:|---:|---:|---:|
| Current Portfolio | $80,540 | 14.75% | 0.77 | -42.94% | $4,661,466 | $4,580,926 |
| Portfolio-Aware Overlay | $80,540 | 13.34% | 0.80 | -39.00% | $3,242,312 | $3,161,772 |
| Clean-Sheet Quant | $100,000 | 9.24% | 0.68 | -27.73% | $1,355,449 | $1,255,449 |
| LLM Analyst Benchmark | $100,000 | 9.77% | 0.83 | -20.90% | $1,563,108 | $1,463,108 |
| CVaR-Constrained Optimiser | $100,000 | 9.99% | 0.67 | -31.93% | $1,657,883 | $1,557,883 |
| Dividend-Income Optimiser | $100,000 | 10.78% | 0.64 | -41.14% | $2,049,676 | $1,949,676 |
| Mean-Variance Optimiser | $100,000 | 9.53% | 0.69 | -29.24% | $1,465,240 | $1,365,240 |
| Regime-Aware Optimiser | $100,000 | 10.66% | 0.68 | -36.43% | $1,982,460 | $1,882,460 |
| Risk-Parity Optimiser | $100,000 | 11.16% | 0.79 | -30.39% | $2,266,941 | $2,166,941 |
| Score-Weighted Optimiser | $100,000 | 10.84% | 0.71 | -35.20% | $2,081,039 | $1,981,039 |
| Final Resolved Portfolio | $80,540 | 9.99% | 0.67 | -31.93% | $1,335,175 | $1,254,635 |
| DRL Baseline Portfolio | $80,540 | 9.99% | 0.67 | -31.93% | $1,335,175 | $1,254,635 |
| DRL Raw Challenger | $80,540 | 9.66% | 0.68 | -30.55% | $1,221,878 | $1,141,338 |
| Trend and Risk-Controlled Regional Indices | $100,000 | 4.68% | 0.32 | -22.34% | $385,838 | $285,838 |

## Evidence Included

- monthly adjusted-close returns converted to USD with historical FRED FX
- pre-listing and unallocated capital held at the 3-month Treasury-bill rate
- monthly rebalancing with commissions, spread, slippage, market impact, and ADV checks
- portfolio-specific regional index blends plus S&P 500 and SPY comparisons
- a lagged trend and risk-controlled regional-index challenger
- 36-month untouched embargo evaluation
- circular moving-block resampling and correlated fat-tailed Monte Carlo
- PSR, Minimum Track Record Length, Sidak FWER, and Deflated Sharpe Ratios
- HTML and PDF reports, source manifest, compact result tables, plots, and SHA-256 checksums

Open [backtest_report.html](backtest_report.html) for the complete rendered report. See [docs/BACKTEST_METHODOLOGY.md](../../../docs/BACKTEST_METHODOLOGY.md) for formulas, assumptions, and the paper-to-code mapping.

Raw provider histories are intentionally excluded from Git. This is research evidence, not authorization for live trading.
