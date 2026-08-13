# Production Point-in-Time Coverage

Generated: 2026-08-13 10:38 UTC

This report contains aggregate coverage only. Licensed Bloomberg observations remain in the ignored local DuckDB and are not published.

Active Mainland China and Hong Kong inventory: **8,607 securities**; canonical Bloomberg-mapped target: **7,862**.

## Dataset Coverage

| dataset | row_count | entity_count | earliest_observation | latest_observation | earliest_available_from | latest_available_from |
| --- | --- | --- | --- | --- | --- | --- |
| fundamental_vintages | 8962 | 6357 | 2002-03-31 00:00:00 | 2022-03-31 00:00:00 | 2021-08-31 00:00:00 | 2021-08-31 00:00:00 |
| corporate_action_vintages | 121142 | 7322 | 1986-01-01 00:00:00 | 2027-01-15 00:00:00 | 1986-01-01 00:00:00 | 2026-08-13 00:00:00 |
| market_cap_vintages | 662723 | 7834 | 2018-07-31 00:00:00 | 2026-07-31 00:00:00 | 2018-07-31 00:00:00 | 2026-07-31 00:00:00 |
| identifier_vintages | 32847 | 7860 | 2026-08-13 00:00:00 | 2026-08-13 00:00:00 | 2026-08-13 09:28:42 | 2026-08-13 09:28:42 |
| macro_release_vintages | 112138 | 21 | 1994-01-01 00:00:00 | 2026-08-12 00:00:00 | 1994-01-01 00:00:00 | 2026-08-12 00:00:00 |
| sentiment_vintages | 0 | 0 |  |  |  |  |
| decision_snapshot_manifests | 60 | 60 | 2021-07-31 00:00:00 | 2026-06-30 00:00:00 | 2026-08-13 09:28:09 | 2026-08-13 09:28:09 |

## Fundamental Snapshots

| fiscal_period_type | available_from | row_count | entity_count |
| --- | --- | --- | --- |
| annual | 2021-08-31 00:00:00 | 4425 | 4425 |
| quarterly | 2021-08-31 00:00:00 | 4537 | 4537 |

## Macro Series

| series_id | row_count | observation_count | earliest_observation | latest_observation |
| --- | --- | --- | --- | --- |
| BAA10YM | 391 | 391 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| BAMLH0A0HYM2 | 786 | 786 | 2023-08-14 00:00:00 | 2026-08-11 00:00:00 |
| CPIAUCSL | 1863 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| CPILFESL | 1689 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| DEXCHUS | 8176 | 8176 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| DEXHKUS | 8178 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| DEXSZUS | 8178 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| DEXUSEU | 6921 | 6921 | 1999-01-04 00:00:00 | 2026-08-07 00:00:00 |
| DEXUSUK | 8178 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| DFF | 11911 | 11911 | 1994-01-01 00:00:00 | 2026-08-11 00:00:00 |
| DGS10 | 8157 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| DGS2 | 8157 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| DGS30 | 8157 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| DTWEXBGS | 5164 | 5164 | 2006-01-02 00:00:00 | 2026-08-07 00:00:00 |
| FEDFUNDS | 359 | 356 | 1996-12-01 00:00:00 | 2026-07-01 00:00:00 |
| GDP | 1331 | 130 | 1994-01-01 00:00:00 | 2026-04-01 00:00:00 |
| GDPC1 | 1499 | 130 | 1994-01-01 00:00:00 | 2026-04-01 00:00:00 |
| T10Y2Y | 8158 | 8158 | 1994-01-03 00:00:00 | 2026-08-12 00:00:00 |
| T10YIE | 5907 | 5907 | 2003-01-02 00:00:00 | 2026-08-12 00:00:00 |
| UNRATE | 741 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| VIXCLS | 8237 | 8237 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |

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
