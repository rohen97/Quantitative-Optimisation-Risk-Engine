from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import time
from typing import Any

import pandas as pd

from src.data.normalisers import record_hash
from src.data.schemas import SCHEMAS
from src.data_ingestion.external_adapters import _price_frame
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient
from src.utils.env import get_env


LOGGER = logging.getLogger(__name__)
OPENFIGI_MAPPING_URL = "https://api.openfigi.com/v3/mapping"


def _history_dates(start: str | None, end: str | None, lookback_days: int) -> tuple[str, str]:
    end_date = datetime.now(UTC).date() if end is None else pd.Timestamp(end).date()
    start_date = end_date - timedelta(days=lookback_days) if start is None else pd.Timestamp(start).date()
    return start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")


def _naive_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize(None) if timestamp.tzinfo is not None else timestamp


def _normalise_market_frame(frame: pd.DataFrame, ticker: str, source: str) -> pd.DataFrame:
    if frame.empty:
        return _price_frame([], source)
    data = frame.copy()
    data.columns = [str(column).strip().lower() for column in data.columns]
    data = data.rename(
        columns={
            "\u65e5\u671f": "date",
            "\u65f6\u95f4": "date",
            "\u5f00\u76d8": "open",
            "\u6700\u9ad8": "high",
            "\u6700\u4f4e": "low",
            "\u6536\u76d8": "close",
            "\u6210\u4ea4\u91cf": "volume",
            "\u80a1\u7968\u4ee3\u7801": "provider_symbol",
            "adj_close": "adjusted_close",
            "adjclose": "adjusted_close",
        }
    )
    if "date" not in data.columns:
        index_name = str(data.index.name or "date").lower()
        data = data.reset_index()
        data = data.rename(columns={data.columns[0]: index_name})
        if index_name != "date":
            data = data.rename(columns={index_name: "date"})
    if "close" not in data.columns:
        raise ValueError(f"{source} response for {ticker} omitted close prices.")
    data["ticker"] = ticker
    if "adjusted_close" not in data.columns:
        data["adjusted_close"] = data["close"]
    return _price_frame(data.to_dict("records"), source)


def _china_symbol(symbol: str) -> tuple[str, str] | None:
    text = str(symbol).strip().upper()
    if "." not in text:
        return None
    code, suffix = text.rsplit(".", 1)
    if not code.isdigit():
        return None
    if suffix == "HK":
        return "hk", code.zfill(5)
    if suffix in {"SS", "SH", "SZ", "BJ"}:
        return "a_share", code.zfill(6)
    return None


