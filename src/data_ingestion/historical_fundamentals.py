from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import math
import re
from threading import Lock
import time
from typing import Any, ClassVar

import pandas as pd

from src.data.normalisers import normalise_fundamentals
from src.data.schemas import SCHEMAS
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient
from src.utils.env import get_env


FINNHUB_REPORTED_SOURCE = "finnhub_reported"
EASTMONEY_CHINA_SOURCE = "eastmoney_china_financials"
EASTMONEY_HK_SOURCE = "eastmoney_hk_financials"

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
EASTMONEY_CHINA_BASE_URL = (
    "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis"
)
EASTMONEY_HK_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"

_ANNUAL_REPORT = "\u5e74\u62a5"
_CURRENCY_ALIASES = {
    "\u4eba\u6c11\u5e01": "CNY",
    "\u4eba\u6c11\u5e01\u5143": "CNY",
    "\u6e2f\u5143": "HKD",
    "\u6e2f\u5e01": "HKD",
    "\u7f8e\u5143": "USD",
    "\u6b27\u5143": "EUR",
    "\u82f1\u9551": "GBP",
}


def utc_now() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(UTC)).tz_localize(None)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(value: Any) -> pd.Timestamp | None:
    result = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(result):
        return None
    return pd.Timestamp(result).tz_localize(None)


def _currency(value: Any, default: str) -> str:
    text = str(value or "").strip()
    if text in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[text]
    upper = text.upper()
    return upper if len(upper) == 3 and upper.isalpha() else default


def _sum_present(values: Sequence[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _derived_shares(net_income: float | None, diluted_eps: float | None) -> float | None:
    if net_income is None or diluted_eps in {None, 0.0}:
        return None
    shares = abs(net_income / float(diluted_eps))
    return shares if math.isfinite(shares) and shares > 0 else None


def _has_core_data(row: Mapping[str, Any]) -> bool:
    core = (
        "revenue",
        "net_income",
        "operating_cash_flow",
        "total_assets",
        "shareholders_equity",
        "diluted_shares",
    )
    return sum(row.get(column) is not None for column in core) >= 3


def _normalise_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    source: str,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=SCHEMAS["fundamentals_reported"].column_names)
    clean = normalise_fundamentals(
        pd.DataFrame(rows),
        source=source,
        retrieved_at=retrieved_at,
    )
    clean["ingestion_run_id"] = ingestion_run_id
    return clean


def mainland_eastmoney_symbol(security_id: str) -> str:
    code, separator, exchange = str(security_id).upper().partition(".")
    if not separator or not code.isdigit():
        raise ValueError(f"Unsupported Mainland security identifier: {security_id}")
    prefix = {"SHG": "SH", "SH": "SH", "SHE": "SZ", "SZ": "SZ"}.get(exchange)
    if prefix is None:
        raise ValueError(f"Unsupported Mainland exchange suffix: {security_id}")
    return f"{prefix}{code.zfill(6)}"


def hong_kong_eastmoney_code(security_id: str) -> str:
    code = str(security_id).upper().split(".", 1)[0]
    if not code.isdigit():
        raise ValueError(f"Unsupported Hong Kong security identifier: {security_id}")
    return code.zfill(5)


_FINNHUB_FACTS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": (
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "NetIncomeLoss",
        "ProfitLoss",
    ),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "shareholders_equity": (
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "StockholdersEquity",
    ),
    "dividends_paid": (
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
    ),
    "diluted_shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "interest_expense": (
        "InterestExpenseNonOperating",
        "InterestExpense",
    ),
}

_FINNHUB_CURRENT_DEBT = (
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
)
_FINNHUB_LONG_DEBT = (
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    "LongTermDebtNoncurrent",
)


def _finnhub_concept(value: Any) -> str:
    text = str(value or "")
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    if "_" in text:
        prefix, suffix = text.split("_", 1)
        if prefix.lower() in {"us-gaap", "dei", "ifrs-full"}:
            text = suffix
    return text


