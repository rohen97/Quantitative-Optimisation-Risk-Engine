# Wolf Quant Model Validation Report

## 1. Validation Overview

- Validation run: `validation-20260812T083559-1d80b816`
- As-of date: `2026-08-12T08:35:59.762589`
- Execution mode: `release_candidate`
- Overall score: **82.5 / 100**

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
| distribution_calibration | 10.0 | 5.0 | WARNING | CONDITIONALLY_APPROVED |  |  |  |
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
| 3M | 18381 | PASS | 0.1284669556244883 | 0.19311614929033094 | 1.0528832071604406 | 0.5418094771775203 | 0.025392432075380594 | All configured point-forecast thresholds passed. |
| 6M | 18381 | PASS | 0.20172665531712097 | 0.298519457142681 | 1.0904262705589942 | 0.5562809422773516 | 0.03275197789714274 | All configured point-forecast thresholds passed. |
| 9M | 18381 | PASS | 0.2862036210778742 | 0.42918559609564916 | 1.1038617250058114 | 0.5615037266742833 | 0.03523317645724921 | All configured point-forecast thresholds passed. |
| 12M | 17929 | PASS | 0.3672414852466898 | 0.5643473933702037 | 1.1144945518320226 | 0.5717552568464499 | 0.038641174537828164 | All configured point-forecast thresholds passed. |

## 8. Distribution Calibration
| horizon | observation_count | status | p5_coverage | p50_coverage | p95_coverage | interval_coverage | quantile_crossing_count | commentary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3M | 18381 | PASS | 0.007072520537511561 | 0.4815842446004026 | 0.9527773244110767 | 0.9457048038735651 | 0 | Quantile ordering and empirical coverage passed. |
| 6M | 18381 | PASS | 0.007398944562319786 | 0.4716283118437517 | 0.9315053587944073 | 0.9241064142320875 | 0 | Quantile ordering and empirical coverage passed. |
| 9M | 18381 | WARNING | 0.011968880909634948 | 0.4565039986943039 | 0.8994069963549317 | 0.8874381154452968 | 0 | Quantiles are ordered, with moderate empirical coverage error. |
| 12M | 17929 | WARNING | 0.01623068771264432 | 0.448658597802443 | 0.8721066428690948 | 0.8558759551564504 | 0 | Quantiles are ordered, with moderate empirical coverage error. |

## 9. Binary-Event Calibration
| event | observation_count | status | brier_score | expected_calibration_error | event_rate |
| --- | --- | --- | --- | --- | --- |
| realised_12m_drawdown_below_20pct | 17929 | WARNING | 0.130768857015211 | 0.21482736917284684 | 0.09091416141446818 |

## 10. Risk Backtesting
| confidence_level | observations | violations | violation_rate | lr_statistic | p_value | christoffersen_lr | christoffersen_p_value | expected_violation_rate | violation_rate_error | realised_tail_mean | mean_expected_shortfall | expected_shortfall_gap | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.95 | 487 | 19 | 0.039014373716632446 | 1.3341002465986378 | 0.24807708754244154 | 0.0876864501985608 | 0.7671392198590687 | 0.050000000000000044 | 0.010985626283367599 | -0.012204699380711892 | -0.010542984497734572 | -0.0016617148829773196 | PASS |
| 0.99 | 487 | 9 | 0.018480492813141684 | 2.8298311951744495 | 0.09252808471914348 | 2.0807591685858 | 0.14916597214294428 | 0.010000000000000009 | 0.008480492813141675 | -0.0233554235686159 | -0.01362250338776081 | -0.00973292018085509 | PASS |

