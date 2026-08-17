# Supervised Alpha Challenger Report

Generated: 2026-08-17T07:20:18.452921+00:00

## Decision

**INSUFFICIENT_EVIDENCE**. insufficient_independent_oos_periods;oos_independent_sign_test_not_significant;oos_uncertainty_interval_unavailable;legacy_oos_exposed_to_research_iteration;point_in_time_evidence_not_native_live

The supervised models remain governed challengers. A rejected or insufficient-evidence result sets the live deployment blend to zero, so the established regional-alpha optimiser remains unchanged.

## Dataset

| horizon_months | rows | securities | decision_dates | start_date | end_date | latest_target_date | minimum_outcome_cross_section_coverage | evidence_modes | numeric_features |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3.0000 | 77895.0000 | 1374.0000 | 88.0000 | 2019-01-31 | 2026-04-30 | 2026-07-30 | 0.9903 | reconstructed_pit_proxy | 67.0000 |
| 6.0000 | 72509.0000 | 1371.0000 | 84.0000 | 2019-01-31 | 2025-12-31 | 2026-06-30 | 1.0000 | reconstructed_pit_proxy | 67.0000 |
| 9.0000 | 68449.0000 | 1366.0000 | 81.0000 | 2019-01-31 | 2025-09-30 | 2026-06-30 | 1.0000 | reconstructed_pit_proxy | 67.0000 |
| 12.0000 | 64404.0000 | 1361.0000 | 78.0000 | 2019-01-31 | 2025-06-30 | 2026-06-30 | 1.0000 | reconstructed_pit_proxy | 67.0000 |

Each row joins features available at a historical decision date to a later realised return. Labels are measured relative to contemporaneous regional and sector peers. Decision dates with less than 90% realised-outcome coverage are excluded so an incomplete final cross-section cannot create forced sales or biased performance. The current panel is a reconstructed point-in-time proxy rather than native live evidence, so it is suitable for research but cannot authorize deployment.

## Validation

| horizon_months | observations | independent_observations | mean_rank_ic | independent_rank_ic_hit_rate | independent_rank_ic_sign_test_p_value | mean_horizon_net_active_return | annualised_turnover | annualised_cost_drag | active_return_ci_lower_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3.0000 | 12.0000 | 4.0000 | 0.0980 | 0.7500 | 0.3125 | 0.0416 | 1.1113 | 0.0080 |  |
| 6.0000 | 9.0000 | 2.0000 | 0.1113 | 1.0000 | 0.2500 | 0.0845 | 1.2150 | 0.0085 |  |
| 9.0000 | 6.0000 | 1.0000 | 0.1230 | 1.0000 | 0.5000 | 0.1312 | 1.2615 | 0.0088 |  |
| 12.0000 | 3.0000 | 1.0000 | 0.1447 | 1.0000 | 0.5000 | 0.1964 | 1.5000 | 0.0102 |  |

Expanding-window folds use only labels whose target date is earlier than the next validation block. Validation labels must also mature before the legacy OOS start, preventing model-family selection from seeing any return realised inside that later calendar. Imputation, encoding, scaling, winsorisation, OLS screening, and model fitting are repeated inside each training fold.

## Legacy OOS

| horizon_months | observations | independent_observations | mean_rank_ic | independent_rank_ic_hit_rate | independent_rank_ic_sign_test_p_value | mean_horizon_net_active_return | initial_funding_turnover | annualised_turnover | annualised_transaction_cost_drag | annualised_bank_fee_drag | annualised_cost_drag | active_return_ci_lower_95 | active_return_ci_upper_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3.0000 | 11.0000 | 4.0000 | 0.1570 | 1.0000 | 0.0625 | 0.0740 | 0.5000 | 0.5438 | 0.0025 | 0.0025 | 0.0050 |  |  |
| 6.0000 | 7.0000 | 2.0000 | 0.1818 | 1.0000 | 0.2500 | 0.1418 | 0.5000 | 0.4740 | 0.0022 | 0.0025 | 0.0047 |  |  |
| 9.0000 | 4.0000 | 1.0000 | 0.2262 | 1.0000 | 0.5000 | 0.2478 | 0.5000 | 0.3490 | 0.0017 | 0.0025 | 0.0042 |  |  |
| 12.0000 | 1.0000 | 1.0000 | 0.2525 | 1.0000 | 0.5000 | 0.3702 | 0.5000 |  |  | 0.0025 |  |  |  |

