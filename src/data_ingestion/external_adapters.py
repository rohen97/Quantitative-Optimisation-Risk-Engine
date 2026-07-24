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


PRICE_COLUMNS = ["date", "ticker", "close", "return", "source"]


def _price_frame(rows: list[dict[str, object]], source: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    data = pd.DataFrame(rows)
    data["date"] = pd.to_datetime(data["date"], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    data["ticker"] = data["ticker"].astype(str)
    data["close"] = pd.to_numeric(data["close"], errors="coerce")
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
            rows.extend(
                {"date": pd.to_datetime(timestamp, unit="s", utc=True), "ticker": symbol, "close": close}
                for timestamp, close in zip(timestamps, closes, strict=False)
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
                rows.append({"date": date, "ticker": symbol, "close": close})
        frame = _price_frame(rows, "alpha_vantage")
        if start is not None and not frame.empty:
            frame = frame[frame["date"] >= pd.Timestamp(start)].reset_index(drop=True)
        if end is not None and not frame.empty:
            frame = frame[frame["date"] <= pd.Timestamp(end)].reset_index(drop=True)
        if not frame.empty:
            frame["return"] = frame.groupby("ticker")["close"].pct_change().fillna(0.0)
        return frame


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
                elif isinstance(record, list) and len(record) >= 5:
                    timestamp, close = record[0], record[4]
                else:
                    continue
                if isinstance(timestamp, (int, float, np.integer, np.floating)):
                    unit = "ms" if float(timestamp) > 10_000_000_000 else "s"
                    timestamp = pd.to_datetime(timestamp, unit=unit, utc=True)
                rows.append({"date": timestamp, "ticker": symbol, "close": close})
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
        payload = self.client.get(
            f"{self.provider.base_url}/rates",
            params={
                "base": base_currency.upper(),
                "quotes": ",".join(currency.upper() for currency in quote_currencies),
                "from": start_date,
                "to": end_date,
                "expand": "providers",
            },
        ).json()
        records = payload if isinstance(payload, list) else payload.get("rates", []) if isinstance(payload, dict) else []
        rows: list[dict[str, object]] = []
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
            "output_type": 2 if preserve_vintages else 1,
        }
        payload = self.client.get(f"{self.provider.base_url}/series/observations", params=params).json()
        observations = payload.get("observations", []) if isinstance(payload, dict) else []
        retrieved_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
        rows = []
        for item in observations:
            if not isinstance(item, dict):
                continue
            if "value" in item:
                vintage_values = [(item.get("realtime_start", retrieved_at.date().isoformat()), item.get("value"))]
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
                        "unit": "",
                        "frequency": "",
                    }
                )
        if not rows:
            return normalise_macro_observations(
                pd.DataFrame(columns=["series_id", "observation_date", "vintage_date", "available_from", "value"]),
                source="fred",
                retrieved_at=retrieved_at,
            )
        return normalise_macro_observations(pd.DataFrame(rows), source="fred", retrieved_at=retrieved_at)


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