## 11. Portfolio Performance
| date | as_of_date | strategy | gross_return | transaction_cost | net_return | turnover | valid_outcome_weight | holding_count | regime | evidence_mode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-07-30 00:00:00 | 2024-06-30 00:00:00 | wolf_cvar | 0.03458314439921517 | 0.004730501702422372 | 0.0298526426967928 | 1.0 | 1.0000000000000002 | 20 | steady | reconstructed_pit_proxy |
| 2024-08-31 00:00:00 | 2024-07-31 00:00:00 | wolf_cvar | 0.004338504724005188 | 0.0009731995279756852 | 0.0033653051960295033 | 0.10000000000000009 | 1.0 | 23 | steady | reconstructed_pit_proxy |
| 2024-09-30 00:00:00 | 2024-08-31 00:00:00 | wolf_cvar | 0.02467601931846424 | 0.00074533124615244 | 0.0239306880723118 | 0.10000000000000005 | 1.0000000000000002 | 26 | steady | reconstructed_pit_proxy |
| 2024-10-30 00:00:00 | 2024-09-30 00:00:00 | wolf_cvar | -0.011005718144086732 | 0.0006076696824124154 | -0.011613387826499146 | 0.10000000000000002 | 1.0000000000000002 | 30 | steady | reconstructed_pit_proxy |
| 2024-11-30 00:00:00 | 2024-10-31 00:00:00 | wolf_cvar | 0.018090719660297353 | 0.000593658488163524 | 0.01749706117213383 | 0.09999999999999999 | 1.0 | 33 | steady | reconstructed_pit_proxy |
| 2024-12-30 00:00:00 | 2024-11-30 00:00:00 | wolf_cvar | -0.0073608242542797945 | 0.0005699941691877458 | -0.00793081842346754 | 0.1 | 1.0 | 34 | steady | reconstructed_pit_proxy |
| 2025-01-31 00:00:00 | 2024-12-31 00:00:00 | wolf_cvar | 0.03513158400418257 | 0.0006173557904803717 | 0.0345142282137022 | 0.1 | 1.0 | 34 | steady | reconstructed_pit_proxy |
| 2025-02-28 00:00:00 | 2025-01-31 00:00:00 | wolf_cvar | 0.046440194135057775 | 0.0007366909423464525 | 0.045703503192711326 | 0.1 | 1.0000000000000002 | 35 | steady | reconstructed_pit_proxy |
| 2025-03-28 00:00:00 | 2025-02-28 00:00:00 | wolf_cvar | 0.029643726523751135 | 0.0008243413661402877 | 0.028819385157610847 | 0.10000000000000002 | 1.0 | 36 | steady | reconstructed_pit_proxy |
| 2025-04-30 00:00:00 | 2025-03-31 00:00:00 | wolf_cvar | -0.025156040862517857 | 0.000788049607561529 | -0.025944090470079385 | 0.09999999999999998 | 1.0 | 36 | steady | reconstructed_pit_proxy |
| 2025-05-30 00:00:00 | 2025-04-30 00:00:00 | wolf_cvar | 0.019112870902799145 | 0.005329853375660173 | 0.013783017527138973 | 0.5196691591925839 | 1.0000000000000002 | 20 | high_volatility | reconstructed_pit_proxy |
| 2025-06-30 00:00:00 | 2025-05-31 00:00:00 | wolf_cvar | 0.004375805285416307 | 0.0005738918296220721 | 0.003801913455794235 | 0.05 | 1.0000000000000002 | 20 | high_volatility | reconstructed_pit_proxy |
| 2025-07-30 00:00:00 | 2025-06-30 00:00:00 | wolf_cvar | 0.0161120196028404 | 0.0013494175969883354 | 0.014762602005852065 | 0.1 | 1.0000000000000002 | 20 | high_volatility | reconstructed_pit_proxy |
| 2025-08-31 00:00:00 | 2025-07-31 00:00:00 | wolf_cvar | 0.02913934494341859 | 0.000925945301714362 | 0.028213399641704228 | 0.09999999999999999 | 1.0000000000000002 | 20 | high_volatility | reconstructed_pit_proxy |
| 2025-09-30 00:00:00 | 2025-08-31 00:00:00 | wolf_cvar | -0.012257909357987604 | 0.0005557982919395319 | -0.012813707649927135 | 0.049999999999999996 | 1.0000000000000002 | 20 | steady | reconstructed_pit_proxy |
| 2025-10-30 00:00:00 | 2025-09-30 00:00:00 | wolf_cvar | 0.022704436593705354 | 0.0010865003720677959 | 0.021617936221637556 | 0.1 | 1.0000000000000002 | 20 | steady | reconstructed_pit_proxy |
| 2025-11-30 00:00:00 | 2025-10-31 00:00:00 | wolf_cvar | 0.03438242973236011 | 0.0007930409414643138 | 0.0335893887908958 | 0.10000000000000002 | 1.0 | 24 | steady | reconstructed_pit_proxy |
| 2025-12-30 00:00:00 | 2025-11-30 00:00:00 | wolf_cvar | -0.011168019158916775 | 0.0007468739302029256 | -0.0119148930891197 | 0.10000000000000002 | 0.9999999999999999 | 25 | steady | reconstructed_pit_proxy |
| 2026-01-31 00:00:00 | 2025-12-31 00:00:00 | wolf_cvar | 0.024177197278922792 | 0.0007154723056330771 | 0.023461724973289716 | 0.09999999999999992 | 0.9999999999999998 | 26 | steady | reconstructed_pit_proxy |
| 2026-02-28 00:00:00 | 2026-01-31 00:00:00 | wolf_cvar | 0.0539281239739523 | 0.0008025464239069795 | 0.05312557755004532 | 0.10000000000000012 | 1.0000000000000002 | 30 | steady | reconstructed_pit_proxy |
| 2026-03-28 00:00:00 | 2026-02-28 00:00:00 | wolf_cvar | 0.007560067493430415 | 0.0008293317404689352 | 0.0067307357529614795 | 0.10000000000000002 | 1.0 | 31 | steady | reconstructed_pit_proxy |
| 2026-04-30 00:00:00 | 2026-03-31 00:00:00 | wolf_cvar | 0.01375387915321747 | 0.0010269316710096034 | 0.012726947482207866 | 0.09999999999999999 | 0.9999999999999998 | 32 | steady | reconstructed_pit_proxy |
| 2026-05-30 00:00:00 | 2026-04-30 00:00:00 | wolf_cvar | -0.012982657024515088 | 0.0070723432123010665 | -0.020055000236816153 | 0.45715323670878427 | 1.0 | 20 | steady | reconstructed_pit_proxy |
| 2026-06-30 00:00:00 | 2026-05-31 00:00:00 | wolf_cvar | -0.034936961866542465 | 0.0007809187830428555 | -0.035717880649585323 | 0.09999999999999998 | 1.0 | 24 | steady | reconstructed_pit_proxy |
| 2026-07-30 00:00:00 | 2026-06-30 00:00:00 | wolf_cvar | 0.11398892991392999 | 0.0007889311647556296 | 0.11319999874917436 | 0.09999999999999999 | 1.0 | 27 | steady | reconstructed_pit_proxy |

