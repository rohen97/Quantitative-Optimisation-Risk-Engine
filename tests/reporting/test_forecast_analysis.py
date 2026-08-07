import pandas as pd

from src.reporting.forecast_analysis import build_security_forecast_summary
from src.reporting.models import ICDataBundle
from src.reporting.portfolio_resolver import ResolvedPortfolio


def test_security_forecast_summary_limits_rows_to_resolved_holdings():
    forecasts = pd.DataFrame(
        {
            "security_id": ["A", "B"],
            "ticker": ["AAA", "BBB"],
            "expected_total_return": [0.1, 0.2],
            "p5_return": [-0.1, -0.2],
            "p50_return": [0.1, 0.2],
            "p95_return": [0.3, 0.4],
        }
    )
    bundle = ICDataBundle({f"ml_forecasts_{horizon}m": forecasts for horizon in (3, 6, 9, 12)})
    resolved = ResolvedPortfolio(
        pd.DataFrame({"security_id": ["B"], "ticker": ["BBB"], "target_weight": [1.0]}),
        "test",
        False,
        (),
    )

    result = build_security_forecast_summary(bundle, resolved)

    assert len(result) == 4
    assert set(result["security_id"]) == {"B"}
