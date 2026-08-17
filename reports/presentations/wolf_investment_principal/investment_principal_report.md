# Wolf Quant Model Investment Principal Report

As of 17 August 2026

## Decision

**Approve a controlled, human-supervised live pilot.** Governance improved
from 80/100 to 87.5/100. 6 components pass,
2 remain warnings, and there are zero critical failures. Adaptive risk
backtesting and the turnover/cost targets now pass. Full-scale or unattended
deployment remains unapproved because observed point-in-time evidence is
incomplete and
benchmark-relative alpha is not established.

## What Improved

| Control | Before | Now | Current gate |
| --- | ---: | ---: | --- |
| Governance score | 80/100 | 87.5/100 | Conditional approval |
| Risk backtesting | Warning, 7.5/15 | Pass, 15/15 | Coverage and independence pass |
| Annual turnover | 2.11x | 1.10x | <=1.50x: pass |
| Annualised cost drag | 2.35% | 0.82% | <=1.50%: pass |
| Hard constraint breaches | 0 | 0 | Pass |

Retention hysteresis, a 6% monthly turnover cap, and minimum-turnover
transitions drove the implementation improvement. The configured no-trade
band did not trigger in this 60-month sample, so it is not credited for the
observed result.

## Supervised Benchmark-Relative Alpha

The new research stack compares OLS after train-only Fama-MacBeth screening,
Ridge, Elastic Net, robust Huber regression, Random Forest, Extra Trees,
histogram gradient boosting, XGBoost regression and XGBoost ranking across
3/6/9/12-month horizons. The primary panel contains
**1,374 securities**, versus the much larger
price master, because model rows also require historical fundamentals,
features and realised outcomes.

| Horizon | Monthly cohorts | Independent | Rank IC | Sign p | Net cohort return | Turnover | 90% coverage | Band width |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3m | 11 | 4 | 0.157 | 0.062 | 7.4% | 0.54x | 94.6% | 56% |
| 6m | 7 | 2 | 0.182 | 0.250 | 14.2% | 0.47x | 93.4% | 83% |
| 9m | 4 | 1 | 0.226 | 0.500 | 24.8% | 0.35x | 91.9% | 100% |
| 12m | 1 | 1 | 0.253 | 0.500 | 37.0% | N/A | 90.5% | 117% |

The 3-month rank IC is positive, but four independent cohorts produce an exact
sign-test p-value above 5%. Longer horizons have only two, one and one
independent observations. Net cohort returns are not compounded portfolio CAGR.
Formal annualised return, Sharpe, t-statistics and confidence intervals remain
suppressed. The governed decision is **INSUFFICIENT_EVIDENCE** with a
**0% live blend**.

Purged date-block conformal calibration now clears the central 90% coverage
target at every horizon. That correction also reveals low precision: average
9- and 12-month bands span about 100% and 117% of benchmark-relative return.
Recurring 3/6/9-month turnover is below 1.5x and includes spread, FX, impact
and the separate 25bp annual bank fee. Twelve-month recurring turnover remains
unestimable from one cohort.

## Portfolio Outputs And Stock Recommendations

The governed CVaR target remains the only committee portfolio. The low-latency
regional-alpha challenger also holds 20 equal-weight names, but only
**8 names overlap**. The supervised overlay cannot change
weights while its deployment blend is zero.

- Governed-only: `000538.SHE`, `0728.HK`, `1113.HK`, `3988.HK`, `600018.SHG`, `601816.SHG`, `601818.SHG`, `ELE.MC`, `ESSITY-B.ST`, `HIG.US`, `NOVN.SW`, `SHELL.AS`
- Shared core: `000333.SHE`, `600036.SHG`, `AD.AS`, `ALV.XETRA`, `CA.PA`, `HEN3.XETRA`, `IMB.LSE`, `ORA.PA`
- Regional-challenger only: `002415.SHE`, `600406.SHG`, `ABT.US`, `CVX.US`, `DG.PA`, `DHL.XETRA`, `GSK.LSE`, `LOW.US`, `NXT.LSE`, `PUB.PA`, `SHEL.LSE`, `T.US`

Highest supervised 3-month research rank in each region:

| Ticker | Region | Score | Cost-adjusted alpha | Q05 | Q95 |
| --- | --- | ---: | ---: | ---: | ---: |
| `NA9.XETRA` | DACH | 99.6 | 4.2% | -33% | 41% |
| `SESG.PA` | EU ex-DACH | 99.2 | 3.7% | -31% | 41% |
| `0354.HK` | Hong Kong | 99.4 | 4.5% | -32% | 43% |
| `000009.SHE` | Mainland China | 85.5 | 2.9% | -31% | 49% |
| `GEN.LSE` | UK | 100.0 | 4.9% | -32% | 39% |
| `HPQ.US` | US | 100.0 | 3.6% | -30% | 36% |

These six names are a research watchlist, not buy orders. The live recommendation
remains the governed target described below.

## DRL And Prospective Evidence

The five PPO seeds, contextual bandit and convex residual challenger remain
rejected for deployment. The selected simple challengers also trailed the
baseline in the 12-month legacy OOS diagnostic:

