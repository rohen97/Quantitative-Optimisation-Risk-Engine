# Final Overnight Verification

- Verified (UTC): `2026-08-13T19:34:10Z`
- Result: **completed_with_external_limits**
- Governance: **CONDITIONALLY_APPROVED, 87.5/100**
- Regression: **403 passed, 2 warnings**
- Required local processes left running: **0**

## Final Evidence

| Area | Result |
|---|---|
| Bounded pipeline | 1,402 securities in 6 regional batches; 2 workers and at most 5,000 securities in flight |
| Walk-forward | 181,664 forecasts, 181,213 aligned outcomes, 60 monthly anchors and 0 chronology breaches |
| Portfolio | 20 equities at 5% each, 0% cash and 0 hard-constraint breaches |
| Costs | 1.10x annual turnover and 0.82% annualised cost drag; both governance limits pass |
| Risk | 95% and 99% Kupiec coverage and Christoffersen independence pass overall and on holdout |
| DRL | Five real PPO seeds completed; every OOS information ratio was negative, so the baseline was retained |
| Overfitting | PBO 24.57%; selected-strategy information ratio fell 48.37% from in-sample to out-of-sample |
| Release | 95 checksummed files, 18-slide PowerPoint, rendered PDF and written principal report |

## Bloomberg Boundary

The local licensed warehouse contains 25,240 fundamental vintages, 151,659
corporate-action vintages, 694,246 market-cap vintages, 34,172 identifier
vintages, 157,155 macro vintages and 361 decision manifests. The remaining
fundamental snapshot pull stopped at a durable checkpoint when Bloomberg
returned daily-capacity error `[nid:19488]`. No licensed observations, local
database, credentials or provider cache are included in the release.

## Decision

The classical constrained portfolio remains authoritative. DRL is operational
and reproducible but is correctly rejected because it did not improve net OOS
performance. Risk and implementation-cost gates pass. Full-scale alpha approval
remains blocked by incomplete native historical PIT membership, inactive-name
prices, broad historical volume and a genuine future shadow record.

The original unattended cycle is preserved in
`overnight_execution_report.md`; this document records the fixes and final
verification performed after that cycle.
