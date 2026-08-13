# Bloomberg Desktop API

The Bloomberg integration uses the logged-in Bloomberg Terminal session on the
same Windows workstation. It does not use or store an API key. Bloomberg's
licensed observations remain in `data/database/wolf.duckdb`, which is excluded
from Git.

## Install

Keep Bloomberg Terminal open and logged in, then run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-bloomberg.txt
.\.venv\Scripts\python.exe scripts\run_bloomberg_backfill.py --health-check
```

The Desktop API defaults to `127.0.0.1:8194`. Override it only when Bloomberg
support has given you a different local configuration:

```powershell
$env:BLOOMBERG_HOST='127.0.0.1'
$env:BLOOMBERG_PORT='8194'
```

## Chinese Equity Backfill

Generate and persist canonical Bloomberg identifiers before a large run:

```powershell
.\.venv\Scripts\python.exe scripts\run_bloomberg_backfill.py `
  --regions 'Mainland China' 'Hong Kong' `
  --sync-identifiers-only
```

Run a small resumable batch first:

```powershell
.\.venv\Scripts\python.exe scripts\run_bloomberg_backfill.py `
  --regions 'Mainland China' 'Hong Kong' `
  --start 1997-01-01 `
  --max-symbols 20 `
  --batch-size 10
```

Then run all mapped Chinese equities:

```powershell
.\.venv\Scripts\python.exe scripts\run_bloomberg_backfill.py `
  --regions 'Mainland China' 'Hong Kong' `
  --start 1997-01-01 `
  --batch-size 50 `
  --request-size 10 `
  --resume
```

Inspect local coverage without downloading data:

```powershell
.\.venv\Scripts\python.exe scripts\run_bloomberg_backfill.py `
  --regions 'Mainland China' 'Hong Kong' `
  --coverage-only
```

The default request includes split, normal-distribution, and abnormal-
distribution adjustments and stores adjusted OHLCV under source `bloomberg`.
Failures are written locally to
`data/locks/bloomberg_backfill_failures.csv` and skipped on later resumable runs.
Use `--retry-failures` after correcting an identifier or entitlement to retry
that quarantine.

## Production Point-In-Time Backfill

Apply migrations and inspect aggregate local coverage:

```powershell
.\.venv\Scripts\python.exe scripts\run_bloomberg_pit_backfill.py --coverage-only
.\.venv\Scripts\python.exe scripts\build_pit_coverage_report.py
```

The production PIT path stores separate immutable tables for fundamental
database snapshots, corporate actions, historical market capitalisation/free
float, identifier observations, macro releases, sentiment and decision
manifests. Model reads always filter `available_from <= decision timestamp`.

Prioritise the 601 securities actually touched by the current 60-month
walk-forward. Annual statements are first because the current feature pipeline
consumes annual fundamentals:

```powershell
.\.venv\Scripts\python.exe scripts\run_bloomberg_pit_backfill.py `
  --regions US UK DACH 'EU ex-DACH' 'Mainland China' 'Hong Kong' `
  --universe-file reports\outputs\walk_forward\historical_portfolio_weights.parquet `
  --datasets fundamentals --period-types Y `
  --start 2018-07-01 --request-size 600 --skip-migrations
```

Then add quarterly vintages for future quarterly-feature work:

```powershell
.\.venv\Scripts\python.exe scripts\run_bloomberg_pit_backfill.py `
  --regions US UK DACH 'EU ex-DACH' 'Mainland China' 'Hong Kong' `
  --universe-file reports\outputs\walk_forward\historical_portfolio_weights.parquet `
  --datasets fundamentals --period-types Q `
  --start 2018-07-01 --request-size 600 --skip-migrations
```

Finally, fill the complete mapped Chinese universe:

```powershell
.\.venv\Scripts\python.exe scripts\run_bloomberg_pit_backfill.py `
  --regions 'Mainland China' 'Hong Kong' `
  --datasets fundamentals --period-types Y Q `
  --start 2018-07-01 --request-size 1000 --skip-migrations
```

All commands are checkpointed at dataset/snapshot/universe granularity. If
Bloomberg reports `Daily capacity reached`, stop and rerun the identical command
after the entitlement resets; completed snapshots are skipped. Fundamentals-
only runs reuse local currencies and stop immediately on request-level errors,
avoiding unnecessary Bloomberg calls.

### Evidence Semantics

- `fundamental_vintages` uses the Bloomberg `FUNDAMENTAL_DATABASE_DATE`
  override. `available_from` is that database-as-of date, not today's retrieval
  date or a guessed filing lag.
- `market_cap_vintages` uses dated Bloomberg observations for shares, free
  float and market cap.
- `corporate_action_vintages` is an event-time reconstruction keyed by declared
  and ex-dates. Historical vendor corrections still require repeated snapshots.
- `identifier_vintages` currently records mappings observed today. It does not
  claim historical ticker/ISIN effective dates.
- Bloomberg rows in `data/database/wolf.duckdb` are licensed local evidence and
  must not be committed or redistributed. Only aggregate coverage is publishable.

The current aggregate status is generated at
`reports/outputs/production_pit_coverage.md`.

## Usage Controls

- Use only on the entitled Bloomberg workstation and under the firm's license.
- Do not commit, publish, or redistribute Bloomberg observations.
- Keep request batches small and use `--resume`; repeated full-history pulls can
  trigger Bloomberg data limits.
- Prefer `--universe-file` for validation-critical names before broad inventory
  enrichment; this changes ingestion order, not model portfolio boundaries.
- A successful API connection does not imply entitlement to every field.
- Use `WAPI <GO>` or `HELP HELP` in the Terminal for entitlement errors.
