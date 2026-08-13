from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import time
from typing import Any, Iterator, Mapping, Sequence

import pandas as pd

from src.data_ingestion.http_client import DataSourceRequestError
from src.utils.env import get_env

try:
    import blpapi

    BLPAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the optional Bloomberg SDK
    blpapi = None
    BLPAPI_AVAILABLE = False


LOGGER = logging.getLogger(__name__)

PRICE_COLUMNS = [
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
    "return",
]

_PRICE_FIELD_MAP = {
    "PX_OPEN": "open",
    "PX_HIGH": "high",
    "PX_LOW": "low",
    "PX_LAST": "close",
    "PX_VOLUME": "volume",
}

_BLOOMBERG_MARKET_BY_EXCHANGE = {
    "US": "US",
    "LSE": "LN",
    "HK": "HK",
    "SHG": "CH",
    "SHE": "CH",
    "XETRA": "GY",
    "F": "GR",
    "DU": "GR",
    "MU": "GR",
    "HM": "GR",
    "HA": "GR",
    "STU": "GR",
    "SW": "SW",
    "VI": "AV",
    "PA": "FP",
    "AS": "NA",
    "BR": "BB",
    "CO": "DC",
    "ST": "SS",
    "MC": "SM",
    "HE": "FH",
    "IR": "ID",
}


class BloombergConfigurationError(DataSourceRequestError):
    """Raised when the local Bloomberg Desktop API cannot be used."""


class BloombergRequestError(DataSourceRequestError):
    """Raised when Bloomberg returns no usable response for a request."""


@dataclass(frozen=True)
class BloombergConfig:
    host: str = "127.0.0.1"
    port: int = 8194
    timeout_seconds: int = 30
    lookback_days: int = 365 * 30
    max_securities_per_request: int = 10
    adjustment_normal: bool = True
    adjustment_abnormal: bool = True
    adjustment_split: bool = True

    @classmethod
    def from_env(cls) -> "BloombergConfig":
        return cls(
            host=get_env("BLOOMBERG_HOST", "127.0.0.1") or "127.0.0.1",
            port=int(get_env("BLOOMBERG_PORT", "8194") or 8194),
            timeout_seconds=int(get_env("BLOOMBERG_TIMEOUT_SECONDS", "30") or 30),
            lookback_days=int(get_env("BLOOMBERG_LOOKBACK_DAYS", str(365 * 30)) or 365 * 30),
            max_securities_per_request=int(
                get_env("BLOOMBERG_MAX_SECURITIES_PER_REQUEST", "10") or 10
            ),
            adjustment_normal=_env_bool("BLOOMBERG_ADJUSTMENT_NORMAL", True),
            adjustment_abnormal=_env_bool("BLOOMBERG_ADJUSTMENT_ABNORMAL", True),
            adjustment_split=_env_bool("BLOOMBERG_ADJUSTMENT_SPLIT", True),
        )


