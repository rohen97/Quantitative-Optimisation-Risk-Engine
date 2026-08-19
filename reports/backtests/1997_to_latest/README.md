# Portfolio Backtest Evidence: 1997 to 2026

This package compares every investable portfolio output currently produced by the repository. Current-derived allocations start with the observed current NAV of $186,060,522; independent clean-sheet, optimiser, and LLM portfolios start with $100,000.

> **Interpretation boundary:** the long history is a retrospective replay of today's selected holdings and weights. It contains selection look-ahead and survivorship bias and is not a 1997 point-in-time model backtest. The shorter reconstructed point-in-time model evidence is reported separately.

## Requested Window

| Portfolio | Start | CAGR | Sharpe | Max drawdown | Ending value | PnL |
|---|---:|---:|---:|---:|---:|---:|
| Current Portfolio | $186,060,522 | 14.06% | 0.75 | -42.57% | $9,013,102,206 | $8,827,041,684 |
| Portfolio-Aware Overlay | $186,060,522 | 13.11% | 0.74 | -46.36% | $7,038,270,415 | $6,852,209,893 |
| Clean-Sheet Quant | $100,000 | 6.30% | 0.52 | -31.20% | $606,712 | $506,712 |
| LLM Analyst Benchmark | $100,000 | 4.84% | 0.66 | -10.21% | $403,101 | $303,101 |
| CVaR-Constrained Optimiser | $100,000 | 9.80% | 0.66 | -35.69% | $1,575,708 | $1,475,708 |
| Dividend-Income Optimiser | $100,000 | 10.80% | 0.64 | -43.00% | $2,058,089 | $1,958,089 |
| Mean-Variance Optimiser | $100,000 | 9.92% | 0.66 | -33.96% | $1,630,361 | $1,530,361 |
| Regime-Aware Optimiser | $100,000 | 10.48% | 0.64 | -43.32% | $1,891,914 | $1,791,914 |
| Risk-Parity Optimiser | $100,000 | 11.83% | 0.79 | -31.79% | $2,709,164 | $2,609,164 |
| Score-Weighted Optimiser | $100,000 | 10.59% | 0.71 | -32.62% | $1,947,693 | $1,847,693 |
| Final Resolved Portfolio | $186,060,522 | 9.22% | 0.62 | -35.82% | $2,506,737,048 | $2,320,676,526 |
| DRL Baseline Portfolio | $186,060,522 | 9.22% | 0.62 | -35.82% | $2,506,737,048 | $2,320,676,526 |
| DRL Raw Challenger | $186,060,522 | 8.90% | 0.62 | -34.35% | $2,303,279,904 | $2,117,219,382 |
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
