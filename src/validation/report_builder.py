from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
import pandas as pd


SECTION_TITLES = {
    "data_integrity": "Data integrity",
    "leakage": "Point-in-time and leakage validation",
    "forecast": "Forecast accuracy",
    "distribution": "Distribution calibration",
    "binary": "Binary-event calibration",
    "risk": "Risk backtesting",
    "portfolio": "Portfolio performance",
    "costs": "Transaction-cost robustness",
    "benchmarks": "Benchmark comparison",
    "regime": "Regime performance",
    "regional": "Regional performance",
    "constraints": "Constraint compliance",
    "drl": "DRL governance",
    "sensitivity": "Sensitivity analysis",
    "ablation": "Ablation analysis",
    "stability": "Stability and concentration",
    "statistics": "Statistical confidence",
}


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No evaluable observations were available."
    columns = [str(column) for column in frame.columns]
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    rows.extend("| " + " | ".join("" if pd.isna(value) else str(value) for value in record) + " |" for record in frame.itertuples(index=False, name=None))
    return "\n".join(rows)


def build_validation_reports(
    output_directory: Path,
    validation_run_id: str,
    as_of_date: pd.Timestamp,
    execution_mode: str,
    approval_status: str,
    overall_score: float,
    critical_failures: tuple[str, ...],
    component_approvals: pd.DataFrame,
    section_frames: dict[str, pd.DataFrame],
    limitations: list[str],
    remediation: list[str],
) -> tuple[Path, Path]:
    template_directory = Path(__file__).parent / "templates"
    environment = Environment(loader=FileSystemLoader(template_directory), autoescape=select_autoescape(["html"]))
    sections = {key: _markdown_table(section_frames.get(key, pd.DataFrame())) for key in SECTION_TITLES}
    production_recommendation = (
        "Do not deploy to production until all critical failures are remediated and historical point-in-time validation is complete."
        if approval_status != "APPROVED"
        else "The model meets the configured governance thresholds for controlled deployment."
    )
    context = {
        "validation_run_id": validation_run_id,
        "as_of_date": as_of_date.isoformat(),
        "execution_mode": execution_mode,
        "approval_status": approval_status,
        "overall_score": overall_score,
        "critical_failures": critical_failures,
        "component_table": _markdown_table(component_approvals),
        "component_table_html": component_approvals.to_html(index=False, border=0),
        "sections": sections,
        "html_sections": {SECTION_TITLES[key]: value for key, value in sections.items()},
        "limitations": limitations,
        "remediation": remediation,
        "production_recommendation": production_recommendation,
    }
    markdown_path = output_directory / "model_approval_report.md"
    html_path = output_directory / "model_approval_report.html"
    markdown_path.write_text(environment.get_template("model_validation_report.md.j2").render(**context), encoding="utf-8")
    html_path.write_text(environment.get_template("model_validation_report.html.j2").render(**context), encoding="utf-8")
    return markdown_path, html_path
