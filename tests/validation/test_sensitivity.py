from src.validation.sensitivity import run_parameter_sensitivity


def test_sensitivity_does_not_retune_parameters():
    parameters = {"risk_aversion": 2.0}
    result = run_parameter_sensitivity(parameters, [-0.1, 0.1], lambda values: {"score": values["risk_aversion"]})
    assert parameters == {"risk_aversion": 2.0}
    assert len(result) == 2
