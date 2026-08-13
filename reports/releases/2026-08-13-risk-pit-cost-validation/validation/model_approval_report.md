# Wolf Quant Model Validation Report

## 1. Validation Overview

- Validation run: `validation-20260813T184133-dccaac94`
- As-of date: `2026-08-13T18:41:33.617250`
- Execution mode: `full`
- Overall score: **87.5 / 100**

## 2. Overall Approval Decision

**CONDITIONALLY_APPROVED**

## 3. Critical Failures

- None.


## 4. Model Component Approval Table

| component | maximum_score | score | status | approval_status | critical_failures | warnings | approved_version |
| --- | --- | --- | --- | --- | --- | --- | --- |
| data_integrity | 20.0 | 20.0 | PASS | APPROVED |  |  |  |
| point_in_time | 15.0 | 7.5 | WARNING | CONDITIONALLY_APPROVED |  |  |  |
| forecast_performance | 15.0 | 15.0 | PASS | APPROVED |  |  |  |
| distribution_calibration | 10.0 | 10.0 | PASS | APPROVED |  |  |  |
| risk_backtesting | 15.0 | 15.0 | PASS | APPROVED |  |  |  |
| portfolio_net_of_costs | 10.0 | 5.0 | WARNING | CONDITIONALLY_APPROVED |  |  |  |
| constraint_compliance | 10.0 | 10.0 | PASS | APPROVED |  |  |  |
| stability_sensitivity | 5.0 | 5.0 | PASS | APPROVED |  |  |  |

## 5. Data Integrity
| component | status | observation_count | commentary |
| --- | --- | --- | --- |
| data_integrity | PASS | 0 | Lineage, active-universe, metadata provenance, and final-selection checks. |

## 6. Point-in-Time and Leakage Validation
| check_name | status | failure_count | details | critical |
| --- | --- | --- | --- | --- |
| future_target_columns_absent | PASS | 0 |  | True |
| india_excluded_from_active_universe | PASS | 0 |  | True |

## 7. Forecast Accuracy
| horizon | observation_count | status | mae | rmse | normalised_rmse | directional_accuracy | rank_ic | commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3M | 45416 | PASS | 0.12602726732994196 | 0.1858670307066247 | 1.0407678669012472 | 0.5252994539369386 | 0.03550475951115762 | All configured point-forecast thresholds passed. |
| 6M | 45416 | PASS | 0.19048883777241352 | 0.28096478707082045 | 1.0752798376142396 | 0.5378280782103223 | 0.04562599760391821 | All configured point-forecast thresholds passed. |
| 9M | 45416 | PASS | 0.25644359941811296 | 0.37032886622028954 | 1.1025599825688097 | 0.5460630614761317 | 0.05221966585244459 | All configured point-forecast thresholds passed. |
| 12M | 44965 | PASS | 0.3188770726212102 | 0.46443125827971643 | 1.1240296333719608 | 0.5558100745023907 | 0.05890573578792653 | All configured point-forecast thresholds passed. |

## 8. Distribution Calibration
| horizon | observation_count | status | p5_coverage | p50_coverage | p95_coverage | interval_coverage | quantile_crossing_count | commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3M | 45416 | PASS | 0.006737713581116787 | 0.5189800951206623 | 0.9648361810815571 | 0.9580984675004404 | 0 | Quantile ordering and empirical coverage passed. |
| 6M | 45416 | PASS | 0.009908402325171746 | 0.5125726616170513 | 0.9518011273559979 | 0.9418927250308261 | 0 | Quantile ordering and empirical coverage passed. |
| 9M | 45416 | PASS | 0.01398185661440902 | 0.49856878633080853 | 0.9336137044213493 | 0.9196318478069403 | 0 | Quantile ordering and empirical coverage passed. |
| 12M | 44965 | PASS | 0.017724897142221727 | 0.48880240186811963 | 0.9160680529300567 | 0.898343155787835 | 0 | Quantile ordering and empirical coverage passed. |

## 9. Binary-Event Calibration
| event | observation_count | status | brier_score | expected_calibration_error | event_rate |
| --- | --- | --- | --- | --- | --- |
| realised_12m_drawdown_below_20pct | 44965 | WARNING | 0.14066850970655698 | 0.19557121285965845 | 0.11902590904036472 |

## 10. Risk Backtesting
| evaluation_segment | confidence_level | observations | violations | violation_rate | lr_statistic | p_value | christoffersen_lr | christoffersen_p_value | expected_violation_rate | violation_rate_error | realised_tail_mean | mean_expected_shortfall | expected_shortfall_gap | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| overall | 0.95 | 1158 | 50 | 0.04317789291882556 | 1.1871579779551098 | 0.2759035762699615 | 3.062789516894668 | 0.08010404153145778 | 0.050000000000000044 | 0.006822107081174485 | -0.012179767464574331 | -0.011967126887261866 | -0.00021264057731246525 | PASS |
| overall | 0.99 | 1158 | 15 | 0.012953367875647668 | 0.9333345728601046 | 0.3339979348430483 | 0.39405686530861317 | 0.5301746123640958 | 0.010000000000000009 | 0.0029533678756476587 | -0.018528279898825422 | -0.017680398478202426 | -0.0008478814206229965 | PASS |
| chronological_holdout | 0.95 | 463 | 15 | 0.032397408207343416 | 3.431750170905275 | 0.0639542929544874 | 2.9567910337241017 | 0.0855175071758496 | 0.050000000000000044 | 0.01760259179265663 | -0.011458302368975203 | -0.012561298135690487 | 0.001102995766715284 | PASS |
| chronological_holdout | 0.99 | 463 | 2 | 0.004319654427645789 | 1.9174226821776372 | 0.16614106089389313 | 0.01739135913724965 | 0.8950821328364661 | 0.010000000000000009 | 0.00568034557235422 | -0.02044258411556829 | -0.019802828635460026 | -0.0006397554801082644 | PASS |

