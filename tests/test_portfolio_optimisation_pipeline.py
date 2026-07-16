from pathlib import Path

from src.pipeline import run_full_pipeline


def test_full_pipeline_creates_optimisation_outputs(tmp_path):
    outputs = run_full_pipeline(tmp_path)
    assert "portfolio_trade_list" in outputs
    assert "portfolio_constraint_report" in outputs
    assert "portfolio_optimisation_summary" in outputs
    assert outputs["portfolio_trade_list"].shape[0] > 0
    assert (Path(tmp_path) / "portfolio_trade_list.csv").exists()
    assert (Path(tmp_path) / "portfolio_constraint_report.csv").exists()
    assert (Path(tmp_path) / "portfolio_optimisation_summary.csv").exists()
    assert (Path(tmp_path) / "optimised_portfolio_cvar_constrained.csv").exists()


def test_india_not_readded_to_optimisation_outputs(tmp_path):
    outputs = run_full_pipeline(tmp_path)
    assert "India" not in set(outputs["optimiser_input_dataset"]["region"])
