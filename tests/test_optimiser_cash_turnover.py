import pandas as pd

from src.optimisation.optimisers import _apply_turnover_limit


def test_hard_cash_cap_overrides_soft_turnover_from_all_cash() -> None:
    data = pd.DataFrame(
        {
            "current_weight": [0.0] * 20,
            "instrument_type": ["Equity"] * 20,
            "listing_status": ["Active"] * 20,
            "final_recommendation": ["Buy"] * 20,
            "sector": [f"S{i % 5}" for i in range(20)],
            "country": [f"C{i % 5}" for i in range(20)],
            "region": [f"R{i % 4}" for i in range(20)],
            "currency": [f"CUR{i % 4}" for i in range(20)],
        }
    )
    target = pd.Series([0.05] * 20)
    target.attrs.update(feasible=True, status="optimal", cash_weight=0.0)

    result = _apply_turnover_limit(
        target,
        data,
        pd.Series(True, index=data.index),
        {
            "max_single_name_weight": 0.05,
            "maximum_cash_weight": 0.25,
            "maximum_turnover": 0.35,
        },
    )

    assert abs(float(result.sum()) - 1.0) < 1.0e-12
    assert float(result.attrs["cash_weight"]) == 0.0
    assert result.attrs["turnover_constraint_skipped_for_infeasible_current"]
    assert not result.attrs["turnover_constraint_applied"]
