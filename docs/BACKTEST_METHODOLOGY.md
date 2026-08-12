# Portfolio Backtest Methodology

## Purpose and Interpretation Boundary

This suite evaluates every investable portfolio output currently produced by The Wolf Quant Model from 1 January 1997 through the latest complete month. It implements the three evidence types recommended in *The Three Types of Backtests*:

1. historical or walk-forward replay;
2. dependence-preserving resampling; and
3. stochastic Monte Carlo simulation.

The long-history portfolio results are **retrospective holdings replays**. They apply today's selected securities and target weights to the history available for those securities. They therefore contain selection look-ahead and survivorship bias and cannot establish that the model would have selected those names in 1997.

The repository's dated, reconstructed model decisions are retained as a separate 25-month point-in-time evidence set. The report never joins that shorter record to the long holdings replay. A lagged regional-index challenger supplies an additional long-horizon point-in-time strategy because its signals can be reconstructed without historical security-selection snapshots.

## Paper-to-Code Mapping

| Paper recommendation | Implementation |
|---|---|
| Historical and walk-forward evidence | Monthly portfolio replay plus a one-period-lagged index challenger |
| Data quality and point-in-time discipline | Coverage audit, explicit price repairs, source hashes, and separate dated model evidence |
| Representativeness and sample length | 1997 start, common investable window, subperiod returns, PSR, and Minimum Track Record Length |
| Selection and multiple-testing bias | Sidak family-wise error control and Deflated Sharpe Ratios |
| Look-ahead controls | One-month signal lag for the index challenger and a final 36-month untouched embargo |
| Trading frictions | Commission, half-spread, slippage, square-root impact, missing-liquidity penalty, and ADV caps |
| Liquidity constraints | Each trade is capped at 5% of trailing median daily dollar volume; unfilled weight remains in cash |
| Causal theory | Explicit causal graph in the report and separation of causal claims from exposure replay |
| Resampling | Circular 12-month moving-block bootstrap with cross-strategy alignment |
| Monte Carlo | Correlated Student-t AR(1) process with EWMA conditional volatility |
| Holistic statistics | CAGR, volatility, Sharpe, Lo-adjusted Sharpe, Sortino, Calmar, drawdown, VaR, Expected Shortfall, PSR, MinTRL, and DSR |
| Non-stationarity | Calendar-year heatmap, drawdowns, embargo comparison, block resampling, and volatility-clustered simulation |

## Portfolio Catalogue and Capital

The catalogue is built directly from current pipeline artifacts rather than a parallel hand-maintained list. It includes:

- current portfolio;
- portfolio-aware overlay;
- clean-sheet quant portfolio;
- LLM analyst benchmark;
- CVaR-constrained, dividend-income, mean-variance, regime-aware, risk-parity, and score-weighted optimisers;
- final resolved portfolio;
- DRL baseline; and
- raw DRL challenger.

Current-derived portfolios use the observed current portfolio NAV, currently USD 80,540. Independent clean-sheet, optimiser, index-challenger, and LLM portfolios use USD 100,000. Unallocated target weight remains in cash. Source filenames, weights, security identifiers, regions, currencies, and capital rules are written to `portfolio_definitions.csv`.

## Historical Replay

### Market and FX Data

- Daily adjusted closes and volumes come from yfinance and are cached outside Git.
- FRED supplies historical exchange rates and the 3-month Treasury-bill yield.
- Local prices are converted to USD before returns are calculated.
- GBX prices are divided by 100 before GBP conversion.
- Pre-euro observations use the configured ECU-to-USD bridge where needed.
- Daily data are sampled at month-end; median daily dollar volume supplies the monthly liquidity reference.
- The end date defaults to the latest complete month, preventing partial-month leakage.

Provider-adjusted prices are used because they incorporate distributions and splits when the provider history supports them. Regional price indices are not uniformly total-return series. The DAX is a performance index; SPY adjusted close is included as a more dividend-consistent US total-return proxy.

### Availability and Cash

A holding is eligible only after its first valid adjusted close. Before listing, and whenever a target allocation is intentionally uninvested, the capital earns the converted daily 3-month Treasury-bill return. The report shows both:

- the requested 1997 window, useful for the capital path including pre-listing cash; and
- the common investable window beginning when every portfolio reaches at least 80% of its intended invested allocation.

Benchmark comparisons in the rendered report use the common investable window. This avoids rewarding a portfolio simply because unavailable holdings sat in cash during an earlier market decline.

### Rebalancing and Execution

Portfolios rebalance monthly. A desired trade is clipped to 5% of trailing median daily dollar volume. Any unfilled target remains in cash and is reported. For executed notional `N` and participation `p`, modeled cost is:

```text
linear bps = commission + half spread + slippage
impact bps = min(max impact, impact coefficient * sqrt(p / reference participation))
cost USD   = N * (linear bps + impact bps) / 10,000
net return = (1 - cost / opening NAV) * (1 + gross return) - 1
```

