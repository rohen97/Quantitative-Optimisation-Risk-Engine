# Production Point-In-Time Evidence

Point-in-time (PIT) data answers one strict question: what information could the
model actually have known at each decision timestamp? A later correction must
be a new vintage, never an overwrite of the earlier record.

## Required Columns

Every production vintage carries a stable entity or security identifier, source,
UTC availability timestamp, retrieval timestamp, and immutable vintage ID.
Economic observations additionally retain release and revision timestamps.
Financial statements retain fiscal period, period type, announcement timestamp,
currency and database-as-of availability.

## Local Tables

| Table | Purpose |
| --- | --- |
| `fundamental_vintages` | Original database snapshots and later statement revisions |
| `corporate_action_vintages` | Dividends, splits and other declared actions |
| `market_cap_vintages` | Historical shares, free float and market capitalisation |
| `identifier_vintages` | Ticker, FIGI, ISIN and issuer mappings with effective dates |
| `macro_release_vintages` | Original macro releases and revisions |
| `sentiment_vintages` | Timestamped, versioned entity sentiment |
| `decision_snapshot_manifests` | Hashes for universe, features, forecasts, ranks and weights |

Migration `012_create_production_pit_vintage_tables.sql` creates these tables and
their PIT indexes. Existing model-facing fundamentals use source
`bloomberg_database_as_of`, and the walk-forward loader retains every vintage,
filters on `available_from`, then selects the latest eligible vintage for each
fiscal period.

## Macro History

Run the resumable release-vintage pull:

```powershell
.\.venv\Scripts\python.exe scripts\run_macro_vintage_backfill.py `
  --start 1994-01-01 --skip-migrations
```

GDP, real GDP, CPI, core CPI and unemployment preserve ALFRED revisions. Daily
rates, yield curves, direct FX, VIX and credit spreads are explicitly configured
as non-revising and become available on their observation date. The pull commits
one series at a time and checkpoints each successful series.

## Decision Archives

Archive current walk-forward artifacts with deterministic hashes:

```powershell
.\.venv\Scripts\python.exe scripts\archive_walk_forward_snapshots.py
```

Future `run_walk_forward_validation.py` runs archive automatically. Existing
artifacts are labelled `retrospective_walk_forward_archive`: their data hashes
are reproducible, but the archive timestamp is today and is not backdated to the
original rebalance.

## Evidence Grades And Gaps

Genuine PIT evidence currently includes Bloomberg database-as-of fundamentals,
dated Bloomberg market-cap observations and ALFRED release vintages. Corporate
actions are event-time reconstructions. Identifier mappings observed today are
not historical mappings. Production news/sentiment vintages remain empty.

A genuine 1997 backtest also needs historical constituents, delisted securities
and identifier mappings plus pre-1997 financial vintages. Until those are
licensed and measured, the 1997 result must remain labelled reconstructed PIT,
not a fully genuine PIT backtest.

Aggregate status is published in
[`reports/outputs/production_pit_coverage.md`](../reports/outputs/production_pit_coverage.md).
