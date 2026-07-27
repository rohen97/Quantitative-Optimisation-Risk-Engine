from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from jinja2 import Template

from .models import ProductionRunResult


def _serialise_result(result: ProductionRunResult) -> dict[str, Any]:
    return {
        "production_run_id": result.production_run_id,
        "mode": result.mode,
        "status": result.status,
        "approval_status": result.approval_status,
        "output_directory": str(result.output_directory),
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat(),
        "duration_seconds": (result.completed_at - result.started_at).total_seconds(),
        "step_results": [asdict(step) for step in result.step_results],
        "health_checks": [asdict(check) for check in result.health_checks],
        "drift_checks": [asdict(check) for check in result.drift_checks],
        "alerts": [asdict(alert) for alert in result.alerts],
        "critical_failures": list(result.critical_failures),
        "warnings": list(result.warnings),
    }


def write_run_status_reports(result: ProductionRunResult) -> dict[str, Path]:
    payload = _serialise_result(result)
    output = result.output_directory
    json_path = output / "production_status.json"
    markdown_path = output / "production_run_report.md"
    html_path = output / "production_status.html"
    json_path.write_text(json.dumps(payload, indent=2, default=str, sort_keys=True), encoding="utf-8")
    markdown = Template(
        """# Production Run Report

Run ID: `{{ production_run_id }}`

- Mode: `{{ mode }}`
- Status: `{{ status }}`
- Approval: `{{ approval_status }}`
- Started: `{{ started_at }}`
- Completed: `{{ completed_at }}`

## Steps
{% for step in step_results -%}
- `{{ step.name }}`: {{ step.status }} after {{ step.attempt_count }} attempt(s)
{% endfor %}

## Health Checks
{% for check in health_checks -%}
- `{{ check.check_name }}`: {{ check.status }} / {{ check.severity }} - {{ check.message }}
{% endfor %}

## Drift Checks
{% for check in drift_checks -%}
- `{{ check.drift_type }}.{{ check.metric_name }}`: {{ check.status }} - {{ check.notes or check.metric_value }}
{% endfor %}

## Critical Failures
{% for failure in critical_failures -%}
- {{ failure }}
{% else -%}
None.
{% endfor %}

## Warnings
{% for warning in warnings -%}
- {{ warning }}
{% else -%}
None.
{% endfor %}
"""
    ).render(**payload)
    markdown_path.write_text(markdown, encoding="utf-8")
    html = Template(
        """<!doctype html>
<html><head><meta charset="utf-8"><title>Wolf Production Status</title>
<style>body{font-family:Arial,sans-serif;margin:32px;line-height:1.45}code{background:#f2f2f2;padding:2px 4px}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px 8px}</style>
</head><body>
<h1>Wolf Production Status</h1>
<p><strong>Run:</strong> <code>{{ production_run_id }}</code></p>
<p><strong>Status:</strong> {{ status }} | <strong>Approval:</strong> {{ approval_status }}</p>
<h2>Steps</h2><table><tr><th>Step</th><th>Status</th><th>Attempts</th></tr>
{% for step in step_results %}<tr><td>{{ step.name }}</td><td>{{ step.status }}</td><td>{{ step.attempt_count }}</td></tr>{% endfor %}
</table>
<h2>Critical Failures</h2><ul>{% for failure in critical_failures %}<li>{{ failure }}</li>{% else %}<li>None.</li>{% endfor %}</ul>
<h2>Warnings</h2><ul>{% for warning in warnings %}<li>{{ warning }}</li>{% else %}<li>None.</li>{% endfor %}</ul>
</body></html>"""
    ).render(**payload)
    html_path.write_text(html, encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path, "html": html_path}


def write_global_status(output_root: Path, result: ProductionRunResult, latest_successful: str | None, latest_approved: str | None) -> dict[str, Path]:
    payload = {
        "latest_run": result.production_run_id,
        "latest_status": result.status,
        "latest_approval_status": result.approval_status,
        "latest_successful_run": latest_successful,
        "latest_approved_run": latest_approved,
        "latest_failure": result.production_run_id if result.status in {"FAILED", "BLOCKED"} else None,
        "database_status": "checked",
        "data_freshness_summary": [asdict(check) for check in result.health_checks if check.check_name.startswith("freshness_")],
        "current_approval_status": result.approval_status,
    }
    json_path = output_root / "status.json"
    html_path = output_root / "status.html"
    json_path.write_text(json.dumps(payload, indent=2, default=str, sort_keys=True), encoding="utf-8")
    html_path.write_text(
        f"<html><body><h1>Wolf Production Status</h1><pre>{json.dumps(payload, indent=2, default=str)}</pre></body></html>",
        encoding="utf-8",
    )
    return {"json": json_path, "html": html_path}
