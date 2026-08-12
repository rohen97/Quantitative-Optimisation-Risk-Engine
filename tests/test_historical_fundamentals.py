import pandas as pd

from src.data_ingestion.historical_fundamentals import (
    EASTMONEY_CHINA_SOURCE,
    EASTMONEY_HK_SOURCE,
    FINNHUB_REPORTED_SOURCE,
    hong_kong_eastmoney_code,
    mainland_eastmoney_symbol,
    parse_eastmoney_china_statements,
    parse_eastmoney_hk_statements,
    parse_finnhub_annual_reports,
)


RETRIEVED_AT = pd.Timestamp("2026-08-12 08:00:00")


def test_provider_symbol_conversions_are_deterministic():
    assert mainland_eastmoney_symbol("601398.SHG") == "SH601398"
    assert mainland_eastmoney_symbol("000001.SHE") == "SZ000001"
    assert hong_kong_eastmoney_code("700.HK") == "00700"
    assert hong_kong_eastmoney_code("0005.HK") == "00005"


def test_finnhub_parser_uses_original_filing_and_canonical_metrics():
    report = {
        "endDate": "2020-12-31",
        "filedDate": "2021-02-15",
        "acceptedDate": "2021-02-15 18:30:00",
        "report": {
            "ic": [
                {
                    "concept": "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                    "value": 1000,
                    "unit": "USD",
                },
                {"concept": "us-gaap_OperatingIncomeLoss", "value": 200, "unit": "USD"},
                {"concept": "us-gaap_NetIncomeLoss", "value": 120, "unit": "USD"},
                {
                    "concept": "us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding",
                    "value": 60,
                    "unit": "shares",
                },
            ],
            "bs": [
                {"concept": "us-gaap_Assets", "value": 2500, "unit": "USD"},
                {"concept": "us-gaap_Liabilities", "value": 900, "unit": "USD"},
                {"concept": "us-gaap_StockholdersEquity", "value": 1600, "unit": "USD"},
                {"concept": "us-gaap_ShortTermBorrowings", "value": 100, "unit": "USD"},
                {"concept": "us-gaap_LongTermDebtNoncurrent", "value": 300, "unit": "USD"},
            ],
            "cf": [
                {
                    "concept": "us-gaap_NetCashProvidedByUsedInOperatingActivities",
                    "value": 180,
                    "unit": "USD",
                },
                {
                    "concept": "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment",
                    "value": 50,
                    "unit": "USD",
                },
                {
                    "concept": "us-gaap_PaymentsOfDividendsCommonStock",
                    "value": 30,
                    "unit": "USD",
                },
            ],
        },
    }
    later_amendment = {
        **report,
        "filedDate": "2021-03-01",
        "acceptedDate": "2021-03-01 18:30:00",
    }
    frame = parse_finnhub_annual_reports(
        "ABC.US",
        [later_amendment, report],
        start_year=2018,
        end_year=2020,
        retrieved_at=RETRIEVED_AT,
        ingestion_run_id="run-1",
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["source"] == FINNHUB_REPORTED_SOURCE
    assert row["filing_date"] == pd.Timestamp("2021-02-15")
    assert row["available_from"] == pd.Timestamp("2021-02-15 18:30:00")
    assert row["free_cash_flow"] == 130
    assert row["total_debt"] == 400
    assert row["dividends_paid"] == 30


def test_mainland_parser_preserves_observed_notice_date():
    common = {
        "REPORT_DATE": "2020-12-31 00:00:00",
        "NOTICE_DATE": "2021-03-27 00:00:00",
        "CURRENCY": "\u4eba\u6c11\u5e01",
    }
    frame = parse_eastmoney_china_statements(
        "601398.SHG",
        [
            {
                **common,
                "OPERATE_INCOME": 1000,
                "OPERATE_PROFIT": 200,
                "PARENT_NETPROFIT": 120,
                "DILUTED_EPS": 2,
            }
        ],
        [
            {
                **common,
                "TOTAL_ASSETS": 3000,
                "TOTAL_LIABILITIES": 1800,
                "TOTAL_PARENT_EQUITY": 1200,
                "CASH_DEPOSIT_PBC": 500,
                "BOND_PAYABLE": 300,
            }
        ],
        [
            {
                **common,
                "NETCASH_OPERATE": 180,
                "CONSTRUCT_LONG_ASSET": 50,
                "ASSIGN_DIVIDEND_PORFIT": 30,
            }
        ],
        start_year=2018,
        end_year=2020,
        filing_lag_days=120,
        retrieved_at=RETRIEVED_AT,
        ingestion_run_id="run-2",
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["source"] == EASTMONEY_CHINA_SOURCE
    assert row["currency"] == "CNY"
    assert row["filing_date"] == pd.Timestamp("2021-03-27")
    assert row["available_from"] == pd.Timestamp("2021-03-27")
    assert row["diluted_shares"] == 60
    assert row["free_cash_flow"] == 130


def test_hong_kong_parser_uses_conservative_filing_proxy():
    period = "2020-12-31 00:00:00"

    def facts(values):
        return [
            {"REPORT_DATE": period, "STD_ITEM_CODE": code, "AMOUNT": value}
            for code, value in values.items()
        ]

    frame = parse_eastmoney_hk_statements(
        "0700.HK",
        [
            {
                "REPORT_DATE": period,
                "REPORT_TYPE": "\u5e74\u62a5",
                "CURRENCY": "\u4eba\u6c11\u5e01",
            }
        ],
        facts(
            {
                "004001001": 1000,
                "004010999": 200,
                "004025002": 120,
                "004027003": 2,
                "004011201": 10,
            }
        ),
        facts(
            {
                "004009999": 3000,
                "004025999": 1800,
                "004030999": 1200,
                "004002010": 500,
                "004011010": 100,
                "004020001": 300,
            }
        ),
        facts(
            {
                "003999": 180,
                "005005": 30,
                "005007": 20,
                "007004": 25,
            }
        ),
        start_year=2018,
        end_year=2020,
        filing_lag_days=120,
        retrieved_at=RETRIEVED_AT,
        ingestion_run_id="run-3",
    )

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["source"] == EASTMONEY_HK_SOURCE
    assert row["currency"] == "CNY"
    assert pd.isna(row["filing_date"])
    assert row["available_from"] == pd.Timestamp("2021-04-30")
    assert row["capital_expenditure"] == 50
    assert row["free_cash_flow"] == 130
    assert row["total_debt"] == 400
