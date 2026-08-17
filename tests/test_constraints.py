import pandas as pd

from src.optimisation.constraints import apply_diversification_caps, build_eligibility_mask


def test_hard_exclusions_get_zero_eligibility():
    data = pd.DataFrame(
        {
            "instrument_type": ["Equity", "ETF"],
            "listing_status": ["Active", "Active"],
            "final_recommendation": ["Buy", "Buy"],
            "liquidity_score": [80, 80],
            "average_daily_value_usd": [10_000_000, 10_000_000],
            "dividend_cut_probability": [0.10, 0.10],
            "large_drawdown_probability_12m": [0.10, 0.10],
            "forecast_uncertainty_score": [30, 30],
            "tail_risk_score": [30, 30],
            "regime_exclusion_flag": [False, False],
            "reframing_exclusion_flag": [False, False],
            "alt_data_exclusion_flag": [False, False],
        }
    )
    mask = build_eligibility_mask(data, {"minimum_liquidity_score": 40})
    assert mask.tolist() == [True, False]


def test_diversification_caps_respect_single_name_cap():
    data = pd.DataFrame({"sector": ["A"] * 20, "country": ["C"] * 20, "region": ["R"] * 20, "currency": ["USD"] * 20})
    weights = pd.Series([1.0] + [0.0] * 19)
    capped = apply_diversification_caps(weights, data, {"max_single_name_weight": 0.05})
    assert capped.max() <= 0.05 + 1e-9


def test_hard_eligibility_never_falls_back_to_avoid():
    data = pd.DataFrame(
        {
            "final_recommendation": ["Avoid"],
            "liquidity_score": [100],
            "average_daily_value_usd": [100_000_000],
            "dividend_cut_probability": [0.0],
            "large_drawdown_probability_12m": [0.0],
            "forecast_uncertainty_score": [0],
            "tail_risk_score": [0],
        }
    )
    assert not build_eligibility_mask(data).any()


def test_diversification_solver_enforces_all_group_caps():
    data = pd.DataFrame(
        {
            "sector": [f"S{i % 4}" for i in range(40)],
            "country": [f"C{i % 5}" for i in range(40)],
            "region": [f"R{i % 4}" for i in range(40)],
            "currency": [f"CUR{i % 3}" for i in range(40)],
        }
    )
    weights = pd.Series(range(40, 0, -1), dtype=float)
    limits = {
        "max_single_name_weight": 0.05,
        "max_sector_weight": 0.25,
        "max_country_weight": 0.30,
        "max_region_weight": 0.40,
        "max_currency_weight": 0.40,
    }
    capped = apply_diversification_caps(weights, data, limits)
    assert capped.attrs["feasible"]
    assert abs(float(capped.sum()) - 1.0) < 1e-9
    assert capped.max() <= 0.05 + 1e-9
    for column, limit in [
        ("sector", 0.25),
        ("country", 0.30),
        ("region", 0.40),
        ("currency", 0.40),
    ]:
        assert capped.groupby(data[column]).sum().max() <= limit + 1e-9


def test_diversification_solver_reports_infeasible_group_system():
    data = pd.DataFrame(
        {
            "sector": ["S"] * 20,
            "country": ["C"] * 20,
            "region": ["R"] * 20,
            "currency": ["USD"] * 20,
        }
    )
    capped = apply_diversification_caps(
        pd.Series(1.0, index=data.index),
        data,
        {"max_single_name_weight": 0.05, "max_sector_weight": 0.25},
    )
    assert not capped.attrs["feasible"]
    assert capped.sum() == 0


def test_diversification_solver_uses_bounded_cash_before_relaxing_caps():
    countries = ["US"] * 10 + ["UK"] * 4 + ["HK"] * 3 + ["CH"] * 2 + ["FR"]
    data = pd.DataFrame(
        {
            "sector": [f"S{i % 5}" for i in range(20)],
            "country": countries,
            "region": [f"R{i % 5}" for i in range(20)],
            "currency": [f"CUR{i % 5}" for i in range(20)],
        }
    )
    capped = apply_diversification_caps(
        pd.Series(1.0, index=data.index),
        data,
        {
            "max_single_name_weight": 0.05,
            "max_country_weight": 0.30,
            "maximum_cash_weight": 0.25,
        },
    )
    assert capped.attrs["feasible"]
    assert abs(float(capped.sum()) + capped.attrs["cash_weight"] - 1.0) < 1e-9
    assert abs(float(capped.attrs["cash_weight"]) - 0.20) < 1e-9
