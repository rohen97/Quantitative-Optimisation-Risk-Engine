from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.data_ingestion.http_client import DataSourceRequestError, HttpClient, HttpClientConfig
from src.data_ingestion.mock_data import generate_mock_universe
from src.data_ingestion.provider_registry import load_data_source_registry
from src.utils.config import load_yaml
from src.utils.env import get_env


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class UniverseRegion:
    name: str
    countries: tuple[str, ...]
    currencies: tuple[str, ...]


_COUNTRY_ALIASES = {
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "great britain": "United Kingdom",
    "china": "China",
    "mainland china": "China",
    "hong kong": "Hong Kong",
}


_EXCHANGE_COUNTRY_ALIASES = {
    "usa": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "great britain": "United Kingdom",
    "peoples republic of china": "China",
    "people's republic of china": "China",
}



_YFINANCE_SUFFIX_BY_EXCHANGE = {
    "US": "",
    "LSE": ".L",
    "HK": ".HK",
    "SHG": ".SS",
    "SHE": ".SZ",
    "XETRA": ".DE",
    "F": ".F",
    "DU": ".DU",
    "MU": ".MU",
    "HM": ".HM",
    "HA": ".HA",
    "STU": ".SG",
    "SW": ".SW",
    "VI": ".VI",
    "PA": ".PA",
    "AS": ".AS",
    "BR": ".BR",
    "CO": ".CO",
    "ST": ".ST",
    "MC": ".MC",
    "HE": ".HE",
    "IR": ".IR",
}

_ITICK_REGION_BY_EXCHANGE = {
    "US": "US",
    "HK": "HK",
    "SHG": "SH",
    "SHE": "SZ",
}


def _yfinance_symbol(code: str, exchange_code: str) -> object:
    suffix = _YFINANCE_SUFFIX_BY_EXCHANGE.get(exchange_code)
    if suffix is None:
        return pd.NA
    if exchange_code == "US":
        if "-P-" in code:
            root, preferred_class = code.split("-P-", 1)
            if root and preferred_class:
                return f"{root}-P{preferred_class}"
        if "-PR-" in code:
            root, preferred_class = code.split("-PR-", 1)
            if root and preferred_class:
                return f"{root}-P{preferred_class}"
        if "-PR" in code:
            root, preferred_class = code.split("-PR", 1)
            if root and len(preferred_class) == 1:
                return f"{root}-P{preferred_class}"
    if exchange_code == "HK" and code.isdigit():
        return f"{code.zfill(4)}{suffix}"
    return f"{code}{suffix}"




def _tickdb_symbol(code: str, exchange_code: str) -> object:
    if exchange_code == "HK":
        hk_code = code.split("-OL", 1)[0]
        if hk_code.isdigit():
            return f"{int(hk_code)}.HK"
    if exchange_code == "SHG":
        return f"{code}.SH"
    if exchange_code == "SHE":
        return f"{code}.SZ"
    if exchange_code == "US":
        return f"{code}.US"
    return pd.NA


def _provider_symbol_columns(code: str, exchange_code: str, eodhd_ticker: str) -> dict[str, object]:
    yfinance_ticker = _yfinance_symbol(code, exchange_code)
    us_symbol = code if exchange_code == "US" else pd.NA
    return {
        "yfinance_ticker": yfinance_ticker,
        "finnhub_ticker": us_symbol if exchange_code == "US" else eodhd_ticker,
        "alpha_vantage_ticker": us_symbol,
        "alpaca_ticker": us_symbol,
        "tickdb_ticker": _tickdb_symbol(code, exchange_code),
        "itick_code": code if exchange_code in _ITICK_REGION_BY_EXCHANGE else pd.NA,
        "itick_region": _ITICK_REGION_BY_EXCHANGE.get(exchange_code, pd.NA),
    }


