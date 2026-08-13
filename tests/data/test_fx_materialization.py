from __future__ import annotations

import pandas as pd
import pytest

from src.data.fx_materialization import fx_rates_from_macro_vintages


def test_fx_rates_from_macro_vintages_maps_direct_and_inverse_quotes() -> None:
    vintages = pd.DataFrame(
        {
            "series_id": ["DEXCHUS", "DEXUSEU", "UNRATE"],
            "observation_date": ["2024-01-02"] * 3,
            "available_from": ["2024-01-02"] * 3,
            "retrieved_at": ["2024-01-03"] * 3,
            "value": [7.1, 1.25, 3.9],
        }
    )

    result = fx_rates_from_macro_vintages(vintages).set_index("quote_currency")

    assert set(result.index) == {"CNY", "EUR"}
    assert result.loc["CNY", "rate"] == pytest.approx(7.1)
    assert result.loc["EUR", "rate"] == pytest.approx(0.8)
    assert result.loc["CNY", "base_currency"] == "USD"
    assert result.loc["CNY", "source"] == "fred_macro_vintage"


def test_fx_rates_from_macro_vintages_rejects_future_availability() -> None:
    vintages = pd.DataFrame(
        {
            "series_id": ["DEXHKUS", "DEXHKUS"],
            "observation_date": ["2024-01-02", "2024-01-03"],
            "available_from": ["2024-01-02", "2024-01-04"],
            "value": [7.8, 7.81],
        }
    )

    result = fx_rates_from_macro_vintages(vintages)

    assert result["rate_date"].tolist() == [pd.Timestamp("2024-01-02")]


def test_fx_rates_from_macro_vintages_keeps_earliest_observed_duplicate() -> None:
    vintages = pd.DataFrame(
        {
            "series_id": ["DEXSZUS", "DEXSZUS"],
            "observation_date": ["2024-01-02", "2024-01-02"],
            "available_from": ["2024-01-02", "2024-01-02"],
            "retrieved_at": ["2024-01-03", "2024-01-04"],
            "value": [0.85, 99.0],
        }
    )

    result = fx_rates_from_macro_vintages(vintages)

    assert len(result) == 1
    assert result.iloc[0]["rate"] == pytest.approx(0.85)
