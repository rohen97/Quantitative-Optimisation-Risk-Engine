# Wolf Quant Model Investment Principal Report

As of 13 August 2026

## Decision

**Approve a controlled, human-supervised live pilot.** Governance improved
from 80/100 to 87.5/100. Six components pass,
two remain warnings, and there are zero critical failures. Adaptive risk
backtesting and the turnover/cost targets now pass. Full-scale or unattended
deployment remains unapproved because observed point-in-time evidence is
incomplete and
benchmark-relative alpha is not established.

## What Improved

| Control | Before | Now | Current gate |
| --- | ---: | ---: | --- |
| Governance score | 80/100 | 87.5/100 | Conditional approval |
| Risk backtesting | Warning, 7.5/15 | Pass, 15/15 | Coverage and independence pass |
| Annual turnover | 2.11x | 1.33x | <=1.50x: pass |
| Annualised cost drag | 2.35% | 1.28% | <=1.50%: pass |
| Hard constraint breaches | 0 | 0 | Pass |

Retention hysteresis, a 6% monthly turnover cap, and minimum-turnover
transitions drove the implementation improvement. The configured no-trade
band did not trigger in this 60-month sample, so it is not credited for the
observed result.

## Adaptive Risk Backtesting

The trailing model-selection stack contains DCC-IGARCH Student-t, filtered
historical simulation, EWMA Normal, and EWMA Student-t forecasts. Kupiec
coverage and Christoffersen independence tests pass overall and on the 40%
chronological holdout.

| Sample | VaR | Exceptions | Kupiec p | Independence p | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Overall | 95% | 62/1152 | 0.557 | 0.367 | Pass |
| Overall | 99% | 10/1152 | 0.645 | 0.072 | Pass |
| Holdout | 95% | 21/460 | 0.664 | 0.074 | Pass |
| Holdout | 99% | 3/460 | 0.423 | 0.843 | Pass |

This holdout is chronological reconstructed evidence, not a pristine future
shadow period. Live monitoring is still required.

## Point-In-Time Evidence

The evidence store now contains **59,183** delisting events and
**7,081** fundamental rows with filing dates.
Observed acceptance timestamps, dated
index membership, inactive-name prices, and historical volume remain below
their governance thresholds. EODHD populated delistings; the Nasdaq
entitlement yielded five usable rows; Beam was unavailable; and SEC blocked
this runner. Unavailable history is not represented as observed evidence.
The point-in-time component therefore remains **7.5/15, warning**.

## Current Target Portfolio

The resolved baseline contains 20 equal-weight positions at 5% each. The
current trade comparison produces 19 buys and one reduction. These are model
targets, not executable orders; live NAV, FX, liquidity, prices and compliance
approval must be refreshed first.

- Buy: `000333.SHE`, `000538.SHE`, `0823.HK`, `3988.HK`, `600018.SHG`, `600036.SHG`, `601816.SHG`, `601818.SHG`, `AD.AS`, `ALV.XETRA`, `CS.PA`, `ESSITY-B.ST`, `HEN3.XETRA`, `LI.PA`, `MCD.US`, `ORA.PA`, `PG.US`, `SBRY.LSE`, `SHEL.US`
- Reduce to 5%: `NOVN.SW`

## Point-In-Time Performance

| Measure | Wolf CVaR | Equal weight | Cap weight |
| --- | ---: | ---: | ---: |
| Annualised net return | 13.8% | 14.9% | 9.9% |
| Sharpe ratio | 1.26 | 1.11 | 0.90 |
| Sortino ratio | 2.67 | 2.36 | 1.70 |
| Maximum drawdown | -13.0% | -17.8% | -15.0% |
| Annualised cost drag | 1.3% | 0.8% | 0.7% |

Applying the realised 60-month Wolf path after modeled trading costs to
current AUM of $186.1m gives an illustrative ending value of $355.3m
and PnL of $169.3m. The separate annual bank charge is 0.25%, equal to
$465k at the reference AUM. This is a scale illustration, not a
forecast or a live-capacity result.

The portfolio component remains **5/10, warning** even though both cost gates
pass. Wolf returned -1.06% per year relative to equal weight.
The paired difference was not statistically significant (p=0.734).

## Alpha And Overfitting

Wolf's point-in-time active return is 3.43% versus cap weight and
-1.24% versus equal weight. Neither alpha test is statistically
significant. The retrospective CSCV test estimates a
19.9% probability of backtest overfitting, while the selected strategy's
median information ratio falls 50.3% out-of-sample. The 1997 replay
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