def _canonical_country(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _COUNTRY_ALIASES.get(text.lower(), _EXCHANGE_COUNTRY_ALIASES.get(text.lower(), text))


def _load_universe_yaml(path: str = "configs/universe.yaml") -> dict[str, Any]:
    return load_yaml(path)


def _load_regions(path: str = "configs/universe.yaml") -> tuple[UniverseRegion, ...]:
    raw = _load_universe_yaml(path).get("regions", {})
    regions: list[UniverseRegion] = []
    for name, config in raw.items():
        regions.append(
            UniverseRegion(
                name=str(name),
                countries=tuple(_canonical_country(country) for country in config.get("countries", [])),
                currencies=tuple(str(currency).upper() for currency in config.get("currencies", [])),
            )
        )
    return tuple(regions)


def _region_for_country(country: str, regions: tuple[UniverseRegion, ...]) -> str:
    canonical = _canonical_country(country)
    for region in regions:
        if canonical in region.countries:
            return region.name
    return ""


def _client_from_policy(policy: dict[str, Any]) -> HttpClient:
    return HttpClient(
        HttpClientConfig(
            timeout_seconds=int(get_env("DATA_REQUEST_TIMEOUT_SECONDS", str(policy.get("request_timeout_seconds", 30))) or 30),
            retry_attempts=int(get_env("DATA_RETRY_ATTEMPTS", str(policy.get("retry_attempts", 3))) or 3),
            retry_backoff_seconds=float(policy.get("retry_backoff_seconds", 1.0)),
            user_agent=str(policy.get("user_agent", "wolf-quant-model/1.0")),
        )
    )


def _value(row: dict[str, Any], *names: str, default: object = "") -> object:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return default


def _normalise_eodhd_symbol_rows(rows: list[dict[str, Any]], exchange_code: str, region_name: str, listing_status: str) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    retrieved_at = pd.Timestamp.now('UTC').tz_localize(None)
    for item in rows:
        code = str(_value(item, "Code", "code")).strip()
        if not code:
            continue
        exchange = str(_value(item, "Exchange", "exchange", default=exchange_code)).strip() or exchange_code
        country = _canonical_country(_value(item, "Country", "country"))
        currency = str(_value(item, "Currency", "currency")).strip().upper()
        instrument_type = str(_value(item, "Type", "type", default="Stock")).strip() or "Stock"
        eodhd_ticker = f"{code}.{exchange_code}"
        security_id = eodhd_ticker.upper()
        records.append(
            {
                "security_id": security_id,
                "ticker": eodhd_ticker,
                "company_name": str(_value(item, "Name", "name", default=code)).strip() or code,
                "instrument_type": "Equity",
                "listing_status": listing_status,
                "exchange_code": exchange_code,
                "exchange_name": exchange,
                "country": country,
                "region": region_name,
                "sector": "Unknown",
                "industry": "Unknown",
                "currency": currency,
                "trading_currency": currency,
                "domicile_currency": currency,
                "isin": _value(item, "Isin", "ISIN", "isin", default=""),
                "eodhd_ticker": eodhd_ticker,
                **_provider_symbol_columns(code, exchange_code, eodhd_ticker),
                "market_cap_usd": pd.NA,
                "avg_daily_traded_value_usd": pd.NA,
                "first_seen_at": retrieved_at,
                "last_seen_at": retrieved_at,
                "source": "eodhd",
            }
        )
    return pd.DataFrame(records)


def load_eodhd_universe(include_delisted: bool = True, instrument_type: str = "stock") -> pd.DataFrame:
    """Pull active and delisted listed-equity symbols for configured countries from EODHD."""
    registry = load_data_source_registry()
    provider = registry.providers.get("eodhd")
    if provider is None or not provider.enabled:
        raise DataSourceRequestError("EODHD provider is not enabled in configs/data_sources.yaml.")
    token = get_env(provider.credential_env or "", "")
    if not token:
        raise DataSourceRequestError("EODHD_API_TOKEN is required for live universe ingestion.")

    regions = _load_regions()
    country_to_region = {country: region.name for region in regions for country in region.countries}
    countries = set(country_to_region)
    client = _client_from_policy(registry.policy)

    exchange_payload = client.get(f"{provider.base_url}/exchanges-list", params={"api_token": token, "fmt": "json"}).json()
    if not isinstance(exchange_payload, list):
        raise DataSourceRequestError("EODHD exchanges-list returned an invalid payload.")

    exchanges: list[tuple[str, str, str]] = []
    overrides = _load_universe_yaml().get("eodhd_exchange_overrides", {})
    for region_name, entries in overrides.items():
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get("code", "")).strip()
            country = _canonical_country(entry.get("country", ""))
            name = str(entry.get("name", code)).strip()
            if code and country in countries:
                exchanges.append((code, name, country))
    for item in exchange_payload:
        if not isinstance(item, dict):
            continue
        country = _canonical_country(_value(item, "Country", "country"))
        code = str(_value(item, "Code", "code")).strip()
        name = str(_value(item, "Name", "name", default=code)).strip()
        if country in countries and code:
            exchanges.append((code, name, country))

    frames: list[pd.DataFrame] = []
    statuses = ["Active", "Delisted"] if include_delisted else ["Active"]
    for exchange_code, exchange_name, country in sorted(set(exchanges)):
        region_name = _region_for_country(country, regions)
        for status in statuses:
            params: dict[str, object] = {"api_token": token, "fmt": "json", "type": instrument_type}
            if status == "Delisted":
                params["delisted"] = 1
            try:
                payload = client.get(f"{provider.base_url}/exchange-symbol-list/{exchange_code}", params=params).json()
            except DataSourceRequestError as exc:
                LOGGER.warning("EODHD universe request failed for %s status=%s: %s", exchange_code, status, exc)
                continue
            if not isinstance(payload, list):
                LOGGER.warning("EODHD returned invalid universe payload for %s status=%s", exchange_code, status)
                continue
            frame = _normalise_eodhd_symbol_rows(payload, exchange_code, region_name, status)
            if not frame.empty:
                frame["country"] = frame["country"].replace("", country)
                frame["region"] = frame["region"].replace("", region_name)
                frames.append(frame)
                LOGGER.info("Loaded %s %s EODHD symbols from %s (%s).", len(frame), status.lower(), exchange_code, exchange_name)

    if not frames:
        raise DataSourceRequestError("No EODHD universe symbols were returned for the configured countries.")

    universe = pd.concat(frames, ignore_index=True)
    universe = universe[universe["country"].isin(countries)].copy()
    universe["region"] = universe["country"].map(country_to_region).fillna(universe["region"])
    if universe.empty:
        raise DataSourceRequestError("EODHD returned symbols, but none matched the configured universe countries.")
    universe = universe.sort_values(["country", "exchange_code", "listing_status", "ticker"]).drop_duplicates("security_id", keep="first")
    return universe.reset_index(drop=True)


def build_universe(use_mock: bool = True, n: int = 24, include_delisted: bool = True) -> pd.DataFrame:
    if use_mock:
        return generate_mock_universe(n=n)
    return load_eodhd_universe(include_delisted=include_delisted)