| Challenger | Net return | Baseline | Mean active return | Status |
| --- | ---: | ---: | ---: | --- |
| Contextual Bandit | 14.2% | 14.6% | -0.03% | Research only |
| Convex Residual | 13.8% | 14.6% | -0.06% | Research only |

DRL receives 0% and
the baseline receives 100%.
The generic shadow programme has completed
0 of
3 required cycles.
The supervised model was separately frozen for prospective evidence: its first
3-month result is due 30 November 2026, and 12 non-overlapping cohorts
cannot complete before 31 August 2029.

## Adaptive Risk Backtesting

The trailing model-selection stack contains DCC-IGARCH Student-t, filtered
historical simulation, EWMA Normal, and EWMA Student-t forecasts. Kupiec
coverage and Christoffersen independence tests pass overall and on the 40%
chronological holdout. Development data selected a
1.075x global scale and a
1.40x buffer for
1 day after an observed exception; those
parameters were locked before holdout scoring.

| Sample | VaR | Exceptions | Kupiec p | Independence p | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Overall | 95% | 50/1158 | 0.276 | 0.080 | Pass |
| Overall | 99% | 15/1158 | 0.334 | 0.530 | Pass |
| Holdout | 95% | 15/463 | 0.064 | 0.086 | Pass |
| Holdout | 99% | 2/463 | 0.166 | 0.895 | Pass |

This holdout is chronological reconstructed evidence, not a pristine future
shadow period. Live monitoring is still required.

## Point-In-Time Evidence

The evidence store now contains **59,183** delisting events and
**32,321** fundamental rows with filing dates.
Bloomberg aggregate coverage adds **25,240** database-as-of
fundamental vintages, **694,246** historical market-cap vintages,
and **151,659** corporate-action vintages. The remaining
snapshot pull is resumable from its daily-capacity checkpoint; licensed rows stay
in the ignored local warehouse and are not published.
Observed acceptance timestamps, dated
index membership, inactive-name prices, and historical volume remain below
their governance thresholds. EODHD populated delistings; the Nasdaq
entitlement yielded five usable rows; Beam was unavailable; and SEC blocked
this runner. Unavailable history is not represented as observed evidence.
The point-in-time component therefore remains **7.5/15, warning**.

## Current Target Portfolio

The resolved baseline contains 20 equities capped at
5.0% each and
0.0% cash. The current trade comparison produces
19 buys and 1 reductions. These are model targets,
not executable orders; live NAV, FX, liquidity, prices and compliance
approval must be refreshed first.

- Buy: `000333.SHE`, `000538.SHE`, `0728.HK`, `1113.HK`, `3988.HK`, `600018.SHG`, `600036.SHG`, `601816.SHG`, `601818.SHG`, `AD.AS`, `ALV.XETRA`, `CA.PA`, `ELE.MC`, `ESSITY-B.ST`, `HEN3.XETRA`, `HIG.US`, `IMB.LSE`, `ORA.PA`, `SHELL.AS`
- Reduce: `NOVN.SW` to 5.0%

## Point-In-Time Performance

| Measure | Wolf CVaR | Equal weight | Cap weight |
| --- | ---: | ---: | ---: |
| Annualised net return | 13.3% | 15.7% | 10.2% |
| Sharpe ratio | 1.32 | 1.23 | 0.92 |
| Sortino ratio | 3.16 | 2.64 | 1.92 |
| Maximum drawdown | -10.1% | -14.9% | -15.0% |
| Annualised cost drag | 0.8% | 0.7% | 0.8% |

Applying the realised 60-month Wolf path after modeled trading costs to
current AUM of $186.1m gives an illustrative ending value of $347.2m
and PnL of $161.2m. The separate annual bank charge is 0.25%, equal to
$465k at the reference AUM. This is a scale illustration, not a
forecast or a live-capacity result.

The portfolio component remains **5/10, warning** even though both cost gates
pass. Wolf returned -2.43% per year relative to equal weight.
The paired difference was not statistically significant
(p=0.550).

## Alpha And Overfitting

Wolf's point-in-time active return is 2.67% versus cap weight and
-2.44% versus equal weight. Neither alpha test is statistically
significant. The retrospective CSCV test estimates a
24.6% probability of backtest overfitting, while the selected strategy's
median information ratio falls 48.4% out-of-sample. The 1997 replay
remains a stress and exposure diagnostic, not proof of historical selection
skill.

## Conditions For Scaling

1. Recalculate orders with live NAV, FX, price and liquidity data.
2. Require human approval before every pilot rebalance.
3. Keep annualised turnover at or below 1.5x, with a 1.0x pilot stretch goal.
4. Track net performance against equal-weight and cap-weight controls.
5. Stop on stale critical data, any hard breach, a failed live risk test,
   failed reconciliation, or a breached cost budget.
6. Require observed PIT vintages and a genuine future shadow record before
   making deployable alpha claims.

The full local test suite passed. GitHub Actions remains the publication gate.
Research output only. This report is not authorization for unattended trading
or individualized investment advice.
