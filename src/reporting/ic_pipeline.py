from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
from typing import Any

import pandas as pd

from src.reporting.branch_comparison import build_branch_comparison, build_model_branch_comparison
from src.reporting.chart_factory import build_charts
from src.reporting.config import ReportingConfig, load_reporting_config
from src.reporting.data_loader import load_ic_data_from_config
from src.reporting.data_quality import build_data_quality_report, build_report_data_quality
from src.reporting.drl_governance import build_drl_governance, build_drl_governance_outputs
from src.reporting.executive_summary import build_executive_summary
from src.reporting.exposure_analysis import build_ic_exposure_outputs
from src.reporting.forecast_analysis import build_forecast_horizon_summary, build_forecast_summary, build_security_forecast_summary
from src.reporting.hedge_analysis import build_hedge_and_substitution_outputs, build_hedge_summary
from src.reporting.html_renderer import render_html_report
from src.reporting.manifest import build_report_manifest, write_manifest
from src.reporting.markdown_renderer import render_markdown_summary
from src.reporting.models import ICReportBundle
from src.reporting.narrative import build_narrative, build_narrative_points
from src.reporting.pdf_renderer import render_pdf
from src.reporting.portfolio_resolver import build_final_trade_recommendations, resolve_final_portfolio_from_bundle
from src.reporting.report_bundle import copy_to_latest, prepare_report_directory, write_report_bundle
from src.reporting.risk_analysis import build_portfolio_risk_summary, build_risk_summary, build_top_risk_contributors, top_risk_contributors
from src.reporting.regime_analysis import build_ic_regime_summary, build_regime_summary
from src.reporting.stress_analysis import build_stress_scenario_summary, worst_stress_scenarios


def _model_run_id(frames: dict[str, pd.DataFrame]) -> str:
    lineage = frames.get("model_run_lineage", pd.DataFrame())
    if not lineage.empty and "model_run_id" in lineage:
        return str(lineage.iloc[-1]["model_run_id"])
    return pd.Timestamp.now('UTC').strftime("ic-%Y%m%d%H%M%S")


