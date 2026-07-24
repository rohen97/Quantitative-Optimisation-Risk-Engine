import pandas as pd
import pytest

from src.data.schemas import SCHEMAS
from src.data.validators import validate_finite_numeric, validate_prices, validate_schema, validate_unique_key


def test_validators_reject_missing_non_finite_and_duplicate_rows():
    valid = pd.DataFrame(
        {
            "security_id": ["AAA"],
            "trade_date": ["2026-01-01"],
            "source": ["mock"],
            "retrieved_at": ["2026-01-01"],
            "row_hash": ["abc"],
        }
    )
    validate_schema(valid, SCHEMAS["prices_daily"])

    with pytest.raises(ValueError):
        validate_finite_numeric(pd.DataFrame({"x": [float("inf")]}), ["x"])
    with pytest.raises(ValueError):
        validate_unique_key(pd.DataFrame({"security_id": ["AAA", "AAA"], "trade_date": ["2026-01-01", "2026-01-01"]}), ("security_id", "trade_date"))


def test_validate_prices_reports_duplicate_and_invalid_prices():
    result = validate_prices(
        pd.DataFrame(
            {
                "security_id": ["AAA", "AAA"],
                "trade_date": ["2026-01-01", "2026-01-01"],
                "adjusted_close": [100.0, -1.0],
                "source": ["mock", "mock"],
            }
        )
    )
    assert not result.valid
    assert {issue.rule for issue in result.issues} >= {"duplicate_natural_key", "positive_adjusted_close"}
