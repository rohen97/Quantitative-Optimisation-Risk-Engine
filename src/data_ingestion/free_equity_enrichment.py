from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import math
from threading import Lock
import time
from typing import Any, ClassVar

import pandas as pd

from src.data.normalisers import normalise_fundamentals, record_hash
from src.data.schemas import SCHEMAS


LOGGER = logging.getLogger(__name__)
REFERENCE_SOURCE = "yahoo_finance"
FUNDAMENTALS_SOURCE = "yahoo_finance_timeseries"
QUOTE_URL = "https://query2.finance.yahoo.com/v7/finance/quote"
SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
TIMESERIES_URL = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}"

SUMMARY_MODULES = (
    "assetProfile",
    "financialData",
    "defaultKeyStatistics",
    "summaryDetail",
)
ANNUAL_METRICS = {
    "TotalRevenue": "revenue",
    "OperatingIncome": "operating_income",
    "NetIncome": "net_income",
    "OperatingCashFlow": "operating_cash_flow",
    "CapitalExpenditure": "capital_expenditure",
    "FreeCashFlow": "free_cash_flow",
    "TotalAssets": "total_assets",
    "TotalLiabilitiesNetMinorityInterest": "total_liabilities",
    "TotalDebt": "total_debt",
    "CashCashEquivalentsAndShortTermInvestments": "cash_and_equivalents",
    "CashAndCashEquivalents": "cash_and_equivalents",
    "StockholdersEquity": "shareholders_equity",
    "CommonStockEquity": "shareholders_equity",
    "CashDividendsPaid": "dividends_paid",
    "DilutedAverageShares": "diluted_shares",
    "EBITDA": "ebitda",
    "InterestExpense": "interest_expense",
    "InterestExpenseNonOperating": "interest_expense",
}

SECTOR_MAP = {
    "basic materials": "Materials",
    "communication services": "Communication Services",
    "consumer cyclical": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples",
    "energy": "Energy",
    "financial services": "Financials",
    "healthcare": "Healthcare",
    "industrials": "Industrials",
    "real estate": "Real Estate",
    "technology": "Technology",
    "utilities": "Utilities",
}


def utc_now() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(UTC)).tz_localize(None)


