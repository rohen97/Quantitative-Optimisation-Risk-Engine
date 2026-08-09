from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from src.utils.env import get_env

try:
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
    from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    ALPACA_PY_AVAILABLE = True
except ImportError:
    DataFeed = None
    CryptoHistoricalDataClient = None
    StockHistoricalDataClient = None
    CryptoBarsRequest = None
    StockBarsRequest = None
    TimeFrame = None
    ALPACA_PY_AVAILABLE = False


class AlpacaConfigurationError(RuntimeError):
    """Raised when Alpaca is enabled without the required credentials."""


class AlpacaRequestError(RuntimeError):
    """Raised when Alpaca returns an HTTP or network error."""


@dataclass(frozen=True)
class AlpacaConfig:
    api_key_id: str
    api_secret_key: str
    trading_base_url: str
    data_base_url: str
    data_api_version: str = "v2"
    data_feed: str = "iex"
    historical_max_pages: int = 100

    @property
    def historical_base_url(self) -> str:
        """Resolve https://data.alpaca.markets/{version} safely."""
        version = self.data_api_version.strip("/")
        template = self.data_base_url.rstrip("/")
        if "{version}" in template:
            return template.format(version=version).rstrip("/")
        if template.endswith(f"/{version}"):
            return template
        return f"{template}/{version}"

    @property
    def trading_api_base_url(self) -> str:
        """Accept either the Alpaca host root or its explicit /v2 endpoint."""
        base = self.trading_base_url.rstrip("/")
        return base if base.endswith("/v2") else f"{base}/v2"

    @classmethod
    def from_env(cls) -> "AlpacaConfig":
        """Build Alpaca configuration from environment variables or .env."""
        api_key_id = get_env("ALPACA_API_KEY_ID", "") or ""
        api_secret_key = get_env("ALPACA_API_SECRET_KEY", "") or ""
        if not api_key_id or not api_secret_key:
            raise AlpacaConfigurationError(
                "Alpaca is enabled but ALPACA_API_KEY_ID or ALPACA_API_SECRET_KEY is missing."
            )
        env = (get_env("ALPACA_ENV", "paper") or "paper").lower()
        paper_url = get_env("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")
        live_url = get_env("ALPACA_LIVE_BASE_URL", "https://api.alpaca.markets")
        return cls(
            api_key_id=api_key_id,
            api_secret_key=api_secret_key,
            trading_base_url=paper_url if env == "paper" else live_url,
            data_base_url=get_env(
                "ALPACA_DATA_BASE_URL",
                "https://data.alpaca.markets/{version}",
            )
            or "https://data.alpaca.markets/{version}",
            data_api_version=get_env("ALPACA_DATA_API_VERSION", "v2") or "v2",
            data_feed=get_env("ALPACA_DATA_FEED", "iex") or "iex",
            historical_max_pages=int(get_env("ALPACA_HISTORICAL_MAX_PAGES", "100") or 100),
        )


