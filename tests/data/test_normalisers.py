import pandas as pd

from src.data.normalisers import normalise_fundamentals, normalise_macro_vintages, normalise_prices, record_hash


def test_normalisers_add_lineage_and_vintage_columns():
    prices = normalise_prices(pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "ticker": ["aaa", "aaa"], "close": [100, 105]}), "yfinance")
    assert prices["security_id"].tolist() == ["AAA", "AAA"]
    assert {"source", "retrieved_at", "row_hash", "trade_date", "close_price"}.issubset(prices.columns)

    fundamentals = normalise_fundamentals(
        pd.DataFrame({"ticker": ["AAA"], "fiscal_period_end": ["2026-03-31"], "filing_date": ["2026-04-30"], "revenue": [10.0]})
    )
    assert fundamentals.loc[0, "revenue"] == 10.0
    assert fundamentals.loc[0, "available_from"] == pd.Timestamp("2026-04-30")
    assert "vintage_id" in fundamentals

    macro = normalise_macro_vintages(
        pd.DataFrame({"series_id": ["GDP"], "observation_date": ["2026-03-31"], "vintage_date": ["2026-04-30"], "value": [1.2]})
    )
    assert macro.loc[0, "vintage_date"] == pd.Timestamp("2026-04-30")
    assert macro.loc[0, "available_from"] == pd.Timestamp("2026-04-30")


def test_record_hash_handles_mixed_missing_values_deterministically():
    frame = pd.DataFrame(
        {
            "security_id": ["AAA", "BBB"],
            "value": [1.5, float("nan")],
            "optional": [pd.NA, "reported"],
        }
    )

    first = record_hash(frame, ["security_id", "value", "optional"])
    second = record_hash(frame, ["security_id", "value", "optional"])

    assert first.equals(second)
    assert first.str.fullmatch(r"[0-9a-f]{64}").all()
