# Wolf Quant Model Investment Committee Briefing

This package translates the current model outputs and validation evidence
into a non-technical investment-principal briefing.

## Published Artifacts

- [PowerPoint deck](wolf_quant_model_ic_briefing.pptx)
- [Rendered PDF](wolf_quant_model_ic_briefing.pdf)
- [Investment principal report](investment_principal_report.md)
- [Artifact manifest](manifest.json)

## Decision

The recommendation is to approve a controlled, human-supervised live pilot.
Full-scale or unattended deployment is not approved. The evidence supports
using Wolf for disciplined screening, portfolio construction, risk controls
and governance, while deployable alpha remains unestablished.

## Evidence Boundary

The 60-month reconstructed point-in-time proxy is the primary model evidence.
The 1997-present holdings replay is used for stress, exposure and liquidity
diagnostics; it is not presented as a historical stock-selection backtest.
Current target weights are research outputs and must be refreshed with live
NAV, FX, prices, liquidity and compliance review before any execution.

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