## 12. Transaction-Cost Robustness
| strategy | cost_multiplier | gross_return | net_return | cost_drag | gross_alpha_consumed | status | evidence_mode |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cap_weight_eligible | 1.0 | 0.35835176227954435 | 0.34811964781487925 | 0.010232114464665109 | 0.02855326955719895 | PASS | reconstructed_pit_proxy |
| equal_weight_eligible | 1.0 | 0.49238773870032143 | 0.4816297652675761 | 0.010757973432745323 | 0.021848581081936474 | PASS | reconstructed_pit_proxy |
| wolf_cvar | 1.0 | 0.41727086697012 | 0.38270627750649955 | 0.03456458946362048 | 0.08283489742430446 | PASS | reconstructed_pit_proxy |
| cap_weight_eligible | 1.5 | 0.35835176227954435 | 0.3430035905825467 | 0.015348171696997663 | 0.042829904335798426 | PASS | reconstructed_pit_proxy |
| equal_weight_eligible | 1.5 | 0.49238773870032143 | 0.47625077855120346 | 0.016136960149117984 | 0.03277287162290471 | PASS | reconstructed_pit_proxy |
| wolf_cvar | 1.5 | 0.41727086697012 | 0.3654239827746893 | 0.05184688419543072 | 0.12425234613645669 | PASS | reconstructed_pit_proxy |
| cap_weight_eligible | 2.0 | 0.35835176227954435 | 0.33788753335021415 | 0.020464228929330218 | 0.0571065391143979 | PASS | reconstructed_pit_proxy |
| equal_weight_eligible | 2.0 | 0.49238773870032143 | 0.4708717918348308 | 0.021515946865490646 | 0.04369716216387295 | PASS | reconstructed_pit_proxy |
| wolf_cvar | 2.0 | 0.41727086697012 | 0.34814168804287904 | 0.06912917892724096 | 0.16566979484860891 | PASS | reconstructed_pit_proxy |

