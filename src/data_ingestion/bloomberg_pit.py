from __future__ import annotations

from datetime import date, datetime
import math
import re
from typing import Any, Mapping

import pandas as pd

from src.data.normalisers import record_hash
from src.data.schemas import SCHEMAS


FUNDAMENTAL_FIELDS = (
    "ARD_REVENUES",
    "SALES_REV_TURN",
    "ARD_OPERATING_INCOME",
    "IS_OPER_INC",
    "ARD_NET_INC",
    "NET_INCOME",
    "ARD_TOT_CASH_FLOWS_FROM_OPS",
    "CF_CASH_FROM_OPER",
    "CAPITAL_EXPEND",
    "CF_FREE_CASH_FLOW",
    "ARD_TOT_ASSETS",
    "BS_TOT_ASSET",
    "ARD_TOT_LIABILITIES",
    "BS_TOT_LIAB2",
    "SHORT_AND_LONG_TERM_DEBT",
    "BS_CASH_NEAR_CASH_ITEM",
    "ARD_TOTAL_SHAREHOLDERS_EQUITY",
    "TOT_COMMON_EQY",
    "CF_DVD_PAID",
    "ARD_WEIGHTED_AVG_SHARE_DILUTED",
    "IS_SH_FOR_DILUTED_EPS",
    "EBITDA",
    "IS_INT_EXPENSE",
    "LATEST_ANNOUNCEMENT_DT",
    "ANNOUNCEMENT_DT",
    "LATEST_ANNOUNCEMENT_PERIOD",
    "FILING_STATUS",
    "FUNDAMENTAL_DATABASE_DATE",
)

MARKET_CAP_FIELDS = (
    "CUR_MKT_CAP",
    "EQY_SH_OUT",
    "EQY_FLOAT",
    "EQY_FREE_FLOAT_PCT",
)

IDENTIFIER_FIELDS = (
    "ID_ISIN",
    "ID_BB_GLOBAL",
    "ID_BB_GLOBAL_PARENT_CO",
    "TICKER_AND_EXCH_CODE",
    "PARSEKYABLE_DES",
)

CURRENCY_FIELDS = (
    "CRNCY",
)

CORPORATE_ACTION_FIELDS = (
    "DVD_HIST_ALL",
    "EQY_DVD_HIST_SPLITS",
)

REFERENCE_FIELDS = IDENTIFIER_FIELDS + CURRENCY_FIELDS + CORPORATE_ACTION_FIELDS

_FUNDAMENTAL_CANDIDATES = {
    "revenue": ("ARD_REVENUES", "SALES_REV_TURN"),
    "operating_income": ("ARD_OPERATING_INCOME", "IS_OPER_INC"),
    "net_income": ("ARD_NET_INC", "NET_INCOME"),
    "operating_cash_flow": ("ARD_TOT_CASH_FLOWS_FROM_OPS", "CF_CASH_FROM_OPER"),
    "capital_expenditure": ("CAPITAL_EXPEND",),
    "free_cash_flow": ("CF_FREE_CASH_FLOW",),
    "total_assets": ("ARD_TOT_ASSETS", "BS_TOT_ASSET"),
    "total_liabilities": ("ARD_TOT_LIABILITIES", "BS_TOT_LIAB2"),
    "total_debt": ("SHORT_AND_LONG_TERM_DEBT",),
    "cash_and_equivalents": ("BS_CASH_NEAR_CASH_ITEM",),
    "shareholders_equity": ("ARD_TOTAL_SHAREHOLDERS_EQUITY", "TOT_COMMON_EQY"),
    "dividends_paid": ("CF_DVD_PAID",),
    "diluted_shares": ("ARD_WEIGHTED_AVG_SHARE_DILUTED", "IS_SH_FOR_DILUTED_EPS"),
    "ebitda": ("EBITDA",),
    "interest_expense": ("IS_INT_EXPENSE",),
}

_IDENTIFIER_FIELDS = {
    "ID_ISIN": "isin",
    "ID_BB_GLOBAL": "figi",
    "ID_BB_GLOBAL_PARENT_CO": "parent_figi",
    "TICKER_AND_EXCH_CODE": "bloomberg_ticker_exchange",
    "PARSEKYABLE_DES": "bloomberg_parsekey",
}


def _number(value: object, scale: float = 1.0) -> float | None:
    try:
        result = float(value) * scale
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _first_number(values: Mapping[str, Any], fields: tuple[str, ...], scale: float) -> float | None:
    for field in fields:
        value = _number(values.get(field), scale)
        if value is not None:
            return value
    return None


