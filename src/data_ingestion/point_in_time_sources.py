from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
import re
from typing import Any

import pandas as pd

from src.data.normalisers import normalise_fundamentals, record_hash
from src.data.schemas import SCHEMAS
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient
from src.utils.env import get_env


BEAM_SEC_SOURCE = "beam_sec_metadata"
SEC_SUBMISSIONS_SOURCE = "sec_edgar_submissions"
SEC_COMPANYFACTS_SOURCE = "sec_edgar_companyfacts"
NASDAQ_MERGENT_SOURCE = "nasdaq_mergent_f1"
EODHD_REFERENCE_SOURCE = "eodhd_reference_history"

BEAM_SEC_METADATA_URL = (
    "https://api.beamapi.com/data/fundamentals/us/sec/metadata/v1/"
)
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts"
NASDAQ_MERGENT_URL = "https://data.nasdaq.com/api/v3/datatables/MER/F1.json"
EODHD_BASE_URL = "https://eodhd.com/api"


def _timestamp(value: Any) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).tz_localize(None)


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _hash(values: Sequence[Any]) -> str:
    payload = "|".join("" if value is None else str(value) for value in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _empty(schema_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=SCHEMAS[schema_name].column_names)


def _graphql_data(payload: object, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise DataSourceRequestError("Beam returned a non-object GraphQL response.")
    errors = payload.get("errors")
    if errors:
        messages = [
            str(item.get("message", "GraphQL error"))
            for item in errors
            if isinstance(item, Mapping)
        ]
        raise DataSourceRequestError(f"Beam GraphQL error: {'; '.join(messages)}")
    data = payload.get("data")
    rows = data.get(field) if isinstance(data, Mapping) else None
    if not isinstance(rows, list):
        raise DataSourceRequestError(f"Beam response omitted the {field} result.")
    return [row for row in rows if isinstance(row, Mapping)]


@dataclass
class BeamSecMetadataClient:
    """Fetch observed SEC filing acceptance timestamps from Beam's metadata API."""

    client: HttpClient
    base_url: str = BEAM_SEC_METADATA_URL
    page_size: int = 10

    def _post(self, query: str, variables: Mapping[str, Any]) -> object:
        api_key = get_env("BEAM_API_KEY", "") or ""
        if not api_key:
            raise DataSourceRequestError("BEAM_API_KEY is required for SEC metadata.")
        return self.client.post_json(
            self.base_url,
            {"query": query, "variables": dict(variables)},
            headers={"api-key": api_key},
        ).json()

    def ticker_cik(self, ticker: str) -> str | None:
        query = """
        query Security($filters: FilterPubliclyListedSecurity) {
          publicly_listed_security(filters: $filters) {
            entity_cik
            exchange
            ticker
          }
        }
        """
        clean_ticker = str(ticker).strip().upper()
        rows = _graphql_data(
            self._post(
                query,
                {"filters": {"ticker": f"^{re.escape(clean_ticker)}$"}},
            ),
            "publicly_listed_security",
        )
        exact = [
            row
            for row in rows
            if str(row.get("ticker", "")).strip().upper() == clean_ticker
        ]
        return str(exact[0]["entity_cik"]) if exact else None

    def filings(
        self,
        security_id: str,
        cik: str | int,
        *,
        start_date: date,
        end_date: date,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
        max_records: int = 250,
    ) -> pd.DataFrame:
        query = """
        query Filings($offset: Int, $filters: FilterFiling) {
          filing(offset: $offset, filters: $filters) {
            acceptance_datetime
            accession_number
            entity_cik
            filing_date
            filing_index_url
            form_type
            report_date
          }
        }
        """
        filters = {
            "entity_cik": {"equal": int(cik)},
            "form_type": "^(10-K|10-Q|20-F|40-F)(/A)?$",
            "report_date": {
                "range": {
                    "lowEnd": {"ge": start_date.isoformat()},
                    "highEnd": {"le": end_date.isoformat()},
                }
            },
        }
        collected: list[Mapping[str, Any]] = []
        for offset in range(0, max(max_records, 1), self.page_size):
            page = _graphql_data(
                self._post(query, {"offset": offset, "filters": filters}),
                "filing",
            )
            collected.extend(page)
            if len(page) < self.page_size or len(collected) >= max_records:
                break

        rows: list[dict[str, Any]] = []
        for filing in collected[:max_records]:
            accession = str(filing.get("accession_number") or "").strip()
            form_type = str(filing.get("form_type") or "").strip().upper()
            if not accession or not form_type:
                continue
            row = {
                "security_id": str(security_id).upper(),
                "entity_cik": str(filing.get("entity_cik") or cik),
                "accession_number": accession,
                "form_type": form_type,
                "report_date": _timestamp(filing.get("report_date")),
                "filing_date": _timestamp(filing.get("filing_date")),
                "acceptance_datetime": _timestamp(
                    filing.get("acceptance_datetime")
                ),
                "filing_index_url": filing.get("filing_index_url"),
                "source": BEAM_SEC_SOURCE,
                "retrieved_at": retrieved_at,
                "ingestion_run_id": ingestion_run_id,
            }
            row["row_hash"] = _hash(
                [
                    row["entity_cik"],
                    row["accession_number"],
                    row["acceptance_datetime"],
                    row["filing_index_url"],
                ]
            )
            rows.append(row)
        if not rows:
            return _empty("filing_metadata")
        return pd.DataFrame(rows)[list(SCHEMAS["filing_metadata"].column_names)]


def _columnar_records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    columns = {
        str(key): value
        for key, value in payload.items()
        if isinstance(value, list)
    }
    length = max((len(values) for values in columns.values()), default=0)
    return [
        {
            key: values[position] if position < len(values) else None
            for key, values in columns.items()
        }
        for position in range(length)
    ]


@dataclass
class SecSubmissionsClient:
    """Fetch SEC submissions directly when an aggregation service is unavailable."""

    client: HttpClient
    ticker_map_url: str = SEC_TICKER_MAP_URL
    submissions_url: str = SEC_SUBMISSIONS_URL

    def _headers(self) -> dict[str, str]:
        user_agent = get_env("SEC_USER_AGENT", "") or ""
        if not user_agent:
            raise DataSourceRequestError(
                "SEC_USER_AGENT is required and must identify the application and contact."
            )
        return {"User-Agent": user_agent}

    def ticker_ciks(self) -> dict[str, str]:
        payload = self.client.get(
            self.ticker_map_url,
            headers=self._headers(),
        ).json()
        records = payload.values() if isinstance(payload, Mapping) else []
        result: dict[str, str] = {}
        for record in records:
            if not isinstance(record, Mapping):
                continue
            ticker = str(record.get("ticker") or "").strip().upper()
            cik = str(record.get("cik_str") or "").strip()
            if ticker and cik:
                result[ticker] = cik.zfill(10)
        return result

    def filings(
        self,
        security_id: str,
        cik: str | int,
        *,
        start_date: date,
        end_date: date,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
        max_records: int = 500,
    ) -> pd.DataFrame:
        padded_cik = str(cik).zfill(10)
        payload = self.client.get(
            f"{self.submissions_url}/CIK{padded_cik}.json",
            headers=self._headers(),
        ).json()
        if not isinstance(payload, Mapping):
            raise DataSourceRequestError("SEC submissions returned a non-object response.")
        filings = payload.get("filings")
        if not isinstance(filings, Mapping):
            raise DataSourceRequestError("SEC submissions omitted filing metadata.")
        records = _columnar_records(filings.get("recent"))
        files = filings.get("files")
        if isinstance(files, list):
            for item in files:
                if not isinstance(item, Mapping) or not item.get("name"):
                    continue
                filing_from = _timestamp(item.get("filingFrom"))
                filing_to = _timestamp(item.get("filingTo"))
                if filing_to is not None and filing_to.date() < start_date:
                    continue
                if filing_from is not None and filing_from.date() > end_date:
                    continue
                historical = self.client.get(
                    f"{self.submissions_url}/{item['name']}",
                    headers=self._headers(),
                ).json()
                records.extend(_columnar_records(historical))

        accepted_forms = re.compile(r"^(10-K|10-Q|20-F|40-F)(/A)?$")
        rows: list[dict[str, Any]] = []
        for filing in records:
            form_type = str(filing.get("form") or "").strip().upper()
            accession = str(filing.get("accessionNumber") or "").strip()
            report_date = _timestamp(filing.get("reportDate"))
            filing_date = _timestamp(filing.get("filingDate"))
            if not accepted_forms.fullmatch(form_type) or not accession:
                continue
            effective_date = report_date if report_date is not None else filing_date
            if (
                effective_date is None
                or effective_date.date() < start_date
                or effective_date.date() > end_date
            ):
                continue
            accession_path = accession.replace("-", "")
            row = {
                "security_id": str(security_id).upper(),
                "entity_cik": str(int(padded_cik)),
                "accession_number": accession,
                "form_type": form_type,
                "report_date": report_date,
                "filing_date": filing_date,
                "acceptance_datetime": _timestamp(
                    filing.get("acceptanceDateTime")
                ),
                "filing_index_url": (
                    "https://www.sec.gov/Archives/edgar/data/"
                    f"{int(padded_cik)}/{accession_path}/{accession}-index.html"
                ),
                "source": SEC_SUBMISSIONS_SOURCE,
                "retrieved_at": retrieved_at,
                "ingestion_run_id": ingestion_run_id,
            }
            row["row_hash"] = _hash(
                [
                    row["entity_cik"],
                    row["accession_number"],
                    row["acceptance_datetime"],
                    row["filing_index_url"],
                ]
            )
            rows.append(row)
            if len(rows) >= max_records:
                break
        if not rows:
            return _empty("filing_metadata")
        return pd.DataFrame(rows)[list(SCHEMAS["filing_metadata"].column_names)]


_SEC_FACT_TAGS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "total_debt": (
        "LongTermDebtAndFinanceLeaseObligations",
        "LongTermDebt",
        "DebtAndFinanceLeaseObligations",
    ),
    "_debt_current": (
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtCurrent",
        "ShortTermBorrowings",
        "DebtCurrent",
    ),
    "_debt_noncurrent": (
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebtNoncurrent",
        "DebtNoncurrent",
    ),
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "shareholders_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "dividends_paid": ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"),
    "diluted_shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "interest_expense": ("InterestExpenseNonOperating", "InterestAndDebtExpense"),
}


