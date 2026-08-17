# Wolf Quant Model Investment Committee Briefing

This package translates model outputs through 17 August 2026 and the 13 August
validation release into a non-technical investment-principal briefing.

## Published Artifacts

- [PowerPoint deck](wolf_quant_model_ic_briefing.pptx)
- [Rendered PDF](wolf_quant_model_ic_briefing_2026-08-17.pdf)
- [Investment principal report](investment_principal_report.md)
- [Publication-safe stock recommendations](recommendation_snapshot.csv)
- [Artifact manifest](manifest.json)

The recommendation snapshot contains the governed 20-name target, the 20-name
regional-alpha challenger and the six regional supervised-model research names.
Both challenger groups are explicitly marked as non-executable. Full
security-level prediction and optimiser panels stay local because they may
contain licensed-derived inputs.

## Current Decision

The recommendation remains a controlled, human-supervised live pilot.
Governance improved from 80/100 to 87.5/100. Adaptive VaR risk backtesting
now scores 15/15, annual turnover fell from 2.11x to 1.10x, and modeled annual
cost drag fell from 2.35% to 0.82%. All four overall and chronological-holdout
VaR coverage/independence checks pass, and hard portfolio breaches remain zero.

Full-scale or unattended deployment is not approved. Point-in-time evidence
remains 7.5/15 because observed filing acceptance, dated membership,
inactive-name prices, and historical volume are incomplete. The portfolio
component remains 5/10 because Wolf did not significantly outperform the
equal-weight control, despite passing the cost and turnover gates.

The refreshed 22-slide deck also covers the supervised benchmark-relative
models. The primary 3-month diagnostic has rank IC 0.157, but only four
independent cohorts and an exact sign-test p-value of 0.0625. The supervised
blend therefore remains 0%. Conformal interval coverage now exceeds 90% at
every horizon, although 9- and 12-month ranges remain too wide for confident
stock claims. DRL, contextual-bandit and convex challengers also remain at 0%.

The governed 20-stock CVaR target is shown separately from the regional-alpha
challenger and the six-name supervised research watchlist. Research watchlist
names are explicitly not presented as executable orders.

## Evidence Boundary

The 60-month reconstructed point-in-time proxy is the primary model evidence.
The 1997-present holdings replay is used for stress, exposure and liquidity
diagnostics; it is not presented as a historical stock-selection backtest.
The chronological risk holdout is reconstructed evidence, not a pristine
future shadow period. Current target weights must be refreshed with live NAV,
FX, prices, liquidity and compliance review before execution.
The supervised research version is frozen for prospective evidence: its first
3-month outcome is due 30 November 2026, and 12 independent cohorts cannot be
complete before 31 August 2029.

## Rebuild

Build the PowerPoint and Markdown report:

```powershell
.\.venv\Scripts\python.exe scripts\build_investment_principal_deck.py
```

On Windows with Microsoft PowerPoint installed, build and render the PDF:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\render_investment_principal_deck.ps1
```

Research output only. This package is not authorization for unattended
trading or individualized investment advice.
