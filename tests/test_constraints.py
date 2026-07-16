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