## 13. Benchmark Comparison
| strategy | observations | annualised_return | annualised_volatility | sharpe | sortino | maximum_drawdown | expected_shortfall | positive_period_ratio | worst_period | best_period | gross_annualised_return | annualised_cost_drag | annualised_turnover | total_transaction_cost | mean_net_return_ci_lower | mean_net_return_ci_upper | status | evidence_mode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| wolf_cvar | 25 | 0.19394235196053966 | 0.10511087493970635 | 1.8451216591222248 | 5.658562506031724 | -0.05505655878151561 | 0.030830985559832352 | 0.72 | -0.035717880649585323 | 0.11319999874917436 | 0.21368172863908153 | 0.019739376678541865 | 1.9568747500326569 | 0.03456458946362048 | 0.009196266159945244 | 0.018447431299726556 | WARNING | reconstructed_pit_proxy |
| equal_weight_eligible | 25 | 0.2499402591552753 | 0.11287833088750114 | 2.2142448173190594 | 4.174141646136274 | -0.051667835665107686 | 0.038654510800678867 | 0.76 | -0.05166783566510767 | 0.08518250117821669 | 0.25632072005183626 | 0.006380460896560969 | 1.1162132982009558 | 0.010757973432745323 | 0.011030049543474535 | 0.02697355255297741 |  | reconstructed_pit_proxy |
| cap_weight_eligible | 25 | 0.1761642203304159 | 0.08875145490607421 | 1.984916422123454 | 4.260486654691978 | -0.03988962634918958 | 0.03495613373924607 | 0.76 | -0.03988962634918942 | 0.07710928234194482 | 0.18188666785906626 | 0.005722447528650365 | 1.1931790159784914 | 0.010232114464665109 | 0.007629461530153679 | 0.018290562006982904 |  | reconstructed_pit_proxy |

## 14. Regime Performance
| regime | observations | status | annualised_return | annualised_volatility | sharpe | sortino | maximum_drawdown | expected_shortfall | positive_period_ratio | worst_period | best_period |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high_volatility | 4 | INSUFFICIENT_DATA |  |  |  |  |  |  |  |  |  |
| steady | 21 | EVALUATED | 0.19334613182417315 | 0.11435473182339843 | 1.690757599106293 | 5.64116687854304 | -0.0550565587815155 | 0.030830985559832352 | 0.6666666666666666 | -0.035717880649585323 | 0.11319999874917436 |