@dataclass
class AkshareMarketDataAdapter:
    """Load unadjusted China/HK bars and volume without importing AKShare at startup."""

    module: Any | None = None
    lookback_days: int | None = None
    adjust: str = ""
    hk_endpoint: str = "auto"
    a_share_endpoint: str = "auto"
    max_workers: int | None = None
    a_share_max_workers: int | None = None
    retry_attempts: int | None = None
    retry_backoff_seconds: float | None = None

    def _module(self) -> Any:
        if self.module is not None:
            return self.module
        try:
            import akshare  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("AKShare is not installed; install the free-data extra.") from exc
        return akshare

    def _load_symbol(
        self,
        module: Any,
        symbol: str,
        start_date: str,
        end_date: str,
        hk_endpoint: str,
        a_share_endpoint: str,
    ) -> pd.DataFrame | None:
        parsed = _china_symbol(symbol)
        if parsed is None:
            return None
        market, code = parsed
        attempts = max(
            self.retry_attempts
            or int(get_env("AKSHARE_RETRY_ATTEMPTS", "3") or 3),
            1,
        )
        backoff = max(
            self.retry_backoff_seconds
            if self.retry_backoff_seconds is not None
            else float(get_env("AKSHARE_RETRY_BACKOFF_SECONDS", "0.5") or 0.5),
            0.0,
        )
        raw: pd.DataFrame | None = None
        for attempt in range(attempts):
            try:
                if market == "hk":
                    if hk_endpoint == "daily":
                        raw = module.stock_hk_daily(symbol=code, adjust=self.adjust)
                    elif hk_endpoint == "history":
                        raw = module.stock_hk_hist(
                            symbol=code,
                            period="daily",
                            start_date=start_date,
                            end_date=end_date,
                            adjust=self.adjust,
                        )
                    else:
                        try:
                            raw = module.stock_hk_hist(
                                symbol=code,
                                period="daily",
                                start_date=start_date,
                                end_date=end_date,
                                adjust=self.adjust,
                            )
                        except Exception as primary_exc:
                            LOGGER.info(
                                "AKShare HK history endpoint failed for %s; trying daily fallback: %s",
                                symbol,
                                primary_exc,
                            )
                            raw = module.stock_hk_daily(
                                symbol=code,
                                adjust=self.adjust,
                            )
                else:
                    if a_share_endpoint == "tencent":
                        raw = module.stock_zh_a_hist_tx(
                            symbol=code,
                            start_date=start_date,
                            end_date=end_date,
                            adjust=self.adjust,
                        )
                    elif a_share_endpoint == "eastmoney":
                        raw = module.stock_zh_a_hist(
                            symbol=code,
                            period="daily",
                            start_date=start_date,
                            end_date=end_date,
                            adjust=self.adjust,
                        )
                    else:
                        try:
                            raw = module.stock_zh_a_hist(
                                symbol=code,
                                period="daily",
                                start_date=start_date,
                                end_date=end_date,
                                adjust=self.adjust,
                            )
                        except Exception as primary_exc:
                            LOGGER.info(
                                "AKShare Eastmoney history failed for %s; trying Tencent fallback: %s",
                                symbol,
                                primary_exc,
                            )
                            raw = module.stock_zh_a_hist_tx(
                                symbol=code,
                                start_date=start_date,
                                end_date=end_date,
                                adjust=self.adjust,
                            )
                break
            except Exception as exc:
                if attempt + 1 >= attempts:
                    LOGGER.warning(
                        "AKShare returned no usable history for %s after %s attempts: %s",
                        symbol,
                        attempts,
                        exc,
                    )
                    return None
                if backoff:
                    time.sleep(backoff * (2**attempt))
        if not isinstance(raw, pd.DataFrame) or raw.empty:
            return None
        try:
            normalised = _normalise_market_frame(raw, symbol, "akshare")
        except (TypeError, ValueError) as exc:
            LOGGER.warning("AKShare returned malformed history for %s: %s", symbol, exc)
            return None
        return normalised.loc[
            normalised["date"].between(
                pd.Timestamp(start_date),
                pd.Timestamp(end_date),
            )
        ]

    def load_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        module = self._module()
        lookback = self.lookback_days or int(
            get_env("AKSHARE_LOOKBACK_DAYS", "12000") or 12000
        )
        start_date, end_date = _history_dates(start, end, lookback)
        hk_endpoint = self.hk_endpoint.strip().lower()
        if hk_endpoint not in {"auto", "history", "daily"}:
            raise ValueError(
                "AKShare HK endpoint must be one of: auto, history, daily."
            )
        a_share_endpoint = self.a_share_endpoint.strip().lower()
        if a_share_endpoint not in {"auto", "eastmoney", "tencent"}:
            raise ValueError(
                "AKShare A-share endpoint must be one of: auto, eastmoney, tencent."
            )
        selected_symbols = sorted(set(symbols))
        configured_workers = self.max_workers or int(
            get_env("AKSHARE_MAX_WORKERS", "8") or 8
        )
        if any(
            (_china_symbol(symbol) or (None, None))[0] == "a_share"
            for symbol in selected_symbols
        ):
            configured_workers = min(
                configured_workers,
                self.a_share_max_workers
                or int(get_env("AKSHARE_A_SHARE_MAX_WORKERS", "4") or 4),
            )
        worker_count = min(max(configured_workers, 1), len(selected_symbols) or 1)

        def load_symbol(symbol: str) -> pd.DataFrame | None:
            return self._load_symbol(
                module,
                symbol,
                start_date,
                end_date,
                hk_endpoint,
                a_share_endpoint,
            )

        frames: list[pd.DataFrame] = []
        if worker_count > 1 and hk_endpoint == "daily":
            # AKShare's HK daily decoder embeds V8, whose first initialization
            # is not thread-safe on Windows. Warm it once before fan-out.
            warmup_symbol = next(
                (
                    symbol
                    for symbol in selected_symbols
                    if (_china_symbol(symbol) or (None, None))[0] == "hk"
                ),
                None,
            )
            if warmup_symbol is not None:
                warmup_frame = load_symbol(warmup_symbol)
                if warmup_frame is not None and not warmup_frame.empty:
                    frames.append(warmup_frame)
                selected_symbols.remove(warmup_symbol)
                worker_count = min(worker_count, len(selected_symbols) or 1)

        if worker_count == 1:
            loaded = map(load_symbol, selected_symbols)
            frames.extend(
                frame
                for frame in loaded
                if frame is not None and not frame.empty
            )
        else:
            with ThreadPoolExecutor(
                max_workers=worker_count,
                thread_name_prefix="akshare",
            ) as executor:
                loaded = executor.map(load_symbol, selected_symbols)
                frames.extend(
                    frame
                    for frame in loaded
                    if frame is not None and not frame.empty
                )
        return pd.concat(frames, ignore_index=True) if frames else _price_frame([], "akshare")


