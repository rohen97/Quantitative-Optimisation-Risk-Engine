from src.optimisation.constraints import check_weight_caps
from src.pipeline import run_full_pipeline


def test_optimisation_constraints(tmp_path):
    proposed = run_full_pipeline(tmp_path)["proposed_portfolio"]
    assert check_weight_caps(proposed, 0.05)