def _finnhub_facts(report: Mapping[str, Any]) -> dict[str, tuple[float, str | None]]:
    output: dict[str, tuple[float, str | None]] = {}
    sections = report.get("report") or {}
    if not isinstance(sections, Mapping):
        return output
    for section_name in ("ic", "bs", "cf"):
        facts = sections.get(section_name) or []
        for fact in facts if isinstance(facts, list) else []:
            if not isinstance(fact, Mapping):
                continue
            concept = _finnhub_concept(fact.get("concept"))
            value = _number(fact.get("value"))
            if concept and value is not None and concept not in output:
                output[concept] = (value, str(fact.get("unit") or "") or None)
    return output


def _first_fact(
    facts: Mapping[str, tuple[float, str | None]],
    concepts: Sequence[str],
) -> float | None:
    for concept in concepts:
        if concept in facts:
            return facts[concept][0]
    return None


def parse_finnhub_annual_reports(
    security_id: str,
    reports: Sequence[Mapping[str, Any]],
    *,
    start_year: int,
    end_year: int,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    candidates: list[tuple[pd.Timestamp, pd.Timestamp, dict[str, Any]]] = []
    for report in reports:
        period_end = _timestamp(report.get("endDate"))
        filing_date = _timestamp(report.get("filedDate"))
        accepted_at = _timestamp(report.get("acceptedDate"))
        if period_end is None or not start_year <= period_end.year <= end_year:
            continue
        available_from = accepted_at or filing_date
        if available_from is None or available_from < period_end:
            continue
        facts = _finnhub_facts(report)
        row: dict[str, Any] = {
            "security_id": str(security_id).upper(),
            "fiscal_period_end": period_end.normalize(),
            "fiscal_period_type": "annual",
            "filing_date": (filing_date or available_from).normalize(),
            "available_from": available_from,
            "currency": "USD",
        }
        for column, concepts in _FINNHUB_FACTS.items():
            row[column] = _first_fact(facts, concepts)
        row["capital_expenditure"] = (
            abs(row["capital_expenditure"])
            if row.get("capital_expenditure") is not None
            else None
        )
        row["dividends_paid"] = (
            abs(row["dividends_paid"])
            if row.get("dividends_paid") is not None
            else None
        )
        row["total_debt"] = _sum_present(
            [
                _first_fact(facts, _FINNHUB_CURRENT_DEBT),
                _first_fact(facts, _FINNHUB_LONG_DEBT),
            ]
        )
        if row.get("operating_cash_flow") is not None and row.get("capital_expenditure") is not None:
            row["free_cash_flow"] = row["operating_cash_flow"] - row["capital_expenditure"]
        if _has_core_data(row):
            candidates.append((period_end, available_from, row))

    earliest_by_period: dict[pd.Timestamp, dict[str, Any]] = {}
    for period_end, _, row in sorted(candidates, key=lambda item: (item[0], item[1])):
        earliest_by_period.setdefault(period_end, row)
    return _normalise_rows(
        list(earliest_by_period.values()),
        source=FINNHUB_REPORTED_SOURCE,
        retrieved_at=retrieved_at,
        ingestion_run_id=ingestion_run_id,
    )


@dataclass
class FinnhubReportedClient:
    client: HttpClient
    minimum_interval_seconds: float = 1.05
    base_url: str = FINNHUB_BASE_URL
    _throttle_lock: ClassVar[Lock] = Lock()
    _last_request_at: ClassVar[float] = 0.0

    def _throttle(self) -> None:
        if self.minimum_interval_seconds <= 0:
            return
        with self._throttle_lock:
            elapsed = time.monotonic() - type(self)._last_request_at
            if elapsed < self.minimum_interval_seconds:
                time.sleep(self.minimum_interval_seconds - elapsed)
            type(self)._last_request_at = time.monotonic()

    def fetch_annual_fundamentals(
        self,
        security_id: str,
        symbol: str,
        *,
        start_year: int,
        end_year: int,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> pd.DataFrame:
        token = get_env("FINNHUB_API_KEY", "") or ""
        if not token:
            raise DataSourceRequestError("FINNHUB_API_KEY is required for US historical filings.")
        self._throttle()
        payload = self.client.get(
            f"{self.base_url}/stock/financials-reported",
            params={"symbol": symbol, "freq": "annual", "token": token},
        ).json()
        if not isinstance(payload, Mapping):
            raise DataSourceRequestError(f"Finnhub returned an invalid payload for {symbol}.")
        error = payload.get("error")
        if error:
            raise DataSourceRequestError(f"Finnhub rejected {symbol}: {error}")
        reports = payload.get("data") or []
        return parse_finnhub_annual_reports(
            security_id,
            reports if isinstance(reports, list) else [],
            start_year=start_year,
            end_year=end_year,
            retrieved_at=retrieved_at,
            ingestion_run_id=ingestion_run_id,
        )


_CHINA_INCOME_MAP = {
    "revenue": ("OPERATE_INCOME", "TOTAL_OPERATE_INCOME"),
    "operating_income": ("OPERATE_PROFIT",),
    "net_income": ("PARENT_NETPROFIT", "NETPROFIT"),
    "interest_expense": ("INTEREST_EXPENSE",),
}
_CHINA_BALANCE_MAP = {
    "total_assets": ("TOTAL_ASSETS",),
    "total_liabilities": ("TOTAL_LIABILITIES",),
    "cash_and_equivalents": (
        "MONETARYFUNDS",
        "CASH_DEPOSIT_PBC",
    ),
    "shareholders_equity": ("TOTAL_PARENT_EQUITY", "TOTAL_EQUITY"),
}
_CHINA_CASH_MAP = {
    "operating_cash_flow": ("NETCASH_OPERATE", "FBNETCASH_OPERATE"),
    "capital_expenditure": ("CONSTRUCT_LONG_ASSET",),
    "dividends_paid": ("ASSIGN_DIVIDEND_PORFIT",),
}
_CHINA_DEBT_FIELDS = (
    "SHORT_LOAN",
    "LONG_LOAN",
    "BOND_PAYABLE",
    "NONCURRENT_LIAB_1YEAR",
    "LEASE_LIAB",
    "LOAN_PBC",
    "BORROW_FUND",
    "SELL_REPO_FINASSET",
)


def _wide_rows(rows: Sequence[Mapping[str, Any]]) -> dict[pd.Timestamp, Mapping[str, Any]]:
    output: dict[pd.Timestamp, Mapping[str, Any]] = {}
    for row in rows:
        period_end = _timestamp(row.get("REPORT_DATE"))
        if period_end is not None:
            output[period_end.normalize()] = row
    return output


def _first_wide_value(row: Mapping[str, Any], columns: Sequence[str]) -> float | None:
    for column in columns:
        value = _number(row.get(column))
        if value is not None:
            return value
    return None


def parse_eastmoney_china_statements(
    security_id: str,
    income_rows: Sequence[Mapping[str, Any]],
    balance_rows: Sequence[Mapping[str, Any]],
    cash_rows: Sequence[Mapping[str, Any]],
    *,
    start_year: int,
    end_year: int,
    filing_lag_days: int,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    income = _wide_rows(income_rows)
    balance = _wide_rows(balance_rows)
    cash = _wide_rows(cash_rows)
    periods = sorted(set(income) | set(balance) | set(cash))
    output: list[dict[str, Any]] = []
    for period_end in periods:
        if not start_year <= period_end.year <= end_year:
            continue
        income_row = income.get(period_end, {})
        balance_row = balance.get(period_end, {})
        cash_row = cash.get(period_end, {})
        notices = [
            timestamp
            for timestamp in (
                _timestamp(income_row.get("NOTICE_DATE")),
                _timestamp(balance_row.get("NOTICE_DATE")),
                _timestamp(cash_row.get("NOTICE_DATE")),
            )
            if timestamp is not None and timestamp >= period_end
        ]
        filing_date = max(notices) if notices else None
        available_from = filing_date or (period_end + pd.Timedelta(days=filing_lag_days))
        row: dict[str, Any] = {
            "security_id": str(security_id).upper(),
            "fiscal_period_end": period_end,
            "fiscal_period_type": "annual",
            "filing_date": filing_date.normalize() if filing_date is not None else pd.NaT,
            "available_from": available_from,
            "currency": _currency(
                income_row.get("CURRENCY")
                or balance_row.get("CURRENCY")
                or cash_row.get("CURRENCY"),
                "CNY",
            ),
        }
        for column, fields in _CHINA_INCOME_MAP.items():
            row[column] = _first_wide_value(income_row, fields)
        for column, fields in _CHINA_BALANCE_MAP.items():
            row[column] = _first_wide_value(balance_row, fields)
        for column, fields in _CHINA_CASH_MAP.items():
            row[column] = _first_wide_value(cash_row, fields)
        row["capital_expenditure"] = (
            abs(row["capital_expenditure"])
            if row.get("capital_expenditure") is not None
            else None
        )
        row["dividends_paid"] = (
            abs(row["dividends_paid"])
            if row.get("dividends_paid") is not None
            else None
        )
        row["total_debt"] = _sum_present(
            [_number(balance_row.get(field)) for field in _CHINA_DEBT_FIELDS]
        )
        diluted_eps = _first_wide_value(income_row, ("DILUTED_EPS", "BASIC_EPS"))
        row["diluted_shares"] = _derived_shares(row.get("net_income"), diluted_eps)
        if row.get("operating_cash_flow") is not None and row.get("capital_expenditure") is not None:
            row["free_cash_flow"] = row["operating_cash_flow"] - row["capital_expenditure"]
        if _has_core_data(row):
            output.append(row)
    return _normalise_rows(
        output,
        source=EASTMONEY_CHINA_SOURCE,
        retrieved_at=retrieved_at,
        ingestion_run_id=ingestion_run_id,
    )


_HK_BALANCE_MAP = {
    "total_assets": ("004009999",),
    "total_liabilities": ("004025999",),
    "cash_and_equivalents": ("004002010",),
    "shareholders_equity": ("004030999", "004036999", "004028999"),
}
_HK_INCOME_MAP = {
    "revenue": ("004001001", "004001999"),
    "operating_income": ("004010999",),
    "net_income": ("004025002", "004012999"),
    "interest_expense": ("004011201",),
}
_HK_CASH_MAP = {
    "operating_cash_flow": ("003999",),
    "dividends_paid": ("007004",),
}
_HK_DEBT_CODES = (
    "004011006",
    "004011010",
    "004020001",
    "004020005",
    "004020018",
)
_HK_CAPEX_CODES = ("005005", "005007")


def _long_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[pd.Timestamp, dict[str, float]]:
    output: dict[pd.Timestamp, dict[str, float]] = {}
    for row in rows:
        period_end = _timestamp(row.get("REPORT_DATE"))
        code = str(row.get("STD_ITEM_CODE") or "")
        value = _number(row.get("AMOUNT"))
        if period_end is None or not code or value is None:
            continue
        output.setdefault(period_end.normalize(), {}).setdefault(code, value)
    return output


def _first_code_value(values: Mapping[str, float], codes: Sequence[str]) -> float | None:
    for code in codes:
        if code in values:
            return values[code]
    return None


def parse_eastmoney_hk_statements(
    security_id: str,
    annual_reports: Sequence[Mapping[str, Any]],
    income_rows: Sequence[Mapping[str, Any]],
    balance_rows: Sequence[Mapping[str, Any]],
    cash_rows: Sequence[Mapping[str, Any]],
    *,
    start_year: int,
    end_year: int,
    filing_lag_days: int,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    metadata: dict[pd.Timestamp, Mapping[str, Any]] = {}
    for report in annual_reports:
        period_end = _timestamp(report.get("REPORT_DATE"))
        if period_end is not None and str(report.get("REPORT_TYPE") or "") == _ANNUAL_REPORT:
            metadata[period_end.normalize()] = report
    income = _long_rows(income_rows)
    balance = _long_rows(balance_rows)
    cash = _long_rows(cash_rows)
    output: list[dict[str, Any]] = []
    for period_end in sorted(set(metadata) | set(income) | set(balance) | set(cash)):
        if not start_year <= period_end.year <= end_year:
            continue
        income_values = income.get(period_end, {})
        balance_values = balance.get(period_end, {})
        cash_values = cash.get(period_end, {})
        available_from = period_end + pd.Timedelta(days=filing_lag_days)
        row: dict[str, Any] = {
            "security_id": str(security_id).upper(),
            "fiscal_period_end": period_end,
            "fiscal_period_type": "annual",
            "filing_date": pd.NaT,
            "available_from": available_from,
            "currency": _currency(metadata.get(period_end, {}).get("CURRENCY"), "HKD"),
        }
        for column, codes in _HK_INCOME_MAP.items():
            row[column] = _first_code_value(income_values, codes)
        for column, codes in _HK_BALANCE_MAP.items():
            row[column] = _first_code_value(balance_values, codes)
        for column, codes in _HK_CASH_MAP.items():
            row[column] = _first_code_value(cash_values, codes)
        row["total_debt"] = _sum_present(
            [balance_values.get(code) for code in _HK_DEBT_CODES]
        )
        row["capital_expenditure"] = _sum_present(
            [abs(cash_values[code]) for code in _HK_CAPEX_CODES if code in cash_values]
        )
        row["dividends_paid"] = (
            abs(row["dividends_paid"])
            if row.get("dividends_paid") is not None
            else None
        )
        diluted_eps = _first_code_value(income_values, ("004027003", "004027002"))
        row["diluted_shares"] = _derived_shares(row.get("net_income"), diluted_eps)
        if row.get("operating_cash_flow") is not None and row.get("capital_expenditure") is not None:
            row["free_cash_flow"] = row["operating_cash_flow"] - row["capital_expenditure"]
        if _has_core_data(row):
            output.append(row)
    return _normalise_rows(
        output,
        source=EASTMONEY_HK_SOURCE,
        retrieved_at=retrieved_at,
        ingestion_run_id=ingestion_run_id,
    )


@dataclass
class EastmoneyHistoricalClient:
    client: HttpClient
    filing_lag_days: int = 120
    request_interval_seconds: float = 0.05
    _throttle_lock: ClassVar[Lock] = Lock()
    _last_request_at: ClassVar[float] = 0.0

    def _throttle(self) -> None:
        if self.request_interval_seconds <= 0:
            return
        with self._throttle_lock:
            elapsed = time.monotonic() - type(self)._last_request_at
            if elapsed < self.request_interval_seconds:
                time.sleep(self.request_interval_seconds - elapsed)
            type(self)._last_request_at = time.monotonic()

    def _get(self, url: str, params: dict[str, object]) -> object:
        self._throttle()
        return self.client.get(url, params=params).json()

    def _company_type(self, symbol: str) -> str:
        self._throttle()
        html = self.client.get(
            f"{EASTMONEY_CHINA_BASE_URL}/Index",
            params={"type": "web", "code": symbol.lower()},
            headers={"Accept": "text/html"},
        ).text()
        patterns = (
            r'id=["\']hidctype["\'][^>]*value=["\']([^"\']+)',
            r'value=["\']([^"\']+)["\'][^>]*id=["\']hidctype["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        raise DataSourceRequestError(f"Eastmoney company type was unavailable for {symbol}.")

    def _china_dates(self, symbol: str, company_type: str) -> list[str]:
        payload = self._get(
            f"{EASTMONEY_CHINA_BASE_URL}/zcfzbDateAjaxNew",
            {"companyType": company_type, "reportDateType": "1", "code": symbol},
        )
        rows = payload.get("data") or [] if isinstance(payload, Mapping) else []
        return [
            timestamp.strftime("%Y-%m-%d")
            for item in rows if isinstance(item, Mapping)
            if (timestamp := _timestamp(item.get("REPORT_DATE"))) is not None
        ]

    def _china_statement_rows(
        self,
        endpoint: str,
        symbol: str,
        company_type: str,
        dates: Sequence[str],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for start in range(0, len(dates), 5):
            payload = self._get(
                f"{EASTMONEY_CHINA_BASE_URL}/{endpoint}",
                {
                    "companyType": company_type,
                    "reportDateType": "1",
                    "reportType": "1",
                    "dates": ",".join(dates[start : start + 5]),
                    "code": symbol,
                },
            )
            data = payload.get("data") or [] if isinstance(payload, Mapping) else []
            rows.extend(item for item in data if isinstance(item, dict))
        return rows

    def fetch_mainland_annual_fundamentals(
        self,
        security_id: str,
        *,
        start_year: int,
        end_year: int,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> pd.DataFrame:
        symbol = mainland_eastmoney_symbol(security_id)
        company_type = self._company_type(symbol)
        dates = [
            value
            for value in self._china_dates(symbol, company_type)
            if start_year <= pd.Timestamp(value).year <= end_year
        ]
        if not dates:
            return pd.DataFrame(columns=SCHEMAS["fundamentals_reported"].column_names)
        balance = self._china_statement_rows(
            "zcfzbAjaxNew", symbol, company_type, dates
        )
        income = self._china_statement_rows("lrbAjaxNew", symbol, company_type, dates)
        cash = self._china_statement_rows("xjllbAjaxNew", symbol, company_type, dates)
        return parse_eastmoney_china_statements(
            security_id,
            income,
            balance,
            cash,
            start_year=start_year,
            end_year=end_year,
            filing_lag_days=self.filing_lag_days,
            retrieved_at=retrieved_at,
            ingestion_run_id=ingestion_run_id,
        )

    def _hk_report_metadata(self, code: str) -> list[dict[str, Any]]:
        payload = self._get(
            EASTMONEY_HK_URL,
            {
                "reportName": "RPT_CUSTOM_HKSK_APPFN_CASHFLOW_SUMMARY",
                "columns": (
                    "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,START_DATE,"
                    "REPORT_DATE,FISCAL_YEAR,CURRENCY,ACCOUNT_STANDARD,REPORT_TYPE"
                ),
                "quoteColumns": "",
                "filter": f'(SECUCODE="{code}.HK")',
                "source": "F10",
                "client": "PC",
            },
        )
        result = payload.get("result") or {} if isinstance(payload, Mapping) else {}
        data = result.get("data") or [] if isinstance(result, Mapping) else []
        if not data or not isinstance(data[0], Mapping):
            return []
        reports = data[0].get("REPORT_LIST") or []
        return [item for item in reports if isinstance(item, dict)]

    def _hk_statement_rows(
        self,
        report_name: str,
        columns: str,
        code: str,
        dates: Sequence[str],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for start in range(0, len(dates), 5):
            quoted_dates = "','".join(dates[start : start + 5])
            payload = self._get(
                EASTMONEY_HK_URL,
                {
                    "reportName": report_name,
                    "columns": columns,
                    "quoteColumns": "",
                    "filter": (
                        f'(SECUCODE="{code}.HK")'
                        f"(REPORT_DATE in ('{quoted_dates}'))"
                    ),
                    "pageNumber": "1",
                    "pageSize": "",
                    "sortTypes": "-1,1",
                    "sortColumns": "REPORT_DATE,STD_ITEM_CODE",
                    "source": "F10",
                    "client": "PC",
                },
            )
            result = payload.get("result") or {} if isinstance(payload, Mapping) else {}
            data = result.get("data") or [] if isinstance(result, Mapping) else []
            rows.extend(item for item in data if isinstance(item, dict))
        return rows

    def fetch_hong_kong_annual_fundamentals(
        self,
        security_id: str,
        *,
        start_year: int,
        end_year: int,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> pd.DataFrame:
        code = hong_kong_eastmoney_code(security_id)
        metadata = self._hk_report_metadata(code)
        annual = [
            item
            for item in metadata
            if str(item.get("REPORT_TYPE") or "") == _ANNUAL_REPORT
            and (period_end := _timestamp(item.get("REPORT_DATE"))) is not None
            and start_year <= period_end.year <= end_year
        ]
        dates = [pd.Timestamp(item["REPORT_DATE"]).strftime("%Y-%m-%d") for item in annual]
        if not dates:
            return pd.DataFrame(columns=SCHEMAS["fundamentals_reported"].column_names)
        common = (
            "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_CODE,REPORT_DATE,"
            "DATE_TYPE_CODE,FISCAL_YEAR"
        )
        balance = self._hk_statement_rows(
            "RPT_HKF10_FN_BALANCE_PC",
            f"{common},STD_ITEM_CODE,STD_ITEM_NAME,AMOUNT,STD_REPORT_DATE",
            code,
            dates,
        )
        income = self._hk_statement_rows(
            "RPT_HKF10_FN_INCOME_PC",
            f"{common},START_DATE,STD_ITEM_CODE,STD_ITEM_NAME,AMOUNT",
            code,
            dates,
        )
        cash = self._hk_statement_rows(
            "RPT_HKF10_FN_CASHFLOW_PC",
            f"{common},START_DATE,STD_ITEM_CODE,STD_ITEM_NAME,AMOUNT",
            code,
            dates,
        )
        return parse_eastmoney_hk_statements(
            security_id,
            annual,
            income,
            balance,
            cash,
            start_year=start_year,
            end_year=end_year,
            filing_lag_days=self.filing_lag_days,
            retrieved_at=retrieved_at,
            ingestion_run_id=ingestion_run_id,
        )
