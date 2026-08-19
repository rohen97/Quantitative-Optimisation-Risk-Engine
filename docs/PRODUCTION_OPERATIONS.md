# Production Operations

The production operations layer wraps the existing Wolf Quant Model. It does not change investment logic, scorecard formulas, optimiser objectives, risk limits, stress assumptions, hedge rules or DRL acceptance rules.

## Modes

- `daily`: full model pipeline, IC reporting, smoke validation, health, freshness and lightweight drift checks.
- `weekly`: daily coverage plus standard validation and broader drift checks.
- `monthly`: weekly coverage plus full validation, DRL seed/benchmark validation, sensitivity and ablation coverage where configured.
- `release_candidate`: complete governance run. It never deploys automatically and only updates the approved pointer when the approval gate passes.

## Commands

```bash
python scripts/run_production_pipeline.py --mode daily
python scripts/run_production_pipeline.py --mode weekly
python scripts/run_production_pipeline.py --mode monthly
python scripts/run_production_pipeline.py --mode release_candidate
```

Thin wrappers are also available:

```bash
python scripts/run_daily_production.py
python scripts/run_weekly_production.py
python scripts/run_monthly_production.py
python scripts/run_release_candidate.py
```

## Shadow Operation

Monthly and release-candidate runs record an immutable, pre-outcome decision
cycle after the pipeline succeeds. The record includes selected, classical,
regional-alpha, DRL, equal-weight and cap-weight challengers when their outputs
are available. Decision prices are frozen at record time; results are evaluated
only after the one-month due date.

```powershell
.\.venv\Scripts\python.exe scripts\run_regional_alpha_optimisation.py
.\.venv\Scripts\python.exe scripts\run_shadow_operation.py
.\.venv\Scripts\python.exe scripts\run_shadow_operation.py --evaluate-only
```

Three completed prospective monthly cycles beginning August 31, 2026 are
required. The August 14 cycle is a pre-freeze rehearsal and does not count.
Recording a second set of weights for an already-frozen date fails closed. Raw local observations remain
in ignored DuckDB tables; the tracked report contains aggregate status only.

The supervised-alpha challenger has a separate 3-month evidence clock. Freeze
the exact checksummed model and report once, before its first prospective
decision:

```powershell
.\.venv\Scripts\python.exe scripts\freeze_supervised_alpha.py --effective-date 2026-08-31
```

Its first outcome is due November 30, 2026. Twelve independent 3-month cohorts
require decisions spaced three months apart, so the earliest complete evidence
date is August 31, 2029. Monthly overlapping scores may be monitored but cannot
shorten this governance clock.

## Health And Diagnostics

```bash
python scripts/check_production_health.py
python scripts/check_data_freshness.py
python scripts/check_model_drift.py
python scripts/show_production_status.py
python scripts/send_test_alert.py
```

## Scheduling

Windows Task Scheduler helpers:

```powershell
scripts/windows/install_production_tasks.ps1
scripts/windows/uninstall_production_tasks.ps1
```

The task actions are location-independent and call the repository's `.venv`
interpreter. The monthly task follows `configs/production.yaml`: first Sunday
at 10:00 Asia/Singapore.

Linux cron examples are documented in `scripts/linux/wolf_model_cron.example`.

## Output Pointers

Every run is preserved under:

```text
reports/outputs/production/<production_run_id>/
```

Copied latest views are maintained without symlinks:

```text
reports/outputs/production/latest_successful/
reports/outputs/production/latest_approved/
```

A blocked or failed run never updates `latest_approved`.

## Alerts And Incidents

Alert sinks are local console and JSONL file by default. Email and Slack webhook sinks are disabled by default and read credentials only from environment variables. Tests and dry runs do not send real alerts.

Critical alerts open or update incidents. Repeated alerts with the same fingerprint increment the existing incident rather than creating duplicates.

## Guardrails

The operations layer:

- prevents concurrent runs with a production lock
- preserves failed run outputs
- records status, manifests and logs
- records immutable monthly shadow decisions without executing trades
- performs freshness and drift checks
- blocks approval on critical health, validation, point-in-time, hard constraint, final-weight, IC report or DRL governance failures
- never stores secrets in DuckDB, Parquet, manifests or logs
- never executes trades
