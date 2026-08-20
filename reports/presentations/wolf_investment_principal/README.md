# Wolf Quant Model Investment Committee Briefing

This package translates model outputs and the 19 August 2026 validation release
into a non-technical investment-principal briefing updated on 20 August 2026.

## Published Artifacts

- [PowerPoint deck](wolf_quant_model_ic_briefing.pptx)
- [Rendered PDF](wolf_quant_model_ic_briefing_2026-08-20.pdf)
- [Investment principal report](investment_principal_report.md)
- [Publication-safe stock recommendations](recommendation_snapshot.csv)
- [Artifact manifest](manifest.json)

The recommendation snapshot contains the governed 20-name target, the 20-name
regional-alpha challenger and the six regional supervised-model research names.
Both challenger groups are explicitly marked as non-executable. Full
security-level prediction and optimiser panels stay local because they may
contain licensed-derived inputs.

## Current Decision

The recommendation is to continue paper and shadow operation; live capital is
not approved. Governance is 75/100 after the expanded evidence run. Adaptive
VaR risk backtesting scores 15/15, annual turnover is 1.01x, modeled annual cost
drag is 0.83%, both chronological-holdout VaR gates pass, and hard portfolio
breaches remain zero. The overall-history VaR rows remain visible as a warning
at 95% and a failure at 99%; they are diagnostics rather than the configured gate.

Full-scale or unattended deployment is not approved. Point-in-time evidence
remains 7.5/15 because observed filing acceptance, dated membership,
inactive-name prices, and broad historical volume are incomplete. The portfolio
component remains 5/10 because Wolf did not significantly outperform the
equal-weight control, despite passing the cost and turnover gates.

The refreshed 25-slide deck includes a design-architecture diagram and a
four-horizon heatmap comparing OLS screening, Ridge, Elastic Net, Huber, Random
Forest, Extra Trees, histogram boosting, XGBoost, XGBoost ranking and the
ensemble. The primary 3-month diagnostic has rank IC 0.157, but only four
independent cohorts and an exact sign-test p-value of 0.0625. The supervised
blend therefore remains 0%. Conformal interval coverage now exceeds 90% at
every horizon, although 9- and 12-month ranges remain too wide for confident
stock claims. DRL, contextual-bandit and convex challengers also remain at 0%.

## Supervised Model Locations

- Engine: `src/models/supervised_alpha.py`
- Runner: `scripts/run_supervised_alpha.py`
- Model families and validation settings: `configs/ml_forecasting.yaml`
- Local bundles: `data/processed/supervised_alpha/*.joblib`
- Local checkpoints: `data/interim/supervised_alpha_checkpoints/`
- Aggregate results: `reports/outputs/supervised_alpha/`
- Presentation comparison plot: `plots/supervised_model_comparison.png`

Security-level predictions and optimiser inputs are intentionally excluded from
the public package; aggregate model-family, validation, OOS and calibration
evidence remains reproducible and checksummed.

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