def _number(value: Any) -> float | None:
    if isinstance(value, Mapping):
        value = value.get("raw")
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def canonical_sector(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return SECTOR_MAP.get(text.lower(), text)


def _major_currency(raw_currency: Any) -> tuple[str | None, float]:
    raw = _text(raw_currency)
    if raw is None:
        return None, 1.0
    if raw == "GBp" or raw.upper() == "GBX":
        return "GBP", 0.01
    return raw.upper(), 1.0


def _to_usd(value: float | None, currency: str | None, units_per_usd: Mapping[str, float]) -> float | None:
    if value is None or currency is None:
        return None
    if currency == "USD":
        return value
    rate = _number(units_per_usd.get(currency))
    return value / rate if rate and rate > 0 else None


def _with_reference_hash(row: dict[str, Any]) -> dict[str, Any]:
    frame = pd.DataFrame([row])
    hash_columns = [
        "security_id",
        "as_of_date",
        "provider_symbol",
        "market_cap_local",
        "average_daily_value_usd",
        "sector",
        "industry",
        "source",
    ]
    row["row_hash"] = record_hash(frame, hash_columns).iloc[0]
    return row


def build_reference_row(
    security: Mapping[str, Any],
    quote: Mapping[str, Any],
    units_per_usd: Mapping[str, float],
    *,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> dict[str, Any]:
    quote_currency, price_scale = _major_currency(quote.get("currency") or security.get("trading_currency"))
    financial_currency, _ = _major_currency(quote.get("financialCurrency") or quote_currency)
    regular_market_price = _number(quote.get("regularMarketPrice"))
    market_cap_local = _number(quote.get("marketCap"))
    enterprise_value_local = _number(quote.get("enterpriseValue"))
    average_volume = (
        _number(quote.get("averageDailyVolume3Month"))
        or _number(quote.get("averageDailyVolume10Day"))
        or _number(quote.get("regularMarketVolume"))
    )
    average_value_local = (
        regular_market_price * price_scale * average_volume
        if regular_market_price is not None and average_volume is not None
        else None
    )
    dividend_yield_percent = _number(quote.get("dividendYield"))
    row = {
        "security_id": str(security["security_id"]).upper(),
        "as_of_date": retrieved_at.normalize(),
        "provider_symbol": str(security["provider_symbol"]),
        "company_name": _text(quote.get("longName") or quote.get("shortName") or security.get("company_name")),
        "sector": None,
        "industry": None,
        "quote_currency": quote_currency,
        "financial_currency": financial_currency,
        "regular_market_price": regular_market_price,
        "price_scale": price_scale,
        "market_cap_local": market_cap_local,
        "market_cap_usd": _to_usd(market_cap_local, quote_currency, units_per_usd),
        "shares_outstanding": _number(quote.get("sharesOutstanding") or quote.get("impliedSharesOutstanding")),
        "average_daily_volume_3m": average_volume,
        "average_daily_value_usd": _to_usd(average_value_local, quote_currency, units_per_usd),
        "dividend_yield": dividend_yield_percent / 100.0 if dividend_yield_percent is not None else None,
        "trailing_pe": _number(quote.get("trailingPE")),
        "price_to_book": _number(quote.get("priceToBook")),
        "enterprise_value_local": enterprise_value_local,
        "enterprise_value_usd": _to_usd(enterprise_value_local, quote_currency, units_per_usd),
        "enterprise_to_ebitda": _number(quote.get("enterpriseToEbitda")),
        "payout_ratio": None,
        "return_on_equity": None,
        "return_on_assets": None,
        "total_cash": None,
        "total_debt": None,
        "ebitda": None,
        "free_cash_flow": None,
        "operating_cash_flow": None,
        "source": REFERENCE_SOURCE,
        "retrieved_at": retrieved_at,
        "ingestion_run_id": ingestion_run_id,
    }
    return _with_reference_hash(row)


def enrich_reference_row(
    base_row: Mapping[str, Any],
    summary: Mapping[str, Any],
    units_per_usd: Mapping[str, float],
) -> dict[str, Any]:
    row = dict(base_row)
    profile = summary.get("assetProfile") or {}
    financial = summary.get("financialData") or {}
    statistics = summary.get("defaultKeyStatistics") or {}
    details = summary.get("summaryDetail") or {}
    row["sector"] = canonical_sector(profile.get("sector"))
    row["industry"] = _text(profile.get("industry"))
    row["payout_ratio"] = _number(statistics.get("payoutRatio") or details.get("payoutRatio"))
    row["return_on_equity"] = _number(financial.get("returnOnEquity"))
    row["return_on_assets"] = _number(financial.get("returnOnAssets"))
    row["total_cash"] = _number(financial.get("totalCash"))
    row["total_debt"] = _number(financial.get("totalDebt"))
    row["ebitda"] = _number(financial.get("ebitda"))
    row["free_cash_flow"] = _number(financial.get("freeCashflow"))
    row["operating_cash_flow"] = _number(financial.get("operatingCashflow"))
    enterprise_value = _number(statistics.get("enterpriseValue"))
    if enterprise_value is not None:
        row["enterprise_value_local"] = enterprise_value
        row["enterprise_value_usd"] = _to_usd(
            enterprise_value,
            _text(row.get("quote_currency")),
            units_per_usd,
        )
    enterprise_to_ebitda = _number(statistics.get("enterpriseToEbitda"))
    if enterprise_to_ebitda is not None:
        row["enterprise_to_ebitda"] = enterprise_to_ebitda
    return _with_reference_hash(row)


def normalise_reference_rows(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    columns = list(SCHEMAS["security_reference_snapshots"].column_names)
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame:
            frame[column] = pd.NA
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.normalize()
    frame["retrieved_at"] = pd.to_datetime(frame["retrieved_at"])
    return frame[columns]


def parse_annual_fundamentals(
    security_id: str,
    payload_rows: Sequence[Mapping[str, Any]],
    *,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    periods: dict[str, dict[str, Any]] = {}
    for metric_payload in payload_rows:
        metric_key = next(
            (key for key in metric_payload if key.startswith("annual") and isinstance(metric_payload[key], list)),
            None,
        )
        if metric_key is None:
            continue
        canonical = ANNUAL_METRICS.get(metric_key.removeprefix("annual"))
        if canonical is None:
            continue
        for observation in metric_payload[metric_key]:
            period_end = _text(observation.get("asOfDate"))
            value = _number(observation.get("reportedValue"))
            if period_end is None or value is None:
                continue
            row = periods.setdefault(
                period_end,
                {
                    "security_id": str(security_id).upper(),
                    "fiscal_period_end": period_end,
                    "fiscal_period_type": "annual",
                    "filing_date": retrieved_at.normalize(),
                    "available_from": retrieved_at,
                    "currency": _text(observation.get("currencyCode")),
                    "source": FUNDAMENTALS_SOURCE,
                    "ingestion_run_id": ingestion_run_id,
                },
            )
            if row.get(canonical) is None:
                row[canonical] = value
    if not periods:
        return pd.DataFrame(columns=SCHEMAS["fundamentals_reported"].column_names)
    frame = pd.DataFrame(periods.values())
    clean = normalise_fundamentals(
        frame,
        source=FUNDAMENTALS_SOURCE,
        retrieved_at=retrieved_at,
    )
    clean["ingestion_run_id"] = ingestion_run_id
    return clean


@dataclass
class YahooPublicDataClient:
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    rate_limit_backoff_seconds: float = 15.0
    minimum_interval_seconds: float = 0.0
    data: Any = None
    _throttle_lock: ClassVar[Lock] = Lock()
    _last_request_at: ClassVar[float] = 0.0

    def __post_init__(self) -> None:
        if self.data is None:
            from yfinance.data import YfData

            self.data = YfData()

    def _get_json(self, url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.minimum_interval_seconds > 0:
                    with self._throttle_lock:
                        elapsed = time.monotonic() - self._last_request_at
                        if elapsed < self.minimum_interval_seconds:
                            time.sleep(self.minimum_interval_seconds - elapsed)
                        type(self)._last_request_at = time.monotonic()
                response = self.data.get(url, params=dict(params))
                if int(response.status_code) >= 400:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
                return response.json()
            except Exception as exc:
                error = exc
                if attempt < self.max_retries:
                    delay = self.retry_delay_seconds * (2 ** (attempt - 1))
                    if "too many requests" in str(exc).lower():
                        delay = max(delay, self.rate_limit_backoff_seconds * attempt)
                    time.sleep(delay)
        raise RuntimeError(f"Yahoo request failed after {self.max_retries} attempts: {error}") from error

    def fetch_quotes(self, symbols: Sequence[str]) -> list[dict[str, Any]]:
        if not symbols:
            return []
        payload = self._get_json(QUOTE_URL, {"symbols": ",".join(symbols)})
        response = payload.get("quoteResponse") or {}
        if response.get("error"):
            raise RuntimeError(f"Yahoo quote error: {response['error']}")
        return list(response.get("result") or [])

    def fetch_summary(self, symbol: str) -> dict[str, Any]:
        payload = self._get_json(
            SUMMARY_URL.format(symbol=symbol),
            {"modules": ",".join(SUMMARY_MODULES)},
        )
        response = payload.get("quoteSummary") or {}
        result = response.get("result") or []
        if not result:
            raise RuntimeError(f"Yahoo summary unavailable for {symbol}: {response.get('error')}")
        return dict(result[0])

    def fetch_annual_fundamentals(
        self,
        security_id: str,
        symbol: str,
        *,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> pd.DataFrame:
        metric_types = ",".join(f"annual{metric}" for metric in ANNUAL_METRICS)
        payload = self._get_json(
            TIMESERIES_URL.format(symbol=symbol),
            {
                "symbol": symbol,
                "type": metric_types,
                "period1": 1483142400,
                "period2": int((retrieved_at + pd.Timedelta(days=2)).timestamp()),
            },
        )
        response = payload.get("timeseries") or {}
        if response.get("error"):
            raise RuntimeError(f"Yahoo fundamentals error for {symbol}: {response['error']}")
        return parse_annual_fundamentals(
            security_id,
            response.get("result") or [],
            retrieved_at=retrieved_at,
            ingestion_run_id=ingestion_run_id,
        )
