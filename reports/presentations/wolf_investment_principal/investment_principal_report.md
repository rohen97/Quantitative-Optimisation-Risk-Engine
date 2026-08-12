# Wolf Quant Model Investment Principal Report

As of 12 August 2026

## Decision

**Approve a controlled, human-supervised live pilot.** The model has a
repeatable six-region equity process, five years of reconstructed
point-in-time decisions, zero hard constraint breaches, and an auditable
governance package. Full-scale or unattended deployment is not approved:
deployable alpha is not established, turnover is high, and tail-risk
exceptions cluster over time.

## Current Target Portfolio

The resolved baseline contains 20 equal-weight positions at 5% each. The
current trade comparison produces 19 buys and one reduction. These are
model targets, not executable orders; live NAV, FX, liquidity, prices and
compliance approval must be refreshed first.

- Buy: `000333.SHE`, `000538.SHE`, `0823.HK`, `3988.HK`, `600018.SHG`, `600036.SHG`, `601816.SHG`, `601818.SHG`, `AD.AS`, `ALV.XETRA`, `CS.PA`, `ESSITY-B.ST`, `HEN3.XETRA`, `LI.PA`, `MCD.US`, `ORA.PA`, `PG.US`, `SBRY.LSE`, `SHEL.US`
- Reduce to 5%: `NOVN.SW`

## Point-In-Time Evidence

| Measure | Wolf CVaR | Equal weight | Cap weight |
| --- | ---: | ---: | ---: |
| Annualised net return | 13.7% | 14.8% | 9.9% |
| Sharpe ratio | 1.16 | 1.11 | 0.90 |
| Maximum drawdown | -13.7% | -17.8% | -15.0% |
| Annualised cost drag | 2.4% | 0.8% | 0.7% |

Applying the realised 60-month Wolf return path after trading costs to
current AUM of
$186.1m gives an illustrative ending value of
$352.9m and PnL of $166.9m.
This is before the separately modeled 25 bp annual bank fee. It is a
scale illustration, not a forecast or a live-capacity result.

## Alpha And Overfitting

Wolf's point-in-time active return is 3.43%
versus cap weight and -1.24%
versus equal weight. Neither alpha test is statistically significant.
The retrospective CSCV test estimates a 19.9%
probability of backtest overfitting, while the selected strategy's median
information ratio falls 50.3%
out-of-sample. The 1997 replay is therefore used for stress and exposure
diagnostics, not as proof of historical selection skill.

## Why Use Wolf In A Pilot

Wolf makes the investment process broader, more consistent and more
auditable. It compares portfolio-aware, clean-sheet and LLM branches;
forecasts return distributions; applies liquidity and concentration
constraints; stress-tests the result; and records why a challenger was
accepted or rejected. The current DRL challenger was rejected for excess
turnover, demonstrating that governance can override model novelty.

## Conditions For Scaling

1. Recalculate orders with live NAV, FX, price and liquidity data.
2. Require human approval before every pilot rebalance.
3. Reduce annualised turnover below 1.0x with no-trade bands and staged
   transitions.
4. Track net performance against equal-weight and cap-weight controls.
5. Stop on stale critical data, any hard breach, failed reconciliation,
   unexplained risk clustering or a breached cost budget.
6. Require native live evidence before making deployable alpha claims.

Research output only. This report is not authorization for unattended
trading or individualized investment advice.