## 15. Regional Performance
| horizon | region | observation_count | status | mae | rmse | normalised_rmse | directional_accuracy | rank_ic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12M | DACH | 2349 | EVALUATED | 0.33144400251027195 | 0.46060918373637305 | 1.077473074195544 | 0.5572584078331205 | 0.12053073111469559 |
| 12M | EU ex-DACH | 3118 | EVALUATED | 0.3116847671039852 | 0.41166689374662113 | 1.1435928060121883 | 0.5830660679923028 | 0.0394685314630434 |
| 12M | Hong Kong | 2961 | EVALUATED | 0.46868898843618845 | 0.8237752961372772 | 1.1042348349330389 | 0.6811887875717663 | -0.04741844608751757 |
| 12M | Mainland China | 3286 | EVALUATED | 0.42232775641472886 | 0.6223212243386014 | 1.1543138131253048 | 0.5450395617772368 | 0.005883346535878018 |
| 12M | UK | 2788 | EVALUATED | 0.3354378971622198 | 0.49881655154819293 | 1.1449615104487763 | 0.5387374461979914 | 0.018265403304804195 |
| 12M | US | 3427 | EVALUATED | 0.32772674748597164 | 0.454439766241862 | 1.2426917793067287 | 0.5293259410563175 | 0.008504167228803518 |
| 3M | DACH | 2525 | EVALUATED | 0.11885567353782085 | 0.15994910393787365 | 1.0353314433861642 | 0.5437623762376238 | 0.07265697804483007 |
| 3M | EU ex-DACH | 3358 | EVALUATED | 0.10958145371479043 | 0.14199241002253638 | 1.0742457181055827 | 0.5291840381179274 | 0.0041309190561911865 |
| 3M | Hong Kong | 2996 | EVALUATED | 0.16497700599977025 | 0.27460731529695603 | 1.0608174786637623 | 0.6298397863818425 | 0.010586920731043397 |
| 3M | Mainland China | 3286 | EVALUATED | 0.14448527261104155 | 0.23608230971643718 | 1.0875757844926113 | 0.5496043822276324 | -0.0011338467949094956 |
| 3M | UK | 2789 | EVALUATED | 0.11966552632610032 | 0.1581411180901407 | 1.0749277084631093 | 0.5044818931516672 | -0.013379647832565704 |
| 3M | US | 3427 | EVALUATED | 0.11393905613591099 | 0.14731938893777247 | 1.1109866554092722 | 0.4986868981616574 | -0.037171861841810434 |
| 6M | DACH | 2525 | EVALUATED | 0.1907349007193824 | 0.25924253397355485 | 1.051988612463789 | 0.5592079207920793 | 0.10826499807308845 |
| 6M | EU ex-DACH | 3358 | EVALUATED | 0.17667111231407928 | 0.22999815095290774 | 1.1177856508376491 | 0.5449672424061942 | 0.008062072165095696 |
| 6M | Hong Kong | 2996 | EVALUATED | 0.25375331104228266 | 0.41451411463309296 | 1.0986553628799098 | 0.6588785046728972 | 0.0001554172949525152 |
| 6M | Mainland China | 3286 | EVALUATED | 0.22460062240554293 | 0.3453509119178656 | 1.126078459899997 | 0.5474741326841144 | -0.0032066101247416835 |
| 6M | UK | 2789 | EVALUATED | 0.19061138964693583 | 0.2675733744580406 | 1.1188854573555822 | 0.5292219433488705 | -0.01772976954012888 |
| 6M | US | 3427 | EVALUATED | 0.17600604058485111 | 0.23190203255922848 | 1.1902682257476644 | 0.5059819083746717 | -0.03069491243439068 |
| 9M | DACH | 2525 | EVALUATED | 0.26257125660577724 | 0.3610857244016178 | 1.062768560507669 | 0.5615841584158416 | 0.11759667641669737 |
| 9M | EU ex-DACH | 3358 | EVALUATED | 0.24356993679899994 | 0.32005058466927033 | 1.1300108478665378 | 0.5646217986896962 | 0.0300527032611556 |
| 9M | Hong Kong | 2996 | EVALUATED | 0.36098179422960724 | 0.6045147396943374 | 1.11400012881547 | 0.6685580774365821 | -0.034606405659703625 |
| 9M | Mainland China | 3286 | EVALUATED | 0.33029805817960767 | 0.49526930507913525 | 1.143266323254752 | 0.5426049908703591 | -0.0076410498596329 |
| 9M | UK | 2789 | EVALUATED | 0.2680177076240499 | 0.38814751084161025 | 1.1292394334750646 | 0.5263535317318035 | 0.0035761454419467606 |
| 9M | US | 3427 | EVALUATED | 0.25253756261400856 | 0.3380081474034362 | 1.2204259394727723 | 0.5115261161365626 | -0.021056118698760545 |

