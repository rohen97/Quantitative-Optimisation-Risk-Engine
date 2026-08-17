# Overnight Execution Report

- Status: **completed_with_external_limits**
- Started (UTC): `2026-08-13T17:44:20.283488+00:00`
- Completed (UTC): `2026-08-13T18:22:05.795035+00:00`
- Runtime: `2265.5` seconds

| Step | Required | External | Status | Attempts | Exit | Seconds | Min free GB |
|---|---:|---:|---|---:|---:|---:|---:|
| refresh_price_summaries | True | False | completed | 1 | 0 | 4.017 | 11.306 |
| bloomberg_priority_pit | False | True | failed_optional | 2 | 75 | 2044.965 | 10.748 |
| bloomberg_full_china_pit | False | True | failed_optional | 0 | 75 | None | None |
| bloomberg_pit_coverage | True | False | completed | 3 | 0 | 2.018 | 11.04 |
| two_phase_preprocessing | True | False | completed | 3 | 0 | 72.059 | 8.439 |
| global_model_and_drl | True | False | completed | 4 | 0 | 98.064 | 9.726 |
| standalone_drl_validation | True | False | completed | 3 | 0 | 100.125 | 10.011 |
| walk_forward_full | True | False | completed | 4 | 0 | 506.272 | 7.58 |
| full_governance_validation | True | False | completed | 3 | 0 | 8.027 | 10.745 |
| risk_backtesting | True | False | completed | 3 | 0 | 8.019 | 10.65 |
| portfolio_backtest_1997 | True | False | completed | 5 | 0 | 62.046 | 10.671 |
| full_regression_suite | True | False | completed | 7 | 0 | 1384.761 | 7.884 |
| release_evidence | True | False | completed | 2 | 0 | 8.018 | 10.828 |
| investment_principal_deck | True | False | completed | 4 | 0 | 16.025 | 10.904 |

## Evidence

- **refresh_price_summaries**: }
- **bloomberg_priority_pit**: 2026-08-14 01:38:08,707 ERROR Bloomberg PIT run paused at a durable chunk checkpoint: Bloomberg fundamental Y 2020-12-31 chunk 6/25: Daily capacity reached. [nid:19488]
- **bloomberg_full_china_pit**: Not attempted after the shared Bloomberg Desktop session reached daily capacity during the higher-priority validation universe.
- **bloomberg_pit_coverage**: decision_snapshot_manifests    241       241           2021-07-31         2026-06-30 2026-08-13 09:28:09.035714 2026-08-13 16:31:34.550287
- **two_phase_preprocessing**: 2026-08-14 01:45:31,722 INFO Phase 1 summary: {'status': 'completed', 'input_data_mode': 'observed', 'security_count': 1402, 'batch_count': 6, 'completed_batches': 6, 'skipped_batches': 0, 'worker_count': 2, 'max_inflight_securities': 5000, 'runtime_seconds': 64.70891600009054}
- **global_model_and_drl**: 2026-08-14 01:47:10,852 INFO Phase 2 produced 94 output frames.
- **standalone_drl_validation**: INFO Constrained regime-gated explainable DRL pipeline completed with 22 output artifacts.
- **walk_forward_full**: 2026-08-14 01:57:18,243 INFO src.validation.validation_pipeline - Validation run validation-20260813T175713-fbce6f4b completed with status=CONDITIONALLY_APPROVED score=80.0
- **full_governance_validation**: 2026-08-14 01:57:25,402 INFO src.validation.validation_pipeline - Validation run validation-20260813T175720-a34c8ea1 completed with status=CONDITIONALLY_APPROVED score=80.0
- **risk_backtesting**: C:\Users\Admin\the-wolf-quant-model\reports\outputs\validation\validation-20260813T175728-ea8e19e8\risk_backtesting_report.csv
- **portfolio_backtest_1997**: PDF report: C:\Users\Admin\the-wolf-quant-model\reports\backtests\1997_to_latest\portfolio_backtest_analysis.pdf
- **full_regression_suite**: 401 passed, 2 warnings in 1382.43s (0:23:02)
- **release_evidence**: Score: 80.0
- **investment_principal_deck**: INFO Registered rendered PDF: C:\Users\Admin\the-wolf-quant-model\reports\presentations\wolf_investment_principal\manifest.json