def _timestamp(value: object) -> pd.Timestamp | None:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        parsed = pd.Timestamp(value)
    else:
        text = str(value).strip()
        if re.fullmatch(r"\d{8}(?:\.0)?", text):
            text = text.split(".", 1)[0]
            parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
        else:
            parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    parsed = pd.Timestamp(parsed)
    return parsed.tz_localize(None) if parsed.tzinfo is not None else parsed


def fiscal_period_end(value: object) -> pd.Timestamp | None:
    text = str(value or "").strip().upper()
    quarter = re.fullmatch(r"(\d{4}):Q([1-4])", text)
    if quarter:
        period = pd.Period(f"{quarter.group(1)}Q{quarter.group(2)}", freq="Q-DEC")
        return period.end_time.normalize()
    annual = re.fullmatch(r"(\d{4}):(A|FY|Y)", text)
    if annual:
        return pd.Timestamp(f"{annual.group(1)}-12-31")
    return None


def _finalise(frame: pd.DataFrame, table_name: str, hash_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=SCHEMAS[table_name].column_names)
    frame = frame.copy()
    frame["row_hash"] = record_hash(frame, hash_columns)
    if "vintage_id" in SCHEMAS[table_name].column_names:
        frame["vintage_id"] = frame["row_hash"]
    return frame[list(SCHEMAS[table_name].column_names)]


def normalise_fundamental_snapshot(
    payload: Mapping[str, Mapping[str, Any]],
    symbol_to_security: Mapping[str, str],
    currency_by_symbol: Mapping[str, str],
    as_of_date: object,
    period_type: str,
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of_date).normalize()
    rows: list[dict[str, object]] = []
    for provider_symbol, values in payload.items():
        period_end = fiscal_period_end(values.get("LATEST_ANNOUNCEMENT_PERIOD"))
        security_id = symbol_to_security.get(provider_symbol)
        if security_id is None or period_end is None:
            continue
        row: dict[str, object] = {
            "security_id": security_id,
            "provider_symbol": provider_symbol,
            "fiscal_period_end": period_end,
            "fiscal_period_type": period_type,
            "available_from": as_of,
            "announcement_at": _timestamp(
                values.get("LATEST_ANNOUNCEMENT_DT", values.get("ANNOUNCEMENT_DT"))
            ),
            "revision_at": as_of,
            "currency": currency_by_symbol.get(provider_symbol),
            "source": "bloomberg_desktop",
            "retrieved_at": retrieved_at,
            "ingestion_run_id": ingestion_run_id,
            "vintage_semantics": "database_as_of_monthly_ard_preferred",
        }
        for column, candidates in _FUNDAMENTAL_CANDIDATES.items():
            row[column] = _first_number(values, candidates, 1_000_000.0)
        if sum(row[column] is not None for column in _FUNDAMENTAL_CANDIDATES) >= 3:
            rows.append(row)
    frame = pd.DataFrame(rows)
    hash_columns = [
        "security_id",
        "fiscal_period_end",
        "fiscal_period_type",
        "available_from",
        "announcement_at",
        "revision_at",
        "currency",
        *_FUNDAMENTAL_CANDIDATES,
        "source",
        "vintage_semantics",
    ]
    return _finalise(frame, "fundamental_vintages", hash_columns)


def to_model_fundamentals(vintages: pd.DataFrame) -> pd.DataFrame:
    """Project audited Bloomberg vintages into the model's canonical statement table."""
    if vintages.empty:
        return pd.DataFrame(columns=SCHEMAS["fundamentals_reported"].column_names)
    output = vintages.copy()
    output["filing_date"] = pd.to_datetime(output["announcement_at"], errors="coerce")
    output["source"] = "bloomberg_database_as_of"
    output["row_hash"] = record_hash(
        output,
        [
            "security_id",
            "fiscal_period_end",
            "fiscal_period_type",
            "available_from",
            "vintage_id",
            "source",
        ],
    )
    return output[list(SCHEMAS["fundamentals_reported"].column_names)]