## 11. Portfolio Performance
| date | as_of_date | strategy | gross_return | transaction_cost | net_return | turnover | valid_outcome_weight | holding_count | cash_weight | regime | evidence_mode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2021-08-31 00:00:00 | 2021-07-31 00:00:00 | wolf_cvar | 0.03247553235052013 | 0.004363837225033472 | 0.028111695125486655 | 1.0 | 1.0 | 20 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2021-09-30 00:00:00 | 2021-08-31 00:00:00 | wolf_cvar | -0.01955475454097112 | 0.0004816931482442617 | -0.02003644768921538 | 0.05999999999999968 | 1.0000000000000002 | 25 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2021-10-30 00:00:00 | 2021-09-30 00:00:00 | wolf_cvar | 0.01891741456328395 | 0.00041566532707912774 | 0.018501749236204824 | 0.06000000000000005 | 0.9999999999999998 | 27 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2021-11-30 00:00:00 | 2021-10-31 00:00:00 | wolf_cvar | -0.010799548502493938 | 0.00043270988145813747 | -0.011232258383952075 | 0.059999999999999956 | 1.0 | 26 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2021-12-30 00:00:00 | 2021-11-30 00:00:00 | wolf_cvar | 0.0611968267139366 | 0.0003839723752196292 | 0.06081285433871697 | 0.05999999999999999 | 1.0 | 29 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-01-31 00:00:00 | 2021-12-31 00:00:00 | wolf_cvar | -0.010249577620165314 | 0.000424034147710201 | -0.010673611767875514 | 0.05999999999999987 | 1.0 | 28 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-02-28 00:00:00 | 2022-01-31 00:00:00 | wolf_cvar | -0.007083027340427486 | 0.0003522723494658441 | -0.00743529968989333 | 0.059999999999999956 | 1.0 | 30 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-03-28 00:00:00 | 2022-02-28 00:00:00 | wolf_cvar | 0.00925284700947119 | 0.0003238238009495849 | 0.008929023208521604 | 0.06000000000000004 | 1.0 | 32 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-04-30 00:00:00 | 2022-03-31 00:00:00 | wolf_cvar | -0.005561062520672517 | 0.0003264070307952203 | -0.005887469551467737 | 0.060000000000000046 | 1.0 | 32 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-05-30 00:00:00 | 2022-04-30 00:00:00 | wolf_cvar | -0.013087195697601164 | 0.00037918245319144394 | -0.013466378150792607 | 0.05999999999999999 | 1.0 | 31 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-06-30 00:00:00 | 2022-05-31 00:00:00 | wolf_cvar | -0.031090603472070728 | 0.00032367584360627397 | -0.031414279315677 | 0.06000000000000005 | 1.0 | 32 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-07-30 00:00:00 | 2022-06-30 00:00:00 | wolf_cvar | 0.020826342715989744 | 0.0003297707522320744 | 0.02049657196375767 | 0.059999999999999984 | 1.0 | 34 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-08-31 00:00:00 | 2022-07-31 00:00:00 | wolf_cvar | -0.016917832336325697 | 0.00037853249028564243 | -0.01729636482661134 | 0.06000000000000005 | 0.9999999999999998 | 35 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-09-30 00:00:00 | 2022-08-31 00:00:00 | wolf_cvar | -0.04675678568686304 | 0.0003433534703502812 | -0.047100139157213325 | 0.060000000000000005 | 1.0 | 36 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-10-30 00:00:00 | 2022-09-30 00:00:00 | wolf_cvar | 0.017233502983029614 | 0.00032617152279916067 | 0.016907331460230452 | 0.06 | 1.0 | 36 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-11-30 00:00:00 | 2022-10-31 00:00:00 | wolf_cvar | 0.07404203249223289 | 0.0003495443806101777 | 0.07369248811162271 | 0.06000000000000006 | 0.9999999999999998 | 38 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2022-12-30 00:00:00 | 2022-11-30 00:00:00 | wolf_cvar | -0.008759932924009985 | 0.0006111367820806679 | -0.009371069706090652 | 0.05999999999999998 | 1.0 | 38 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2023-01-31 00:00:00 | 2022-12-31 00:00:00 | wolf_cvar | 0.024864089136015795 | 0.0003649059510799169 | 0.024499183184935876 | 0.060000000000000005 | 1.0 | 39 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2023-02-28 00:00:00 | 2023-01-31 00:00:00 | wolf_cvar | -0.006557515022357632 | 0.000378437855258402 | -0.006935952877616034 | 0.060000000000000046 | 1.0 | 39 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2023-03-28 00:00:00 | 2023-02-28 00:00:00 | wolf_cvar | 0.044517291208818165 | 0.00037574215870071477 | 0.04414154905011745 | 0.06000000000000003 | 1.0000000000000002 | 39 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2023-04-30 00:00:00 | 2023-03-31 00:00:00 | wolf_cvar | 0.046043181035138346 | 0.00046656603331113875 | 0.045576615001827206 | 0.05999999999999983 | 1.0 | 40 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2023-05-30 00:00:00 | 2023-04-30 00:00:00 | wolf_cvar | -0.021143317108670165 | 0.0021657658232492015 | -0.023309082931919366 | 0.26990028269742006 | 0.9999999999999999 | 36 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2023-06-30 00:00:00 | 2023-05-31 00:00:00 | wolf_cvar | 0.005913084524347406 | 0.00033307624215696936 | 0.005580008282190436 | 0.05999999999999999 | 1.0 | 44 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2023-07-30 00:00:00 | 2023-06-30 00:00:00 | wolf_cvar | 0.021373570540623416 | 0.00032712462948329945 | 0.021046445911140115 | 0.060000000000000005 | 1.0000000000000002 | 45 | 0.0 | steady | reconstructed_pit_proxy |
| 2023-08-31 00:00:00 | 2023-07-31 00:00:00 | wolf_cvar | -0.02825472822208112 | 0.00033224192467776507 | -0.028586970146758886 | 0.06000000000000006 | 0.9999999999999999 | 46 | 0.0 | steady | reconstructed_pit_proxy |
| 2023-09-30 00:00:00 | 2023-08-31 00:00:00 | wolf_cvar | -0.016725842178731187 | 0.0003197647156696962 | -0.017045606894400885 | 0.06000000000000001 | 1.0 | 48 | 0.0 | negative_momentum | reconstructed_pit_proxy |
| 2023-10-30 00:00:00 | 2023-09-30 00:00:00 | wolf_cvar | -0.03324006324286588 | 0.00031596252914813404 | -0.03355602577201401 | 0.06 | 1.0 | 49 | 0.0 | negative_momentum | reconstructed_pit_proxy |
| 2023-11-30 00:00:00 | 2023-10-31 00:00:00 | wolf_cvar | 0.02054111026576111 | 0.00032252585143820807 | 0.0202185844143229 | 0.05999999999999994 | 1.0 | 48 | 0.0 | negative_momentum | reconstructed_pit_proxy |
| 2023-12-30 00:00:00 | 2023-11-30 00:00:00 | wolf_cvar | 0.023478783000163064 | 0.0003185236536450415 | 0.02316025934651802 | 0.060000000000000046 | 1.0 | 50 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-01-31 00:00:00 | 2023-12-31 00:00:00 | wolf_cvar | 0.02279648349950053 | 0.0003163164245950438 | 0.022480167074905487 | 0.06000000000000001 | 1.0 | 52 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-02-29 00:00:00 | 2024-01-31 00:00:00 | wolf_cvar | 0.015320878185980605 | 0.0003228225621567938 | 0.014998055623823812 | 0.06 | 1.0 | 52 | 0.0 | negative_momentum | reconstructed_pit_proxy |
| 2024-03-29 00:00:00 | 2024-02-29 00:00:00 | wolf_cvar | 0.02172452544477968 | 0.0003159777765138528 | 0.021408547668265828 | 0.06 | 1.0 | 54 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-04-30 00:00:00 | 2024-03-31 00:00:00 | wolf_cvar | 0.002425142738575012 | 0.0003042442525908754 | 0.0021208984859841366 | 0.060000000000000005 | 1.0 | 55 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-05-30 00:00:00 | 2024-04-30 00:00:00 | wolf_cvar | 0.023204568435140738 | 0.001037398545349003 | 0.022167169889791734 | 0.14227375015628893 | 1.0 | 44 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-06-30 00:00:00 | 2024-05-31 00:00:00 | wolf_cvar | 0.018966442674003454 | 0.0003302373098259842 | 0.01863620536417747 | 0.05999999999999993 | 0.9999999999999999 | 50 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-07-30 00:00:00 | 2024-06-30 00:00:00 | wolf_cvar | 0.04298533253486595 | 0.0003241198050367376 | 0.042661212729829215 | 0.06000000000000002 | 1.0 | 50 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-08-31 00:00:00 | 2024-07-31 00:00:00 | wolf_cvar | 0.012742429482873227 | 0.0003266302465296135 | 0.012415799236343613 | 0.05999999999999999 | 1.0 | 50 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-09-30 00:00:00 | 2024-08-31 00:00:00 | wolf_cvar | 0.015545159423319183 | 0.00032249731256939223 | 0.015222662110749791 | 0.06000000000000001 | 1.0 | 53 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-10-30 00:00:00 | 2024-09-30 00:00:00 | wolf_cvar | -0.009470072054829628 | 0.0003296253984310026 | -0.00979969745326063 | 0.060000000000000046 | 0.9999999999999999 | 54 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-11-30 00:00:00 | 2024-10-31 00:00:00 | wolf_cvar | 0.02076788743433431 | 0.0003137346972687094 | 0.0204541527370656 | 0.06 | 1.0 | 56 | 0.0 | steady | reconstructed_pit_proxy |
| 2024-12-30 00:00:00 | 2024-11-30 00:00:00 | wolf_cvar | 0.002387037449547182 | 0.0003126872460358671 | 0.0020743502035113145 | 0.06000000000000001 | 1.0 | 56 | 0.0 | steady | reconstructed_pit_proxy |
| 2025-01-31 00:00:00 | 2024-12-31 00:00:00 | wolf_cvar | 0.031749258792477184 | 0.0003065297405039574 | 0.03144272905197323 | 0.059999999999999984 | 1.0 | 58 | 0.0 | steady | reconstructed_pit_proxy |
| 2025-02-28 00:00:00 | 2025-01-31 00:00:00 | wolf_cvar | 0.03608860691609004 | 0.0003028888306000824 | 0.035785718085489956 | 0.060000000000000026 | 1.0 | 58 | 0.0 | steady | reconstructed_pit_proxy |
| 2025-03-28 00:00:00 | 2025-02-28 00:00:00 | wolf_cvar | 0.023157764047569897 | 0.00032164905568181666 | 0.02283611499188808 | 0.05999999999999999 | 0.9999999999999998 | 59 | 0.0 | steady | reconstructed_pit_proxy |
| 2025-04-30 00:00:00 | 2025-03-31 00:00:00 | wolf_cvar | -0.021542616086232758 | 0.00033672307231141904 | -0.021879339158544175 | 0.060000000000000026 | 1.0 | 59 | 0.0 | steady | reconstructed_pit_proxy |
| 2025-05-30 00:00:00 | 2025-04-30 00:00:00 | wolf_cvar | 0.02370717537725372 | 0.0012611623124583998 | 0.02244601306479532 | 0.14299325440244465 | 1.0000000000000002 | 47 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2025-06-30 00:00:00 | 2025-05-31 00:00:00 | wolf_cvar | 0.005601871314775553 | 0.00033992586473192185 | 0.005261945450043631 | 0.05999999999999999 | 1.0 | 54 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2025-07-30 00:00:00 | 2025-06-30 00:00:00 | wolf_cvar | 0.01974747133738567 | 0.0004114198221398764 | 0.019336051515245794 | 0.05999999999999992 | 1.0000000000000002 | 54 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2025-08-31 00:00:00 | 2025-07-31 00:00:00 | wolf_cvar | 0.03410696963248193 | 0.0003458055289750637 | 0.033761164103506866 | 0.0599999999999999 | 1.0 | 54 | 0.0 | high_volatility | reconstructed_pit_proxy |
| 2025-09-30 00:00:00 | 2025-08-31 00:00:00 | wolf_cvar | -0.01268495930605115 | 0.00032736255670508816 | -0.013012321862756238 | 0.06 | 1.0 | 56 | 0.0 | steady | reconstructed_pit_proxy |
| 2025-10-30 00:00:00 | 2025-09-30 00:00:00 | wolf_cvar | 0.021523284380640804 | 0.0003270863215854842 | 0.02119619805905532 | 0.06 | 1.0 | 57 | 0.0 | steady | reconstructed_pit_proxy |
| 2025-11-30 00:00:00 | 2025-10-31 00:00:00 | wolf_cvar | 0.03029035689717029 | 0.0003171323146283286 | 0.029973224582541962 | 0.05999999999999991 | 1.0 | 58 | 0.0 | steady | reconstructed_pit_proxy |
| 2025-12-30 00:00:00 | 2025-11-30 00:00:00 | wolf_cvar | -0.0028961808707096736 | 0.0003136781283487739 | -0.0032098589990584474 | 0.059999999999999776 | 0.9999999999999999 | 59 | 0.0 | steady | reconstructed_pit_proxy |
| 2026-01-31 00:00:00 | 2025-12-31 00:00:00 | wolf_cvar | 0.027823231528429564 | 0.00031517183819428356 | 0.02750805969023528 | 0.06000000000000002 | 1.0 | 60 | 0.0 | steady | reconstructed_pit_proxy |
| 2026-02-28 00:00:00 | 2026-01-31 00:00:00 | wolf_cvar | 0.06716773259107872 | 0.0003237175365388772 | 0.06684401505453984 | 0.06 | 0.9999999999999998 | 61 | 0.0 | steady | reconstructed_pit_proxy |
| 2026-03-28 00:00:00 | 2026-02-28 00:00:00 | wolf_cvar | -0.00019503780354399839 | 0.00033127393207220515 | -0.0005263117356162036 | 0.06000000000000004 | 1.0 | 62 | 0.0 | steady | reconstructed_pit_proxy |
| 2026-04-30 00:00:00 | 2026-03-31 00:00:00 | wolf_cvar | 0.006010643693418855 | 0.0003485308540827985 | 0.005662112839336056 | 0.060000000000000005 | 1.0 | 63 | 0.0 | steady | reconstructed_pit_proxy |
| 2026-05-30 00:00:00 | 2026-04-30 00:00:00 | wolf_cvar | -0.014635965323846064 | 0.007859432952915626 | -0.02249539827676169 | 0.6281802484884454 | 1.0 | 20 | 0.0 | steady | reconstructed_pit_proxy |
| 2026-06-30 00:00:00 | 2026-05-31 00:00:00 | wolf_cvar | -0.03880691004594132 | 0.0004951115860495299 | -0.03930202163199085 | 0.060000000000000005 | 1.0 | 23 | 0.0 | steady | reconstructed_pit_proxy |
| 2026-07-30 00:00:00 | 2026-06-30 00:00:00 | wolf_cvar | 0.11716375296231606 | 0.0004181924867193356 | 0.11674556047559673 | 0.060000000000000026 | 1.0 | 25 | 0.0 | steady | reconstructed_pit_proxy |

