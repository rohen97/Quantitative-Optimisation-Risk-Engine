import pandas as pd

from src.validation.walk_forward import CASH_SECURITY_ID, _cash_mask


def test_walk_forward_uses_the_canonical_cash_identifier() -> None:
    portfolio = pd.DataFrame(
        {
            "security_id": ["CASH", "AAA"],
            "instrument_type": ["Cash", "Equity"],
        }
    )

    assert CASH_SECURITY_ID == "CASH"
    assert _cash_mask(portfolio).tolist() == [True, False]
