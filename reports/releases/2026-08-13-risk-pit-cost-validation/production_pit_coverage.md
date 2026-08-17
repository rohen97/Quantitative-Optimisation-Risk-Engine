# Production Point-in-Time Coverage

Generated: 2026-08-13 18:30 UTC

This report contains aggregate coverage only. Licensed Bloomberg observations remain in the ignored local DuckDB and are not published.

Active Mainland China and Hong Kong inventory: **8,607 securities**; canonical Bloomberg-mapped target: **7,862**.

## Dataset Coverage

| dataset | row_count | entity_count | earliest_observation | latest_observation | earliest_available_from | latest_available_from |
| --- | --- | --- | --- | --- | --- | --- |
| fundamental_vintages | 25240 | 6692 | 2002-03-31 00:00:00 | 2022-03-31 00:00:00 | 2018-07-31 00:00:00 | 2021-08-31 00:00:00 |
| corporate_action_vintages | 151659 | 7649 | 1962-05-31 00:00:00 | 2027-03-12 00:00:00 | 1962-05-23 00:00:00 | 2026-08-13 00:00:00 |
| market_cap_vintages | 694246 | 8161 | 2018-07-31 00:00:00 | 2026-07-31 00:00:00 | 2018-07-31 00:00:00 | 2026-07-31 00:00:00 |
| identifier_vintages | 34172 | 8187 | 2026-08-13 00:00:00 | 2026-08-13 00:00:00 | 2026-08-13 09:28:42 | 2026-08-13 17:04:05 |
| macro_release_vintages | 157155 | 26 | 1960-01-01 00:00:00 | 2026-08-13 00:00:00 | 1994-01-01 00:00:00 | 2026-08-13 00:00:00 |
| sentiment_vintages | 0 | 0 |  |  |  |  |
| decision_snapshot_manifests | 301 | 301 | 2021-07-31 00:00:00 | 2026-06-30 00:00:00 | 2026-08-13 09:28:09 | 2026-08-13 17:56:52 |

## Fundamental Snapshots

| fiscal_period_type | available_from | row_count | entity_count |
| --- | --- | --- | --- |
| annual | 2018-07-31 00:00:00 | 548 | 548 |
| annual | 2018-08-31 00:00:00 | 551 | 551 |
| annual | 2018-09-30 00:00:00 | 553 | 553 |
| annual | 2018-10-31 00:00:00 | 553 | 553 |
| annual | 2018-11-30 00:00:00 | 553 | 553 |
| annual | 2018-12-31 00:00:00 | 553 | 553 |
| annual | 2019-01-31 00:00:00 | 555 | 555 |
| annual | 2019-02-28 00:00:00 | 547 | 547 |
| annual | 2019-03-31 00:00:00 | 552 | 552 |
| annual | 2019-04-30 00:00:00 | 552 | 552 |
| annual | 2019-05-31 00:00:00 | 553 | 553 |
| annual | 2019-06-30 00:00:00 | 553 | 553 |
| annual | 2019-07-31 00:00:00 | 554 | 554 |
| annual | 2019-08-31 00:00:00 | 555 | 555 |
| annual | 2019-09-30 00:00:00 | 557 | 557 |
| annual | 2019-10-31 00:00:00 | 558 | 558 |
| annual | 2019-11-30 00:00:00 | 559 | 559 |
| annual | 2019-12-31 00:00:00 | 560 | 560 |
| annual | 2020-01-31 00:00:00 | 562 | 562 |
| annual | 2020-02-29 00:00:00 | 563 | 563 |
| annual | 2020-03-31 00:00:00 | 562 | 562 |
| annual | 2020-04-30 00:00:00 | 562 | 562 |
| annual | 2020-05-31 00:00:00 | 560 | 560 |
| annual | 2020-06-30 00:00:00 | 562 | 562 |
| annual | 2020-07-31 00:00:00 | 562 | 562 |
| annual | 2020-08-31 00:00:00 | 563 | 563 |
| annual | 2020-09-30 00:00:00 | 564 | 564 |
| annual | 2020-10-31 00:00:00 | 564 | 564 |
| annual | 2020-11-30 00:00:00 | 565 | 565 |
| annual | 2020-12-31 00:00:00 | 123 | 123 |
| annual | 2021-08-31 00:00:00 | 4425 | 4425 |
| quarterly | 2021-08-31 00:00:00 | 4537 | 4537 |