## 12. Transaction-Cost Robustness
| strategy | cost_multiplier | gross_return | net_return | cost_drag | gross_alpha_consumed | status | evidence_mode |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cap_weight_eligible | 1.0 | 0.5525319816790627 | 0.518269429833124 | 0.03426255184593869 | 0.06201007902170636 | PASS | reconstructed_pit_proxy |
| equal_weight_eligible | 1.0 | 0.802995076209048 | 0.7735062083855666 | 0.029488867823481396 | 0.036723597313571076 | PASS | reconstructed_pit_proxy |
| wolf_cvar | 1.0 | 0.6876660874058781 | 0.6515405807448027 | 0.03612550666107543 | 0.052533500375674676 | PASS | reconstructed_pit_proxy |
| cap_weight_eligible | 1.5 | 0.5525319816790627 | 0.5011381539101547 | 0.05139382776890804 | 0.09301511853255955 | PASS | reconstructed_pit_proxy |
| equal_weight_eligible | 1.5 | 0.802995076209048 | 0.7587617744738259 | 0.044233301735222094 | 0.05508539597035662 | PASS | reconstructed_pit_proxy |
| wolf_cvar | 1.5 | 0.6876660874058781 | 0.633477827414265 | 0.05418825999161315 | 0.07880025056351202 | PASS | reconstructed_pit_proxy |
| cap_weight_eligible | 2.0 | 0.5525319816790627 | 0.48400687798718534 | 0.06852510369187738 | 0.12402015804341272 | PASS | reconstructed_pit_proxy |
| equal_weight_eligible | 2.0 | 0.802995076209048 | 0.7440173405620851 | 0.05897773564696279 | 0.07344719462714215 | PASS | reconstructed_pit_proxy |
| wolf_cvar | 2.0 | 0.6876660874058781 | 0.6154150740837272 | 0.07225101332215086 | 0.10506700075134935 | PASS | reconstructed_pit_proxy |

