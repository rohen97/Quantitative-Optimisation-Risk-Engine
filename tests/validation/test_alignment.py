import pandas as pd
import pytest

from src.validation.alignment import add_realisation_dates, validate_chronology


def test_realisation_dates_are_horizon_specific():
    result = add_realisation_dates(pd.DataFrame({"security_id": ["A", "A"], "forecast_date": ["2020-01-31", "2020-01-31"], "horizon": ["3M", "12M"]}))
    assert result["realisation_date"].tolist() == [pd.Timestamp("2020-04-30"), pd.Timestamp("2021-01-31")]


def test_invalid_horizon_fails():
    with pytest.raises(ValueError):
        add_realisation_dates(pd.DataFrame({"security_id": ["A"], "forecast_date": ["2020-01-31"], "horizon": ["1M"]}))


def test_chronology_applies_purge_and_embargo():
    splits = pd.DataFrame([{"train_end": "2020-01-01", "validation_start": "2020-01-10", "validation_end": "2020-02-01", "test_start": "2020-02-10"}])
    assert validate_chronology(splits, purge_days=5, embargo_days=5)["chronology_ok"].all()
