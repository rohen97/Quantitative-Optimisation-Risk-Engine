import pandas as pd

from src.data.point_in_time import point_in_time_fundamentals


def test_point_in_time_fundamentals_use_latest_available_filing():
    fundamentals = pd.DataFrame(
        {
            "security_id": ["AAA", "AAA"],
            "fiscal_period_end": ["2026-03-31", "2026-03-31"],
            "fiscal_period_type": ["quarterly", "quarterly"],
            "available_from": ["2026-03-31", "2026-06-30"],
            "revenue": [10.0, 20.0],
        }
    )
    as_of = point_in_time_fundamentals(fundamentals, "2026-04-30")
    assert len(as_of) == 1
    assert as_of.loc[0, "revenue"] == 10.0
