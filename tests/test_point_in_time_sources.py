from __future__ import annotations

from datetime import date

import pandas as pd

from src.data_ingestion.point_in_time_sources import (
    BeamSecMetadataClient,
    EodhdReferenceHistoryClient,
    NasdaqMergentClient,
    SecSubmissionsClient,
)
from src.validation.leakage import point_in_time_evidence_report


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class _BeamHttp:
    def post_json(self, _url, payload, headers=None):
        assert headers and headers["api-key"] == "beam-test"
        if "publicly_listed_security" in payload["query"]:
            return _Response(
                {
                    "data": {
                        "publicly_listed_security": [
                            {"entity_cik": 320193, "exchange": "NASDAQ", "ticker": "AAPL"}
                        ]
                    }
                }
            )
        return _Response(
            {
                "data": {
                    "filing": [
                        {
                            "acceptance_datetime": "2020-10-29T18:06:25Z",
                            "accession_number": 12345,
                            "entity_cik": 320193,
                            "filing_date": "2020-10-30",
                            "filing_index_url": "https://example.test/filing",
                            "form_type": "10-K",
                            "report_date": "2020-09-26",
                        }
                    ]
                }
            }
        )


def test_beam_metadata_preserves_observed_acceptance(monkeypatch):
    monkeypatch.setenv("BEAM_API_KEY", "beam-test")
    client = BeamSecMetadataClient(_BeamHttp())
    cik = client.ticker_cik("aapl")
    frame = client.filings(
        "AAPL.US",
        cik,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
        retrieved_at=pd.Timestamp("2026-08-13"),
        ingestion_run_id="run-1",
    )
    assert cik == "320193"
    assert frame.loc[0, "acceptance_datetime"] == pd.Timestamp("2020-10-29 18:06:25")
    assert frame.loc[0, "report_date"] == pd.Timestamp("2020-09-26")


class _SecHttp:
    def get(self, url, headers=None):
        assert headers and headers["User-Agent"] == "wolf-test contact@example.test"
        if "company_tickers" in url:
            return _Response(
                {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
            )
        return _Response(
            {
                "filings": {
                    "recent": {
                        "acceptanceDateTime": ["2020-10-29T18:06:25.000Z"],
                        "accessionNumber": ["0000320193-20-000096"],
                        "filingDate": ["2020-10-30"],
                        "form": ["10-K"],
                        "reportDate": ["2020-09-26"],
                    },
                    "files": [],
                }
            }
        )


def test_sec_submissions_preserve_observed_acceptance(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "wolf-test contact@example.test")
    client = SecSubmissionsClient(_SecHttp())
    cik = client.ticker_ciks()["AAPL"]
    frame = client.filings(
        "AAPL.US",
        cik,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
        retrieved_at=pd.Timestamp("2026-08-13"),
        ingestion_run_id="run-sec",
    )
    assert cik == "0000320193"
    assert frame.loc[0, "acceptance_datetime"] == pd.Timestamp(
        "2020-10-29 18:06:25"
    )
    assert frame.loc[0, "source"] == "sec_edgar_submissions"


class _NasdaqHttp:
    def get(self, _url, params=None):
        assert params and params["api_key"] == "nasdaq-test"
        columns = [
            {"name": "compnumber"},
            {"name": "reportdate"},
            {"name": "reporttype"},
            {"name": "mapcode"},
            {"name": "amount"},
            {"name": "currency"},
        ]
        values = [
            [1, "2015-09-26", "A", -3887, 1000.0, "USD"],
            [1, "2015-09-26", "A", -3994, 100.0, "USD"],
            [1, "2015-09-26", "A", -873, 2000.0, "USD"],
            [1, "2015-09-26", "A", -4497, 800.0, "USD"],
        ]
        return _Response(
            {"datatable": {"columns": columns, "data": values, "meta": {}}}
        )


def test_nasdaq_mergent_uses_conservative_availability_lag(monkeypatch):
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "nasdaq-test")
    frame = NasdaqMergentClient(
        _NasdaqHttp(), reporting_lag_days=120
    ).annual_fundamentals(
        "AAPL.US",
        "AAPL",
        start_year=2015,
        end_year=2015,
        retrieved_at=pd.Timestamp("2026-08-13"),
        ingestion_run_id="run-2",
    )
    assert len(frame) == 1
    assert frame.loc[0, "available_from"] == pd.Timestamp("2016-01-24")
    assert frame.loc[0, "revenue"] == 1000.0
    assert pd.isna(frame.loc[0, "filing_date"])


class _EodhdHttp:
    def get(self, url, params=None):
        assert params and params["api_token"] == "eodhd-test"
        assert "exchange-symbol-list" in url
        return _Response(
            [
                {
                    "Code": "OLD",
                    "Exchange": "US",
                    "PreviousCloseDate": "2019-06-28",
                }
            ]
        )


def test_eodhd_delisting_event_starts_after_last_trade(monkeypatch):
    monkeypatch.setenv("EODHD_API_TOKEN", "eodhd-test")
    frame = EodhdReferenceHistoryClient(_EodhdHttp()).delisted_symbols(
        "US",
        retrieved_at=pd.Timestamp("2026-08-13"),
        ingestion_run_id="run-3",
    )
    assert frame.loc[0, "security_id"] == "OLD.US"
    assert frame.loc[0, "effective_from"] == pd.Timestamp("2019-06-29")
    assert bool(frame.loc[0, "is_delisted"])


def test_pit_evidence_report_never_promotes_missing_evidence():
    report = point_in_time_evidence_report(
        {
            "fundamental_securities": 100,
            "filing_metadata_securities": 0,
            "historical_membership_events": 0,
            "delisting_events": 50,
            "inactive_securities": 20,
            "inactive_price_securities": 5,
            "price_securities": 100,
            "securities_with_historical_volume": 90,
        }
    ).set_index("check_name")
    assert report.loc["observed_filing_acceptance_coverage", "status"] == "WARNING"
    assert report.loc["historical_membership_evidence", "status"] == "WARNING"
    assert report.loc["delisting_evidence", "status"] == "PASS"
    assert report.loc["historical_volume_coverage", "status"] == "PASS"
