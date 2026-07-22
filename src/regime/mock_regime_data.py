from __future__ import annotations

import numpy as np
import pandas as pd


FACTOR_COLUMNS = [
    "global_equity_return",
    "regional_equity_return",
    "value_factor",
    "quality_factor",
    "low_vol_factor",
    "momentum_factor",
    "dividend_factor",
    "small_cap_factor",
    "credit_proxy",
    "rates_proxy",
    "inflation_proxy",
    "fx_proxy",
    "commodity_proxy",
    "china_policy_proxy",
    "europe_recession_proxy",
    "uk_rate_pressure_proxy",
]

REGIONS = ["Global", "DACH", "EU ex-DACH", "UK", "US", "Mainland China", "Hong Kong"]


def build_mock_factor_lens(periods: int = 180, seed: int = 42) -> pd.DataFrame:
    """Generate deterministic regional factor lens data for mock regime modeling."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=periods)
    rows = []
    for region in REGIONS:
        region_bias = {
            "Global": 0.0,
            "DACH": -0.0001,
            "EU ex-DACH": -0.00005,
            "UK": -0.00002,
            "US": 0.00003,
            "Mainland China": -0.00015,
            "Hong Kong": -0.00012,
        }[region]
        for idx, date in enumerate(dates):
            stress_cycle = np.sin(idx / 19) * 0.01
            inflation_cycle = np.cos(idx / 31) * 0.006
            row = {"date": date, "region": region}
            for factor in FACTOR_COLUMNS:
                row[factor] = float(rng.normal(region_bias, 0.01) + stress_cycle * (factor in {"credit_proxy", "china_policy_proxy", "europe_recession_proxy"}) + inflation_cycle * (factor == "inflation_proxy"))
            rows.append(row)
    return pd.DataFrame(rows)