class AlpacaMarketDataAdapter:
    """Minimal Alpaca adapter for account checks and daily stock bars."""

    def __init__(self, config: AlpacaConfig | None = None, timeout: int = 30) -> None:
        self.config = config or AlpacaConfig.from_env()
        self.timeout = timeout
        self.last_request_id: str | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.config.api_key_id,
            "APCA-API-SECRET-KEY": self.config.api_secret_key,
            "Accept": "application/json",
        }

    def _get_json(self, url: str) -> dict:
        request = Request(url, headers=self._headers(), method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_headers = getattr(response, "headers", {})
                self.last_request_id = response_headers.get("X-Request-ID") if response_headers else None
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            self.last_request_id = exc.headers.get("X-Request-ID") if exc.headers else None
            body = exc.read().decode("utf-8", errors="replace")
            request_context = f" request_id={self.last_request_id}" if self.last_request_id else ""
            raise AlpacaRequestError(f"Alpaca HTTP {exc.code}:{request_context} {body}") from exc
        except URLError as exc:
            raise AlpacaRequestError(f"Alpaca request failed: {exc.reason}") from exc

    def fetch_account(self) -> dict:
        """Fetch the Alpaca account profile for credential validation."""
        return self._get_json(f"{self.config.trading_api_base_url}/account")

    def historical_url(self, endpoint: str) -> str:
        """Build an endpoint under Alpaca's versioned historical API base."""
        return f"{self.config.historical_base_url}/{endpoint.lstrip('/')}"

    def fetch_historical(self, endpoint: str, params: dict[str, object]) -> dict:
        """Fetch one versioned historical endpoint with authenticated headers."""
        query = urlencode({key: value for key, value in params.items() if value is not None})
        return self._get_json(f"{self.historical_url(endpoint)}?{query}")

    def load_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Fetch daily bars and normalize them to the model price schema."""
        if not symbols:
            return pd.DataFrame(
                columns=["date", "ticker", "open", "high", "low", "close", "adjusted_close", "volume", "return"]
            )
        end_dt = datetime.now(UTC) if end is None else pd.Timestamp(end).to_pydatetime()
        start_dt = end_dt - timedelta(days=365 * 3) if start is None else pd.Timestamp(start).to_pydatetime()
        rows = []
        base_params: dict[str, object] = {
            "symbols": ",".join(symbols),
            "timeframe": "1Day",
            "start": start_dt.date().isoformat(),
            "end": end_dt.date().isoformat(),
            "adjustment": "all",
            "feed": self.config.data_feed,
            "limit": 10000,
        }
        page_token: str | None = None
        for _ in range(max(self.config.historical_max_pages, 1)):
            payload = self.fetch_historical(
                "stocks/bars",
                {**base_params, "page_token": page_token},
            )
            for symbol, bars in payload.get("bars", {}).items():
                for bar in bars:
                    close = float(bar["c"])
                    rows.append(
                        {
                            "date": pd.to_datetime(bar["t"]).normalize(),
                            "ticker": symbol,
                            "open": float(bar.get("o", close)),
                            "high": float(bar.get("h", close)),
                            "low": float(bar.get("l", close)),
                            "close": close,
                            "adjusted_close": close,
                            "volume": float(bar["v"]) if bar.get("v") is not None else float("nan"),
                        }
                    )
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        else:
            raise AlpacaRequestError(
                f"Alpaca historical pagination exceeded {self.config.historical_max_pages} pages."
            )
        data = pd.DataFrame(rows)
        if data.empty:
            return pd.DataFrame(
                columns=["date", "ticker", "open", "high", "low", "close", "adjusted_close", "volume", "return"]
            )
        data = data.sort_values(["ticker", "date"]).reset_index(drop=True)
        data["return"] = data.groupby("ticker")["close"].pct_change().fillna(0.0)
        return data[
            ["date", "ticker", "open", "high", "low", "close", "adjusted_close", "volume", "return"]
        ]


class AlpacaSdkMarketDataAdapter:
    """Official alpaca-py adapter for historical stock and no-key crypto bars."""

    def __init__(self, config: AlpacaConfig | None = None) -> None:
        if not ALPACA_PY_AVAILABLE:
            raise AlpacaConfigurationError("alpaca-py is not installed.")
        self.config = config
        if self.config is None:
            try:
                self.config = AlpacaConfig.from_env()
            except AlpacaConfigurationError:
                self.config = None

    @staticmethod
    def _normalise_bars(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty:
            return pd.DataFrame(
                columns=["date", "ticker", "open", "high", "low", "close", "adjusted_close", "volume", "return"]
            )
        data = frame.reset_index()
        symbol_column = "symbol" if "symbol" in data.columns else "ticker"
        timestamp_column = "timestamp" if "timestamp" in data.columns else "date"
        output = pd.DataFrame(
            {
                "date": pd.to_datetime(data[timestamp_column], utc=True).dt.tz_localize(None).dt.normalize(),
                "ticker": data[symbol_column].astype(str),
                "open": pd.to_numeric(data.get("open"), errors="coerce"),
                "high": pd.to_numeric(data.get("high"), errors="coerce"),
                "low": pd.to_numeric(data.get("low"), errors="coerce"),
                "close": pd.to_numeric(data["close"], errors="coerce"),
                "adjusted_close": pd.to_numeric(data["close"], errors="coerce"),
                "volume": pd.to_numeric(data.get("volume"), errors="coerce"),
            }
        )
        output = output.dropna(subset=["date", "ticker", "close"])
        output = output.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
        output["return"] = output.groupby("ticker")["close"].pct_change().fillna(0.0)
        return output[
            ["date", "ticker", "open", "high", "low", "close", "adjusted_close", "volume", "return"]
        ].reset_index(drop=True)

    @staticmethod
    def _datetime(value: str | None, fallback: datetime) -> datetime:
        if value is None:
            return fallback
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        return timestamp.to_pydatetime()

    def load_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        if self.config is None:
            raise AlpacaConfigurationError(
                "Authenticated Alpaca stock history requires ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY."
            )
        end_dt = self._datetime(end, datetime.now(UTC))
        start_dt = self._datetime(start, end_dt - timedelta(days=365 * 3))
        feed_value = self.config.data_feed.lower()
        feed = next(
            (candidate for candidate in DataFeed if str(candidate.value).lower() == feed_value),
            DataFeed.IEX,
        )
        try:
            client = StockHistoricalDataClient(
                api_key=self.config.api_key_id,
                secret_key=self.config.api_secret_key,
            )
            request = StockBarsRequest(
                symbol_or_symbols=sorted(set(symbols)),
                timeframe=TimeFrame.Day,
                start=start_dt,
                end=end_dt,
                feed=feed,
            )
            return self._normalise_bars(client.get_stock_bars(request).df)
        except Exception as exc:
            raise AlpacaRequestError(f"alpaca-py stock history request failed: {exc}") from exc

    def load_crypto_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        end_dt = self._datetime(end, datetime.now(UTC))
        start_dt = self._datetime(start, end_dt - timedelta(days=365))
        try:
            client = CryptoHistoricalDataClient()
            request = CryptoBarsRequest(
                symbol_or_symbols=sorted(set(symbols)),
                timeframe=TimeFrame.Day,
                start=start_dt,
                end=end_dt,
            )
            return self._normalise_bars(client.get_crypto_bars(request).df)
        except Exception as exc:
            raise AlpacaRequestError(f"alpaca-py crypto history request failed: {exc}") from exc
