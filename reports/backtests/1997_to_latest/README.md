# Portfolio Backtest Evidence: 1997 to 2026

This package compares every investable portfolio output currently produced by the repository. Current-derived allocations start with the observed current NAV of $186,060,522; independent clean-sheet, optimiser, and LLM portfolios start with $100,000.

> **Interpretation boundary:** the long history is a retrospective replay of today's selected holdings and weights. It contains selection look-ahead and survivorship bias and is not a 1997 point-in-time model backtest. The shorter reconstructed point-in-time model evidence is reported separately.

## Requested Window

| Portfolio | Start | CAGR | Sharpe | Max drawdown | Ending value | PnL |
|---|---:|---:|---:|---:|---:|---:|
| Current Portfolio | $186,060,522 | 14.06% | 0.75 | -42.57% | $9,013,105,522 | $8,827,045,000 |
| Portfolio-Aware Overlay | $186,060,522 | 12.96% | 0.77 | -41.21% | $6,770,759,519 | $6,584,698,997 |
| Clean-Sheet Quant | $100,000 | 8.97% | 0.66 | -27.73% | $1,260,577 | $1,160,577 |
| LLM Analyst Benchmark | $100,000 | 9.50% | 0.81 | -20.91% | $1,454,455 | $1,354,455 |
| CVaR-Constrained Optimiser | $100,000 | 9.72% | 0.65 | -32.27% | $1,541,859 | $1,441,859 |
| Dividend-Income Optimiser | $100,000 | 10.51% | 0.63 | -41.29% | $1,906,226 | $1,806,226 |
| Mean-Variance Optimiser | $100,000 | 9.26% | 0.66 | -29.60% | $1,362,692 | $1,262,692 |
| Regime-Aware Optimiser | $100,000 | 10.38% | 0.66 | -36.59% | $1,843,697 | $1,743,697 |
| Risk-Parity Optimiser | $100,000 | 10.89% | 0.77 | -30.56% | $2,108,263 | $2,008,263 |
| Score-Weighted Optimiser | $100,000 | 10.57% | 0.69 | -35.52% | $1,935,381 | $1,835,381 |
| Final Resolved Portfolio | $186,060,522 | 9.09% | 0.65 | -28.45% | $2,424,094,460 | $2,238,033,938 |
| DRL Baseline Portfolio | $186,060,522 | 9.09% | 0.65 | -28.45% | $2,424,094,460 | $2,238,033,938 |
| DRL Raw Challenger | $186,060,522 | 8.83% | 0.65 | -27.87% | $2,260,590,356 | $2,074,529,834 |
| Trend and Risk-Controlled Regional Indices | $100,000 | 4.43% | 0.30 | -23.30% | $358,822 | $258,822 |

## Evidence Included

- monthly adjusted-close returns converted to USD with historical FRED FX
- pre-listing and unallocated capital held at the 3-month Treasury-bill rate
- monthly rebalancing with commissions, spread, slippage, market impact, and ADV checks
- a 25 bp annual bank AUM charge assessed once each December on then-current portfolio value
- portfolio-specific regional blends plus DAX, FTSE, Dow, Nasdaq, S&P 500, and global index comparisons
- lagged interest-rate and market-regime performance plus retrospective recession analysis
- source-backed macro-event windows and charts from the Asian crisis through the 2026 US-Iran war
- a lagged trend and risk-controlled regional-index challenger
- 36-month untouched embargo evaluation
- circular moving-block resampling and correlated fat-tailed Monte Carlo
- PSR, Minimum Track Record Length, Sidak FWER, and Deflated Sharpe Ratios
- Newey-West alpha tests, block-bootstrap max-t control, and CSCV PBO diagnostics
- HTML and PDF reports, source manifest, compact result tables, plots, and SHA-256 checksums

Open [backtest_report.html](backtest_report.html) or [portfolio_backtest_analysis.pdf](portfolio_backtest_analysis.pdf) for the complete rendered report and [written_interpretation.md](written_interpretation.md) for the plain-language explanation of every table. See [docs/BACKTEST_METHODOLOGY.md](../../../docs/BACKTEST_METHODOLOGY.md) for formulas, assumptions, and the paper-to-code mapping.

Raw provider histories are intentionally excluded from Git. This is research evidence, not authorization for live trading.
