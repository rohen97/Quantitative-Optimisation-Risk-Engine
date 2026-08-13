# Wolf Quant Model Investment Principal Report

As of 13 August 2026

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