## 16. Constraint Compliance
| constraint_name | constraint_type | limit | actual_value | breach_flag | severity | affected_stocks | commentary | portfolio | as_of_date | strategy | limit_value | check_name | status | breach_count | critical |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fully_invested | hard | 1.0 | 1.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| recommendation_eligibility | hard | no Avoid or Exclude | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| unique_issuer | hard | one listing per issuer | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| price_data_quality | hard | no quarantined price histories | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| single_name_concentration | hard | 0.05 | 0.05 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| sector_concentration | hard | 0.25 | 0.2500000000000001 | False | OK | Consumer Staples, Financials |  | classical |  |  |  |  |  |  |  |
| country_concentration | hard | 0.3 | 0.3000000000000001 | False | OK | China |  | classical |  |  |  |  |  |  |  |
| region_concentration | hard | 0.4 | 0.3000000000000001 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| currency_concentration | hard | 0.4 | 0.3000000000000001 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| liquidity | hard | 40 | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| turnover | soft | 0.35 | 0.6941023094114726 | True | High |  |  | classical |  |  |  |  |  |  |  |
| portfolio_dividend_yield | soft | 0.03 | 0.043325 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| portfolio_volatility | soft | 0.2 | 0.1113852912349695 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| portfolio_var_5 | soft | -0.15 | 0.0136638135575122 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| portfolio_cvar_5 | soft | -0.25 | -0.050996930305742 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| portfolio_expected_shortfall_5 | soft | -0.25 | -0.050996930305742 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| dividend_cut_risk | soft | 0.35 | 0.2667612712268629 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| drawdown_risk | soft | 0.35 | 0.2854599127072832 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| HHI | soft | 0.15 | 0.05 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| effective_holdings | soft | 15 | 20.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| regime_risk | soft | no reviewed names preferred | 0.0 | False | OK |  |  | classical |  |  |  |  |  |  |  |
| narrative_risk | soft | no reviewed names preferred | 20.0 | True | High | 000333.SHE, ALV.XETRA, 601816.SHG, 600036.SHG, NOVN.SW, AD.AS, PG.US, SHEL.US, 3988.HK, ORA.PA, MCD.US, 000538.SHE, SBRY.LSE, 0823.HK, HEN3.XETRA, 601818.SHG, CS.PA, LI.PA, ESSITY-B.ST, 600018.SHG |  | classical |  |  |  |  |  |  |  |
| alt_data_risk | soft | no reviewed names preferred | 1.0 | True | High | CS.PA |  | classical |  |  |  |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2024-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2999999999999999 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2999999999999999 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.31666666666666665 | False |  |  |  | walk_forward | 2024-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3333333333333334 | False |  |  |  | walk_forward | 2024-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.24705882352941178 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2892156862745099 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.35686274509803934 | False |  |  |  | walk_forward | 2024-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2157357179182911 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2923857150929537 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.36954286037181455 | False |  |  |  | walk_forward | 2024-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.22855182748532796 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.29523373944118414 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.38093495776473624 | False |  |  |  | walk_forward | 2024-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2299891862861687 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2655324285936606 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2977006909992209 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.39080276399688346 | False |  |  |  | walk_forward | 2024-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24286092802249265 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2555413601516359 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.26701773207677715 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3967187876135698 | False |  |  |  | walk_forward | 2025-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24768565051386332 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.25179640211778803 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.25551682061914865 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.39893629420961657 | False |  |  |  | walk_forward | 2025-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2492940728218629 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.21579903476276274 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2864316580175183 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3996755464844566 | False |  |  |  | walk_forward | 2025-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.4 | False |  |  |  | walk_forward | 2025-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.4 | False |  |  |  | walk_forward | 2025-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.2 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.4 | False |  |  |  | walk_forward | 2025-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2500000000000001 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.24999999999999978 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.2500000000000001 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3500000000000001 | False |  |  |  | walk_forward | 2025-07-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.35000000000000003 | False |  |  |  | walk_forward | 2025-08-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-09-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2499999999999999 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-10-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999999 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24999999999999994 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-11-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999998 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2025-12-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0000000000000002 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.050000000000000024 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.24242569511025872 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000016 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000016 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000016 | False |  |  |  | walk_forward | 2026-01-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000002 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.23192605662305496 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3000000000000001 | False |  |  |  | walk_forward | 2026-02-28 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 0.9999999999999998 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.2485532874430361 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-03-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2026-04-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.3 | False |  |  |  | walk_forward | 2026-05-31 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| weights_sum_to_one | hard |  | 1.0 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 1.0 |  |  |  |  |
| maximum_single_name_weight | hard |  | 0.05000000000000001 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.05 |  |  |  |  |
| maximum_sector_weight | hard |  | 0.25000000000000006 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.25 |  |  |  |  |
| maximum_country_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.3 |  |  |  |  |
| maximum_region_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
| maximum_currency_weight | hard |  | 0.30000000000000004 | False |  |  |  | walk_forward | 2026-06-30 00:00:00 | wolf_cvar | 0.4 |  |  |  |  |
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
| drl_governance | FAIL | 11 | DRL remains a challenger and cannot be promoted without realised out-of-sample comparison. |