def _sec_fact_tag_index() -> dict[str, tuple[str, int]]:
    return {
        tag: (metric, rank)
        for metric, tags in _SEC_FACT_TAGS.items()
        for rank, tag in enumerate(tags)
    }


def _sec_period_type(form: str) -> str | None:
    clean = form.upper().replace("/A", "")
    if clean in {"10-K", "20-F", "40-F"}:
        return "annual"
    if clean == "10-Q":
        return "quarterly"
    return None


def _sec_fact_duration(record: Mapping[str, Any]) -> int | None:
    start = _timestamp(record.get("start"))
    end = _timestamp(record.get("end"))
    if start is None or end is None:
        return None
    return max((end.normalize() - start.normalize()).days, 0)


def _select_sec_fact(records: list[dict[str, Any]], period_type: str) -> dict[str, Any]:
    def ordering(record: dict[str, Any]) -> tuple[int, int]:
        duration = record.get("duration_days")
        if duration is None:
            duration_order = 0
        elif period_type == "annual":
            duration_order = -int(duration)
        else:
            duration_order = int(duration)
        return int(record["tag_rank"]), duration_order

    return min(records, key=ordering)


@dataclass(frozen=True)
class SecCompanyFactsResult:
    fundamental_vintages: pd.DataFrame
    fundamentals_reported: pd.DataFrame
    facts_seen: int
    filing_vintages: int


