# Wolf Quant Model Governance

## Decision Framework

The validation score totals 100 points:

- data integrity: 20
- point-in-time correctness: 15
- forecast performance: 15
- distribution calibration: 10
- risk backtesting: 15
- portfolio performance net of costs: 10
- constraint compliance: 10
- stability and sensitivity: 5

Possible decisions are `APPROVED`, `CONDITIONALLY_APPROVED`, `REJECTED` and `INSUFFICIENT_DATA`. Unavailable evidence is not silently scored as a failure or a pass.

## Critical Overrides

The following block approval regardless of numerical score:

- look-ahead or target leakage
- point-in-time availability failure
- unresolved hard portfolio constraint breach
- invalid or irreproducible final weights
- failed required tail-risk backtest
- missing lineage or input snapshot hash
- test-period tuning
- DRL selection after governance rejection
- inability to reproduce results from the stored snapshot

## Release Controls

Smoke validation runs daily after IC reporting. Full validation runs monthly. Release-candidate validation is mandatory before a production tag. Every result uses an immutable run ID, stores source and configuration hashes, writes a manifest, registers lineage in DuckDB when available, and copies the completed bundle to `latest` without symlinks.

The final test period cannot be used for hyperparameter selection. Failed periods remain in reports. Multiple comparisons require false-discovery-rate context, and serially dependent returns use block bootstrap methods.

## Current Governance Position

The present repository has current cross-sectional forecasts and proxy backtests but insufficient aligned realised outcomes for full 3M, 6M, 9M and 12M calibration. Production approval therefore requires accumulated point-in-time forecast vintages, at least 24 months of realised net strategy returns, completed risk backtests and remediation of all hard constraints. DRL cannot be promoted before the selected classical optimiser passes these controls.