def _env_bool(name: str, default: bool) -> bool:
    value = get_env(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _clean_security_code(value: object, exchange_code: object) -> str:
    code = _optional_text(value).upper()
    exchange = _optional_text(exchange_code).upper()
    suffix = f".{exchange}"
    if code.endswith(suffix):
        code = code[: -len(suffix)]
    if exchange == "HK":
        code = code.split("-OL", 1)[0]
        if code.isdigit():
            code = str(int(code))
    return code


def bloomberg_equity_symbol(
    security_code: object,
    exchange_code: object,
    isin: object | None = None,
) -> str | None:
    """Build a Bloomberg equity identifier, falling back to ISIN resolution."""
    exchange = _optional_text(exchange_code).upper()
    code = _clean_security_code(security_code, exchange)
    market = _BLOOMBERG_MARKET_BY_EXCHANGE.get(exchange)
    if code and market:
        return f"{code} {market} Equity"
    isin_value = _optional_text(isin).upper()
    if isin_value and isin_value not in {"NAN", "<NA>", "NONE"}:
        return f"/isin/{isin_value}"
    return None


def bloomberg_symbol_for_row(row: Mapping[str, object]) -> str | None:
    explicit = _optional_text(row.get("bloomberg_ticker"))
    if explicit and explicit.upper() not in {"NAN", "<NA>", "NONE"}:
        return explicit
    security_id = row.get("security_id", row.get("ticker", ""))
    return bloomberg_equity_symbol(security_id, row.get("exchange_code", ""), row.get("isin"))


def _chunks(values: Sequence[str], size: int) -> Iterator[list[str]]:
    chunk_size = max(int(size), 1)
    for start in range(0, len(values), chunk_size):
        yield list(values[start : start + chunk_size])


def normalise_historical_payload(
    payload: Mapping[str, Any],
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Convert one HistoricalDataResponse payload into model-ready rows."""
    security_data = payload.get("securityData", {})
    if not isinstance(security_data, Mapping):
        return pd.DataFrame(columns=PRICE_COLUMNS), {"request": "Missing securityData"}
    symbol = str(security_data.get("security", "")).strip()
    security_error = security_data.get("securityError")
    if isinstance(security_error, Mapping):
        message = str(security_error.get("message", security_error.get("category", "Unknown security error")))
        return pd.DataFrame(columns=PRICE_COLUMNS), {symbol or "request": message}

    field_errors: dict[str, str] = {}
    for item in security_data.get("fieldExceptions", []) or []:
        if not isinstance(item, Mapping):
            continue
        field_id = str(item.get("fieldId", "unknown_field"))
        error_info = item.get("errorInfo", {})
        message = error_info.get("message", "Field unavailable") if isinstance(error_info, Mapping) else error_info
        field_errors[f"{symbol}:{field_id}"] = str(message)

    rows: list[dict[str, object]] = []
    for item in security_data.get("fieldData", []) or []:
        if not isinstance(item, Mapping) or item.get("date") is None or item.get("PX_LAST") is None:
            continue
        row: dict[str, object] = {"date": item["date"], "ticker": symbol}
        for field, column in _PRICE_FIELD_MAP.items():
            row[column] = item.get(field)
        row["adjusted_close"] = item.get("PX_LAST")
        rows.append(row)

    if not rows:
        if not field_errors:
            field_errors[symbol or "request"] = "No historical rows returned"
        return pd.DataFrame(columns=PRICE_COLUMNS), field_errors

    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ("open", "high", "low", "close", "adjusted_close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "ticker", "close"])
    frame = frame.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
    frame["return"] = frame.groupby("ticker", sort=False)["adjusted_close"].pct_change().fillna(0.0)
    return frame[PRICE_COLUMNS].reset_index(drop=True), field_errors


class BloombergDesktopAdapter:
    """Bloomberg Desktop API adapter for entitled historical and reference data."""

    def __init__(self, config: BloombergConfig | None = None) -> None:
        if not BLPAPI_AVAILABLE or blpapi is None:
            raise BloombergConfigurationError(
                "blpapi is not installed. Install requirements-bloomberg.txt using Bloomberg's package index."
            )
        self.config = config or BloombergConfig.from_env()
        self.last_errors: dict[str, str] = {}

    @contextmanager
    def _session(self):
        options = blpapi.SessionOptions()
        options.setServerHost(self.config.host)
        options.setServerPort(self.config.port)
        options.setClientMode(blpapi.SessionOptions.DAPI)
        options.setConnectTimeout(max(self.config.timeout_seconds * 1000, 1000))
        session = blpapi.Session(options)
        started = False
        try:
            started = bool(session.start())
            if not started:
                raise BloombergConfigurationError(
                    f"Could not connect to Bloomberg Desktop API at {self.config.host}:{self.config.port}. "
                    "Keep Bloomberg Terminal open and logged in on this Windows session."
                )
            if not session.openService("//blp/refdata"):
                raise BloombergConfigurationError("Connected to Bloomberg but could not open //blp/refdata.")
            yield session, session.getService("//blp/refdata")
        finally:
            if started:
                session.stop()

    def health_check(self) -> dict[str, object]:
        started_at = time.perf_counter()
        with self._session():
            pass
        return {
            "connected": True,
            "host": self.config.host,
            "port": self.config.port,
            "blpapi_version": blpapi.version(),
            "latency_seconds": time.perf_counter() - started_at,
        }

    def _historical_request(
        self,
        session,
        service,
        symbols: Sequence[str],
        fields: Sequence[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        periodicity: str = "DAILY",
        overrides: Mapping[str, object] | None = None,
    ) -> tuple[list[Mapping[str, Any]], dict[str, str]]:
        request = service.createRequest("HistoricalDataRequest")
        for symbol in symbols:
            request.append("securities", symbol)
        for field in fields:
            request.append("fields", field)
        request.set("startDate", start_date.strftime("%Y%m%d"))
        request.set("endDate", end_date.strftime("%Y%m%d"))
        request.set("periodicitySelection", str(periodicity).upper())
        request.set("adjustmentNormal", self.config.adjustment_normal)
        request.set("adjustmentAbnormal", self.config.adjustment_abnormal)
        request.set("adjustmentSplit", self.config.adjustment_split)
        for field_id, value in (overrides or {}).items():
            override = request.getElement("overrides").appendElement()
            override.setElement("fieldId", str(field_id))
            override.setElement("value", str(value))
        session.sendRequest(request)

        payloads: list[Mapping[str, Any]] = []
        errors: dict[str, str] = {}
        deadline = time.monotonic() + self.config.timeout_seconds
        while time.monotonic() < deadline:
            remaining_ms = max(int((deadline - time.monotonic()) * 1000), 1)
            event = session.nextEvent(min(remaining_ms, 5000))
            for message in event:
                message_type = str(message.messageType())
                if message_type == "HistoricalDataResponse":
                    payload = message.toPy()
                    if isinstance(payload, Mapping):
                        response_error = payload.get("responseError")
                        if isinstance(response_error, Mapping):
                            errors["request"] = str(
                                response_error.get("message", response_error)
                            )
                        else:
                            payloads.append(payload)
                elif message_type in {"RequestFailure", "AuthorizationFailure"}:
                    errors["request"] = str(message)
            if event.eventType() == blpapi.Event.RESPONSE:
                return payloads, errors
        errors["request"] = f"Bloomberg request timed out after {self.config.timeout_seconds} seconds"
        return payloads, errors

    def _reference_request(
        self,
        session,
        service,
        symbols: Sequence[str],
        fields: Sequence[str],
        overrides: Mapping[str, object] | None = None,
    ) -> tuple[list[Mapping[str, Any]], dict[str, str]]:
        request = service.createRequest("ReferenceDataRequest")
        for symbol in symbols:
            request.append("securities", symbol)
        for field in fields:
            request.append("fields", field)
        for field_id, value in (overrides or {}).items():
            override = request.getElement("overrides").appendElement()
            override.setElement("fieldId", str(field_id))
            override.setElement("value", str(value))
        session.sendRequest(request)

        rows: list[Mapping[str, Any]] = []
        errors: dict[str, str] = {}
        deadline = time.monotonic() + self.config.timeout_seconds
        while time.monotonic() < deadline:
            remaining_ms = max(int((deadline - time.monotonic()) * 1000), 1)
            event = session.nextEvent(min(remaining_ms, 5000))
            for message in event:
                message_type = str(message.messageType())
                if message_type == "ReferenceDataResponse":
                    payload = message.toPy()
                    if isinstance(payload, Mapping):
                        response_error = payload.get("responseError")
                        if isinstance(response_error, Mapping):
                            errors["request"] = str(
                                response_error.get("message", response_error)
                            )
                        else:
                            rows.extend(payload.get("securityData", []) or [])
                elif message_type in {"RequestFailure", "AuthorizationFailure"}:
                    errors["request"] = str(message)
            if event.eventType() == blpapi.Event.RESPONSE:
                return rows, errors
        errors["request"] = f"Bloomberg request timed out after {self.config.timeout_seconds} seconds"
        return rows, errors

    @staticmethod
    def _payload_errors(security_data: Mapping[str, Any]) -> dict[str, str]:
        symbol = str(security_data.get("security", "")).strip()
        security_error = security_data.get("securityError")
        if isinstance(security_error, Mapping):
            return {
                symbol or "request": str(
                    security_error.get("message", security_error.get("category", "Unknown security error"))
                )
            }
        errors: dict[str, str] = {}
        for item in security_data.get("fieldExceptions", []) or []:
            if not isinstance(item, Mapping):
                continue
            field_id = str(item.get("fieldId", "unknown_field"))
            error_info = item.get("errorInfo", {})
            message = error_info.get("message", "Field unavailable") if isinstance(error_info, Mapping) else error_info
            errors[f"{symbol}:{field_id}"] = str(message)
        return errors

    def load_historical_fields(
        self,
        symbols: Sequence[str],
        fields: Sequence[str],
        start: str,
        end: str,
        periodicity: str = "MONTHLY",
        overrides: Mapping[str, object] | None = None,
    ) -> pd.DataFrame:
        """Load entitled Bloomberg history without imposing price-field semantics."""
        clean_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        clean_fields = tuple(dict.fromkeys(str(field).strip() for field in fields if str(field).strip()))
        columns = ["provider_symbol", "date", *clean_fields]
        if not clean_symbols or not clean_fields:
            return pd.DataFrame(columns=columns)
        start_date = pd.Timestamp(start).normalize()
        end_date = pd.Timestamp(end).normalize()
        if start_date > end_date:
            raise ValueError("Bloomberg start date must not be after end date.")

        frames: list[pd.DataFrame] = []
        all_errors: dict[str, str] = {}
        with self._session() as (session, service):
            for symbol_chunk in _chunks(clean_symbols, self.config.max_securities_per_request):
                payloads, request_errors = self._historical_request(
                    session,
                    service,
                    symbol_chunk,
                    clean_fields,
                    start_date,
                    end_date,
                    periodicity=periodicity,
                    overrides=overrides,
                )
                all_errors.update(request_errors)
                if "request" in request_errors:
                    break
                for payload in payloads:
                    security_data = payload.get("securityData", {})
                    if not isinstance(security_data, Mapping):
                        continue
                    symbol = str(security_data.get("security", "")).strip()
                    payload_errors = self._payload_errors(security_data)
                    all_errors.update(payload_errors)
                    if symbol in payload_errors:
                        continue
                    rows = security_data.get("fieldData", []) or []
                    if rows:
                        frame = pd.DataFrame(rows)
                        frame.insert(0, "provider_symbol", symbol)
                        frames.append(frame)
                    elif symbol:
                        all_errors.setdefault(symbol, "No historical rows returned")
        self.last_errors = all_errors
        if not frames:
            return pd.DataFrame(columns=columns)
        output = pd.concat(frames, ignore_index=True)
        output["date"] = pd.to_datetime(output["date"], errors="coerce").dt.normalize()
        for field in clean_fields:
            if field not in output:
                output[field] = pd.NA
        return output[columns].dropna(subset=["provider_symbol", "date"]).reset_index(drop=True)

    def load_reference_data(
        self,
        symbols: Sequence[str],
        fields: Sequence[str],
        overrides: Mapping[str, object] | None = None,
    ) -> dict[str, Mapping[str, Any]]:
        """Load scalar and bulk reference fields keyed by Bloomberg security."""
        clean_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        clean_fields = tuple(dict.fromkeys(str(field).strip() for field in fields if str(field).strip()))
        output: dict[str, Mapping[str, Any]] = {}
        all_errors: dict[str, str] = {}
        if not clean_symbols or not clean_fields:
            return output
        with self._session() as (session, service):
            for symbol_chunk in _chunks(clean_symbols, self.config.max_securities_per_request):
                rows, request_errors = self._reference_request(
                    session,
                    service,
                    symbol_chunk,
                    clean_fields,
                    overrides=overrides,
                )
                all_errors.update(request_errors)
                if "request" in request_errors:
                    break
                for security_data in rows:
                    symbol = str(security_data.get("security", "")).strip()
                    payload_errors = self._payload_errors(security_data)
                    all_errors.update(payload_errors)
                    if symbol in payload_errors:
                        continue
                    field_data = security_data.get("fieldData", {})
                    if symbol and isinstance(field_data, Mapping):
                        output[symbol] = field_data
        self.last_errors = all_errors
        return output

    def load_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        clean_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        if not clean_symbols:
            return pd.DataFrame(columns=PRICE_COLUMNS)
        end_date = pd.Timestamp(datetime.now(UTC).date() if end is None else end).normalize()
        start_date = pd.Timestamp(
            end_date - timedelta(days=self.config.lookback_days) if start is None else start
        ).normalize()
        if start_date > end_date:
            raise ValueError("Bloomberg start date must not be after end date.")

        frames: list[pd.DataFrame] = []
        all_errors: dict[str, str] = {}
        fields = tuple(_PRICE_FIELD_MAP)
        with self._session() as (session, service):
            for symbol_chunk in _chunks(clean_symbols, self.config.max_securities_per_request):
                payloads, request_errors = self._historical_request(
                    session,
                    service,
                    symbol_chunk,
                    fields,
                    start_date,
                    end_date,
                )
                all_errors.update(request_errors)
                if "request" in request_errors:
                    break
                for payload in payloads:
                    frame, payload_errors = normalise_historical_payload(payload)
                    all_errors.update(payload_errors)
                    if not frame.empty:
                        frames.append(frame)

        self.last_errors = all_errors
        if all_errors:
            LOGGER.warning(
                "Bloomberg returned no data or field errors for %s request items; successful symbols were retained.",
                len(all_errors),
            )
        if not frames:
            details = "; ".join(f"{key}: {value}" for key, value in list(all_errors.items())[:5])
            raise BloombergRequestError(f"Bloomberg returned no usable historical price rows. {details}")
        output = pd.concat(frames, ignore_index=True)
        output = output.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
        output["return"] = output.groupby("ticker", sort=False)["adjusted_close"].pct_change().fillna(0.0)
        output["source"] = "bloomberg"
        return output.reset_index(drop=True)