@dataclass
class SecCompanyFactsClient:
    """Build filing-accession vintages from the SEC's first-party XBRL facts."""

    client: HttpClient
    base_url: str = SEC_COMPANYFACTS_URL

    def _headers(self) -> dict[str, str]:
        user_agent = get_env("SEC_USER_AGENT", "") or ""
        if not user_agent:
            raise DataSourceRequestError(
                "SEC_USER_AGENT is required and must identify the application and contact."
            )
        return {"User-Agent": user_agent}

    def fundamentals(
        self,
        security_id: str,
        cik: str | int,
        *,
        start_date: date,
        end_date: date,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
        acceptance_by_accession: Mapping[str, object] | None = None,
    ) -> SecCompanyFactsResult:
        padded_cik = str(cik).zfill(10)
        payload = self.client.get(
            f"{self.base_url}/CIK{padded_cik}.json",
            headers=self._headers(),
        ).json()
        if not isinstance(payload, Mapping):
            raise DataSourceRequestError("SEC companyfacts returned a non-object response.")
        facts = payload.get("facts")
        if not isinstance(facts, Mapping):
            raise DataSourceRequestError("SEC companyfacts omitted facts.")
        namespaces = [
            values
            for name, values in facts.items()
            if str(name).lower() in {"us-gaap", "ifrs-full"} and isinstance(values, Mapping)
        ]
        tag_index = _sec_fact_tag_index()
        flat: list[dict[str, Any]] = []
        for namespace in namespaces:
            for tag, fact in namespace.items():
                target = tag_index.get(str(tag))
                if target is None or not isinstance(fact, Mapping):
                    continue
                units = fact.get("units")
                if not isinstance(units, Mapping):
                    continue
                metric, tag_rank = target
                for unit, records in units.items():
                    if not isinstance(records, list):
                        continue
                    for record in records:
                        if not isinstance(record, Mapping):
                            continue
                        form = str(record.get("form") or "").upper()
                        period_type = _sec_period_type(form)
                        accession = str(record.get("accn") or "").strip()
                        fiscal_end = _timestamp(record.get("end"))
                        filed = _timestamp(record.get("filed"))
                        value = _number(record.get("val"))
                        if (
                            period_type is None
                            or not accession
                            or fiscal_end is None
                            or filed is None
                            or value is None
                            or fiscal_end.date() < start_date
                            or fiscal_end.date() > end_date
                        ):
                            continue
                        flat.append(
                            {
                                "accession": accession,
                                "fiscal_period_end": fiscal_end.normalize(),
                                "fiscal_period_type": period_type,
                                "filing_date": filed.normalize(),
                                "metric": metric,
                                "value": value,
                                "unit": str(unit).upper(),
                                "tag_rank": tag_rank,
                                "duration_days": _sec_fact_duration(record),
                            }
                        )

        retrieved = _timestamp(retrieved_at) or pd.Timestamp(retrieved_at)
        acceptance_map = {
            str(accession): _timestamp(timestamp)
            for accession, timestamp in (acceptance_by_accession or {}).items()
        }
        grouped: dict[tuple[str, pd.Timestamp, str, pd.Timestamp], list[dict[str, Any]]] = {}
        for fact in flat:
            key = (
                fact["accession"],
                fact["fiscal_period_end"],
                fact["fiscal_period_type"],
                fact["filing_date"],
            )
            grouped.setdefault(key, []).append(fact)

        rows: list[dict[str, Any]] = []
        for (accession, fiscal_end, period_type, filing_date), records in grouped.items():
            metrics: dict[str, float] = {}
            currency_counts: dict[str, int] = {}
            for metric in _SEC_FACT_TAGS:
                candidates = [record for record in records if record["metric"] == metric]
                if not candidates:
                    continue
                selected = _select_sec_fact(candidates, period_type)
                metrics[metric] = float(selected["value"])
                unit = str(selected["unit"])
                if metric != "diluted_shares" and re.fullmatch(r"[A-Z]{3}", unit):
                    currency_counts[unit] = currency_counts.get(unit, 0) + 1
            if "total_debt" not in metrics:
                debt_parts = [metrics.get("_debt_current"), metrics.get("_debt_noncurrent")]
                if any(value is not None for value in debt_parts):
                    metrics["total_debt"] = sum(value or 0.0 for value in debt_parts)
            if "operating_cash_flow" in metrics and "capital_expenditure" in metrics:
                metrics["free_cash_flow"] = metrics["operating_cash_flow"] - abs(
                    metrics["capital_expenditure"]
                )
            canonical_metrics = {
                key: value for key, value in metrics.items() if not key.startswith("_")
            }
            if len(canonical_metrics) < 3:
                continue
            observed_acceptance = acceptance_map.get(accession)
            available_from = observed_acceptance or filing_date + pd.Timedelta(days=1)
            currency = max(currency_counts, key=currency_counts.get) if currency_counts else None
            rows.append(
                {
                    "security_id": str(security_id).upper(),
                    "provider_symbol": accession,
                    "fiscal_period_end": fiscal_end,
                    "fiscal_period_type": period_type,
                    "available_from": available_from,
                    "announcement_at": observed_acceptance or filing_date,
                    "revision_at": available_from,
                    "currency": currency,
                    **canonical_metrics,
                    "source": SEC_COMPANYFACTS_SOURCE,
                    "retrieved_at": retrieved,
                    "ingestion_run_id": ingestion_run_id,
                    "vintage_semantics": "observed_filing_accession_companyfacts",
                }
            )

        vintage_frame = pd.DataFrame(rows)
        if vintage_frame.empty:
            empty_vintages = _empty("fundamental_vintages")
            empty_model = _empty("fundamentals_reported")
            return SecCompanyFactsResult(empty_vintages, empty_model, len(flat), 0)
        metric_columns = [
            column
            for column in SCHEMAS["fundamentals_reported"].column_names
            if column
            not in {
                "security_id",
                "fiscal_period_end",
                "fiscal_period_type",
                "filing_date",
                "available_from",
                "currency",
                "source",
                "retrieved_at",
                "ingestion_run_id",
                "vintage_id",
                "row_hash",
            }
        ]
        for column in metric_columns:
            if column not in vintage_frame:
                vintage_frame[column] = pd.NA
        vintage_frame["row_hash"] = record_hash(
            vintage_frame,
            [
                "security_id",
                "provider_symbol",
                "fiscal_period_end",
                "fiscal_period_type",
                "available_from",
                *metric_columns,
                "source",
            ],
        )
        vintage_frame["vintage_id"] = vintage_frame["row_hash"]
        vintage_frame = vintage_frame[list(SCHEMAS["fundamental_vintages"].column_names)]

        model_frame = vintage_frame.copy()
        model_frame["filing_date"] = pd.to_datetime(model_frame["announcement_at"]).dt.normalize()
        model_frame["source"] = SEC_COMPANYFACTS_SOURCE
        model_frame["row_hash"] = record_hash(
            model_frame,
            [
                "security_id",
                "fiscal_period_end",
                "fiscal_period_type",
                "available_from",
                "vintage_id",
                "source",
            ],
        )
        model_frame = model_frame[list(SCHEMAS["fundamentals_reported"].column_names)]
        return SecCompanyFactsResult(vintage_frame, model_frame, len(flat), len(vintage_frame))


