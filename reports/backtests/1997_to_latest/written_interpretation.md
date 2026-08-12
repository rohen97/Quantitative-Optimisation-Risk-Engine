# Plain-Language Backtest Interpretation

## Overall Result

The test covers 29.6 years and 13 portfolio outputs. The current portfolio starts at $186,060,522 and finishes at $9,013,105,522 after modeled costs, a net PnL of $8,827,045,000. On the common investable window, Portfolio-Aware Overlay has the highest Sharpe ratio at 0.88. The long results replay securities selected with today's information, so they describe exposure and path behavior rather than proving historical selection skill.

## Portfolio Performance

The performance table converts each assigned starting balance into a fully net ending balance. CAGR is the smooth annual growth rate, volatility measures return variation, Sharpe compares excess return with total variability, and maximum drawdown is the deepest peak-to-trough loss. Current Portfolio records the highest common-window CAGR at 14.20% alongside a -28.91% maximum drawdown.

## Performance Ratios

Sharpe uses all volatility; Lo-adjusted Sharpe allows for serially related monthly returns; Sortino counts downside variability; and Calmar divides CAGR by maximum drawdown. Monthly VaR is the 5% loss threshold, while expected shortfall is the average loss beyond it. PSR measures confidence that Sharpe clears a hurdle, MinTRL estimates the required history, and DSR discounts non-normal returns and multiple trials. SPDR S&P 500 ETF adjusted-close proxy has the strongest Lo-adjusted Sharpe at 1.21.

## Annual Bank Fee Assumption

The bank charge is 25 basis points, assessed once in month 12 on then-current AUM. At reference AUM of $186,060,522, the configured and calculated charges equal $465,151 and differ by $0. The same percentage, not the full reference-dollar amount, applies to each portfolio; external benchmarks remain uncharged.

## Annual Bank Fee Impact

The fee-impact table separates trading costs from the annual bank charge and compares ending value before bank fees with the fully net result. current_portfolio pays the largest cumulative bank charge at $155,185,066, with ending-value fee drag of $678,600,433.

## Major Index Benchmarks

Each standalone index is converted to USD and replayed as an uncharged buy-and-hold reference on $100,000. Price-index and total-return conventions differ, so these are broad path comparisons rather than perfectly dividend-consistent alpha tests. Nasdaq Composite Index has the highest common-window CAGR at 16.35%.

## Portfolio-Relative Benchmarks

Each portfolio is compared with an index blend matching its regional weights. Alpha is annualized return not explained by beta, tracking error is active-return volatility, and information ratio is active return per unit of tracking error. Portfolio-Aware Overlay has the highest information ratio at 1.04 and relative PnL of $596,268,264.

## Interest-Rate Levels

This table groups non-contiguous months by the lagged 3-month Treasury-bill yield level and annualizes the observations in each group. It is a conditional description, not a continuous investable path or a causal estimate. For Final Resolved Portfolio, the strongest group is High (>=4%), with a conditional geometric return of 15.77% across 105 months.

## Interest-Rate Direction

This table groups non-contiguous months by the prior 12-month change in the Treasury-bill yield and annualizes the observations in each group. It is a conditional description, not a continuous investable path or a causal estimate. For Final Resolved Portfolio, the strongest group is Rising, with a conditional geometric return of 13.03% across 79 months.

## Market Regimes

This table groups non-contiguous months by lagged S&P 500 momentum and volatility and annualizes the observations in each group. It is a conditional description, not a continuous investable path or a causal estimate. For Final Resolved Portfolio, the strongest group is Bull / Volatile, with a conditional geometric return of 14.09% across 36 months.

## Economic Cycle

This table groups non-contiguous months by the retrospective NBER recession indicator and annualizes the observations in each group. It is a conditional description, not a continuous investable path or a causal estimate. For Final Resolved Portfolio, the strongest group is Expansion, with a conditional geometric return of 9.91% across 326 months.

## Macro-Event Definitions

The event-definition table supplies source-backed windows shaded on the charts. They are market-response intervals for monthly analysis, not claims about legal war dates, and overlapping events can share return months.

## Macro-Event Performance

Event return compounds all overlapping monthly observations, event drawdown measures the loss within that window, and event PnL applies the return to actual simulated AUM at the start of the window. The weakest configured event for the final portfolio is COVID-19 market crash, returning -12.58% with a -15.19% within-window drawdown.

## Statistical Significance

PSR and MinTRL evaluate reliability, Sidak controls family-wise error across tested strategies, and DSR penalizes multiple trials and non-normal returns. 13 of 14 results clear Sidak; significance does not remove retrospective selection look-ahead.

## Alpha and Overfitting

Newey-West regressions test alpha against each portfolio-specific regional index blend while allowing serial correlation. The block-bootstrap max-t test controls selection across the whole strategy family, and CSCV repeatedly selects in one half of the history and ranks that winner in the other half. 6 unique results clear the max-t family-wise test. CSCV estimates PBO at 19.91%, while the median selected information ratio falls from 1.32 in-sample to 0.66 out-of-sample. The largest measured common-window alpha is 8.33% for Current Portfolio. Every long portfolio path is still a retrospective holdings replay, so these tests measure path robustness, not deployable stock-selection alpha.

## Block Resampling

The moving-block bootstrap rearranges 12-month blocks while preserving short-run dependence and cross-strategy alignment. Its 5th, median, and 95th percentiles show sensitivity to historical path order. The lowest 5th-percentile CAGR is trend_risk_controlled_indices at 1.46%.

## Monte Carlo

Monte Carlo uses correlated Student-t shocks, AR(1) persistence, and EWMA volatility to create fat-tailed, volatility-clustered paths. It is a modeled stress distribution, not a forecast promise. The lowest simulated 5th-percentile CAGR is trend_risk_controlled_indices at 1.63%.

## Embargo Test

The embargo table compares the development sample with the final untouched 36 months. A sharp fall in Sharpe or return signals instability; agreement is encouraging but cannot cure retrospective selection bias.

## Execution and Liquidity

Execution rows show dollar costs, turnover, peak ADV participation, constrained trades, and unfilled weight. Large current-derived AUM can leave low-liquidity targets partly in cash, making these results capacity-aware.

## Price Repairs

The adjusted-price process made 6 explicit repairs. Each row records the raw move, rule, repaired return, and scale factor so provider anomalies remain auditable.

## Bias and Limitations

The limitation register distinguishes modeled, controlled, separated, and unresolved risks. The critical issue is that current holdings survived long enough to be selected today, so the 1997 replay cannot prove selection skill.

## Point-in-Time Evidence

The point-in-time table contains 60 dated decision months and remains separate from the long holdings replay. It is the more relevant evidence for decisions made with contemporaneous data. Against equal-weight eligible stocks, annualised active return is -1.24% and the alpha verdict is NOT_SIGNIFICANT. Against cap-weight eligible stocks, annualised active return is 3.43% and the verdict is NOT_SIGNIFICANT. Native live evidence and at least 60 months are required before alpha can be considered deployable.
