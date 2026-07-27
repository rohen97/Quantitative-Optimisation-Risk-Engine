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
- performs freshness and drift checks
- blocks approval on critical health, validation, point-in-time, hard constraint, final-weight, IC report or DRL governance failures
- never stores secrets in DuckDB, Parquet, manifests or logs
- never executes trades