The monthly decision cohorts are scored separately but their forward return windows overlap. `independent_observations` counts a deterministic non-overlapping subset. Formal Sharpe ratios, t-statistics, confidence intervals and annualised return are suppressed until twelve independent cohorts exist; the independent sign-test p-value is shown instead. Recurring turnover excludes initial portfolio funding, which is reported separately. Desired weights move through an ex-ante 1.5x annual turnover budget; mandatory exits that exceed the monthly budget are disclosed rather than hidden. Net return and annual cost drag include the 0.25% annual bank charge in addition to spread, FX and impact estimates. This record has already informed research iteration, so it is labelled legacy OOS rather than untouched evidence; the cumulative plot is a cohort sum, not a CAGR or compound portfolio claim.

### Turnover Control Audit

| horizon_months | recurring_observations | maximum_monthly_turnover | monthly_turnover_budget | maximum_mandatory_exit_turnover | maximum_cash_weight | budget_breaches |
| --- | --- | --- | --- | --- | --- | --- |
| 3.0000 | 10.0000 | 0.1043 | 0.1250 | 0.0579 | 0.0371 | 0.0000 |
| 6.0000 | 6.0000 | 0.0604 | 0.1250 | 0.0000 | 0.0000 | 0.0000 |
| 9.0000 | 3.0000 | 0.0326 | 0.1250 | 0.0000 | 0.0000 | 0.0000 |
| 12.0000 | 0.0000 |  | 0.1250 | 0.0000 | 0.0000 | 0.0000 |

The 12-month horizon has no recurring OOS rebalance, so its ongoing turnover remains unestimable. A temporary cash weight can arise when a previously held security lacks a valid next-period outcome; the model exits that name rather than inventing a return. Passing interval coverage does not imply precise forecasts: the 9- and 12-month bands remain very wide and should be treated as low-confidence risk bounds.

## Model Selection

| horizon_months | candidate | family | category | ensemble_weight |
| --- | --- | --- | --- | --- |
| 3.0000 | huber | huber | linear | 0.3333 |
| 3.0000 | extra_trees | extra_trees | tree | 0.3333 |
| 3.0000 | xgb_ranker | xgb_ranker | ranker | 0.3333 |
| 6.0000 | huber | huber | linear | 0.3333 |
| 6.0000 | hist_gradient_boosting__l2_regularization-10p0_learning_rate-0p04_max_iter-160_max_leaf_nodes-15 | hist_gradient_boosting | tree | 0.3333 |
| 6.0000 | xgb_ranker | xgb_ranker | ranker | 0.3333 |
| 9.0000 | elastic_net__alpha-0p001_l1_ratio-0p5 | elastic_net | linear | 0.3333 |
| 9.0000 | hist_gradient_boosting__l2_regularization-5p0_learning_rate-0p04_max_iter-160_max_leaf_nodes-7 | hist_gradient_boosting | tree | 0.3333 |
| 9.0000 | xgb_ranker | xgb_ranker | ranker | 0.3333 |
| 12.0000 | ridge__alpha-100p0 | ridge | linear | 0.3333 |
| 12.0000 | random_forest__max_depth-6_max_features-0p7_min_samples_leaf-80_n_estimators-120 | random_forest | tree | 0.3333 |
| 12.0000 | xgb_ranker | xgb_ranker | ranker | 0.3333 |

At most one positive-validation model from each of the linear, tree, and ranking categories enters the equal-weight ensemble. This limits meta-model flexibility and reduces another source of overfitting.

## Quantiles

| horizon_months | observations | calibration_method | calibration_dates | calibration_target_coverage | lower_coverage | central_90_coverage | upper_coverage | mean_interval_width | pinball_loss_q05 | pinball_loss_q50 | pinball_loss_q95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3.0000 | 14837.0000 | purged_date_block_conformal | 12.0000 | 0.9500 | 0.0144 | 0.9464 | 0.9608 | 0.5604 | 0.0146 | 0.0576 | 0.0219 |
| 6.0000 | 9451.0000 | purged_date_block_conformal | 12.0000 | 0.9500 | 0.0159 | 0.9337 | 0.9495 | 0.8289 | 0.0211 | 0.0889 | 0.0377 |
| 9.0000 | 5391.0000 | purged_date_block_conformal | 12.0000 | 0.9500 | 0.0247 | 0.9195 | 0.9442 | 1.0007 | 0.0252 | 0.1160 | 0.0502 |
| 12.0000 | 1346.0000 | purged_date_block_conformal | 12.0000 | 0.9500 | 0.0334 | 0.9049 | 0.9383 | 1.1743 | 0.0307 | 0.1475 | 0.0742 |