## 13. Benchmark Comparison
| strategy | observations | annualised_return | annualised_volatility | sharpe | sortino | maximum_drawdown | expected_shortfall | positive_period_ratio | worst_period | best_period | gross_annualised_return | annualised_cost_drag | annualised_turnover | total_transaction_cost | mean_net_return_ci_lower | mean_net_return_ci_upper | status | evidence_mode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| wolf_cvar | 60 | 0.1329058485879846 | 0.10072602558672467 | 1.3194787326692767 | 3.1604499464880527 | -0.10065585494552254 | 0.03998606218707273 | 0.6333333333333333 | -0.047100139157213325 | 0.11674556047559673 | 0.1410800545334594 | 0.0081742059454748 | 1.0966695071489194 | 0.03612550666107543 | 0.003884077258251091 | 0.015744366264377207 | WARNING | reconstructed_pit_proxy |
| equal_weight_eligible | 60 | 0.15721211312930472 | 0.12732525688534346 | 1.2347284189724776 | 2.6358144082518646 | -0.14854222167884545 | 0.056561750940990724 | 0.6 | -0.06640961532452215 | 0.12792604534158467 | 0.16398859545765632 | 0.006776482328351596 | 1.000997043184499 | 0.029488867823481396 | 0.003992091272851749 | 0.01938210179709912 |  | reconstructed_pit_proxy |
| cap_weight_eligible | 60 | 0.10220512786450131 | 0.11056547057217923 | 0.9243855910492406 | 1.9244212036816961 | -0.15048930912150604 | 0.05092959828263428 | 0.6166666666666667 | -0.06210439491568566 | 0.10318506096395301 | 0.10974792814046763 | 0.0075428002759663215 | 1.2159345637495307 | 0.03426255184593869 | 0.0010900618594399888 | 0.014100414368402103 |  | reconstructed_pit_proxy |

## 14. Regime Performance
| regime | status | observations | annualised_return | annualised_volatility | sharpe | sortino | maximum_drawdown | expected_shortfall | positive_period_ratio | worst_period | best_period |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high_volatility | EVALUATED | 27 | 0.09915025493072482 | 0.0984242024083095 | 1.0073767681591497 | 2.356255371604918 | -0.10065585494552254 | 0.03925720923644516 | 0.5555555555555556 | -0.047100139157213325 | 0.07369248811162271 |
| negative_momentum | INSUFFICIENT_DATA | 4 |  |  |  |  |  |  |  |  |  |
| steady | EVALUATED | 29 | 0.19357734860049614 | 0.10411673027258078 | 1.859233843530283 | 4.2433800711089065 | -0.06091330527905903 | 0.03394449588937487 | 0.7241379310344828 | -0.03930202163199085 | 0.11674556047559673 |

