# Production Point-in-Time Coverage

Generated: 2026-08-19 06:28 UTC

This report contains aggregate coverage only. Credentials, raw provider payloads, the local DuckDB and licensed observations are not published.

Active Mainland China and Hong Kong inventory: **8,607 securities**; current OpenFIGI-mapped inventory: **7,617**.

## Dataset Coverage

| dataset | row_count | entity_count | earliest_observation | latest_observation | earliest_available_from | latest_available_from |
| --- | --- | --- | --- | --- | --- | --- |
| fundamental_vintages | 25240 | 6692 | 2002-03-31 00:00:00 | 2022-03-31 00:00:00 | 2018-07-31 00:00:00 | 2021-08-31 00:00:00 |
| corporate_action_vintages | 151659 | 7649 | 1962-05-31 00:00:00 | 2027-03-12 00:00:00 | 1962-05-23 00:00:00 | 2026-08-13 00:00:00 |
| market_cap_vintages | 694246 | 8161 | 2018-07-31 00:00:00 | 2026-07-31 00:00:00 | 2018-07-31 00:00:00 | 2026-07-31 00:00:00 |
| identifier_vintages | 186711 | 51840 | 2026-08-13 00:00:00 | 2026-08-19 00:00:00 | 2026-08-13 09:28:42 | 2026-08-19 06:21:12 |
| macro_release_vintages | 157155 | 26 | 1960-01-01 00:00:00 | 2026-08-13 00:00:00 | 1994-01-01 00:00:00 | 2026-08-13 00:00:00 |
| sentiment_vintages | 0 | 0 |  |  |  |  |
| decision_snapshot_manifests | 534 | 534 | 2019-02-28 00:00:00 | 2026-06-30 00:00:00 | 2026-08-13 09:28:09 | 2026-08-14 09:44:09 |

## Fundamental Snapshots

| source | fiscal_period_type | row_count | entity_count | earliest_available_from | latest_available_from |
| --- | --- | --- | --- | --- | --- |
| bloomberg_desktop | annual | 20703 | 4856 | 2018-07-31 00:00:00 | 2021-08-31 00:00:00 |
| bloomberg_desktop | quarterly | 4537 | 4537 | 2021-08-31 00:00:00 | 2021-08-31 00:00:00 |

## China And Hong Kong Market History

| region | source | row_count | entity_count | positive_volume_rows | positive_volume_entities | earliest_observation | latest_observation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Hong Kong | akshare | 11999221 | 3344 | 10999020 | 3344 | 1998-06-01 00:00:00 | 2026-08-18 00:00:00 |
| Hong Kong | yfinance | 5693400 | 2826 | 67104 | 74 | 2000-01-04 00:00:00 | 2026-08-18 00:00:00 |
| Mainland China | akshare | 188936 | 30 | 188936 | 30 | 1993-10-11 00:00:00 | 2026-08-18 00:00:00 |
| Mainland China | yfinance | 17528764 | 5103 | 16770560 | 5068 | 1993-10-11 00:00:00 | 2026-08-18 00:00:00 |

## Macro Series

| source | series_id | row_count | observation_count | earliest_observation | latest_observation |
| --- | --- | --- | --- | --- | --- |
| china_data | china-cpi | 16 | 16 | 2010-01-01 00:00:00 | 2025-01-01 00:00:00 |
| china_data | china-gdp | 66 | 66 | 1960-01-01 00:00:00 | 2025-01-01 00:00:00 |
| ecb | EXR.D.CHF.EUR.SP00.A | 2569 | 2569 | 2016-08-01 00:00:00 | 2026-08-13 00:00:00 |
| ecb | EXR.D.GBP.EUR.SP00.A | 2569 | 2569 | 2016-08-01 00:00:00 | 2026-08-13 00:00:00 |
| ecb | EXR.D.USD.EUR.SP00.A | 2569 | 2569 | 2016-08-01 00:00:00 | 2026-08-13 00:00:00 |
| fred | BAA10YM | 514 | 391 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| fred | BAMLH0A0HYM2 | 787 | 787 | 2023-08-14 00:00:00 | 2026-08-12 00:00:00 |
| fred | CPIAUCSL | 1863 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| fred | CPILFESL | 1689 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| fred | DEXCHUS | 10681 | 8176 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| fred | DEXHKUS | 10680 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| fred | DEXSZUS | 10680 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| fred | DEXUSEU | 9423 | 6921 | 1999-01-04 00:00:00 | 2026-08-07 00:00:00 |
| fred | DEXUSUK | 10680 | 8178 | 1994-01-03 00:00:00 | 2026-08-07 00:00:00 |
| fred | DFF | 15575 | 11911 | 1994-01-01 00:00:00 | 2026-08-11 00:00:00 |
| fred | DGS10 | 10666 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| fred | DGS2 | 10664 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| fred | DGS30 | 10665 | 8157 | 1994-01-03 00:00:00 | 2026-08-11 00:00:00 |
| fred | DTWEXBGS | 16930 | 5166 | 2006-01-02 00:00:00 | 2026-08-07 00:00:00 |
| fred | FEDFUNDS | 359 | 356 | 1996-12-01 00:00:00 | 2026-07-01 00:00:00 |
| fred | GDP | 1331 | 130 | 1994-01-01 00:00:00 | 2026-04-01 00:00:00 |
| fred | GDPC1 | 1499 | 130 | 1994-01-01 00:00:00 | 2026-04-01 00:00:00 |
| fred | T10Y2Y | 8898 | 8159 | 1994-01-03 00:00:00 | 2026-08-12 00:00:00 |
| fred | T10YIE | 6646 | 5907 | 2003-01-02 00:00:00 | 2026-08-12 00:00:00 |
| fred | UNRATE | 741 | 390 | 1994-01-01 00:00:00 | 2026-07-01 00:00:00 |
| fred | VIXCLS | 8395 | 8238 | 1994-01-03 00:00:00 | 2026-08-12 00:00:00 |

## Evidence Grades

- Fundamental vintages retain their source and `available_from` timestamp; SEC rows require observed filing accessions, while any local Bloomberg rows use their database-as-of date.
- FRED GDP, real GDP, CPI, core CPI, unemployment and monthly Fed funds: ALFRED release/revision vintages.
- Daily rates, curves, FX, VIX and market credit spreads: non-revising observations available on the observation date.
- AKShare bars are observed unadjusted daily price/volume records; they do not establish historical index membership.
- Any local licensed market-cap/free-float rows are aggregate-only release evidence and are never published as observations.
- Corporate actions: event-time reconstruction using declaration dates; later vendor corrections are not yet separately versioned.
- Identifier mappings: current retrieval snapshots only. Historical effective-date mappings remain incomplete.
- Decision archives: retrospective cryptographic registration of existing walk-forward artifacts; availability is the archive timestamp, not the original rebalance date.

## Open Production Gaps

- Complete original filing and amendment vintages from July 2018 onward; SEC automated access remains blocked until a truthful identifying user agent is configured and accepted.
- Historical constituent/delisted-security membership and historical ticker/ISIN mappings for a survivorship-clean 1997 universe.
- Timestamped entity-mapped news and immutable sentiment vintages. No production sentiment rows are currently present.
- Genuine pre-1997 China/Hong Kong fundamentals are not established by the free stack; the 1997 test remains reconstructed rather than fully genuine PIT.

## DRL Decision

The production DRL challenger uses five Stable-Baselines3 PPO seeds over a chronological regional panel. All validation information ratios are currently negative, so the validation guard selects the constrained baseline optimiser with a 0% DRL live blend.