## 18. Sensitivity Analysis
| parameter | relative_change | scale | observation_count | status | mae | rmse | normalised_rmse | directional_accuracy | rank_ic | normalised_rmse_change | validation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| expected_return_scale | -0.19999999999999996 | 0.8 | 17929 | EVALUATED | 0.35169816303020035 | 0.555808414583941 | 1.0976314539471066 | 0.5717552568464499 | 0.038641174537828164 | -0.016863097884916023 | PASS |
| expected_return_scale | -0.09999999999999998 | 0.9 | 17929 | EVALUATED | 0.35892561652782917 | 0.5595482655602263 | 1.1050170529357768 | 0.5717552568464499 | 0.038641174537828164 | -0.009477498896245828 | PASS |
| expected_return_scale | 0.10000000000000009 | 1.1 | 17929 | EVALUATED | 0.376597940098192 | 0.5701790512279202 | 1.1260111300725284 | 0.5717552568464499 | 0.038641174537828164 | 0.011516578240505781 | PASS |
| expected_return_scale | 0.19999999999999996 | 1.2 | 17929 | EVALUATED | 0.3869520518865506 | 0.577011933722121 | 1.1395049645485207 | 0.5717552568464499 | 0.038641174537828164 | 0.025010412716498065 | PASS |

## 19. Ablation Analysis
| ablation | net_return | sharpe | cvar | drawdown | turnover | dividend_yield | worst_scenario_loss | seed_dispersion | feature_value_added | status | validation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| without_regime_features | 0.3850597944425601 | 2.139221080236445 | -0.2 | -0.1 | 0.1 | 0.03 | -0.18 | 0.01 | -0.0026 | deterministic_proxy | PROXY_ONLY |
| with_regime_features | 0.3872597944425601 | 2.127801068365715 | -0.205 | -0.104 | 0.11 | 0.031 | -0.19 | 0.012 | -0.0003999999999999 | mvp_run | PROXY_ONLY |
| without_distributional_features | 0.3854597944425602 | 2.094890187187827 | -0.21 | -0.108 | 0.12 | 0.032 | -0.1999999999999999 | 0.014 | -0.0022 | deterministic_proxy | PROXY_ONLY |
| with_distributional_features | 0.3876597944425601 | 2.15366552468089 | -0.215 | -0.112 | 0.13 | 0.03 | -0.21 | 0.016 | 0.0 | mvp_run | PROXY_ONLY |
| without_sentiment_narrative | 0.3858597944425601 | 2.1201087606734075 | -0.2 | -0.116 | 0.1 | 0.031 | -0.18 | 0.018 | -0.0018 | deterministic_proxy | PROXY_ONLY |
| with_sentiment_narrative | 0.3880597944425601 | 2.109020621970436 | -0.205 | -0.1 | 0.11 | 0.032 | -0.19 | 0.01 | 0.0003999999999999 | mvp_run | PROXY_ONLY |
| differential_sharpe_reward_only | 0.3862597944425601 | 2.145887746903112 | -0.21 | -0.104 | 0.12 | 0.03 | -0.1999999999999999 | 0.012 | -0.0014 | deterministic_proxy | PROXY_ONLY |
| full_conservative_reward | 0.3884597944425602 | 2.1343944749591217 | -0.215 | -0.108 | 0.13 | 0.031 | -0.21 | 0.014 | 0.0008 | mvp_run | PROXY_ONLY |
| no_transaction_costs | 0.3866597944425601 | 2.101411926318262 | -0.2 | -0.112 | 0.1 | 0.032 | -0.18 | 0.016 | -0.001 | deterministic_proxy | PROXY_ONLY |
| realistic_transaction_costs | 0.3888597944425601 | 2.1603321913475564 | -0.205 | -0.116 | 0.11 | 0.03 | -0.19 | 0.018 | 0.0012 | mvp_run | PROXY_ONLY |
| universal_agent | 0.3870597944425601 | 2.126702167266814 | -0.21 | -0.1 | 0.12 | 0.031 | -0.1999999999999999 | 0.01 | -0.0006 | deterministic_proxy | PROXY_ONLY |
| regime_specialist_blend | 0.3892597944425601 | 2.1155423611008706 | -0.215 | -0.104 | 0.13 | 0.032 | -0.21 | 0.012 | 0.0016 | mvp_run | PROXY_ONLY |
| mlp_encoder | 0.3874597944425602 | 2.1525544135697787 | -0.2 | -0.108 | 0.1 | 0.03 | -0.18 | 0.014 | -0.0001999999999999 | deterministic_proxy | PROXY_ONLY |
| tcn_gap_encoder_when_available | 0.3896597944425601 | 2.1409878815525283 | -0.205 | -0.112 | 0.11 | 0.031 | -0.19 | 0.016 | 0.002 | mvp_run | PROXY_ONLY |
| no_risk_throttle | 0.3878597944425601 | 2.107933665448696 | -0.21 | -0.116 | 0.12 | 0.032 | -0.1999999999999999 | 0.018 | 0.0002 | deterministic_proxy | PROXY_ONLY |
| wolf_chaos_risk_throttle | 0.3900597944425601 | 2.166998858014223 | -0.215 | -0.1 | 0.13 | 0.03 | -0.21 | 0.01 | 0.0024 | mvp_run | PROXY_ONLY |