## 15. Regional Performance
| horizon | region | observation_count | status | mae | rmse | normalised_rmse | directional_accuracy | rank_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12M | DACH | 4483 | EVALUATED | 0.29979051761394115 | 0.40850679240274357 | 1.103448792815438 | 0.5708231095248717 | 0.09137652268172637 |
| 12M | EU ex-DACH | 5778 | EVALUATED | 0.2933304221956769 | 0.3821373721779847 | 1.1948359128136226 | 0.5623052959501558 | 0.0058587248734434825 |
| 12M | Hong Kong | 9202 | EVALUATED | 0.3759500525369352 | 0.5999393309391547 | 1.0613130496861032 | 0.5785698761138883 | 0.0949488615609304 |
| 12M | Mainland China | 10978 | EVALUATED | 0.32426332670172736 | 0.4703481854396798 | 1.127521395542131 | 0.5540171251594097 | 0.09952893190913988 |
| 12M | UK | 5267 | EVALUATED | 0.30137216064556765 | 0.43354880028298326 | 1.1583391157174987 | 0.5494588950066451 | 0.050196105050536656 |
| 12M | US | 9257 | EVALUATED | 0.29090430446215293 | 0.38557574656519494 | 1.2706387599049014 | 0.5276007345792373 | -0.005685807886082629 |
| 3M | DACH | 4659 | EVALUATED | 0.11168786668394998 | 0.14786760968978904 | 1.047645754493388 | 0.54045932603563 | 0.04356447283361916 |
| 3M | EU ex-DACH | 6018 | EVALUATED | 0.10690222144749462 | 0.13786708671211398 | 1.0865844489399692 | 0.5216018610834164 | -0.005049665260813541 |
| 3M | Hong Kong | 9236 | EVALUATED | 0.1563296905462977 | 0.23149750738854427 | 1.0206717316787859 | 0.5299913382416631 | 0.07240521725118497 |
| 3M | Mainland China | 10978 | EVALUATED | 0.1372936281063008 | 0.22499877629245363 | 1.0290935891154076 | 0.5335215886318091 | 0.07409062861828276 |
| 3M | UK | 5268 | EVALUATED | 0.11274613213888358 | 0.14947465447204963 | 1.0670774350251166 | 0.5176537585421412 | 0.020612492894704033 |
| 3M | US | 9257 | EVALUATED | 0.10964091370431923 | 0.1410956197923163 | 1.0960463177343753 | 0.5099924381549098 | -0.011590715780973156 |
| 6M | DACH | 4659 | EVALUATED | 0.17863846649325163 | 0.23718297044581077 | 1.0728550615179444 | 0.5526937110968019 | 0.063759679750797 |
| 6M | EU ex-DACH | 6018 | EVALUATED | 0.1706291484184057 | 0.22054217483841274 | 1.1424870827914926 | 0.5284147557328016 | -0.004659958965488458 |
| 6M | Hong Kong | 9236 | EVALUATED | 0.22969183578059624 | 0.3374408977382161 | 1.0446667202588544 | 0.5509961022087484 | 0.08838482701876096 |
| 6M | Mainland China | 10978 | EVALUATED | 0.19930589519230582 | 0.334859909286837 | 1.0514384620833797 | 0.5410821643286573 | 0.08913953112218576 |
| 6M | UK | 5268 | EVALUATED | 0.17644732512027847 | 0.2446502741385425 | 1.1098041182490417 | 0.5394836750189825 | 0.02795019630473039 |
| 6M | US | 9257 | EVALUATED | 0.16778435824495636 | 0.21613502268351376 | 1.183884647664919 | 0.5185265204709949 | -0.01221031168425007 |
| 9M | DACH | 4659 | EVALUATED | 0.23859656066525173 | 0.32069656079344894 | 1.0908727210757883 | 0.5634256278171281 | 0.08236307871223353 |
| 9M | EU ex-DACH | 6018 | EVALUATED | 0.2307799434689901 | 0.2987746935643626 | 1.1756246732724172 | 0.5451977401129944 | 0.0003771372617068368 |
| 9M | Hong Kong | 9236 | EVALUATED | 0.3042625203120965 | 0.4604556370279188 | 1.055203786512346 | 0.5661541792983976 | 0.08830994538132848 |
| 9M | Mainland China | 10978 | EVALUATED | 0.26638186266061764 | 0.4049168722842609 | 1.0868265570241653 | 0.5468209145563855 | 0.09330179245903435 |
| 9M | UK | 5268 | EVALUATED | 0.24241172269193248 | 0.3438029859763528 | 1.1330989212277418 | 0.5400531511009871 | 0.03658495545409797 |
| 9M | US | 9257 | EVALUATED | 0.23059887157884199 | 0.29967459243928235 | 1.2313238752481162 | 0.5203629685643297 | -0.010553912773777754 |