def normalise_market_cap_history(
    history: pd.DataFrame,
    symbol_to_security: Mapping[str, str],
    currency_by_symbol: Mapping[str, str],
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for values in history.to_dict("records"):
        provider_symbol = str(values.get("provider_symbol", ""))
        security_id = symbol_to_security.get(provider_symbol)
        as_of = _timestamp(values.get("date"))
        if security_id is None or as_of is None:
            continue
        market_cap = _number(values.get("CUR_MKT_CAP"), 1_000_000.0)
        float_percent = _number(values.get("EQY_FREE_FLOAT_PCT"))
        row = {
            "security_id": security_id,
            "provider_symbol": provider_symbol,
            "as_of_date": as_of,
            # The walk-forward anchor is an end-of-day decision timestamp.
            "available_from": as_of,
            "market_cap_local": market_cap,
            "shares_outstanding": _number(values.get("EQY_SH_OUT"), 1_000_000.0),
            "free_float_shares": _number(values.get("EQY_FLOAT"), 1_000_000.0),
            "free_float_percent": float_percent,
            "free_float_market_cap_local": (
                market_cap * float_percent / 100.0
                if market_cap is not None and float_percent is not None
                else None
            ),
            "currency": currency_by_symbol.get(provider_symbol),
            "source": "bloomberg_desktop",
            "retrieved_at": retrieved_at,
            "ingestion_run_id": ingestion_run_id,
        }
        if any(row[key] is not None for key in ("market_cap_local", "shares_outstanding", "free_float_shares")):
            rows.append(row)
    frame = pd.DataFrame(rows)
    hash_columns = [
        "security_id",
        "as_of_date",
        "available_from",
        "market_cap_local",
        "shares_outstanding",
        "free_float_shares",
        "free_float_percent",
        "free_float_market_cap_local",
        "currency",
        "source",
    ]
    return _finalise(frame, "market_cap_vintages", hash_columns)


def reference_currency_map(payload: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    return {
        symbol: str(values.get("CRNCY", "")).strip().upper()
        for symbol, values in payload.items()
        if str(values.get("CRNCY", "")).strip()
    }


def normalise_identifier_snapshot(
    payload: Mapping[str, Mapping[str, Any]],
    symbol_to_security: Mapping[str, str],
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for provider_symbol, values in payload.items():
        security_id = symbol_to_security.get(provider_symbol)
        if security_id is None:
            continue
        for field, identifier_type in _IDENTIFIER_FIELDS.items():
            identifier_value = str(values.get(field, "")).strip()
            if not identifier_value:
                continue
            rows.append(
                {
                    "security_id": security_id,
                    "identifier_type": identifier_type,
                    "identifier_value": identifier_value,
                    "effective_from": retrieved_at.normalize(),
                    "effective_to": pd.NaT,
                    "available_from": retrieved_at,
                    "provider_symbol": provider_symbol,
                    "source": "bloomberg_desktop",
                    "retrieved_at": retrieved_at,
                    "ingestion_run_id": ingestion_run_id,
                }
            )
    frame = pd.DataFrame(rows)
    hash_columns = [
        "security_id",
        "identifier_type",
        "identifier_value",
        "effective_from",
        "provider_symbol",
        "source",
    ]
    return _finalise(frame, "identifier_vintages", hash_columns)


def normalise_corporate_actions(
    payload: Mapping[str, Mapping[str, Any]],
    symbol_to_security: Mapping[str, str],
    currency_by_symbol: Mapping[str, str],
    retrieved_at: pd.Timestamp,
    ingestion_run_id: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for provider_symbol, values in payload.items():
        security_id = symbol_to_security.get(provider_symbol)
        if security_id is None:
            continue
        events = list(values.get("DVD_HIST_ALL", []) or [])
        events.extend(values.get("EQY_DVD_HIST_SPLITS", []) or [])
        for event in events:
            ex_date = _timestamp(event.get("Ex-Date")) if isinstance(event, Mapping) else None
            if ex_date is None:
                continue
            event_type_text = str(event.get("Dividend Type", "distribution")).strip().lower()
            action_type = re.sub(r"[^a-z0-9]+", "_", event_type_text).strip("_") or "distribution"
            declaration = _timestamp(event.get("Declared Date"))
            amount = _number(event.get("Dividend Amount"))
            event_frame = pd.DataFrame(
                [{"security_id": security_id, "action_type": action_type, "ex_date": ex_date}]
            )
            event_id = record_hash(event_frame, ["security_id", "action_type", "ex_date"]).iloc[0]
            rows.append(
                {
                    "event_id": event_id,
                    "security_id": security_id,
                    "provider_symbol": provider_symbol,
                    "action_type": action_type,
                    "declaration_date": declaration,
                    "ex_date": ex_date,
                    "record_date": _timestamp(event.get("Record Date")),
                    "payment_date": _timestamp(event.get("Payable Date")),
                    "effective_date": ex_date,
                    "split_ratio": amount if "split" in action_type else None,
                    "cash_amount": None if "split" in action_type else amount,
                    "currency": currency_by_symbol.get(provider_symbol),
                    "available_from": declaration if declaration is not None else ex_date,
                    "revision_at": retrieved_at,
                    "source": "bloomberg_desktop",
                    "retrieved_at": retrieved_at,
                    "ingestion_run_id": ingestion_run_id,
                }
            )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(
            ["event_id", "declaration_date", "cash_amount", "split_ratio"], keep="last"
        )
    hash_columns = [
        "event_id",
        "declaration_date",
        "record_date",
        "payment_date",
        "cash_amount",
        "split_ratio",
        "currency",
        "source",
    ]
    return _finalise(frame, "corporate_action_vintages", hash_columns)
