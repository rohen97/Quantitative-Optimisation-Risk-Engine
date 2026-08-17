# Portfolio Backtest Evidence: 1997 to 2026

This package compares every investable portfolio output currently produced by the repository. Current-derived allocations start with the observed current NAV of $186,060,522; independent clean-sheet, optimiser, and LLM portfolios start with $100,000.

> **Interpretation boundary:** the long history is a retrospective replay of today's selected holdings and weights. It contains selection look-ahead and survivorship bias and is not a 1997 point-in-time model backtest. The shorter reconstructed point-in-time model evidence is reported separately.

## Requested Window

| Portfolio | Start | CAGR | Sharpe | Max drawdown | Ending value | PnL |
|---|---:|---:|---:|---:|---:|---:|
| Current Portfolio | $186,060,522 | 14.06% | 0.75 | -42.57% | $9,013,102,206 | $8,827,041,684 |
| Portfolio-Aware Overlay | $186,060,522 | 13.69% | 0.77 | -47.39% | $8,192,397,366 | $8,006,336,844 |
| Clean-Sheet Quant | $100,000 | 8.50% | 0.61 | -36.03% | $1,108,623 | $1,008,623 |
| LLM Analyst Benchmark | $100,000 | 5.52% | 0.63 | -13.29% | $488,283 | $388,283 |
| CVaR-Constrained Optimiser | $100,000 | 8.69% | 0.59 | -37.09% | $1,168,765 | $1,068,765 |
| Dividend-Income Optimiser | $100,000 | 10.60% | 0.59 | -45.88% | $1,951,982 | $1,851,982 |
| Mean-Variance Optimiser | $100,000 | 9.02% | 0.61 | -37.88% | $1,278,845 | $1,178,845 |
| Regime-Aware Optimiser | $100,000 | 10.11% | 0.61 | -39.50% | $1,713,229 | $1,613,229 |
| Risk-Parity Optimiser | $100,000 | 10.41% | 0.74 | -29.10% | $1,859,175 | $1,759,175 |
| Score-Weighted Optimiser | $100,000 | 9.81% | 0.62 | -33.64% | $1,580,605 | $1,480,605 |
| Final Resolved Portfolio | $186,060,522 | 8.34% | 0.58 | -37.34% | $1,976,496,316 | $1,790,435,794 |
| DRL Baseline Portfolio | $186,060,522 | 8.34% | 0.58 | -37.34% | $1,976,496,316 | $1,790,435,794 |
| DRL Raw Challenger | $186,060,522 | 8.05% | 0.57 | -35.80% | $1,826,083,914 | $1,640,023,392 |
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