## 16. Constraint Compliance
| constraint_name | constraint_type | limit | actual_value | breach_flag | severity | affected_stocks | commentary | portfolio | as_of_date | strategy | limit_value | check_name | status | breach_count | critical |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fully_invested | hard | 1.0 | 1.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| recommendation_eligibility | hard | no Avoid or Exclude | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| unique_issuer | hard | one listing per issuer | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| price_data_quality | hard | no quarantined price histories | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| single_name_concentration | hard | 0.05 | 0.05 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| cash_weight | hard | 0.25 | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| sector_concentration | hard | 0.25 | 0.25 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| country_concentration | hard | 0.3 | 0.3 | False | OK | China |  | classical |  |  |  |  |  |  |  |
| region_concentration | hard | 0.4 | 0.3 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| currency_concentration | hard | 0.4 | 0.35 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| liquidity | hard | 40 | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| turnover | soft | 0.35 | 0.6941023094114727 | True | High |  |  | classical |  |  |  |  |  |  |  |
| portfolio_dividend_yield | soft | 0.03 | 0.046155 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| portfolio_volatility | soft | 0.2 | 0.115456098997563 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| portfolio_var_5 | soft | -0.15 | -0.0037564494781304 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| portfolio_cvar_5 | soft | -0.25 | -0.0707964355986662 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| portfolio_expected_shortfall_5 | soft | -0.25 | -0.0707964355986662 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| dividend_cut_risk | soft | 0.35 | 0.2723955310387996 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| drawdown_risk | soft | 0.35 | 0.2907713086281331 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| HHI | soft | 0.15 | 0.05 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| effective_holdings | soft | 15 | 20.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| regime_risk | soft | no reviewed names preferred | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| narrative_risk | soft | no reviewed names preferred | 20.0 | True | High | 000333.SHE, HIG.US, 600036.SHG, AD.AS, 3988.HK, 0728.HK, ALV.XETRA, IMB.LSE, 1113.HK, SHELL.AS, CA.PA, ORA.PA, HEN3.XETRA, 601816.SHG, NOVN.SW, 601818.SHG, 000538.SHE, ESSITY-B.ST, ELE.MC, 600018.SHG |  | classical |  |  |  |  |  |  |  |
| alt_data_risk | soft | no reviewed names preferred | 2.0 | True | High | 3988.HK, ORA.PA |  | classical |  |  |  |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2021-07-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2021-07-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2021-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2021-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2021-07-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2021-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2021-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2021-08-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2021-08-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2021-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2021-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2021-08-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2021-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2021-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999998 | False |  |  |  | walk_forward | 2021-09-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2021-09-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2021-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2021-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.29860606060606054 | False |  |  |  | walk_forward | 2021-09-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.29860606060606054 | False |  |  |  | walk_forward | 2021-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.29860606060606054 | False |  |  |  | walk_forward | 2021-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2021-10-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2021-10-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2021-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2021-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2021-10-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2021-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2021-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2021-11-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2021-11-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2021-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2021-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2877522268678422 | False |  |  |  | walk_forward | 2021-11-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2877522268678422 | False |  |  |  | walk_forward | 2021-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.2877522268678422 | False |  |  |  | walk_forward | 2021-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2021-12-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2021-12-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2021-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2021-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2021-12-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2021-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2021-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-01-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.04999999999999999 | False |  |  |  | walk_forward | 2022-01-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999994 | False |  |  |  | walk_forward | 2022-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.29999999999999993 | False |  |  |  | walk_forward | 2022-01-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.29999999999999993 | False |  |  |  | walk_forward | 2022-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.29999999999999993 | False |  |  |  | walk_forward | 2022-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-02-28 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2022-02-28 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2022-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2022-02-28 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2022-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2022-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-03-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2022-03-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2022-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2022-03-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2022-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2022-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-04-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2022-04-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2022-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.29398447289594487 | False |  |  |  | walk_forward | 2022-04-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.29398447289594487 | False |  |  |  | walk_forward | 2022-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.29398447289594487 | False |  |  |  | walk_forward | 2022-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-05-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2022-05-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2022-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.29557473468300927 | False |  |  |  | walk_forward | 2022-05-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.29557473468300927 | False |  |  |  | walk_forward | 2022-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.29557473468300927 | False |  |  |  | walk_forward | 2022-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-06-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2022-06-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2022-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2965982100327828 | False |  |  |  | walk_forward | 2022-06-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2965982100327828 | False |  |  |  | walk_forward | 2022-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.2965982100327828 | False |  |  |  | walk_forward | 2022-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999998 | False |  |  |  | walk_forward | 2022-07-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.04999999999999999 | False |  |  |  | walk_forward | 2022-07-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2022-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.29806736505829967 | False |  |  |  | walk_forward | 2022-07-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.29806736505829967 | False |  |  |  | walk_forward | 2022-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.29806736505829967 | False |  |  |  | walk_forward | 2022-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-08-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2022-08-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2022-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2986300133252102 | False |  |  |  | walk_forward | 2022-08-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2986300133252102 | False |  |  |  | walk_forward | 2022-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.2986300133252102 | False |  |  |  | walk_forward | 2022-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-09-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2022-09-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2022-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2022-09-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2022-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2022-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999998 | False |  |  |  | walk_forward | 2022-10-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.04999999999999999 | False |  |  |  | walk_forward | 2022-10-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2022-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.29999999999999993 | False |  |  |  | walk_forward | 2022-10-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.29999999999999993 | False |  |  |  | walk_forward | 2022-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.29999999999999993 | False |  |  |  | walk_forward | 2022-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-11-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2022-11-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2022-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2840879553898749 | False |  |  |  | walk_forward | 2022-11-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2840879553898749 | False |  |  |  | walk_forward | 2022-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.2840879553898749 | False |  |  |  | walk_forward | 2022-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2022-12-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2022-12-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2022-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2022-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2894380917715671 | False |  |  |  | walk_forward | 2022-12-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2894380917715671 | False |  |  |  | walk_forward | 2022-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.2894380917715671 | False |  |  |  | walk_forward | 2022-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2023-01-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2023-01-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2023-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2924893343011733 | False |  |  |  | walk_forward | 2023-01-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2924893343011733 | False |  |  |  | walk_forward | 2023-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.2924893343011733 | False |  |  |  | walk_forward | 2023-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2023-02-28 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2023-02-28 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2023-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.29589134542599327 | False |  |  |  | walk_forward | 2023-02-28 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.29589134542599327 | False |  |  |  | walk_forward | 2023-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.29589134542599327 | False |  |  |  | walk_forward | 2023-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2023-03-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2023-03-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2023-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2750748048901239 | False |  |  |  | walk_forward | 2023-03-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2750748048901239 | False |  |  |  | walk_forward | 2023-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.2750748048901239 | False |  |  |  | walk_forward | 2023-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999999 | False |  |  |  | walk_forward | 2023-04-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2023-04-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2023-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.23443772284860792 | False |  |  |  | walk_forward | 2023-04-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.23443772284860792 | False |  |  |  | walk_forward | 2023-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.23443772284860792 | False |  |  |  | walk_forward | 2023-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2023-05-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2023-05-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2023-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.24207037202682347 | False |  |  |  | walk_forward | 2023-05-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.24207037202682347 | False |  |  |  | walk_forward | 2023-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.24207037202682347 | False |  |  |  | walk_forward | 2023-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2023-06-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2023-06-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2023-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.24980268780799392 | False |  |  |  | walk_forward | 2023-06-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.24980268780799392 | False |  |  |  | walk_forward | 2023-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.24980268780799392 | False |  |  |  | walk_forward | 2023-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999999 | False |  |  |  | walk_forward | 2023-07-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2023-07-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2023-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2571247827754647 | False |  |  |  | walk_forward | 2023-07-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2571247827754647 | False |  |  |  | walk_forward | 2023-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.2571247827754647 | False |  |  |  | walk_forward | 2023-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2023-08-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2023-08-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2023-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.26284150077197865 | False |  |  |  | walk_forward | 2023-08-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.26284150077197865 | False |  |  |  | walk_forward | 2023-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.26284150077197865 | False |  |  |  | walk_forward | 2023-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2023-09-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2023-09-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2023-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.26837397847274125 | False |  |  |  | walk_forward | 2023-09-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.26837397847274125 | False |  |  |  | walk_forward | 2023-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.26837397847274125 | False |  |  |  | walk_forward | 2023-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2023-10-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2023-10-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2023-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.27297186782627825 | False |  |  |  | walk_forward | 2023-10-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.27297186782627825 | False |  |  |  | walk_forward | 2023-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.27297186782627825 | False |  |  |  | walk_forward | 2023-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2023-11-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.050000000000000024 | False |  |  |  | walk_forward | 2023-11-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2023-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.27716611765377136 | False |  |  |  | walk_forward | 2023-11-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.27716611765377136 | False |  |  |  | walk_forward | 2023-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.27716611765377136 | False |  |  |  | walk_forward | 2023-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2023-12-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2023-12-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2023-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2023-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.28027714706906237 | False |  |  |  | walk_forward | 2023-12-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.28027714706906237 | False |  |  |  | walk_forward | 2023-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.28027714706906237 | False |  |  |  | walk_forward | 2023-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-01-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2024-01-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2024-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.28340391643347385 | False |  |  |  | walk_forward | 2024-01-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.28340391643347385 | False |  |  |  | walk_forward | 2024-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.28340391643347385 | False |  |  |  | walk_forward | 2024-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-02-29 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2024-02-29 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-02-29 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2024-02-29 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.28597008584730055 | False |  |  |  | walk_forward | 2024-02-29 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.28597008584730055 | False |  |  |  | walk_forward | 2024-02-29 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.28597008584730055 | False |  |  |  | walk_forward | 2024-02-29 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-03-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2024-03-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2024-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.28076199587000716 | False |  |  |  | walk_forward | 2024-03-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.28076199587000716 | False |  |  |  | walk_forward | 2024-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.28076199587000716 | False |  |  |  | walk_forward | 2024-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-04-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2024-04-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2445263951361692 | False |  |  |  | walk_forward | 2024-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2422348709819364 | False |  |  |  | walk_forward | 2024-04-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2422348709819364 | False |  |  |  | walk_forward | 2024-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.32500721974924685 | False |  |  |  | walk_forward | 2024-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999999 | False |  |  |  | walk_forward | 2024-05-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2024-05-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24526171481255482 | False |  |  |  | walk_forward | 2024-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.249994991968494 | False |  |  |  | walk_forward | 2024-05-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.249994991968494 | False |  |  |  | walk_forward | 2024-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.32164776995504823 | False |  |  |  | walk_forward | 2024-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24597369872318686 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2575088413382598 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2575088413382598 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3183949341084648 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24669885785236345 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2651617340292014 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2651617340292014 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3240871812811888 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24722713176592012 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.27073681873711 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.27073681873711 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.336235328813222 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999999 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.04999999999999999 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24756915907829816 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.24969278848783594 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.24969278848783594 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3441005633896944 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24786527714666462 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.23145764237865785 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.24587006706922954 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3509100724135209 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24818578141705253 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.21922770714500273 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2539970586517758 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.35828036472098346 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24119072498444802 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2019196026527056 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.26067523551916894 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3643367405758974 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2255023304302862 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2013947584428649 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2588386747635451 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3704722251334352 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999998 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.04999999999999999 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2210779939370812 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.20982716208417632 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2573052748487874 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.37559492606707745 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2267900361441124 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.207886315917488 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2657374033654188 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.38041488261045503 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.22597353852439525 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2554139466098755 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.4 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.20949933748154984 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.24816718266466956 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3934612454187531 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24403016387404503 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.19642547546824002 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2483860150474842 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.39424195128511075 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2449415150744689 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.181705226710093 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2485699826343521 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3874255822371033 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.23740576607841424 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.18149140849093073 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2488097665381583 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.38115009745865996 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.22797510564660103 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.19340378343840448 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2490167260881968 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3670395988093975 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.23120644300865598 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2090428294970306 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.24182533729726904 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3498683732677705 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999999 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.23410100538854606 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.22304212664609394 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.24308438959580483 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.34219752617032373 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.050000000000000024 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2364747768055766 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2345321865239273 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2345321865239273 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.32096697471442315 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999998 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.23052676610675837 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2452081464361584 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2452081464361584 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.31754785057315693 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.050000000000000024 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.22532144705001714 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2545510646644637 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2545510646644637 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3145556515084457 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.22986695183966116 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.26292223430599837 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.26292223430599837 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3026652451412266 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.049999999999999996 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_cash_weight | hard |  | 0.0 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999997 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
|  |  |  |  |  |  |  |  | selected_classical |  |  |  | finite_weights | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | selected_classical |  |  |  | weights_sum_to_one | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | selected_classical |  |  |  | long_only | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | selected_classical |  |  |  | single_name_cap | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | drl |  |  |  | finite_weights | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | drl |  |  |  | weights_sum_to_one | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | drl |  |  |  | long_only | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | drl |  |  |  | single_name_cap | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | final_portfolio |  |  |  | finite_weights | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | final_portfolio |  |  |  | weights_sum_to_one | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | final_portfolio |  |  |  | long_only | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | final_portfolio |  |  |  | single_name_cap | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | current_portfolio |  |  |  | finite_weights | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | current_portfolio |  |  |  | weights_sum_to_one | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | current_portfolio |  |  |  | long_only | PASS | 0.0 | True |
|  |  |  |  |  |  |  |  | current_portfolio |  |  |  | single_name_cap | PASS | 0.0 | True |