## Macro Series

| series_id | row_count | observation_count | earliest_observation | latest_observation |
| --- | --- | --- | --- | --- |
| BAA10YM | 514 | 391 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| BAMLH0A0HYM2 | 787 | 787 | 2023-08-14 00:00:00 | 2026-08-12 00:00:00 |
| CPIAUCSL | 1863 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| CPILFESL | 1689 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| DEXCHUS | 10681 | 8176 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| DEXHKUS | 10680 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| DEXSZUS | 10680 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| DEXUSEU | 9423 | 6921 | 1999-01-04 00:00:00 | 2026-08-07 00:00:00 |
| DEXUSUK | 10680 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| DFF | 15575 | 11911 | 1994-01-01 00:00:00 | 2026-08-11 00:00:00 |
| DGS10 | 10666 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| DGS2 | 10664 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| DGS30 | 10665 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| DTWEXBGS | 16930 | 5166 | 2006-01-02 00:00:00 | 2026-08-07 00:00:00 |
| EXR.D.CHF.EUR.SP00.A | 2569 | 2569 | 2016-08-01 00:00:00 | 2026-08-13 00:00:00 |
| EXR.D.GBP.EUR.SP00.A | 2569 | 2569 | 2016-08-01 00:00:00 | 2026-08-13 00:00:00 |
| EXR.D.USD.EUR.SP00.A | 2569 | 2569 | 2016-08-01 00:00:00 | 2026-08-13 00:00:00 |
| FEDFUNDS | 359 | 356 | 1996-12-01 00:00:00 | 2026-07-01 00:00:00 |
| GDP | 1331 | 130 | 1994-01-01 00:00:00 | 2026-04-01 00:00:00 |
| GDPC1 | 1499 | 130 | 1994-01-01 00:00:00 | 2026-04-01 00:00:00 |
| T10Y2Y | 8898 | 8159 | 1994-01-03 00:00:00 | 2026-08-12 00:00:00 |
| T10YIE | 6646 | 5907 | 2003-01-02 00:00:00 | 2026-08-12 00:00:00 |
| UNRATE | 741 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| VIXCLS | 8395 | 8238 | 1994-01-03 00:00:00 | 2026-08-12 00:00:00 |
| china-cpi | 16 | 16 | 2010-01-01 00:00:00 | 2025-01-01 00:00:00 |
| china-gdp | 66 | 66 | 1960-01-01 00:00:00 | 2025-01-01 00:00:00 |

## Evidence Grades

- Bloomberg fundamentals: genuine `FUNDAMENTAL_DATABASE_DATE` snapshots. Each row is usable only from its database-as-of date.
- FRED GDP, real GDP, CPI, core CPI, unemployment and monthly Fed funds: ALFRED release/revision vintages.
- Daily rates, curves, FX, VIX and market credit spreads: non-revising observations available on the observation date.
- Bloomberg market cap/free float: dated historical observations, not reconstructed from today's shares.
- Corporate actions: event-time reconstruction using declaration dates; later vendor corrections are not yet separately versioned.
- Identifier mappings: current retrieval snapshots only. Historical effective-date mappings remain incomplete.
- Decision archives: retrospective cryptographic registration of existing walk-forward artifacts; availability is the archive timestamp, not the original rebalance date.

## Open Production Gaps

- Complete monthly Bloomberg fundamental snapshots from July 2018 onward. The current session stopped at Bloomberg's daily data capacity and is safely resumable.
- Historical constituent/delisted-security membership and historical ticker/ISIN mappings for a survivorship-clean 1997 universe.
- Timestamped entity-mapped news and immutable sentiment vintages. No production sentiment rows are currently present.
- Genuine pre-1997 China/Hong Kong fundamentals are not established by the current entitlements; the 1997 test remains reconstructed rather than fully genuine PIT.

## DRL Decision

The production DRL challenger uses five Stable-Baselines3 PPO seeds over a chronological regional panel. All validation information ratios are currently negative, so the validation guard selects the constrained baseline optimiser with a 0% DRL live blend.
