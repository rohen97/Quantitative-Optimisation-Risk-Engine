from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.run_bloomberg_pit_backfill import _load_universe_ids
from src.data_ingestion.bloomberg_pit import (
    fiscal_period_end,
    normalise_corporate_actions,
    normalise_fundamental_snapshot,
    normalise_identifier_snapshot,
    normalise_market_cap_history,
    reference_currency_map,
    to_model_fundamentals,
)
from src.data_ingestion.macro_vintages import normalise_macro_release_vintages


RETRIEVED = pd.Timestamp("2026-08-13 08:00:00")


def test_fundamental_snapshot_is_database_as_of_and_ard_preferred():
    payload = {
        "700 HK Equity": {
            "ARD_REVENUES": 100.0,
            "SALES_REV_TURN": 999.0,
            "ARD_NET_INC": 20.0,
            "ARD_TOT_CASH_FLOWS_FROM_OPS": 30.0,
            "ARD_TOT_ASSETS": 500.0,
            "LATEST_ANNOUNCEMENT_PERIOD": "2021:Q2",
            "ANNOUNCEMENT_DT": pd.Timestamp("2021-08-18"),
        }
    }
    frame = normalise_fundamental_snapshot(
        payload,
        {"700 HK Equity": "0700.HK"},
        {"700 HK Equity": "HKD"},
        "2021-08-31",
        "quarterly",
        RETRIEVED,
        "run",
    )
    assert len(frame) == 1
    assert frame.loc[0, "fiscal_period_end"] == pd.Timestamp("2021-06-30")
    assert frame.loc[0, "available_from"] == pd.Timestamp("2021-08-31")
    assert frame.loc[0, "revenue"] == 100_000_000.0
    assert frame.loc[0, "vintage_id"] == frame.loc[0, "row_hash"]

    model_frame = to_model_fundamentals(frame)
    assert model_frame.loc[0, "source"] == "bloomberg_database_as_of"
    assert model_frame.loc[0, "filing_date"] == pd.Timestamp("2021-08-18")


def test_market_cap_history_uses_bloomberg_million_unit_scale():
    history = pd.DataFrame(
        [
            {
                "provider_symbol": "700 HK Equity",
                "date": "2021-08-31",
                "CUR_MKT_CAP": 1_000.0,
                "EQY_SH_OUT": 100.0,
                "EQY_FLOAT": 60.0,
                "EQY_FREE_FLOAT_PCT": 60.0,
            }
        ]
    )
    frame = normalise_market_cap_history(
        history,
        {"700 HK Equity": "0700.HK"},
        {"700 HK Equity": "HKD"},
        RETRIEVED,
        "run",
    )
    assert frame.loc[0, "market_cap_local"] == 1_000_000_000.0
    assert frame.loc[0, "shares_outstanding"] == 100_000_000.0
    assert frame.loc[0, "free_float_market_cap_local"] == 600_000_000.0
    assert frame.loc[0, "available_from"] == pd.Timestamp("2021-08-31")


def test_reference_payload_normalises_identifiers_and_actions():
    payload = {
        "700 HK Equity": {
            "CRNCY": "HKD",
            "ID_ISIN": "KYG875721634",
            "ID_BB_GLOBAL": "BBG000BJ35N5",
            "DVD_HIST_ALL": [
                {
                    "Declared Date": pd.Timestamp("2025-03-19"),
                    "Ex-Date": pd.Timestamp("2025-05-16"),
                    "Record Date": pd.Timestamp("2025-05-19"),
                    "Payable Date": pd.Timestamp("2025-05-30"),
                    "Dividend Amount": 4.5,
                    "Dividend Type": "Final",
                }
            ],
            "EQY_DVD_HIST_SPLITS": [
                {
                    "Declared Date": pd.Timestamp("2014-03-19"),
                    "Ex-Date": pd.Timestamp("2014-05-15"),
                    "Dividend Amount": 5.0,
                    "Dividend Type": "Stock Split",
                }
            ],
        }
    }
    mapping = {"700 HK Equity": "0700.HK"}
    currencies = reference_currency_map(payload)
    identifiers = normalise_identifier_snapshot(payload, mapping, RETRIEVED, "run")
    actions = normalise_corporate_actions(payload, mapping, currencies, RETRIEVED, "run")
    assert set(identifiers["identifier_type"]) == {"isin", "figi"}
    assert set(actions["action_type"]) == {"final", "stock_split"}
    assert actions.loc[actions["action_type"].eq("stock_split"), "split_ratio"].iloc[0] == 5.0


def test_macro_release_vintages_track_initial_release_and_revision():
    observations = pd.DataFrame(
        {
            "series_id": ["GDP", "GDP"],
            "observation_date": ["2025-10-01", "2025-10-01"],
            "vintage_date": ["2026-01-15", "2026-02-15"],
            "available_from": ["2026-01-15", "2026-02-15"],
            "value": [2.5, 2.7],
            "unit": ["percent", "percent"],
            "frequency": ["quarterly", "quarterly"],
            "source": ["fred", "fred"],
            "retrieved_at": [RETRIEVED, RETRIEVED],
        }
    )
    frame = normalise_macro_release_vintages(observations, "run")
    assert frame["release_at"].nunique() == 1
    assert frame["release_at"].iloc[0] == pd.Timestamp("2026-01-15")
    assert frame["revision_at"].tolist() == [
        pd.Timestamp("2026-01-15"),
        pd.Timestamp("2026-02-15"),
    ]


def test_fiscal_period_parser_rejects_ambiguous_labels():
    assert fiscal_period_end("2020:A") == pd.Timestamp("2020-12-31")
    assert fiscal_period_end("2020:Q3") == pd.Timestamp("2020-09-30")
    assert fiscal_period_end("2020 S1") is None


def test_universe_file_deduplicates_security_ids(tmp_path: Path):
    path = tmp_path / "universe.parquet"
    pd.DataFrame({"security_id": ["SEC-2", "SEC-1", "SEC-2", None]}).to_parquet(path)
    assert _load_universe_ids(path) == ["SEC-1", "SEC-2"]
