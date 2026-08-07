from __future__ import annotations

import logging

import pandas as pd

from src.data_ingestion.alpaca_adapter import ALPACA_PY_AVAILABLE, AlpacaMarketDataAdapter, AlpacaSdkMarketDataAdapter
from src.data_ingestion.external_adapters import AlphaVantageAdapter, EodhdAdapter, FinnhubAdapter, ITickAdapter, TickDbAdapter
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient, HttpClientConfig
from src.data_ingestion.mock_data import generate_mock_prices
from src.data_ingestion.provider_registry import load_data_source_registry
from src.data_ingestion.yfinance_adapter import YFinanceMarketDataAdapter
from src.utils.env import env_flag, get_env


LOGGER = logging.getLogger(__name__)


def _client_from_policy(policy: dict) -> HttpClient:
    return HttpClient(
        HttpClientConfig(
            timeout_seconds=int(get_env("DATA_REQUEST_TIMEOUT_SECONDS", str(policy.get("request_timeout_seconds", 30))) or 30),
            retry_attempts=int(get_env("DATA_RETRY_ATTEMPTS", str(policy.get("retry_attempts", 3))) or 3),
            retry_backoff_seconds=float(policy.get("retry_backoff_seconds", 1.0)),
            user_agent=str(policy.get("user_agent", "wolf-quant-model/1.0")),
        )
    )


def _load_provider(
    provider_name: str,
    symbols: list[str],
    client: HttpClient,
    registry,
    universe: pd.DataFrame | None = None,
) -> pd.DataFrame:
    provider = registry.providers.get(provider_name)
    if provider_name == "yfinance":
        data = YFinanceMarketDataAdapter().load_daily_bars(symbols)
        data["source"] = "yfinance"
        return data
    if provider_name == "alpaca":
        use_sdk = env_flag("ALPACA_USE_SDK", True) and ALPACA_PY_AVAILABLE
        adapter = AlpacaSdkMarketDataAdapter() if use_sdk else AlpacaMarketDataAdapter()
        data = adapter.load_daily_bars(symbols)
        data["source"] = "alpaca"
        return data
    if provider is None:
        raise NotImplementedError(f"Unsupported price data provider: {provider_name}")
    if provider_name == "eodhd":
        return EodhdAdapter(provider, client).load_daily_bars(symbols)
    if provider_name == "finnhub":
        return FinnhubAdapter(provider, client).load_daily_bars(symbols)
    if provider_name == "alpha_vantage":
        return AlphaVantageAdapter(provider, client).load_daily_bars(symbols)
    if provider_name == "tickdb":
        return TickDbAdapter(provider, client).load_daily_bars(symbols)
    if provider_name == "itick":
        adapter = ITickAdapter(provider, client)
        if universe is None or "itick_region" not in universe.columns:
            region = get_env("ITICK_DEFAULT_REGION", "US") or "US"
            return adapter.load_daily_bars(symbols, region=region)
        symbol_column = str(provider.settings.get("symbol_column", "itick_code"))
        grouped = (
            universe[["ticker", symbol_column, "itick_region"]]
            .dropna(subset=[symbol_column, "itick_region"])
            .astype(str)
            .drop_duplicates()
        )
        frames: list[pd.DataFrame] = []
        for region, region_rows in grouped.groupby("itick_region"):
            region_symbols = sorted(region_rows[symbol_column].str.strip().loc[lambda values: values.ne("")].unique())
            if region_symbols:
                frames.append(adapter.load_daily_bars(region_symbols, region=region))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raise NotImplementedError(f"Unsupported price data provider: {provider_name}")


def _provider_symbols(universe: pd.DataFrame, provider_name: str, registry) -> tuple[list[str], dict[str, str]]:
    definition = registry.providers.get(provider_name)
    configured_column = definition.settings.get("symbol_column") if definition is not None else None
    symbol_column = str(configured_column) if configured_column and configured_column in universe.columns else "ticker"
    if symbol_column == "ticker":
        pairs = universe[["ticker"]].copy()
        pairs["provider_symbol"] = pairs["ticker"]
    else:
        pairs = universe[["ticker", symbol_column]].rename(columns={symbol_column: "provider_symbol"})
    pairs = pairs.dropna().astype(str).drop_duplicates()
    pairs = pairs[(pairs["ticker"].str.strip() != "") & (pairs["provider_symbol"].str.strip() != "")]
    reverse_map = dict(zip(pairs["provider_symbol"], pairs["ticker"], strict=False))
    return sorted(reverse_map), reverse_map


