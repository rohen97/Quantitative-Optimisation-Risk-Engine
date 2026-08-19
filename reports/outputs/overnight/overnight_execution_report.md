# Overnight Execution Report

- Status: **completed**
- Started (UTC): `2026-08-19T07:28:16.827824+00:00`
- Completed (UTC): `2026-08-19T07:28:34.880287+00:00`
- Runtime: `18.1` seconds
- Disabled resource groups: `bloomberg`

| Step | Required | External | Status | Attempts | Exit | Seconds | Min free GB |
|---|---:|---:|---|---:|---:|---:|---:|
| refresh_price_summaries | True | False | completed | 1 | 0 | 18.023 | 12.439 |
| bloomberg_pit_coverage | True | False | completed | 1 | 0 | 2.017 | 15.802 |
| point_in_time_evidence_coverage | True | False | completed | 1 | 0 | 4.016 | 15.516 |
| production_pit_coverage | True | False | completed | 1 | 0 | 4.014 | 15.613 |
| free_data_evidence | True | False | completed | 1 | 0 | 2.014 | 15.589 |
| credential_history_audit | True | False | completed | 1 | 0 | 20.032 | 15.394 |
| two_phase_preprocessing | True | False | completed | 1 | 0 | 64.063 | 13.142 |
| global_model_and_drl | True | False | completed | 1 | 0 | 30.029 | 14.547 |
| walk_forward_full | True | False | completed | 1 | 0 | 648.387 | 10.782 |
| standalone_drl_validation | True | False | completed | 1 | 0 | 1853.056 | 12.721 |
| full_governance_validation | True | False | completed | 1 | 0 | 10.021 | 15.321 |
| risk_backtesting | True | False | completed | 1 | 0 | 10.016 | 15.352 |
| portfolio_backtest_1997 | True | False | completed | 2 | 0 | 38.033 | 15.145 |
| full_regression_suite | True | False | completed | 1 | 0 | 412.216 | 14.485 |
| release_evidence | True | False | completed | 1 | 0 | 6.019 | 15.878 |
| investment_principal_deck | True | False | completed | 2 | 0 | 18.028 | 15.737 |

## Evidence

- **refresh_price_summaries**: }
- **bloomberg_pit_coverage**: decision_snapshot_manifests    534       534           2019-02-28         2026-06-30 2026-08-13 09:28:09.035714 2026-08-14 09:44:09.509880
- **point_in_time_evidence_coverage**: INFO PIT evidence coverage written to C:\Users\Admin\the-wolf-quant-model\reports\outputs\validation\pit_evidence_coverage.json
- **production_pit_coverage**: Wrote reports\outputs\production_pit_coverage.md and reports\outputs\production_pit_coverage.csv.
- **free_data_evidence**: Manifest: C:\Users\Admin\the-wolf-quant-model\reports\outputs\validation\free_data_evidence_manifest.json
- **credential_history_audit**: Report: C:\Users\Admin\the-wolf-quant-model\reports\outputs\validation\credential_history_audit.json
- **two_phase_preprocessing**: 2026-08-19 14:30:17,860 INFO Phase 1 summary: {'status': 'completed', 'input_data_mode': 'observed', 'security_count': 1403, 'batch_count': 6, 'completed_batches': 6, 'skipped_batches': 0, 'worker_count': 2, 'max_inflight_securities': 5000, 'runtime_seconds': 57.650035699945875}
- **global_model_and_drl**: 2026-08-19 14:30:47,045 INFO Phase 2 produced 98 output frames.
- **walk_forward_full**: 2026-08-19 14:41:36,551 INFO src.validation.validation_pipeline - Validation run validation-20260819T064130-222c6c80 completed with status=CONDITIONALLY_APPROVED score=75.0
- **standalone_drl_validation**: INFO Constrained regime-gated explainable DRL pipeline completed with 25 output artifacts.
- **full_governance_validation**: 2026-08-19 15:12:38,932 INFO src.validation.validation_pipeline - Validation run validation-20260819T071232-eb55e9d5 completed with status=CONDITIONALLY_APPROVED score=75.0
- **risk_backtesting**: C:\Users\Admin\the-wolf-quant-model\reports\outputs\validation\validation-20260819T071242-c060013a\risk_backtesting_report.csv
- **portfolio_backtest_1997**: PDF report: C:\Users\Admin\the-wolf-quant-model\reports\backtests\1997_to_latest\portfolio_backtest_analysis.pdf
- **full_regression_suite**: 450 passed, 2 warnings in 408.72s (0:06:48)
- **release_evidence**: Score: 75.0
- **investment_principal_deck**: INFO Registered rendered PDF: C:\Users\Admin\the-wolf-quant-model\reports\presentations\wolf_investment_principal\manifest.json
