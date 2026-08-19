from src.utils.config import load_yaml


def test_regression_step_isolated_from_full_universe_environment() -> None:
    config = load_yaml("configs/overnight.yaml")["overnight"]
    regression = next(
        step for step in config["steps"] if step["name"] == "full_regression_suite"
    )

    assert regression["environment"]["PIPELINE_INPUT_SOURCE"] == ""
    assert regression["environment"]["USE_MOCK_DATA"] == "true"
    assert config["environment"]["BLOOMBERG_DESKTOP_ENABLED"] == "false"


def test_publishable_pit_coverage_is_refreshed_before_release() -> None:
    config = load_yaml("configs/overnight.yaml")["overnight"]
    names = [step["name"] for step in config["steps"]]

    assert names.index("point_in_time_evidence_coverage") < names.index(
        "release_evidence"
    )
    assert names.index("production_pit_coverage") < names.index(
        "release_evidence"
    )
    assert names.index("free_data_evidence") < names.index("release_evidence")
    assert names.index("credential_history_audit") < names.index(
        "release_evidence"
    )
    price_summary = next(
        step for step in config["steps"] if step["name"] == "refresh_price_summaries"
    )
    assert "--force" in price_summary["command"]


def test_final_governance_run_uses_strict_release_candidate_mode() -> None:
    config = load_yaml("configs/overnight.yaml")["overnight"]
    validation = next(
        step for step in config["steps"] if step["name"] == "full_governance_validation"
    )

    assert "release_candidate" in validation["command"]
    assert "--strict" in validation["command"]


def test_expensive_drl_validation_runs_once_after_walk_forward_refresh() -> None:
    config = load_yaml("configs/overnight.yaml")["overnight"]
    names = [step["name"] for step in config["steps"]]
    phase_two = next(
        step for step in config["steps"] if step["name"] == "global_model_and_drl"
    )
    governed_drl = next(
        step
        for step in config["steps"]
        if step["name"] == "standalone_drl_validation"
    )

    assert phase_two["environment"]["DRL_MOCK_MODE"] == "true"
    assert governed_drl["environment"]["DRL_MOCK_MODE"] == "false"
    assert names.index("walk_forward_full") < names.index(
        "standalone_drl_validation"
    )
    assert names.index("standalone_drl_validation") < names.index(
        "full_governance_validation"
    )