The 5th, 50th, and 95th percentile forecasts are trained on an earlier development slice with histogram gradient boosting. A later purged development block applies date-block conformal interval correction and median-bias calibration before legacy OOS evaluation. The calibration block uses a conservative 95% target as a buffer around the published central 90% interval. Coverage shows how often realised benchmark-relative returns landed inside the calibrated interval.

## Generalisation Audit

| horizon_months | validation_folds | validation_independent_observations | legacy_oos_independent_observations | validation_mean_rank_ic | legacy_oos_mean_rank_ic | rank_ic_retention_ratio | validation_mean_net_active_return | legacy_oos_mean_net_active_return | overfitting_signal | deployment_interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3.0000 | 4.0000 | 4.0000 | 4.0000 | 0.0980 | 0.1570 | 1.6011 | 0.0416 | 0.0740 | NO_DEGRADATION_IN_LEGACY_SAMPLE | NOT_PROSPECTIVE_OR_NATIVE_PIT_EVIDENCE |
| 6.0000 | 3.0000 | 2.0000 | 2.0000 | 0.1113 | 0.1818 | 1.6337 | 0.0845 | 0.1418 | NO_DEGRADATION_IN_LEGACY_SAMPLE | NOT_PROSPECTIVE_OR_NATIVE_PIT_EVIDENCE |
| 9.0000 | 2.0000 | 1.0000 | 1.0000 | 0.1230 | 0.2262 | 1.8391 | 0.1312 | 0.2478 | NO_DEGRADATION_IN_LEGACY_SAMPLE | NOT_PROSPECTIVE_OR_NATIVE_PIT_EVIDENCE |
| 12.0000 | 1.0000 | 1.0000 | 1.0000 | 0.1447 | 0.2525 | 1.7453 | 0.1964 | 0.3702 | NO_DEGRADATION_IN_LEGACY_SAMPLE | NOT_PROSPECTIVE_OR_NATIVE_PIT_EVIDENCE |

This comparison checks whether performance deteriorated after validation. A favourable legacy result is encouraging but cannot disprove overfitting because this holdout has been inspected and the feature history is reconstructed. Only the prospective shadow record can provide new falsification evidence.

## Acceptance Gates

| scope | status | oos_monthly_observations | oos_observations | deployment_blend_weight | reasons |
| --- | --- | --- | --- | --- | --- |
| 3m | INSUFFICIENT_EVIDENCE | 11.0000 | 4.0000 | 0.0000 | insufficient_independent_oos_periods;oos_independent_sign_test_not_significant;oos_uncertainty_interval_unavailable;legacy_oos_exposed_to_research_iteration;point_in_time_evidence_not_native_live |
| 6m | INSUFFICIENT_EVIDENCE | 7.0000 | 2.0000 | 0.0000 | insufficient_independent_oos_periods;oos_independent_sign_test_not_significant;oos_uncertainty_interval_unavailable;legacy_oos_exposed_to_research_iteration;point_in_time_evidence_not_native_live |
| 9m | INSUFFICIENT_EVIDENCE | 4.0000 | 1.0000 | 0.0000 | insufficient_independent_oos_periods;oos_independent_sign_test_not_significant;oos_uncertainty_interval_unavailable;legacy_oos_exposed_to_research_iteration;point_in_time_evidence_not_native_live |
| 12m | INSUFFICIENT_EVIDENCE | 1.0000 | 1.0000 | 0.0000 | insufficient_independent_oos_periods;oos_independent_sign_test_not_significant;oos_uncertainty_interval_unavailable;ongoing_turnover_estimate_unavailable;legacy_oos_exposed_to_research_iteration;point_in_time_evidence_not_native_live |
| overall | INSUFFICIENT_EVIDENCE | 11.0000 | 4.0000 | 0.0000 | insufficient_independent_oos_periods;oos_independent_sign_test_not_significant;oos_uncertainty_interval_unavailable;legacy_oos_exposed_to_research_iteration;point_in_time_evidence_not_native_live |

`oos_observations` is the non-overlapping count used by governance. Promotion requires twelve genuinely prospective independent observations, a significant independent sign test, native point-in-time evidence, positive net active return, an estimable positive block-bootstrap lower confidence bound, and recurring annual turnover no greater than 1.5x. The legacy OOS record can never promote a model.

## Evidence Still Requiring New Data

No code change can make an inspected holdout untouched or turn reconstructed snapshots into native point-in-time facts. Deployment still requires future shadow outcomes, original filing/vintage timestamps, historical membership and inactive-security mappings, broader annual fundamentals and observed execution fills. These gaps remain explicit rather than being filled with current values or synthetic history.

## Failures

No observations were available.