def _openbb_frame(result: object) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        return result
    for method_name in ("to_df", "to_dataframe"):
        method = getattr(result, method_name, None)
        if callable(method):
            frame = method()
            if isinstance(frame, pd.DataFrame):
                return frame
    records = getattr(result, "results", None)
    if isinstance(records, Sequence) and not isinstance(records, (str, bytes)):
        return pd.DataFrame(
            [item.model_dump() if hasattr(item, "model_dump") else item for item in records]
        )
    raise ValueError("OpenBB returned an unsupported historical-price object.")


@dataclass
class OpenBBMarketDataAdapter:
    """Normalize an OpenBB provider response into the model's price contract."""

    client: Any | None = None
    provider: str = "yfinance"

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        try:
            from openbb import obb  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("OpenBB is not installed; install the openbb extra.") from exc
        return obb

    def load_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        client = self._client()
        frames: list[pd.DataFrame] = []
        for symbol in sorted(set(symbols)):
            try:
                result = client.equity.price.historical(
                    symbol=symbol,
                    start_date=start,
                    end_date=end,
                    provider=self.provider,
                )
                raw = _openbb_frame(result)
                if not raw.empty:
                    frames.append(_normalise_market_frame(raw, symbol, "openbb"))
            except Exception as exc:  # OpenBB wraps provider-specific exception types.
                LOGGER.warning("OpenBB/%s returned no usable history for %s: %s", self.provider, symbol, exc)
        return pd.concat(frames, ignore_index=True) if frames else _price_frame([], "openbb")


@dataclass(frozen=True)
class OpenFigiMappingResult:
    identifiers: pd.DataFrame
    jobs: int
    matched_jobs: int
    request_count: int
    warnings: tuple[str, ...]


