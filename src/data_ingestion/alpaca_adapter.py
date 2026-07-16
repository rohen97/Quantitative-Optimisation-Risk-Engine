from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from src.utils.env import get_env


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
    data_feed: str = "iex"

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
            data_base_url=get_env("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets") or "https://data.alpaca.markets",
            data_feed=get_env("ALPACA_DATA_FEED", "iex") or "iex",
        )


class AlpacaMarketDataAdapter:
    """Minimal Alpaca adapter for account checks and daily stock bars."""

    def __init__(self, config: AlpacaConfig | None = None, timeout: int = 30) -> None:
        self.config = config or AlpacaConfig.from_env()
        self.timeout = timeout

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
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AlpacaRequestError(f"Alpaca HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise AlpacaRequestError(f"Alpaca request failed: {exc.reason}") from exc

    def fetch_account(self) -> dict:
        """Fetch the Alpaca account profile for credential validation."""
        return self._get_json(f"{self.config.trading_base_url.rstrip('/')}/v2/account")

    def load_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Fetch daily bars and normalize them to the model price schema."""
        if not symbols:
            return pd.DataFrame(columns=["date", "ticker", "close", "return"])
        end_dt = datetime.now(UTC) if end is None else pd.Timestamp(end).to_pydatetime()
        start_dt = end_dt - timedelta(days=365 * 3) if start is None else pd.Timestamp(start).to_pydatetime()
        params = urlencode(
            {
                "symbols": ",".join(symbols),
                "timeframe": "1Day",
                "start": start_dt.date().isoformat(),
                "end": end_dt.date().isoformat(),
                "adjustment": "all",
                "feed": self.config.data_feed,
                "limit": 10000,
            }
        )
        payload = self._get_json(f"{self.config.data_base_url.rstrip('/')}/v2/stocks/bars?{params}")
        rows = []
        for symbol, bars in payload.get("bars", {}).items():
            for bar in bars:
                rows.append({"date": pd.to_datetime(bar["t"]).normalize(), "ticker": symbol, "close": float(bar["c"])})
        data = pd.DataFrame(rows)
        if data.empty:
            return pd.DataFrame(columns=["date", "ticker", "close", "return"])
        data = data.sort_values(["ticker", "date"]).reset_index(drop=True)
        data["return"] = data.groupby("ticker")["close"].pct_change().fillna(0.0)
        return data[["date", "ticker", "close", "return"]]
