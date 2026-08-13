from __future__ import annotations

from datetime import date

import pandas as pd

from src.data_ingestion.bloomberg_adapter import (
    PRICE_COLUMNS,
    bloomberg_equity_symbol,
    bloomberg_symbol_for_row,
    normalise_historical_payload,
)


def test_bloomberg_equity_symbol_maps_core_model_exchanges():
    assert bloomberg_equity_symbol("0700.HK", "HK") == "700 HK Equity"
    assert bloomberg_equity_symbol("000001.SHE", "SHE") == "000001 CH Equity"
    assert bloomberg_equity_symbol("600519.SHG", "SHG") == "600519 CH Equity"
    assert bloomberg_equity_symbol("AAPL.US", "US") == "AAPL US Equity"
    assert bloomberg_equity_symbol("VOD.LSE", "LSE") == "VOD LN Equity"
    assert bloomberg_equity_symbol("SAP.XETRA", "XETRA") == "SAP GY Equity"


def test_bloomberg_symbol_uses_explicit_override_and_isin_fallback():
    assert (
        bloomberg_symbol_for_row(
            {
                "security_id": "CUSTOM.ID",
                "exchange_code": "UNKNOWN",
                "bloomberg_ticker": "CUSTOM JP Equity",
                "isin": pd.NA,
            }
        )
        == "CUSTOM JP Equity"
    )
    assert (
        bloomberg_symbol_for_row(
            {
                "security_id": "CUSTOM.ID",
                "exchange_code": "UNKNOWN",
                "bloomberg_ticker": pd.NA,
                "isin": "US0378331005",
            }
        )
        == "/isin/US0378331005"
    )


def test_bloomberg_historical_response_is_normalised_to_price_schema():
    payload = {
        "securityData": {
            "security": "700 HK Equity",
            "fieldExceptions": [],
            "fieldData": [
                {
                    "date": date(2025, 1, 2),
                    "PX_OPEN": 410.0,
                    "PX_HIGH": 418.0,
                    "PX_LOW": 408.0,
                    "PX_LAST": 416.0,
                    "PX_VOLUME": 20_733_037,
                },
                {
                    "date": date(2025, 1, 3),
                    "PX_OPEN": 414.0,
                    "PX_HIGH": 417.0,
                    "PX_LOW": 410.0,
                    "PX_LAST": 414.2,
                    "PX_VOLUME": 16_843_241,
                },
            ],
        }
    }
    frame, errors = normalise_historical_payload(payload)
    assert errors == {}
    assert list(frame.columns) == PRICE_COLUMNS
    assert frame["ticker"].eq("700 HK Equity").all()
    assert frame["close"].tolist() == [416.0, 414.2]
    assert frame["volume"].tolist() == [20_733_037, 16_843_241]
    assert frame.loc[0, "return"] == 0.0
    assert frame.loc[1, "return"] == (414.2 / 416.0) - 1.0


def test_bloomberg_security_error_is_preserved_without_rows():
    payload = {
        "securityData": {
            "security": "NOTREAL HK Equity",
            "securityError": {
                "category": "BAD_SEC",
                "message": "Unknown/Invalid security",
            },
            "fieldExceptions": [],
            "fieldData": [],
        }
    }
    frame, errors = normalise_historical_payload(payload)
    assert frame.empty
    assert errors == {"NOTREAL HK Equity": "Unknown/Invalid security"}
