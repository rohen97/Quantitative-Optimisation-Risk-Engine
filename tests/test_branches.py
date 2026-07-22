from src.branches.clean_sheet import run_clean_sheet_branch
from src.branches.llm_benchmark import run_llm_benchmark_branch
from src.branches.portfolio_aware import run_portfolio_aware_branch
from src.data_ingestion.universe import build_universe
from src.pipeline import run_full_pipeline


def test_active_universe_includes_eu_uk_and_us_but_not_india():
    universe = build_universe()
    assert "EU ex-DACH" in set(universe["region"])
    assert "UK" in set(universe["region"])
    assert "US" in set(universe["region"])
    assert "United States" in set(universe["country"])
    assert "India" not in set(universe["region"])
    assert "India" not in set(universe["country"])


def test_branch_outputs_are_created_from_pipeline(tmp_path):
    outputs = run_full_pipeline(tmp_path)
    scorecard = outputs["scorecard"]
    portfolio_aware = run_portfolio_aware_branch(outputs["diagnostics"], scorecard, outputs["features"])
    clean_sheet = run_clean_sheet_branch(scorecard)
    llm_benchmark = run_llm_benchmark_branch(scorecard)

    assert not portfolio_aware.empty
    assert "target_weight_portfolio_aware" in portfolio_aware.columns
    assert not clean_sheet.empty
    assert "clean_sheet_target_weight" in clean_sheet.columns
    assert not llm_benchmark.empty
    assert "investment_thesis" in llm_benchmark.columns