## 17. DRL Governance
| component | status | observation_count | commentary |
| --- | --- | --- | --- |
| drl_governance | WARNING | 11 | DRL remains a challenger and cannot be promoted without realised out-of-sample comparison. |

## 18. Sensitivity Analysis
| parameter | relative_change | scale | observation_count | status | mae | rmse | normalised_rmse | directional_accuracy | rank_ic | normalised_rmse_change | validation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| expected_return_scale | -0.19999999999999996 | 0.8 | 44965 | EVALUATED | 0.3002516968206425 | 0.45012583321681277 | 1.0894072400639694 | 0.5558100745023907 | 0.05890573578792653 | -0.03462239330799144 | PASS |
| expected_return_scale | -0.09999999999999998 | 0.9 | 44965 | EVALUATED | 0.30899241797919064 | 0.4566894677415584 | 1.1052927335076383 | 0.5558100745023907 | 0.05890573578792653 | -0.018736899864322476 | PASS |
| expected_return_scale | 0.10000000000000009 | 1.1 | 44965 | EVALUATED | 0.3298323009688276 | 0.4732933940937358 | 1.145478024479015 | 0.5558100745023907 | 0.05890573578792653 | 0.02144839110705421 | PASS |
| expected_return_scale | 0.19999999999999996 | 1.2 | 44965 | EVALUATED | 0.34180660581384936 | 0.48321423781023937 | 1.1694887303189003 | 0.5558100745023907 | 0.05890573578792653 | 0.0454590969469395 | PASS |

