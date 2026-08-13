# Wolf Quant Model Investment Committee Briefing

This package translates the current model outputs and 13 August 2026
validation evidence into a non-technical investment-principal briefing.

## Published Artifacts

- [PowerPoint deck](wolf_quant_model_ic_briefing.pptx)
- [Rendered PDF](wolf_quant_model_ic_briefing_2026-08-13.pdf)
- [Investment principal report](investment_principal_report.md)
- [Artifact manifest](manifest.json)

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

## Evidence Boundary

The 60-month reconstructed point-in-time proxy is the primary model evidence.
The 1997-present holdings replay is used for stress, exposure and liquidity
diagnostics; it is not presented as a historical stock-selection backtest.
The chronological risk holdout is reconstructed evidence, not a pristine
future shadow period. Current target weights must be refreshed with live NAV,
FX, prices, liquidity and compliance review before execution.

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