@dataclass
class OpenFigiMappingClient:
    """Resolve current FIGIs; results are never presented as historical mappings."""

    client: HttpClient
    base_url: str = OPENFIGI_MAPPING_URL
    sleep: Callable[[float], None] = time.sleep
    request_pause_seconds: float | None = None

    def _headers(self) -> tuple[dict[str, str], bool]:
        api_key = get_env("OPENFIGI_API_KEY", "") or get_env("OPEN_FIGI_API_KEY", "") or ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-OPENFIGI-APIKEY"] = api_key
        return headers, bool(api_key)

    def map_identifiers(
        self,
        candidates: pd.DataFrame,
        *,
        retrieved_at: pd.Timestamp,
        ingestion_run_id: str,
    ) -> OpenFigiMappingResult:
        required = {"security_id", "id_type", "id_value"}
        missing = required.difference(candidates.columns)
        if missing:
            raise ValueError(f"OpenFIGI candidates are missing columns: {sorted(missing)}")
        clean = candidates.copy().dropna(subset=list(required))
        clean = clean.loc[clean["id_value"].astype(str).str.strip().ne("")].reset_index(drop=True)
        if clean.empty:
            return OpenFigiMappingResult(
                pd.DataFrame(columns=SCHEMAS["identifier_vintages"].column_names),
                0,
                0,
                0,
                (),
            )

        headers, authenticated = self._headers()
        batch_size = 100 if authenticated else 5
        pause = self.request_pause_seconds
        if pause is None:
            pause = 0.3 if authenticated else 12.1
        retrieved = _naive_timestamp(retrieved_at)
        rows: list[dict[str, object]] = []
        warnings: list[str] = []
        matched_jobs = 0
        request_count = 0

        for offset in range(0, len(clean), batch_size):
            batch = clean.iloc[offset : offset + batch_size]
            jobs: list[dict[str, str]] = []
            for candidate in batch.to_dict("records"):
                job = {
                    "idType": str(candidate["id_type"]).strip(),
                    "idValue": str(candidate["id_value"]).strip(),
                }
                for source_column, api_field in (
                    ("exchange_code", "exchCode"),
                    ("mic_code", "micCode"),
                    ("currency", "currency"),
                ):
                    value = candidate.get(source_column)
                    if value is not None and not pd.isna(value) and str(value).strip():
                        job[api_field] = str(value).strip().upper()
                jobs.append(job)

            payload = self.client.post_json(self.base_url, jobs, headers=headers).json()
            request_count += 1
            if not isinstance(payload, list) or len(payload) != len(batch):
                raise DataSourceRequestError("OpenFIGI returned a response that did not align with submitted jobs.")
            for candidate, response in zip(batch.to_dict("records"), payload, strict=True):
                if not isinstance(response, Mapping):
                    warnings.append(f"{candidate['security_id']}: invalid response")
                    continue
                data = response.get("data")
                if not isinstance(data, list) or not data or not isinstance(data[0], Mapping):
                    message = response.get("error") or response.get("warning") or "no mapping"
                    warnings.append(f"{candidate['security_id']}: {message}")
                    continue
                match = data[0]
                matched_jobs += 1
                for response_field, identifier_type in (
                    ("figi", "figi"),
                    ("compositeFIGI", "composite_figi"),
                    ("shareClassFIGI", "share_class_figi"),
                ):
                    identifier_value = str(match.get(response_field) or "").strip()
                    if not identifier_value:
                        continue
                    rows.append(
                        {
                            "security_id": str(candidate["security_id"]).upper(),
                            "identifier_type": identifier_type,
                            "identifier_value": identifier_value,
                            "effective_from": retrieved.normalize(),
                            "effective_to": pd.NaT,
                            "available_from": retrieved,
                            "provider_symbol": str(candidate["id_value"]),
                            "source": "openfigi_current_snapshot",
                            "retrieved_at": retrieved,
                            "ingestion_run_id": ingestion_run_id,
                        }
                    )
            if offset + batch_size < len(clean) and pause > 0:
                self.sleep(pause)

        identifiers = pd.DataFrame(rows)
        if identifiers.empty:
            identifiers = pd.DataFrame(columns=SCHEMAS["identifier_vintages"].column_names)
        else:
            identifiers = identifiers.drop_duplicates(
                ["security_id", "identifier_type", "identifier_value"], keep="last"
            )
            identifiers["row_hash"] = record_hash(
                identifiers,
                [
                    "security_id",
                    "identifier_type",
                    "identifier_value",
                    "effective_from",
                    "provider_symbol",
                    "source",
                ],
            )
            identifiers["vintage_id"] = identifiers["row_hash"]
            identifiers = identifiers[list(SCHEMAS["identifier_vintages"].column_names)]
        return OpenFigiMappingResult(
            identifiers=identifiers,
            jobs=len(clean),
            matched_jobs=matched_jobs,
            request_count=request_count,
            warnings=tuple(warnings),
        )