def _combine_provider_prices(frames: list[pd.DataFrame], provider_order: list[str], tolerance: float) -> pd.DataFrame:
    combined = pd.concat(frames, ignore_index=True)
    combined["provider_rank"] = combined["source"].map({name: rank for rank, name in enumerate(provider_order)}).fillna(len(provider_order))
    comparison = (
        combined.groupby(["ticker", "date"])["close"]
        .agg(source_count="count", minimum_close="min", maximum_close="max")
        .reset_index()
    )
    comparison["close_difference_fraction"] = (
        (comparison["maximum_close"] - comparison["minimum_close"])
        / comparison["minimum_close"].replace(0.0, pd.NA)
    ).fillna(0.0)
    discrepancies = comparison[comparison["close_difference_fraction"] > tolerance].copy()
    if not discrepancies.empty:
        LOGGER.warning(
            "Found %s cross-provider close discrepancies above %.2f%%; highest-priority values were retained.",
            len(discrepancies),
            tolerance * 100.0,
        )
    combined["_missing_volume"] = pd.to_numeric(
        combined.get("volume", pd.Series(float("nan"), index=combined.index)),
        errors="coerce",
    ).fillna(0.0).le(0.0)
    selected = (
        combined.sort_values(["ticker", "date", "_missing_volume", "provider_rank"])
        .drop_duplicates(["ticker", "date"], keep="first")
        .drop(columns=["provider_rank", "_missing_volume"])
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    selected["return"] = selected.groupby("ticker")["close"].pct_change().fillna(0.0)
    selected.attrs["source_comparison"] = comparison
    selected.attrs["source_discrepancies"] = discrepancies
    return selected


def load_prices(universe: pd.DataFrame, use_mock: bool | None = None) -> pd.DataFrame:
    """Load prices from every configured and credentialed source, then cross-validate."""
    if use_mock is None:
        use_mock = env_flag("USE_MOCK_DATA", True)
    if use_mock:
        return generate_mock_prices(universe)

    registry = load_data_source_registry()
    use_all = env_flag("USE_ALL_AVAILABLE_DATA_SOURCES", True)
    configured = get_env("DATA_PRICE_PROVIDERS", ",".join(registry.price_provider_order)) or ""
    providers = [name.strip().lower() for name in configured.split(",") if name.strip()]
    if not use_all:
        providers = [(get_env("DATA_PROVIDER", "yfinance") or "yfinance").lower()]

    client = _client_from_policy(registry.policy)
    frames: list[pd.DataFrame] = []
    failures: dict[str, str] = {}
    for provider_name in providers:
        definition = registry.providers.get(provider_name)
        if definition is not None and not definition.available:
            LOGGER.info("Skipping %s because its credentials are not configured.", provider_name)
            continue
        try:
            symbols, reverse_map = _provider_symbols(universe, provider_name, registry)
            frame = _load_provider(provider_name, symbols, client, registry, universe)
            if not frame.empty:
                frame["ticker"] = frame["ticker"].map(reverse_map).fillna(frame["ticker"])
            if not frame.empty:
                frames.append(frame)
                LOGGER.info("Loaded %s price rows from %s.", len(frame), provider_name)
        except (DataSourceRequestError, RuntimeError, NotImplementedError, ValueError) as exc:
            failures[provider_name] = str(exc)
            LOGGER.warning("Price provider %s failed: %s", provider_name, exc)

    if not frames:
        failure_text = "; ".join(f"{name}: {message}" for name, message in failures.items())
        raise DataSourceRequestError(f"No configured price provider returned data. {failure_text}")

    tolerance = float(registry.policy.get("maximum_close_difference_fraction", 0.02))
    return _combine_provider_prices(frames, providers, tolerance)