The default linear cost is 10 bps, impact is 10 bps at 1% participation, impact is capped at 50 bps, and missing liquidity receives a 15 bps penalty. `cost_liquidity_summary.csv` records turnover, modeled cost, participation, constrained trades, cash, and unfilled allocations.

### Price-Quality Repairs

Every absolute daily adjusted-close return above 50% is audited. Two deterministic, logged repairs are allowed:

- an isolated spike followed by an offsetting reversal is replaced by log-price interpolation; or
- a persistent discontinuity is treated as an unadjusted level shift and the earlier history is rescaled.

Raw and post-repair extreme-return counts are retained in `data_coverage.csv`. Every changed observation, method, and factor is recorded in `price_quality_adjustments.csv`. This policy is intentionally narrow; it does not smooth ordinary losses or gains.

## Benchmarks

The suite evaluates:

- S&P 500 Index;
- SPY adjusted-close total-return proxy;
- FTSE 100;
- DAX Performance Index;
- STOXX Europe 600;
- Shanghai Composite;
- Hang Seng Index;
- an equal-weight regional-index basket; and
- a portfolio-specific regional blend using each portfolio's geographic target weights.

All benchmarks are converted to USD. Relative output includes alpha, beta, tracking error, information ratio, cumulative active return, capture ratios, and capital-matched relative PnL.

## Point-in-Time Index Challenger

The independent challenger uses only regional indices. At each month-end it:

1. computes trailing 12-month momentum and 6-month volatility;
2. admits only positive-momentum regions;
3. assigns inverse-volatility weights capped at 35% per region;
4. scales risk using a trailing 36-month covariance matrix and a 10% volatility target; and
5. executes the schedule one period later with a 10 bps linear cost.

Because every signal is lagged and based only on prior observations, this series is suitable for long-horizon point-in-time interpretation. It is a research challenger, not an output of the stock-selection model.

## Resampling Backtest

The circular moving-block bootstrap draws 5,000 paths using 12-month blocks. All strategies and their benchmarks use the same sampled month indices, preserving cross-sectional dependence and approximately preserving serial dependence within each block. Output reports 5th, 50th, and 95th percentiles for CAGR, Sharpe, maximum drawdown, ending value, and benchmark-outperformance probability.

Resampling evaluates path-order sensitivity. It cannot remove survivorship or selection look-ahead inherited from the retrospective holdings sample.

## Monte Carlo Backtest

The simulator jointly models monthly strategy returns to preserve their observed dependence:

- each strategy receives a clipped AR(1) mean process;
- Ledoit-Wolf shrinkage estimates the residual correlation matrix;
- marginal tail thickness is estimated from kurtosis and represented by Student-t innovations;
- degrees of freedom are bounded from 5 to 30; and
- EWMA variance with lambda 0.94 creates volatility clustering.

Five thousand seeded paths are simulated over the observed common history length. Compact diagnostics and quantile summaries are committed; path-level draws are reproducible and omitted to keep the repository lean.

The simulation is conditional on the observed retrospective sample. It is a robustness exercise, not an unbiased expected-return forecast.

## Statistical Integrity

Monthly risk-free excess returns drive Sharpe statistics. The suite reports:

- conventional and Lo autocorrelation-adjusted annualised Sharpe;
- Sortino and Calmar ratios;
- maximum drawdown and drawdown duration;
- 5% monthly historical VaR and Expected Shortfall;
- skewness and Pearson kurtosis;
- Probabilistic Sharpe Ratio;
- Minimum Track Record Length at 95% confidence;
- Sidak-adjusted one-sided significance across all strategy trials; and
- Deflated Sharpe Ratios using both the actual trial count and a correlation-clustered effective trial count.

The final 36 months are labeled as an untouched embargo and compared with the development period. The static holdings replays remain hindsight-selected even in this embargo; the split measures temporal degradation, not true research-process isolation.

## Reproducibility and Outputs

Run the suite from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\run_portfolio_backtest_1997.py
```

Force fresh provider downloads:

```powershell
.\.venv\Scripts\python.exe scripts\run_portfolio_backtest_1997.py --refresh-data
```

Outputs are written to `reports/backtests/1997_to_latest/`:

- rendered HTML and PDF reports;
- monthly portfolio and benchmark returns;
- performance, relative, embargo, significance, resampling, and simulation summaries;
- data coverage, repair, execution, and liquidity diagnostics;
- publication-ready plots;
- run manifest with source hashes and configuration; and
- SHA-256 checksums for the complete evidence package.

Raw yfinance and FRED caches remain under `data/backtests/cache/` and are ignored by Git. Keep the cache for low-latency reruns; use `--refresh-data` only when a new provider snapshot is required.

## Decision Use

The 1997 results answer how today's allocations would have behaved through historical market paths under explicit trading and data assumptions. They do not answer which securities the model would have selected at each historical date. Deployment claims should rely on genuinely immutable point-in-time universes, fundamentals, model versions, and decisions, followed by a forward or shadow-trading record.
