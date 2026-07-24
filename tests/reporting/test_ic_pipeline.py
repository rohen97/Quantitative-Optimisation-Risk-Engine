import pandas as pd
import pytest

from src.reporting.config import ReportingConfig
from src.reporting.ic_pipeline import run_ic_reporting


def test_ic_pipeline_creates_report_bundle(tmp_path):
    out = tmp_path / "outputs"
    out.mkdir()
    pd.DataFrame({"ticker": ["AAA"], "final_selected_weight": [0.1]}).to_csv(out / "final_recommendations.csv", index=False)
    pd.DataFrame({"portfolio_var_5": [-0.1]}).to_csv(out / "portfolio_risk_report.csv", index=False)
    pd.DataFrame({"scenario_name": ["shock"], "portfolio_loss_pct": [-0.2]}).to_csv(out / "stress_test_report.csv", index=False)
    pd.DataFrame({"dominant_regime": ["stable"], "wolf_chaos_index": [10]}).to_csv(out / "regime_dashboard_summary.csv", index=False)
    pd.DataFrame({"model_run_id": ["run1"]}).to_csv(out / "model_run_lineage.csv", index=False)
    template = tmp_path / "template.html.j2"
    template.write_text("{{ model_run_id }}", encoding="utf-8")
    css = tmp_path / "style.css"
    css.write_text("body{}", encoding="utf-8")
    cfg = ReportingConfig(out, tmp_path / "ic", tmp_path / "latest", template, css)
    bundle = run_ic_reporting(cfg)
    assert bundle.html_path.exists()
    assert bundle.markdown_path.exists()
    assert (bundle.latest_dir / "investment_committee_report.html").exists()
    assert (bundle.latest_dir / "investment_committee_summary.md").exists()


def test_ic_pipeline_runtime_overrides_create_canonical_outputs(tmp_path):
    out = tmp_path / "outputs"
    out.mkdir()
    pd.DataFrame(
        {
            "security_id": ["sec-1"],
            "ticker": ["AAA"],
            "final_selected_weight": [1.0],
        }
    ).to_csv(out / "final_recommendations.csv", index=False)
    pd.DataFrame({"portfolio_var_5": [-0.1]}).to_csv(
        out / "portfolio_risk_report.csv", index=False
    )
    pd.DataFrame(
        {"scenario_name": ["shock"], "portfolio_loss_pct": [-0.2]}
    ).to_csv(out / "stress_test_report.csv", index=False)
    template = tmp_path / "template.html.j2"
    template.write_text("{{ model_run_id }}", encoding="utf-8")
    css = tmp_path / "style.css"
    css.write_text("body{}", encoding="utf-8")
    cfg = ReportingConfig(out, out / "ic", out / "ic" / "latest", template, css)

    result = run_ic_reporting(
        cfg,
        model_run_id="historical-run",
        as_of_date="2026-06-30",
        backend_override="legacy_csv",
        generate_pdf=False,
    )

    assert result.model_run_id == "historical-run"
    assert result.bundle_path is not None and result.bundle_path.exists()
    assert result.report_manifest_path is not None and result.report_manifest_path.exists()
    for filename in (
        "investment_committee_report.md",
        "executive_summary.csv",
        "final_portfolio_weights.csv",
        "hedge_summary.csv",
    ):
        assert (result.latest_dir / filename).exists()


def test_ic_pipeline_strict_mode_rejects_failed_quality_rules(tmp_path):
    out = tmp_path / "outputs"
    out.mkdir()
    pd.DataFrame(
        {"security_id": ["sec-1"], "ticker": ["AAA"], "final_selected_weight": [1.0]}
    ).to_csv(out / "final_recommendations.csv", index=False)
    template = tmp_path / "template.html.j2"
    template.write_text("{{ model_run_id }}", encoding="utf-8")
    css = tmp_path / "style.css"
    css.write_text("body{}", encoding="utf-8")
    cfg = ReportingConfig(out, out / "ic", out / "latest", template, css)

    with pytest.raises(RuntimeError, match="Strict IC reporting validation failed"):
        run_ic_reporting(cfg, strict=True, generate_pdf=False)