## 20. Stability and Concentration Tests
| excluded_dimension | excluded_group | observation_count | status | mae | rmse | normalised_rmse | directional_accuracy | rank_ic | rank_ic_change | validation_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none | none | 17929 | EVALUATED | 0.3672414852466898 | 0.5643473933702037 | 1.1144945518320226 | 0.5717552568464499 | 0.038641174537828164 | 0.0 | PASS |
| region | DACH | 15580 | EVALUATED | 0.3726386795308904 | 0.578376131561443 | 1.1196791686929066 | 0.5739409499358151 | 0.02878030875020187 | -0.009860865787626294 | PASS |
| region | EU ex-DACH | 14811 | EVALUATED | 0.37893724158785197 | 0.5914889731142582 | 1.1144832494658228 | 0.5693741138343124 | 0.03982479820446943 | 0.0011836236666412647 | PASS |
| region | Hong Kong | 14968 | EVALUATED | 0.34717293521033854 | 0.4972411466707889 | 1.1468323882627127 | 0.5501068947087119 | 0.022206706273498227 | -0.016434468264329937 | PASS |
| region | Mainland China | 14643 | EVALUATED | 0.3548797091722395 | 0.5504994995099005 | 1.1054722937726393 | 0.5777504609711125 | 0.05021881201501024 | 0.011577637477182073 | PASS |
| region | UK | 15141 | EVALUATED | 0.37309766407104106 | 0.5756011866923796 | 1.1135508201293811 | 0.5778350175021465 | 0.041564842988799554 | 0.0029236684509713895 | PASS |
| region | US | 14502 | EVALUATED | 0.37657930115525284 | 0.5873231197473339 | 1.100289602380486 | 0.5817818231968005 | 0.04590624802296825 | 0.007265073485140085 | PASS |
| forecast_year | 2024 | 8784 | EVALUATED | 0.3764726384435739 | 0.5709197050209097 | 1.1012545877497926 | 0.5767304189435337 | 0.055744671451135465 | 0.0171034969133073 | PASS |
| forecast_year | 2025 | 9145 | EVALUATED | 0.35837473295785105 | 0.5579616367757563 | 1.1284433291290337 | 0.5669764898851831 | 0.02258294411571683 | -0.016058230422111335 | PASS |

## 21. Statistical Confidence
| strategy | baseline | observations | mean_difference | t_statistic | p_value | difference_ci_lower | difference_ci_upper | bootstrap_block_size | bootstrap_significant | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| wolf_cvar | equal_weight_eligible | 25 | -0.003956939510443061 | -0.7285320877656106 | 0.4733373395853032 | -0.014470865359821242 | 0.004636539658732527 | 6 | False | WARNING |

## 22. Known Limitations
- Historical filing availability is reconstructed from fiscal period end plus a conservative reporting lag when an observed filing date is unavailable.
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