MERGENT_MAPCODES: dict[int, str] = {
    -3887: "revenue",
    -4524: "operating_income",
    -3994: "net_income",
    -976: "operating_cash_flow",
    -873: "total_assets",
    -965: "total_liabilities",
    -4049: "cash_and_equivalents",
    -4497: "shareholders_equity",
    -4022: "diluted_shares",
    -984: "ebitda",
}


def _datatable_rows(payload: object) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(payload, Mapping):
        raise DataSourceRequestError("Nasdaq Data Link returned a non-object response.")
    table = payload.get("datatable")
    if not isinstance(table, Mapping):
        raise DataSourceRequestError("Nasdaq Data Link response omitted datatable.")
    columns_raw = table.get("columns") or []
    columns = [
        str(column.get("name"))
        for column in columns_raw
        if isinstance(column, Mapping) and column.get("name")
    ]
    data = table.get("data") or []
    rows = [dict(zip(columns, values, strict=False)) for values in data]
    meta = table.get("meta")
    cursor = meta.get("next_cursor_id") if isinstance(meta, Mapping) else None
    return rows, str(cursor) if cursor else None


@dataclass
class NasdaqMergentClient:
    """Fetch Mergent global fundamentals through Nasdaq Data Link Tables."""

    client: HttpClient
    base_url: str = NASDAQ_MERGENT_URL
    reporting_lag_days: int = 120
    page_size: int = 10_000

    def _raw_rows(self, ticker: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
        api_key = get_env("NASDAQ_DATA_LINK_API_KEY", "") or get_env(
            "NASDAQ_API_KEY", ""
        ) or ""
        if not api_key:
            raise DataSourceRequestError(
                "NASDAQ_DATA_LINK_API_KEY is required for Mergent fundamentals."
            )
        params: dict[str, object] = {
            "ticker": str(ticker).strip().upper(),
            "reporttype": "A",
            "reportdate.gte": f"{int(start_year)}-01-01",
            "reportdate.lte": f"{int(end_year)}-12-31",
            "qopts.per_page": self.page_size,
            "api_key": api_key,
        }
        output: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            if cursor:
                params["qopts.cursor_id"] = cursor
            page, cursor = _datatable_rows(
                self.client.get(self.base_url, params=params).json()
            )
            output.extend(page)
            if not cursor:
                return output

    def annual_fundamentals(
        self,
        security_id: str,
        ticker: str,
        *,
        start_year: int,
        end_year: int,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> pd.DataFrame:
        raw = pd.DataFrame(self._raw_rows(ticker, start_year, end_year))
        if raw.empty:
            return _empty("fundamentals_reported")
        raw["reportdate"] = pd.to_datetime(raw.get("reportdate"), errors="coerce")
        raw["mapcode"] = pd.to_numeric(raw.get("mapcode"), errors="coerce")
        raw["amount"] = pd.to_numeric(raw.get("amount"), errors="coerce")
        raw = raw.loc[
            raw["reportdate"].notna()
            & raw["mapcode"].isin(MERGENT_MAPCODES)
            & raw["amount"].notna()
        ].copy()
        if raw.empty:
            return _empty("fundamentals_reported")

        company_column = "compnumber" if "compnumber" in raw else "ticker"
        best_company = (
            raw.groupby(company_column, dropna=False)["reportdate"]
            .nunique()
            .sort_values(ascending=False)
            .index[0]
        )
        raw = raw.loc[raw[company_column].eq(best_company)]
        rows: list[dict[str, Any]] = []
        for report_date, group in raw.groupby("reportdate", sort=True):
            values: dict[str, float] = {}
            for record in group.itertuples(index=False):
                column = MERGENT_MAPCODES.get(int(record.mapcode))
                if column and column not in values:
                    values[column] = float(record.amount)
            if sum(column in values for column in ("revenue", "net_income", "total_assets", "shareholders_equity")) < 3:
                continue
            currency_values = group.get("currency", pd.Series(dtype=object)).dropna()
            rows.append(
                {
                    "security_id": str(security_id).upper(),
                    "fiscal_period_end": pd.Timestamp(report_date).normalize(),
                    "fiscal_period_type": "annual",
                    "filing_date": pd.NaT,
                    "available_from": pd.Timestamp(report_date).normalize()
                    + pd.Timedelta(days=self.reporting_lag_days),
                    "currency": (
                        str(currency_values.iloc[0]).upper()
                        if not currency_values.empty
                        else None
                    ),
                    **values,
                }
            )
        if not rows:
            return _empty("fundamentals_reported")
        clean = normalise_fundamentals(
            pd.DataFrame(rows),
            source=NASDAQ_MERGENT_SOURCE,
            retrieved_at=retrieved_at,
        )
        clean["ingestion_run_id"] = ingestion_run_id
        return clean[list(SCHEMAS["fundamentals_reported"].column_names)]


def _event_row(
    *,
    security_id: str,
    provider_symbol: str,
    exchange_code: str | None,
    event_type: str,
    effective_from: pd.Timestamp,
    effective_to: pd.Timestamp | None,
    old_symbol: str | None,
    new_symbol: str | None,
    index_symbol: str | None,
    is_delisted: bool | None,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> dict[str, Any]:
    identity = [
        provider_symbol,
        event_type,
        effective_from.date(),
        effective_to.date() if effective_to is not None else None,
        old_symbol,
        new_symbol,
        index_symbol,
        EODHD_REFERENCE_SOURCE,
    ]
    row_hash = _hash(identity)
    return {
        "event_id": row_hash,
        "security_id": security_id,
        "provider_symbol": provider_symbol,
        "exchange_code": exchange_code,
        "event_type": event_type,
        "effective_from": effective_from.normalize(),
        "effective_to": effective_to.normalize() if effective_to is not None else pd.NaT,
        "old_symbol": old_symbol,
        "new_symbol": new_symbol,
        "index_symbol": index_symbol,
        "is_delisted": is_delisted,
        "source": EODHD_REFERENCE_SOURCE,
        "retrieved_at": retrieved_at,
        "ingestion_run_id": ingestion_run_id,
        "row_hash": row_hash,
    }


@dataclass
class EodhdReferenceHistoryClient:
    """Fetch delistings, symbol changes, and historical index membership."""

    client: HttpClient
    base_url: str = EODHD_BASE_URL

    def _token(self) -> str:
        token = get_env("EODHD_API_TOKEN", "") or get_env("EODHD_API_KEY", "") or ""
        if not token:
            raise DataSourceRequestError(
                "EODHD_API_TOKEN is required for historical reference evidence."
            )
        return token

    def delisted_symbols(
        self,
        exchange: str,
        *,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> pd.DataFrame:
        payload = self.client.get(
            f"{self.base_url}/exchange-symbol-list/{exchange}",
            params={"api_token": self._token(), "fmt": "json", "delisted": 1},
        ).json()
        if not isinstance(payload, list):
            raise DataSourceRequestError(
                f"EODHD returned invalid delisted-symbol data for {exchange}."
            )
        rows: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            code = str(item.get("Code") or item.get("code") or "").strip().upper()
            if not code:
                continue
            exchange_code = str(
                item.get("Exchange") or item.get("exchange") or exchange
            ).strip().upper()
            provider_symbol = (
                code if "." in code else f"{code}.{exchange_code or exchange.upper()}"
            )
            last_trade = _timestamp(
                item.get("PreviousCloseDate")
                or item.get("previousCloseDate")
                or item.get("LastTradeDate")
            )
            effective = (
                last_trade.normalize() + pd.Timedelta(days=1)
                if last_trade is not None
                else retrieved_at.normalize()
            )
            rows.append(
                _event_row(
                    security_id=provider_symbol,
                    provider_symbol=provider_symbol,
                    exchange_code=exchange_code,
                    event_type="delisted",
                    effective_from=effective,
                    effective_to=None,
                    old_symbol=code,
                    new_symbol=None,
                    index_symbol=None,
                    is_delisted=True,
                    retrieved_at=retrieved_at,
                    ingestion_run_id=ingestion_run_id,
                )
            )
        if not rows:
            return _empty("security_reference_events")
        return pd.DataFrame(rows)[list(SCHEMAS["security_reference_events"].column_names)]

    def symbol_changes(
        self,
        *,
        start_date: date,
        end_date: date,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> pd.DataFrame:
        payload = self.client.get(
            f"{self.base_url}/symbol-change-history",
            params={
                "api_token": self._token(),
                "fmt": "json",
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "ex": "US",
            },
        ).json()
        if not isinstance(payload, list):
            raise DataSourceRequestError("EODHD returned invalid symbol-change data.")
        rows: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            old_symbol = str(item.get("old_symbol") or "").strip().upper()
            new_symbol = str(item.get("new_symbol") or "").strip().upper()
            effective = _timestamp(item.get("effective"))
            exchange = str(item.get("exchange") or "US").strip().upper()
            if not old_symbol or not new_symbol or effective is None:
                continue
            provider_symbol = f"{new_symbol}.{exchange}"
            rows.append(
                _event_row(
                    security_id=provider_symbol,
                    provider_symbol=provider_symbol,
                    exchange_code=exchange,
                    event_type="symbol_change",
                    effective_from=effective,
                    effective_to=None,
                    old_symbol=old_symbol,
                    new_symbol=new_symbol,
                    index_symbol=None,
                    is_delisted=False,
                    retrieved_at=retrieved_at,
                    ingestion_run_id=ingestion_run_id,
                )
            )
        if not rows:
            return _empty("security_reference_events")
        return pd.DataFrame(rows)[list(SCHEMAS["security_reference_events"].column_names)]

    def historical_index_membership(
        self,
        index_symbol: str,
        *,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> pd.DataFrame:
        payload = self.client.get(
            f"{self.base_url}/fundamentals/{index_symbol}",
            params={
                "api_token": self._token(),
                "fmt": "json",
                "filter": "HistoricalTickerComponents",
            },
        ).json()
        if isinstance(payload, Mapping) and "HistoricalTickerComponents" in payload:
            components = payload.get("HistoricalTickerComponents")
        else:
            components = payload
        if isinstance(components, Mapping):
            records = list(components.values())
        elif isinstance(components, list):
            records = components
        else:
            raise DataSourceRequestError(
                f"EODHD returned invalid membership history for {index_symbol}."
            )
        rows: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, Mapping):
                continue
            code = str(item.get("Code") or item.get("code") or "").strip().upper()
            start = _timestamp(item.get("StartDate") or item.get("start_date"))
            end = _timestamp(item.get("EndDate") or item.get("end_date"))
            exchange = str(item.get("Exchange") or item.get("exchange") or "US").upper()
            if not code or start is None:
                continue
            provider_symbol = code if "." in code else f"{code}.{exchange}"
            rows.append(
                _event_row(
                    security_id=provider_symbol,
                    provider_symbol=provider_symbol,
                    exchange_code=exchange,
                    event_type="index_membership",
                    effective_from=start,
                    effective_to=end,
                    old_symbol=None,
                    new_symbol=None,
                    index_symbol=str(index_symbol).upper(),
                    is_delisted=bool(
                        int(item.get("IsDelisted") or item.get("is_delisted") or 0)
                    ),
                    retrieved_at=retrieved_at,
                    ingestion_run_id=ingestion_run_id,
                )
            )
        if not rows:
            return _empty("security_reference_events")
        return pd.DataFrame(rows)[list(SCHEMAS["security_reference_events"].column_names)]


def point_in_time_coverage(repository: Any) -> pd.DataFrame:
    """Return measurable PIT evidence coverage without upgrading governance by fiat."""

    return repository.query(
        """
        WITH universe AS (
            SELECT COUNT(*) AS securities,
                   COUNT(*) FILTER (WHERE listing_status <> 'Active') AS inactive
            FROM securities
            WHERE instrument_type = 'Equity'
        ), fundamentals AS (
            SELECT COUNT(*) AS rows,
                   COUNT(*) FILTER (WHERE filing_date IS NOT NULL) AS dated,
                   COUNT(DISTINCT fundamentals_reported.security_id) AS securities,
                   COUNT(DISTINCT fundamentals_reported.security_id) FILTER (
                       WHERE securities.region = 'US'
                   ) AS us_securities
            FROM fundamentals_reported
            LEFT JOIN securities USING (security_id)
            WHERE LOWER(fundamentals_reported.source) NOT LIKE '%mock%'
              AND LOWER(fundamentals_reported.source) NOT LIKE '%synthetic%'
        ), prices AS (
            SELECT COUNT(DISTINCT security_id) AS securities,
                   COUNT(DISTINCT security_id) FILTER (WHERE volume > 0) AS volume_securities,
                   COUNT(DISTINCT prices_daily.security_id) FILTER (
                       WHERE securities.listing_status <> 'Active'
                   ) AS inactive_securities
            FROM prices_daily
            LEFT JOIN securities USING (security_id)
        ), filings AS (
            SELECT COUNT(*) AS rows,
                   COUNT(DISTINCT security_id) AS securities,
                   COUNT(*) FILTER (WHERE acceptance_datetime IS NOT NULL) AS accepted
            FROM filing_metadata
        ), events AS (
            SELECT COUNT(*) AS rows,
                   COUNT(*) FILTER (WHERE event_type = 'delisted') AS delistings,
                   COUNT(*) FILTER (WHERE event_type = 'symbol_change') AS symbol_changes,
                   COUNT(*) FILTER (WHERE event_type = 'index_membership') AS memberships
            FROM security_reference_events
        )
        SELECT
            universe.securities AS universe_securities,
            universe.inactive AS inactive_securities,
            fundamentals.rows AS fundamental_rows,
            fundamentals.securities AS fundamental_securities,
            fundamentals.us_securities AS us_fundamental_securities,
            fundamentals.dated AS fundamental_rows_with_filing_date,
            filings.rows AS filing_metadata_rows,
            filings.securities AS filing_metadata_securities,
            filings.accepted AS observed_acceptance_timestamps,
            prices.securities AS price_securities,
            prices.volume_securities AS securities_with_historical_volume,
            prices.inactive_securities AS inactive_price_securities,
            events.rows AS reference_event_rows,
            events.delistings AS delisting_events,
            events.symbol_changes AS symbol_change_events,
            events.memberships AS historical_membership_events
        FROM universe, fundamentals, prices, filings, events
        """
    )
