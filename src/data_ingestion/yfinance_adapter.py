from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pandas as pd
import yfinance as yf

from src.utils.env import get_env


class YFinanceRequestError(RuntimeError):
    """Raised when yfinance returns no usable market data."""


@dataclass(frozen=True)
class YFinanceConfig:
    lookback_days: int = 756
    interval: str = "1d"
    auto_adjust: bool = True
    progress: bool = False

    @classmethod
    def from_env(cls) -> "YFinanceConfig":
        """Build yfinance configuration from environment variables or .env."""
        return cls(
            lookback_days=int(get_env("YFINANCE_LOOKBACK_DAYS", "756") or 756),
            interval=get_env("YFINANCE_INTERVAL", "1d") or "1d",
            auto_adjust=(get_env("YFINANCE_AUTO_ADJUST", "true") or "true").lower() in {"1", "true", "yes", "y", "on"},
            progress=(get_env("YFINANCE_PROGRESS", "false") or "false").lower() in {"1", "true", "yes", "y", "on"},
        )


class YFinanceMarketDataAdapter:
    """yfinance adapter for model-ready daily bars."""

    def __init__(self, config: YFinanceConfig | None = None) -> None:
        self.config = config or YFinanceConfig.from_env()

    @staticmethod
    def _normalise_download(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["date", "ticker", "close", "return"])
        data = raw.copy()
        close_frames = []
        if isinstance(data.columns, pd.MultiIndex):
            if "Close" in data.columns.get_level_values(0):
                close = data["Close"]
            elif "Adj Close" in data.columns.get_level_values(0):
                close = data["Adj Close"]
            else:
                raise YFinanceRequestError("yfinance response did not contain Close or Adj Close columns.")
            close = close if isinstance(close, pd.DataFrame) else close.to_frame(name=symbols[0])
            for ticker in close.columns:
                close_frames.append(pd.DataFrame({"date": close.index, "ticker": str(ticker), "close": close[ticker].to_numpy(dtype=float)}))
        else:
            close_column = "Close" if "Close" in data.columns else "Adj Close" if "Adj Close" in data.columns else None
            if close_column is None:
                raise YFinanceRequestError("yfinance response did not contain Close or Adj Close columns.")
            ticker = symbols[0] if symbols else "UNKNOWN"
            close_frames.append(pd.DataFrame({"date": data.index, "ticker": ticker, "close": data[close_column].to_numpy(dtype=float)}))
        output = pd.concat(close_frames, ignore_index=True) if close_frames else pd.DataFrame(columns=["date", "ticker", "close"])
        output["date"] = pd.to_datetime(output["date"]).dt.normalize()
        output["close"] = pd.to_numeric(output["close"], errors="coerce")
        output = output.dropna(subset=["date", "ticker", "close"]).sort_values(["ticker", "date"]).reset_index(drop=True)
        output["return"] = output.groupby("ticker")["close"].pct_change().fillna(0.0)
        return output[["date", "ticker", "close", "return"]]

    def load_daily_bars(
        self,
        symbols: list[str],
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Fetch yfinance daily bars and normalize them to the model price schema."""
        clean_symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        if not clean_symbols:
            return pd.DataFrame(columns=["date", "ticker", "close", "return"])
        end_dt = datetime.now(UTC).date() if end is None else pd.Timestamp(end).date()
        start_dt = end_dt - timedelta(days=self.config.lookback_days) if start is None else pd.Timestamp(start).date()
        raw = yf.download(
            tickers=clean_symbols,
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
            interval=self.config.interval,
            auto_adjust=self.config.auto_adjust,
            progress=self.config.progress,
            group_by="column",
            threads=False,
        )
        bars = self._normalise_download(raw, clean_symbols)
        if bars.empty:
            raise YFinanceRequestError("yfinance returned no daily bars for the requested symbols.")
        return bars
