import pandas as pd

from src.validation.regime_validation import validate_regime_probabilities


def test_regime_probabilities_must_normalise():
    passed = validate_regime_probabilities(pd.DataFrame({"a": [0.4], "b": [0.6]}), ["a", "b"])
    failed = validate_regime_probabilities(pd.DataFrame({"a": [0.7], "b": [0.6]}), ["a", "b"])
    assert passed.loc[0, "status"] == "PASS"
    assert failed.loc[0, "status"] == "FAIL"