## 19. Ablation Analysis
| ablation | net_return | sharpe | cvar | drawdown | turnover | dividend_yield | worst_scenario_loss | seed_dispersion | feature_value_added | status | validation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| without_regime_features | 0.3827942562741496 | 2.126634757078609 | -0.2 | -0.1 | 0.1 | 0.03 | -0.18 | 0.01 | -0.0026 | deterministic_proxy | PROXY_ONLY |
| with_regime_features | 0.3849942562741495 | 2.1153530564513714 | -0.205 | -0.104 | 0.11 | 0.031 | -0.19 | 0.012 | -0.0003999999999999 | mvp_run | PROXY_ONLY |
| without_distributional_features | 0.3831942562741496 | 2.082577479750813 | -0.21 | -0.108 | 0.12 | 0.032 | -0.1999999999999999 | 0.014 | -0.0022 | deterministic_proxy | PROXY_ONLY |
| with_distributional_features | 0.3853942562741496 | 2.1410792015230533 | -0.215 | -0.112 | 0.13 | 0.03 | -0.21 | 0.016 | 0.0 | mvp_run | PROXY_ONLY |
| without_sentiment_narrative | 0.3835942562741495 | 2.107660748759064 | -0.2 | -0.116 | 0.1 | 0.031 | -0.18 | 0.018 | -0.0018 | deterministic_proxy | PROXY_ONLY |
| with_sentiment_narrative | 0.3857942562741496 | 2.0967079145334218 | -0.205 | -0.1 | 0.11 | 0.032 | -0.19 | 0.01 | 0.0003999999999999 | mvp_run | PROXY_ONLY |
| differential_sharpe_reward_only | 0.3839942562741495 | 2.133301423745276 | -0.21 | -0.104 | 0.12 | 0.03 | -0.1999999999999999 | 0.012 | -0.0014 | deterministic_proxy | PROXY_ONLY |
| full_conservative_reward | 0.3861942562741496 | 2.121946463044778 | -0.215 | -0.108 | 0.13 | 0.031 | -0.21 | 0.014 | 0.0008 | mvp_run | PROXY_ONLY |
| no_transaction_costs | 0.3843942562741496 | 2.089099218881248 | -0.2 | -0.112 | 0.1 | 0.032 | -0.18 | 0.016 | -0.001 | deterministic_proxy | PROXY_ONLY |
| realistic_transaction_costs | 0.3865942562741495 | 2.14774586818972 | -0.205 | -0.116 | 0.11 | 0.03 | -0.19 | 0.018 | 0.0012 | mvp_run | PROXY_ONLY |
| universal_agent | 0.3847942562741496 | 2.1142541553524703 | -0.21 | -0.1 | 0.12 | 0.031 | -0.1999999999999999 | 0.01 | -0.0006 | deterministic_proxy | PROXY_ONLY |
| regime_specialist_blend | 0.3869942562741496 | 2.1032296536638566 | -0.215 | -0.104 | 0.13 | 0.032 | -0.21 | 0.012 | 0.0016 | mvp_run | PROXY_ONLY |
| mlp_encoder | 0.3851942562741496 | 2.1399680904119425 | -0.2 | -0.108 | 0.1 | 0.03 | -0.18 | 0.014 | -0.0001999999999999 | deterministic_proxy | PROXY_ONLY |
| tcn_gap_encoder_when_available | 0.3873942562741496 | 2.1285398696381845 | -0.205 | -0.112 | 0.11 | 0.031 | -0.19 | 0.016 | 0.002 | mvp_run | PROXY_ONLY |
| no_risk_throttle | 0.3855942562741495 | 2.0956209580116822 | -0.21 | -0.116 | 0.12 | 0.032 | -0.1999999999999999 | 0.018 | 0.0002 | deterministic_proxy | PROXY_ONLY |
| wolf_chaos_risk_throttle | 0.3877942562741496 | 2.1544125348563865 | -0.215 | -0.1 | 0.13 | 0.03 | -0.21 | 0.01 | 0.0024 | mvp_run | PROXY_ONLY |

## 20. Stability and Concentration Tests
| excluded_dimension | excluded_group | observation_count | status | mae | rmse | normalised_rmse | directional_accuracy | rank_ic | rank_ic_change | validation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | none | 44965 | EVALUATED | 0.3188770726212102 | 0.46443125827971643 | 1.1240296333719608 | 0.5558100745023907 | 0.05890573578792653 | 0.0 | PASS |
| region | DACH | 40482 | EVALUATED | 0.3209907287176873 | 0.4702154749840403 | 1.1258046601005411 | 0.5541475223556148 | 0.05592459064296979 | -0.0029811451449567386 | PASS |
| region | EU ex-DACH | 39187 | EVALUATED | 0.32264384594294265 | 0.47536158465882944 | 1.1179362861881215 | 0.5548523745119555 | 0.06544062995668518 | 0.006534894168758645 | PASS |
| region | Hong Kong | 35763 | EVALUATED | 0.3041919074733058 | 0.42259328041706257 | 1.1644201978601425 | 0.5499538629309622 | 0.04693194669841766 | -0.011973789089508871 | PASS |
| region | Mainland China | 33987 | EVALUATED | 0.31713728101571637 | 0.46250388237851264 | 1.123519483745253 | 0.5563892076382146 | 0.04400073981002691 | -0.01490499597789962 | PASS |
| region | UK | 39698 | EVALUATED | 0.32119956673617084 | 0.4683756631184186 | 1.1207218316480991 | 0.5566527280971334 | 0.060267383121195624 | 0.0013616473332690934 | PASS |
| region | US | 35708 | EVALUATED | 0.32612877853720634 | 0.48277611096092976 | 1.1043500691303798 | 0.5631231096673014 | 0.07962664205237119 | 0.020720906264444658 | PASS |
| forecast_year | 2021 | 40987 | EVALUATED | 0.31907083213758153 | 0.467691801525363 | 1.1321616494918563 | 0.5645692536657965 | 0.05853656984107356 | -0.0003691659468529687 | PASS |
| forecast_year | 2022 | 37132 | EVALUATED | 0.3301654014679266 | 0.48605117661109126 | 1.1181294703158318 | 0.5572282667241194 | 0.055216416783863506 | -0.003689319004063024 | PASS |
| forecast_year | 2023 | 35114 | EVALUATED | 0.3308998227188364 | 0.4902009178522797 | 1.1176730447434295 | 0.5462208805604603 | 0.045435974848490185 | -0.013469760939436345 | PASS |
| forecast_year | 2024 | 30454 | EVALUATED | 0.3081424448098877 | 0.4372262471121529 | 1.1187848354718308 | 0.5575950614040849 | 0.07756573096863884 | 0.018659995180712305 | PASS |
| forecast_year | 2025 | 36173 | EVALUATED | 0.3044366242316427 | 0.43350853424447355 | 1.1412144354208815 | 0.552235092472286 | 0.059821972421168844 | 0.0009162366332423136 | PASS |

## 21. Statistical Confidence
| strategy | baseline | observations | mean_difference | t_statistic | p_value | difference_ci_lower | difference_ci_upper | bootstrap_block_size | bootstrap_significant | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| wolf_cvar | equal_weight_eligible | 60 | -0.0020327604606794 | -0.6011923060196006 | 0.5500148371891631 | -0.0064776861297677546 | 0.0033225708752743213 | 6 | False | WARNING |

## 22. Known Limitations
- Historical filing availability is reconstructed from fiscal period end plus a conservative reporting lag when an observed filing date is unavailable.
- Early anchors include only regions and securities for which usable historical filings were available; region counts are reported for every anchor.
- When represented countries cannot support full equity investment under hard concentration caps, the reconstruction holds up to 25% in zero-return cash rather than relaxing those caps.
- The current active universe and current sector metadata introduce survivorship and reference-data bias.
- Historical sentiment, narrative, and regime vintages are unavailable and are held neutral in this reconstruction.
- Stored candidate price bars have zero volume, so observed current 3-month ADV is used as a static liquidity proxy.
- Adjusted-close outcomes may include provider-side retrospective corporate-action adjustments.
- This evidence can support conditional model use but cannot support full production approval.


## 23. Required Remediation
- Replace reconstructed filing lags with exchange or regulator filing timestamps.
- Add delisted constituents and historical security metadata to remove survivorship bias.
- Repair and repopulate historical volume, then remove the static ADV proxy.
- Archive immutable sentiment, narrative, and regime vintages for future walk-forward runs.
- Continue storing live forecast vintages until native out-of-sample evidence supersedes this proxy.


## 24. Final Production Recommendation

Do not deploy to production until all critical failures are remediated and historical point-in-time validation is complete.

Attributions, where reported, are model attributions and are not causal claims.
