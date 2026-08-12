# Portfolio Backtest Methodology

## Purpose and Interpretation Boundary

This suite evaluates every investable portfolio output currently produced by The Wolf Quant Model from 1 January 1997 through the latest complete month. It implements the three evidence types recommended in *The Three Types of Backtests*:

1. historical or walk-forward replay;
2. dependence-preserving resampling; and
3. stochastic Monte Carlo simulation.

The long-history portfolio results are **retrospective holdings replays**. They apply today's selected securities and target weights to the history available for those securities. They therefore contain selection look-ahead and survivorship bias and cannot establish that the model would have selected those names in 1997.

The repository's dated, reconstructed model decisions are retained as a separate 60-month point-in-time evidence set. The report never joins that shorter record to the long holdings replay. A lagged regional-index challenger supplies an additional long-horizon point-in-time strategy because its signals can be reconstructed without historical security-selection snapshots.

The dated evidence exports all three aligned monthly paths: `wolf_cvar`,
`equal_weight_eligible`, and `cap_weight_eligible`. Paired Newey-West alpha tests
use those raw paths, apply Sidak control across the two benchmarks, disclose
incremental cost drag, and require at least 60 months plus native live vintages
before a result can be labeled deployable alpha.

## Paper-to-Code Mapping

| Paper recommendation | Implementation |
|---|---|
| Historical and walk-forward evidence | Monthly portfolio replay plus a one-period-lagged index challenger |
| Data quality and point-in-time discipline | Coverage audit, explicit price repairs, source hashes, and separate dated model evidence |
| Representativeness and sample length | 1997 start, common investable window, subperiod returns, PSR, and Minimum Track Record Length |
| Selection and multiple-testing bias | Sidak, Deflated Sharpe, block-bootstrap max-t, duplicate-path removal, and CSCV PBO |
| Look-ahead controls | One-month signal lag for the index challenger and a final 36-month untouched embargo |
| Trading frictions | Commission, half-spread, slippage, square-root impact, missing-liquidity penalty, and ADV caps |
| Recurring AUM charge | 25 bp bank custody/AUM fee deducted once each December from then-current simulated AUM |
| Liquidity constraints | Each trade is capped at 5% of trailing median daily dollar volume; unfilled weight remains in cash |
| Causal theory | Explicit causal graph in the report and separation of causal claims from exposure replay |
| Resampling | Circular 12-month moving-block bootstrap with cross-strategy alignment |
| Monte Carlo | Correlated Student-t AR(1) process with EWMA conditional volatility |
| Holistic statistics | CAGR, volatility, Sharpe, Lo-adjusted Sharpe, Sortino, Calmar, drawdown, VaR, Expected Shortfall, PSR, MinTRL, and DSR |
| Non-stationarity | Calendar-year heatmap, lagged rate and market regimes, macro-event windows, drawdowns, embargo comparison, block resampling, and volatility-clustered simulation |

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

Current-derived portfolios use USD 186,060,522, the current AUM supplied for this analysis. This applies to the current portfolio, portfolio-aware overlay, final resolved portfolio, DRL baseline, and raw DRL challenger because each is derived from the current book. Independent clean-sheet, optimiser, index-challenger, and LLM portfolios use USD 100,000. Unallocated target weight remains in cash. Source filenames, weights, security identifiers, regions, currencies, and capital rules are written to `portfolio_definitions.csv`.

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

### Annual Bank AUM Charge

The bank charge is 0.25% annually. The supplied reference amount reconciles exactly:

```text
reference AUM                 = USD 186,060,522
annual bank rate             = 0.25% = 25 bps
reference annual bank charge = 186,060,522 * 0.0025
                             = USD 465,151.305
```

The engine deducts the percentage once each December after that month's market return and transaction costs:

```text
pre-fee return = (1 - transaction cost / opening NAV) * (1 + gross return) - 1
bank fee USD   = AUM immediately before annual fee * 0.0025
net return     = (1 + pre-fee return) * (1 - 0.0025) - 1
```

The fee scales with each simulated account. A USD 100,000 research portfolio therefore pays 25 bps of its own then-current AUM, not the USD 465,151 reference-dollar charge. Portfolio outputs and the point-in-time index challenger are charged; external index benchmarks remain uncharged reference paths. Gross, pre-bank-fee, and fully net returns and wealth are retained separately. `annual_bank_fee_assumption.csv` reconciles the input, while `cost_liquidity_summary.csv` reports cumulative fee dollars and ending-value drag.

### Price-Quality Repairs

Every absolute daily adjusted-close return above 50% is audited. Two deterministic, logged repairs are allowed:

- an isolated spike followed by an offsetting reversal is replaced by log-price interpolation; or
- a persistent discontinuity is treated as an unadjusted level shift and the earlier history is rescaled.

