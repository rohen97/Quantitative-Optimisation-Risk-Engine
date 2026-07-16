from pathlib import Path

from src.pipeline import run_full_pipeline


def test_full_pipeline_creates_risk_stress_hedge_outputs(tmp_path):
    outputs = run_full_pipeline(tmp_path)
    assert "risk_contribution_report" in outputs
    assert "stress_test_contribution_report" in outputs
    assert "defensive_substitution_recommendations" in outputs
    assert (Path(tmp_path) / "portfolio_risk_report.csv").exists()
    assert (Path(tmp_path) / "risk_contribution_report.csv").exists()
    assert (Path(tmp_path) / "stress_test_report.csv").exists()
    assert (Path(tmp_path) / "stress_test_contribution_report.csv").exists()
    assert (Path(tmp_path) / "hedge_recommendations.csv").exists()
    assert (Path(tmp_path) / "defensive_substitution_recommendations.csv").exists()
    assert (Path(tmp_path) / "risk_stress_hedge_summary.md").exists()
    assert "India" not in set(outputs["optimiser_input_dataset"]["region"])
