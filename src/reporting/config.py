from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.utils.config import ROOT, load_yaml


@dataclass(frozen=True)
class ReportingConfig:
    output_root: Path
    archive_root: Path
    latest_folder: Path
    template_path: Path
    css_path: Path
    chart_format: str = "png"
    max_table_rows: int = 25
    pdf_enabled: bool = False
    generate_html: bool = True
    generate_markdown: bool = True
    generate_report_bundle: bool = True
    generate_static_charts: bool = True
    preserve_historical_runs: bool = True
    critical_sources: tuple[str, ...] = ("current_portfolio", "final_portfolio", "final_recommendations", "portfolio_risk_report")
    concentration_warning_weight: float = 0.10
    minimum_effective_holdings_warning: float = 10.0
    severe_loss_threshold: float = -0.20
    warning_loss_threshold: float = -0.10
    chart_dpi: int = 160


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def load_reporting_config(path: str | Path = "configs/reporting.yaml") -> ReportingConfig:
    raw = load_yaml(path).get("reporting", {})
    output = raw.get("output", {})
    charts = raw.get("charts", {})
    portfolio = raw.get("portfolio", {})
    stress = raw.get("stress", {})
    return ReportingConfig(
        output_root=_resolve(raw.get("output_root", "reports/outputs")),
        archive_root=_resolve(output.get("root", raw.get("archive_root", "reports/outputs/ic"))),
        latest_folder=_resolve(output.get("latest_directory", raw.get("latest_folder", "reports/outputs/ic/latest"))),
        template_path=_resolve(raw.get("template", "src/reporting/templates/investment_committee_report.html.j2")),
        css_path=_resolve(raw.get("css", "src/reporting/assets/ic_report.css")),
        chart_format=str(charts.get("image_format", raw.get("chart_format", "png"))),
        max_table_rows=int(raw.get("max_table_rows", charts.get("top_n", 25))),
        pdf_enabled=bool(output.get("generate_pdf_when_available", raw.get("pdf", {}).get("enabled", False))),
        generate_html=bool(output.get("generate_html", True)),
        generate_markdown=bool(output.get("generate_markdown", True)),
        generate_report_bundle=bool(output.get("generate_report_bundle", True)),
        generate_static_charts=bool(output.get("generate_static_charts", True)),
        preserve_historical_runs=bool(output.get("preserve_historical_runs", True)),
        critical_sources=tuple(raw.get("critical_sources", ("current_portfolio", "final_portfolio", "final_recommendations", "portfolio_risk_report"))),
        concentration_warning_weight=float(portfolio.get("concentration_warning_weight", 0.10)),
        minimum_effective_holdings_warning=float(portfolio.get("minimum_effective_holdings_warning", 10.0)),
        severe_loss_threshold=float(stress.get("severe_loss_threshold", -0.20)),
        warning_loss_threshold=float(stress.get("warning_loss_threshold", -0.10)),
        chart_dpi=int(charts.get("dpi", 160)),
    )