Raw and post-repair extreme-return counts are retained in `data_coverage.csv`. Every changed observation, method, and factor is recorded in `price_quality_adjustments.csv`. This policy is intentionally narrow; it does not smooth ordinary losses or gains.

## Benchmarks

The suite evaluates:

- S&P 500 Index;
- SPY adjusted-close total-return proxy;
- Dow Jones Industrial Average, Nasdaq Composite, and Russell 2000;
- FTSE 100 and FTSE 250;
- DAX Performance Index and Swiss Market Index;
- STOXX Europe 600, EURO STOXX 50, and CAC 40;
- Shanghai Composite and Hang Seng Index;
- Nikkei 225;
- adjusted-close MSCI EAFE and ACWI ETF proxies;
- an equal-weight regional-index basket; and
- a portfolio-specific regional blend using each portfolio's geographic target weights.

All benchmarks are converted to USD using the same historical FX process as the portfolios. External benchmark paths begin at USD 100,000 and do not incur the portfolio bank charge. Regional price-index and total-return conventions are not uniform, so standalone index results provide broad market context rather than a perfectly dividend-consistent alpha test. Relative output includes alpha, beta, tracking error, information ratio, cumulative active return, capture ratios, and capital-matched relative PnL.

## Interest-Rate, Market, and Economic Regimes

Conditional tables classify each return month using information observed before that month:

- **Rate level:** the prior month-end 3-month Treasury-bill yield is low below 2%, moderate from 2% to below 4%, or high at 4% and above.
- **Rate direction:** the prior 12-month yield change is rising above +0.75 percentage points, falling below -0.75 percentage points, or stable between those thresholds.
- **Market regime:** prior 12-month S&P 500 momentum defines bull or bear, while prior 6-month annualised volatility defines calm below 18% or volatile at 18% and above.
- **Economic cycle:** the prior-month USREC value labels expansion or recession. NBER recession announcements are retrospective, so this split is descriptive and is never treated as an available trading signal.

The conditional geometric return compresses non-contiguous months in each group and annualises them. It describes performance association within an environment; it is not a continuous portfolio path and does not identify causal effects.

## Major Macro Events

Thirteen source-backed analytical windows cover the Asian financial crisis, dot-com bust, 9/11 and Afghanistan shock, Iraq invasion, global financial crisis, euro-area debt crisis, Crimea shock, Brexit referendum, COVID-19 crash, Russia-Ukraine full-scale invasion, Gaza war, 2025 Israel-Iran war, and 2026 US-Iran war. The definitions and primary-source URLs are versioned in `configs/backtest.yaml` and exported to `macro_event_definitions.csv`.

A monthly return is included when its measurement period overlaps an event window. Event output reports cumulative return, within-window drawdown, worst month, starting simulated AUM, and event PnL. These windows are selected for market-path analysis, not legal definitions of war duration or causal estimates. Events may overlap and therefore can share return months.

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
- Deflated Sharpe Ratios using both the actual trial count and a correlation-clustered effective trial count;
- Newey-West alpha regressions against each portfolio's regional index blend;
- a circular-block max-t reality check that preserves serial and cross-strategy dependence; and
- Combinatorially Symmetric Cross-Validation, including Probability of Backtest Overfitting and the selected strategy's in-sample to out-of-sample information-ratio haircut.

Exact duplicate active-return paths are counted once in the max-t and CSCV trial
families. These diagnostics control strategy-family selection effects, but they
cannot remove a bias shared by every trial. In particular, favorable results from
today's hindsight-selected holdings remain retrospective diagnostics rather than
deployable alpha evidence.

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

- rendered HTML and `portfolio_backtest_analysis.pdf` reports;
- a standalone `written_interpretation.md` with plain-language explanations for every rendered table;
- monthly portfolio and benchmark returns;
- performance, paper-ratio, fee-impact, relative, alpha, overfitting, embargo, significance, resampling, and simulation summaries;
- standalone major-index, interest-rate, market-regime, recession, and macro-event evidence tables;
- data coverage, repair, execution, and liquidity diagnostics;
- publication-ready wealth, index, regime, event, risk, and robustness plots;
- run manifest with source hashes and configuration; and
- SHA-256 checksums for the complete evidence package.

Raw yfinance and FRED caches remain under `data/backtests/cache/` and are ignored by Git. Keep the cache for low-latency reruns; use `--refresh-data` only when a new provider snapshot is required.

## Decision Use

The 1997 results answer how today's allocations would have behaved through historical market paths under explicit trading and data assumptions. They do not answer which securities the model would have selected at each historical date. Deployment claims should rely on genuinely immutable point-in-time universes, fundamentals, model versions, and decisions, followed by a forward or shadow-trading record.
