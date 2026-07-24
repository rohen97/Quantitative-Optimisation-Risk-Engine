import pandas as pd
import pytest

from src.reporting.column_resolver import canonicalise_dataframe, require_any, resolve_column, safe_numeric


def test_column_resolver_finds_candidates_and_numeric_default():
    frame = pd.DataFrame({"ticker": ["AAA"], "value": ["1.2"]})
    assert require_any(frame, ["security_id", "ticker"], "id") == "ticker"
    assert safe_numeric(frame, "value").iloc[0] == 1.2
    assert safe_numeric(frame, "missing", default=3.0).iloc[0] == 3.0
    with pytest.raises(ValueError):
        require_any(frame, ["missing"], "bad")


def test_column_resolver_canonicalises_aliases_without_mutating_source():
    frame = pd.DataFrame({"symbol": ["AAA"], "recommended_weight": [0.2]})
    result = canonicalise_dataframe(frame)
    assert resolve_column(result, "ticker", required=True) == "ticker"
    assert result["target_weight"].iloc[0] == 0.2
    assert "ticker" not in frame.columns
