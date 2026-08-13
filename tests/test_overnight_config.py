from src.utils.config import load_yaml


def test_regression_step_isolated_from_full_universe_environment() -> None:
    config = load_yaml("configs/overnight.yaml")["overnight"]
    regression = next(
        step for step in config["steps"] if step["name"] == "full_regression_suite"
    )

    assert regression["environment"]["PIPELINE_INPUT_SOURCE"] == ""
    assert regression["environment"]["USE_MOCK_DATA"] == "true"


def test_publishable_pit_coverage_is_refreshed_before_release() -> None:
    config = load_yaml("configs/overnight.yaml")["overnight"]
    names = [step["name"] for step in config["steps"]]

    assert names.index("point_in_time_evidence_coverage") < names.index(
        "release_evidence"
    )
    assert names.index("production_pit_coverage") < names.index(
        "release_evidence"
    )