def run_ic_reporting(
    config: ReportingConfig | None = None,
    *,
    settings: dict[str, Any] | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    model_run_id: str | None = None,
    backend_override: str | None = None,
    generate_pdf: bool | None = None,
    strict: bool = False,
    output_root: str | Path | None = None,
) -> ICReportBundle:
    """Generate an immutable IC package from already-computed model outputs."""
    del settings
    cfg = config or load_reporting_config()
    if output_root is not None:
        root = Path(output_root)
        cfg = replace(
            cfg,
            output_root=root,
            archive_root=root / "ic",
            latest_folder=root / "ic" / "latest",
        )
    if generate_pdf is not None:
        cfg = replace(cfg, pdf_enabled=bool(generate_pdf))
    bundle = load_ic_data_from_config(
        cfg.output_root,
        backend_override=backend_override,
        model_run_id=model_run_id,
        as_of_date=as_of_date,
    )
    model_run_id = model_run_id or bundle.model_run_id or _model_run_id(bundle.frames)
    bundle.model_run_id = model_run_id
    report_dir = prepare_report_directory(cfg.archive_root, cfg.latest_folder, model_run_id)
    resolved_portfolio = resolve_final_portfolio_from_bundle(bundle)
    final_portfolio = resolved_portfolio.portfolio
    quality = build_data_quality_report(bundle)
    report_quality = build_report_data_quality(bundle, final_portfolio, bundle.as_of_date)
    failed_rules = report_quality.loc[report_quality["status"].eq("fail")] if not report_quality.empty else pd.DataFrame()
    if strict and not failed_rules.empty:
        failures = "; ".join(f"{row.section}.{row.rule}" for row in failed_rules.itertuples())
        raise RuntimeError(f"Strict IC reporting validation failed: {failures}")
    exposure_outputs = build_ic_exposure_outputs(bundle, resolved_portfolio)
    analysis_outputs = {
        "model_branch_comparison": build_model_branch_comparison(bundle, resolved_portfolio),
        "forecast_horizon_summary": build_forecast_horizon_summary(bundle, resolved_portfolio),
        "security_forecast_summary": build_security_forecast_summary(bundle, resolved_portfolio),
        "regime_summary": build_ic_regime_summary(bundle, resolved_portfolio),
        "portfolio_risk_summary": build_portfolio_risk_summary(bundle, resolved_portfolio),
        "top_risk_contributors": build_top_risk_contributors(bundle),
        "stress_scenario_summary": build_stress_scenario_summary(bundle),
    }
    analysis_outputs.update(build_hedge_and_substitution_outputs(bundle))
    analysis_outputs.update(build_drl_governance_outputs(bundle))
    summary = build_executive_summary(
        bundle,
        resolved_portfolio,
        report_quality=report_quality,
    )
    nav = summary.get("current_nav_usd")
    trade_recommendations = build_final_trade_recommendations(bundle, resolved_portfolio, nav_usd=nav if isinstance(nav, (int, float)) else None)
    context = {
        "model_run_id": model_run_id,
        "as_of_date": str(bundle.as_of_date),
        "summary": summary,
        "selected_portfolio_source": resolved_portfolio.source_name,
        "fallback_used": resolved_portfolio.fallback_used,
        "portfolio_resolution_warnings": resolved_portfolio.warnings,
        "final_portfolio": final_portfolio.head(cfg.max_table_rows),
        "current_diagnostics": bundle.frames.get("current_diagnostics", pd.DataFrame()),
        "branch_comparison": build_branch_comparison(bundle).head(cfg.max_table_rows),
        "forecast_summary": build_forecast_summary(bundle),
        "risk_summary": build_risk_summary(bundle),
        "risk_contributors": top_risk_contributors(bundle),
        "worst_stress": worst_stress_scenarios(bundle),
        "regime_summary": build_regime_summary(bundle),
        "hedges": build_hedge_summary(bundle),
        "drl": build_drl_governance(bundle),
        "data_quality": quality,
        "report_data_quality": report_quality,
        "final_trade_recommendations": trade_recommendations.head(cfg.max_table_rows),
        **exposure_outputs,
        **analysis_outputs,
    }
    context["regime_summary_table"] = analysis_outputs["regime_summary"]
    context["top_risk_contributors_table"] = analysis_outputs["top_risk_contributors"]
    context["narrative"] = build_narrative(context["summary"])
    context["narrative_points"] = build_narrative_points(context["summary"])
    chart_paths = build_charts(context, report_dir, cfg.chart_format)
    context["chart_paths"] = {name: str(path.relative_to(report_dir)) for name, path in chart_paths.items()}
    html_path = render_html_report(context, cfg.template_path, report_dir / "investment_committee_report.html")
    markdown_path = render_markdown_summary(context, report_dir / "investment_committee_report.md")
    markdown_compatibility_path = report_dir / "investment_committee_summary.md"
    shutil.copy2(markdown_path, markdown_compatibility_path)
    quality_path = report_dir / "data_quality_report.csv"
    quality.to_csv(quality_path, index=False)
    report_quality_path = report_dir / "report_data_quality.csv"
    report_quality.to_csv(report_quality_path, index=False)
    executive_summary_path = report_dir / "executive_summary.csv"
    pd.DataFrame([summary]).to_csv(executive_summary_path, index=False)
    final_portfolio_path = report_dir / "final_portfolio_weights.csv"
    final_portfolio.to_csv(final_portfolio_path, index=False)
    for name, frame in exposure_outputs.items():
        frame.to_csv(report_dir / f"{name}.csv", index=False)
    for name, frame in analysis_outputs.items():
        frame.to_csv(report_dir / f"{name}.csv", index=False)
    hedge_summary_path = report_dir / "hedge_summary.csv"
    analysis_outputs["hedge_concepts"].to_csv(hedge_summary_path, index=False)
    trade_recommendations.to_csv(report_dir / "final_trade_recommendations.csv", index=False)
    if cfg.css_path.exists():
        shutil.copy2(cfg.css_path, report_dir / "ic_report.css")
    pdf_path = report_dir / "investment_committee_report.pdf"
    pdf_rendered = False
    if cfg.pdf_enabled:
        try:
            pdf_rendered = render_pdf(html_path, pdf_path)
        except Exception:
            pdf_rendered = False
    if not pdf_rendered:
        pdf_path = None
    report_bundle_path = write_report_bundle(
        report_dir / "report_bundle.json",
        {
            "metadata": {"model_run_id": model_run_id, "as_of_date": bundle.as_of_date, "selected_portfolio_source": resolved_portfolio.source_name},
            "executive_summary": summary,
            "portfolio_tables": {"final_portfolio": final_portfolio, **exposure_outputs, "final_trade_recommendations": trade_recommendations},
            "forecast_tables": {key: analysis_outputs[key] for key in ("forecast_horizon_summary", "security_forecast_summary")},
            "regime_tables": {"regime_summary": analysis_outputs["regime_summary"]},
            "risk_tables": {"portfolio_risk_summary": analysis_outputs["portfolio_risk_summary"], "top_risk_contributors": analysis_outputs["top_risk_contributors"]},
            "stress_tables": {"stress_scenario_summary": analysis_outputs["stress_scenario_summary"]},
            "hedge_tables": {"hedge_concepts": analysis_outputs["hedge_concepts"], "defensive_substitution_summary": analysis_outputs["defensive_substitution_summary"]},
            "drl_governance_tables": {key: analysis_outputs[key] for key in ("drl_governance_summary", "drl_constraint_trace", "drl_seed_summary")},
            "narratives": context["narrative_points"],
            "chart_paths": context["chart_paths"],
            "source_manifest": bundle.sources,
            "data_quality_flags": quality,
        },
    )
    manifest_payload = {
            "model_run_id": model_run_id,
            "as_of_date": str(bundle.as_of_date),
            "html": str(html_path),
            "markdown": str(markdown_path),
            "pdf": str(pdf_path) if pdf_path is not None else None,
            "report_bundle": str(report_bundle_path),
            "charts": {k: str(v) for k, v in chart_paths.items()},
            "selected_portfolio_source": resolved_portfolio.source_name,
            "backend": bundle.metadata.get("backend", "legacy_csv"),
            "fallback_used": resolved_portfolio.fallback_used,
            "portfolio_resolution_warnings": resolved_portfolio.warnings,
            "ic_outputs": sorted(
                [f"{name}.csv" for name in {**exposure_outputs, **analysis_outputs}]
                + [
                    "executive_summary.csv",
                    "final_portfolio_weights.csv",
                    "final_trade_recommendations.csv",
                    "hedge_summary.csv",
                ]
            ),
            "sources": [source.__dict__ for source in bundle.sources],
        }
    manifest_path = write_manifest(
        manifest_payload,
        report_dir / "manifest.json",
    )
    output_files = [
        html_path,
        markdown_path,
        markdown_compatibility_path,
        report_bundle_path,
        manifest_path,
        quality_path,
        report_quality_path,
        executive_summary_path,
        final_portfolio_path,
        hedge_summary_path,
        *[report_dir / f"{name}.csv" for name in {**exposure_outputs, **analysis_outputs}],
        report_dir / "final_trade_recommendations.csv",
    ]
    if pdf_path is not None:
        output_files.append(pdf_path)
    audit_manifest_path = write_manifest(
        build_report_manifest(
            report_run_id=model_run_id,
            bundle=bundle,
            config=cfg,
            output_files=output_files,
            pdf_rendered=pdf_rendered,
            readiness_status=str(summary.get("decision_readiness_status", "UNKNOWN")),
            warnings=tuple(resolved_portfolio.warnings),
        ),
        report_dir / "report_manifest.json",
    )
    copy_to_latest(report_dir, cfg.latest_folder)
    latest_html = cfg.latest_folder / html_path.name
    latest_markdown = cfg.latest_folder / markdown_path.name
    latest_manifest = cfg.latest_folder / manifest_path.name
    latest_quality = cfg.latest_folder / quality_path.name
    latest_pdf = cfg.latest_folder / pdf_path.name if pdf_path is not None else None
    warnings = list(resolved_portfolio.warnings)
    if cfg.pdf_enabled and not pdf_rendered:
        warnings.append("Optional PDF rendering was unavailable or failed.")
    return ICReportBundle(
        model_run_id,
        report_dir,
        cfg.latest_folder,
        latest_html,
        latest_markdown,
        latest_manifest,
        chart_paths,
        latest_quality,
        latest_pdf,
        cfg.latest_folder / report_bundle_path.name,
        cfg.latest_folder / audit_manifest_path.name,
        str(summary.get("decision_readiness_status", "UNKNOWN")),
        tuple(warnings),
    )
