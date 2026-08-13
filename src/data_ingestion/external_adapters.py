from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import numpy as np
import pandas as pd

from src.data.normalisers import normalise_macro_observations
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient
from src.data_ingestion.provider_registry import ProviderDefinition
from src.utils.env import get_env


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
    "source",
]


def _price_frame(rows: list[dict[str, object]], source: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    data = pd.DataFrame(rows)
    data["date"] = pd.to_datetime(data["date"], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    data["ticker"] = data["ticker"].astype(str)
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
    for column in ("open", "high", "low", "adjusted_close", "volume"):
        fallback = data["close"] if column != "volume" else np.nan
        data[column] = pd.to_numeric(data.get(column, fallback), errors="coerce")
    data = data.dropna(subset=["date", "ticker", "close"])
    data = data[data["close"] > 0].sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
    data["return"] = data.groupby("ticker")["close"].pct_change().fillna(0.0)
    data["source"] = source
    return data[PRICE_COLUMNS].reset_index(drop=True)


def _date_range(start: str | None, end: str | None, lookback_days: int = 756) -> tuple[str, str]:
    end_date = datetime.now(UTC).date() if end is None else pd.Timestamp(end).date()
    start_date = end_date - timedelta(days=lookback_days) if start is None else pd.Timestamp(start).date()
    return start_date.isoformat(), end_date.isoformat()


def _unix_range(start: str | None, end: str | None) -> tuple[int, int]:
    start_date, end_date = _date_range(start, end)
    return int(pd.Timestamp(start_date, tz="UTC").timestamp()), int(pd.Timestamp(end_date, tz="UTC").timestamp())


@dataclass
class EodhdAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_daily_bars(self, symbols: list[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
        token = get_env(self.provider.credential_env or "", "")
        if not token:
            raise DataSourceRequestError("EODHD_API_TOKEN is required.")
        start_date, end_date = _date_range(start, end)
        rows: list[dict[str, object]] = []
        for symbol in sorted(set(symbols)):
            payload = self.client.get(
                f"{self.provider.base_url}/eod/{symbol}",
                params={
                    "api_token": token,
                    "fmt": "json",
                    "from": start_date,
                    "to": end_date,
                    "period": "d",
                    "order": "a",
                },
            ).json()
            if not isinstance(payload, list):
                raise DataSourceRequestError(f"EODHD returned an invalid payload for {symbol}.")
            rows.extend(
                {
                    "date": item.get("date"),
                    "ticker": symbol,
                    "close": item.get("adjusted_close", item.get("close")),
                    "open": item.get("open"),
                    "high": item.get("high"),
                    "low": item.get("low"),
                    "adjusted_close": item.get("adjusted_close"),
                    "volume": item.get("volume"),
                }
                for item in payload
                if isinstance(item, dict)
            )
        return _price_frame(rows, "eodhd")


@dataclass
class FinnhubAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_daily_bars(self, symbols: list[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
        token = get_env(self.provider.credential_env or "", "")
        if not token:
            raise DataSourceRequestError("FINNHUB_API_KEY is required.")
        start_unix, end_unix = _unix_range(start, end)
        rows: list[dict[str, object]] = []
        for symbol in sorted(set(symbols)):
            payload = self.client.get(
                f"{self.provider.base_url}/stock/candle",
                params={"symbol": symbol, "resolution": "D", "from": start_unix, "to": end_unix, "token": token},
            ).json()
            if not isinstance(payload, dict) or payload.get("s") == "no_data":
                continue
            timestamps = payload.get("t", [])
            closes = payload.get("c", [])
            if not isinstance(timestamps, list) or not isinstance(closes, list):
                raise DataSourceRequestError(f"Finnhub returned an invalid candle payload for {symbol}.")
            opens = payload.get("o", [])
            highs = payload.get("h", [])
            lows = payload.get("l", [])
            volumes = payload.get("v", [])
            rows.extend(
                {
                    "date": pd.to_datetime(timestamp, unit="s", utc=True),
                    "ticker": symbol,
                    "open": opens[index] if index < len(opens) else None,
                    "high": highs[index] if index < len(highs) else None,
                    "low": lows[index] if index < len(lows) else None,
                    "close": close,
                    "volume": volumes[index] if index < len(volumes) else None,
                }
                for index, (timestamp, close) in enumerate(zip(timestamps, closes, strict=False))
            )
        return _price_frame(rows, "finnhub")


@dataclass
class AlphaVantageAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_daily_bars(self, symbols: list[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
        token = get_env(self.provider.credential_env or "", "")
        if not token:
            raise DataSourceRequestError("ALPHA_VANTAGE_API_KEY is required.")
        function = get_env(
            "ALPHA_VANTAGE_DAILY_FUNCTION",
            str(self.provider.settings.get("daily_function", "TIME_SERIES_DAILY")),
        ) or "TIME_SERIES_DAILY"
        output_size = get_env(
            "ALPHA_VANTAGE_OUTPUT_SIZE",
            str(self.provider.settings.get("output_size", "compact")),
        ) or "compact"
        rows: list[dict[str, object]] = []
        for symbol in sorted(set(symbols)):
            payload = self.client.get(
                f"{self.provider.base_url}/query",
                params={
                    "function": function,
                    "symbol": symbol,
                    "outputsize": output_size,
                    "datatype": "json",
                    "apikey": token,
                },
            ).json()
            if not isinstance(payload, dict):
                raise DataSourceRequestError(f"Alpha Vantage returned an invalid payload for {symbol}.")
            error = payload.get("Error Message") or payload.get("Information") or payload.get("Note")
            if error:
                raise DataSourceRequestError(f"Alpha Vantage rejected {symbol}: {error}")
            series = next(
                (
                    values
                    for key, values in payload.items()
                    if "Time Series" in str(key) and isinstance(values, dict)
                ),
                None,
            )
            if series is None:
                raise DataSourceRequestError(f"Alpha Vantage returned no daily time series for {symbol}.")
            for date, values in series.items():
                if not isinstance(values, dict):
                    continue
                close = values.get("5. adjusted close", values.get("4. close"))
                rows.append(
                    {
                        "date": date,
                        "ticker": symbol,
                        "open": values.get("1. open"),
                        "high": values.get("2. high"),
                        "low": values.get("3. low"),
                        "close": close,
                        "adjusted_close": values.get("5. adjusted close"),
                        "volume": values.get("6. volume", values.get("5. volume")),
                    }
                )
        frame = _price_frame(rows, "alpha_vantage")
        if start is not None and not frame.empty:
            frame = frame[frame["date"] >= pd.Timestamp(start)].reset_index(drop=True)
        if end is not None and not frame.empty:
            frame = frame[frame["date"] <= pd.Timestamp(end)].reset_index(drop=True)
        if not frame.empty:
            frame["return"] = frame.groupby("ticker")["close"].pct_change().fillna(0.0)
        return frame


@dataclass
class TickDbAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_daily_bars(self, symbols: list[str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
        token = get_env(self.provider.credential_env or "", "")
        if not token:
            raise DataSourceRequestError("TICKDB_API_KEY is required.")
        interval = str(self.provider.settings.get("interval", "1d"))
        limit = int(self.provider.settings.get("limit", 1000))
        use_time_range = (get_env("TICKDB_USE_TIME_RANGE", str(self.provider.settings.get("use_time_range", False))) or "false").lower() in {"1", "true", "yes", "y", "on"}
        range_params = {}
        if use_time_range:
            start_date, end_date = _date_range(start, end)
            range_params = {
                "start_time": int(pd.Timestamp(start_date, tz="UTC").timestamp() * 1000),
                "end_time": int(pd.Timestamp(end_date, tz="UTC").timestamp() * 1000),
            }
        rows: list[dict[str, object]] = []
        for symbol in sorted(set(symbols)):
            try:
                payload = self.client.get(
                    f"{self.provider.base_url}/v1/market/kline",
                    params={
                        "symbol": symbol,
                        "interval": interval,
                        "limit": min(max(limit, 1), 1000),
                        **range_params,
                    },
                    headers={"X-API-Key": token, "X-TickDB-Key": token},
                ).json()
            except DataSourceRequestError as exc:
                message = str(exc).lower()
                if "http 404" in message or "symbol not found" in message or "http error 500" in message or "internal server error" in message:
                    continue
                raise
            if not isinstance(payload, dict):
                raise DataSourceRequestError(f"TickDB returned an invalid payload for {symbol}.")
            if payload.get("code", 0) not in {0, "0", None}:
                raise DataSourceRequestError(f"TickDB rejected {symbol}: {payload.get('message', payload)}")
            data = payload.get("data", {})
            records = data.get("klines", []) if isinstance(data, dict) else []
            for record in records if isinstance(records, list) else []:
                if not isinstance(record, dict):
                    continue
                timestamp = record.get("time", record.get("timestamp", record.get("date")))
                if isinstance(timestamp, (int, float, np.integer, np.floating)):
                    timestamp = pd.to_datetime(timestamp, unit="ms", utc=True)
                rows.append(
                    {
                        "date": timestamp,
                        "ticker": symbol,
                        "open": record.get("open"),
                        "high": record.get("high"),
                        "low": record.get("low"),
                        "close": record.get("close"),
                        "adjusted_close": record.get("adjusted_close"),
                        "volume": record.get("volume", record.get("vol")),
                    }
                )
        return _price_frame(rows, "tickdb")


@dataclass
class ITickAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
        region: str = "US",
    ) -> pd.DataFrame:
        del start, end
        token = get_env(self.provider.credential_env or "", "")
        if not token:
            raise DataSourceRequestError("ITICK_API_TOKEN is required.")
        rows: list[dict[str, object]] = []
        for symbol in sorted(set(symbols)):
            payload = self.client.get(
                f"{self.provider.base_url}/stock/kline",
                params={"region": region, "code": symbol, "kType": 6, "limit": 5000},
                headers={"token": token},
            ).json()
            records = payload.get("data", []) if isinstance(payload, dict) else []
            for record in records if isinstance(records, list) else []:
                if isinstance(record, dict):
                    timestamp = record.get("t", record.get("timestamp", record.get("date")))
                    close = record.get("c", record.get("close"))
                    open_price = record.get("o", record.get("open"))
                    high = record.get("h", record.get("high"))
                    low = record.get("l", record.get("low"))
                    volume = record.get("v", record.get("volume"))
                elif isinstance(record, list) and len(record) >= 5:
                    timestamp, close = record[0], record[4]
                    open_price = record[1] if len(record) > 1 else None
                    high = record[2] if len(record) > 2 else None
                    low = record[3] if len(record) > 3 else None
                    volume = record[5] if len(record) > 5 else None
                else:
                    continue
                if isinstance(timestamp, (int, float, np.integer, np.floating)):
                    unit = "ms" if float(timestamp) > 10_000_000_000 else "s"
                    timestamp = pd.to_datetime(timestamp, unit=unit, utc=True)
                rows.append(
                    {
                        "date": timestamp,
                        "ticker": symbol,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": volume,
                    }
                )
        return _price_frame(rows, "itick")


@dataclass
class FrankfurterAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_fx_rates(
        self,
        base_currency: str,
        quote_currencies: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        start_date, end_date = _date_range(start, end)
        rows: list[dict[str, object]] = []
        window_start = pd.Timestamp(start_date).date()
        final_end = pd.Timestamp(end_date).date()
        window_days = max(int(self.provider.settings.get("window_days", 730)), 30)
        while window_start <= final_end:
            window_end = min(window_start + timedelta(days=window_days - 1), final_end)
            payload = self.client.get(
                f"{self.provider.base_url}/rates",
                params={
                    "base": base_currency.upper(),
                    "quotes": ",".join(currency.upper() for currency in quote_currencies),
                    "from": window_start.isoformat(),
                    "to": window_end.isoformat(),
                    "expand": "providers",
                },
            ).json()
            records = payload if isinstance(payload, list) else payload.get("rates", []) if isinstance(payload, dict) else []
            if isinstance(records, dict):
                for date, rates in records.items():
                    for quote, rate in rates.items():
                        rows.append({"base_currency": base_currency, "quote_currency": quote, "rate_date": date, "rate": rate})
            else:
                for item in records:
                    if isinstance(item, dict):
                        rows.append(
                            {
                                "base_currency": item.get("base", base_currency),
                                "quote_currency": item.get("quote"),
                                "rate_date": item.get("date"),
                                "rate": item.get("rate"),
                            }
                        )
            window_start = window_end + timedelta(days=1)
        data = pd.DataFrame(rows)
        if data.empty:
            return pd.DataFrame(
                columns=["base_currency", "quote_currency", "rate_date", "rate", "source", "retrieved_at", "ingestion_run_id"]
            )
        from src.data.ingestion.fx import ingest_fx

        return ingest_fx(data, source="frankfurter")

@dataclass
class FredAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_series(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
        preserve_vintages: bool = True,
        realtime_window_years: int = 5,
    ) -> pd.DataFrame:
        api_key = get_env(self.provider.credential_env or "", "")
        if not api_key:
            raise DataSourceRequestError("FRED_API_KEY is required.")
        params: dict[str, object] = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start,
            "observation_end": end,
            "output_type": 3 if preserve_vintages else 1,
            "limit": 100000,
        }
        request_params: list[dict[str, object]] = []
        if preserve_vintages and start and end:
            realtime_start = pd.Timestamp(start).date()
            final_realtime_end = min(pd.Timestamp(end).date(), pd.Timestamp.today().date())
            while realtime_start <= final_realtime_end:
                realtime_end = min(
                    (pd.Timestamp(realtime_start) + pd.DateOffset(years=max(realtime_window_years, 1)) - pd.Timedelta(days=1)).date(),
                    final_realtime_end,
                )
                request_params.append(
                    {
                        **params,
                        "realtime_start": realtime_start.isoformat(),
                        "realtime_end": realtime_end.isoformat(),
                    }
                )
                realtime_start = realtime_end + timedelta(days=1)
        else:
            if preserve_vintages:
                params["realtime_start"] = "1776-07-04"
                params["realtime_end"] = "9999-12-31"
            request_params.append(params)
        payloads = [
            self.client.get(f"{self.provider.base_url}/series/observations", params=item).json()
            for item in request_params
        ]
        metadata_payload = self.client.get(
            f"{self.provider.base_url}/series",
            params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
        ).json()
        metadata_rows = metadata_payload.get("seriess", []) if isinstance(metadata_payload, dict) else []
        metadata = metadata_rows[0] if metadata_rows and isinstance(metadata_rows[0], dict) else {}
        unit = str(metadata.get("units") or metadata.get("units_short") or "")
        frequency = str(metadata.get("frequency_short") or metadata.get("frequency") or "")
        observations = [
            observation
            for payload in payloads
            if isinstance(payload, dict)
            for observation in payload.get("observations", [])
        ]
        retrieved_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
        rows = []
        for item in observations:
            if not isinstance(item, dict):
                continue
            if "value" in item:
                availability = (
                    item.get("realtime_start", retrieved_at.date().isoformat())
                    if preserve_vintages
                    else item.get("date")
                )
                vintage_values = [(availability, item.get("value"))]
            else:
                prefix = f"{series_id}_"
                vintage_values = []
                for key, value in item.items():
                    if key == "date":
                        continue
                    raw_vintage = key[len(prefix) :] if key.startswith(prefix) else key
                    vintage = pd.to_datetime(raw_vintage, format="%Y%m%d", errors="coerce")
                    if pd.isna(vintage):
                        continue
                    vintage_values.append((vintage.date().isoformat(), value))
            for vintage, value in vintage_values:
                if value in {None, "."}:
                    continue
                rows.append(
                    {
                        "series_id": series_id,
                        "observation_date": item.get("date"),
                        "vintage_date": vintage,
                        "available_from": vintage,
                        "value": value,
                        "unit": unit,
                        "frequency": frequency,
                    }
                )
        if not rows:
            return normalise_macro_observations(
                pd.DataFrame(columns=["series_id", "observation_date", "vintage_date", "available_from", "value"]),
                source="fred",
                retrieved_at=retrieved_at,
            )
        frame = pd.DataFrame(rows).drop_duplicates(
            ["series_id", "observation_date", "vintage_date"], keep="last"
        )
        return normalise_macro_observations(frame, source="fred", retrieved_at=retrieved_at)


@dataclass
class EcbAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_series(
        self,
        flow: str,
        key: str,
        start: str | None = None,
        end: str | None = None,
        include_history: bool = True,
    ) -> pd.DataFrame:
        response = self.client.get(
            f"{self.provider.base_url}/data/{flow}/{key}",
            params={
                "startPeriod": start,
                "endPeriod": end,
                "format": "csvdata",
                "includeHistory": str(include_history).lower(),
            },
            headers={"Accept": "text/csv"},
        )
        raw = pd.read_csv(StringIO(response.text()))
        if raw.empty:
            return pd.DataFrame()
        retrieved_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
        available_column = next(
            (column for column in ("LAST_UPDATE", "OBS_STATUS_TIME") if column in raw.columns),
            None,
        )
        rows = pd.DataFrame(
            {
                "series_id": raw.get("KEY", pd.Series([f"{flow}/{key}"] * len(raw))).astype(str),
                "observation_date": raw["TIME_PERIOD"],
                "vintage_date": raw[available_column] if available_column else retrieved_at,
                "available_from": raw[available_column] if available_column else retrieved_at,
                "value": raw["OBS_VALUE"],
                "unit": raw.get("UNIT", ""),
                "frequency": raw.get("FREQ", ""),
            }
        )
        return normalise_macro_observations(rows, source="ecb", retrieved_at=retrieved_at)


@dataclass
class ChinaDataAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_dataset(self, dataset_id: str) -> pd.DataFrame:
        payload = self.client.get(f"{self.provider.base_url}/data/{dataset_id}").json()
        dataset = payload.get("data", {}) if isinstance(payload, dict) else {}
        observations = dataset.get("data", []) if isinstance(dataset, dict) else []
        retrieved_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
        rows = []
        for item in observations:
            if not isinstance(item, dict):
                continue
            raw_date = str(item.get("date", ""))
            observation_date = f"{raw_date}-01-01" if len(raw_date) == 4 else raw_date
            rows.append(
                {
                    "series_id": dataset_id,
                    "observation_date": observation_date,
                    "vintage_date": retrieved_at.normalize(),
                    "available_from": retrieved_at,
                    "value": item.get("value"),
                    "unit": dataset.get("unit", ""),
                    "frequency": dataset.get("frequency", ""),
                }
            )
        if not rows:
            return pd.DataFrame()
        return normalise_macro_observations(pd.DataFrame(rows), source="china_data", retrieved_at=retrieved_at)


@dataclass
class BankOfEnglandAdapter:
    provider: ProviderDefinition
    client: HttpClient

    def load_series(self, series_codes: list[str], start: str, end: str) -> pd.DataFrame:
        response = self.client.get(
            self.provider.base_url,
            params={
                "csv.x": "yes",
                "Datefrom": pd.Timestamp(start).strftime("%d/%b/%Y"),
                "Dateto": pd.Timestamp(end).strftime("%d/%b/%Y"),
                "SeriesCodes": ",".join(series_codes),
                "UsingCodes": "Y",
                "CSVF": "TN",
                "VPD": "Y",
                "VFD": "N",
            },
            headers={"Accept": "text/csv"},
        )
        raw = pd.read_csv(StringIO(response.text()))
        if raw.empty:
            return pd.DataFrame()
        date_column = raw.columns[0]
        retrieved_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
        rows = []
        for series_id in series_codes:
            if series_id not in raw.columns:
                continue
            for date, value in zip(raw[date_column], raw[series_id], strict=False):
                rows.append(
                    {
                        "series_id": series_id,
                        "observation_date": date,
                        "vintage_date": retrieved_at.normalize(),
                        "available_from": retrieved_at,
                        "value": value,
                        "unit": "",
                        "frequency": "",
                    }
                )
        return normalise_macro_observations(pd.DataFrame(rows), source="bank_of_england", retrieved_at=retrieved_at)


@dataclass
class OpenJsonAdapter:
    """Generic reader for official JSON catalogues such as ONS and HKMA."""

    provider: ProviderDefinition
    client: HttpClient

    def get(self, endpoint: str, params: dict[str, object] | None = None) -> object:
        clean_endpoint = endpoint.lstrip("/")
        return self.client.get(f"{self.provider.base_url}/{clean_endpoint}", params=params).json()
