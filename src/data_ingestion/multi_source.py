from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from src.data_ingestion.external_adapters import ChinaDataAdapter, EcbAdapter, FrankfurterAdapter, FredAdapter
from src.data_ingestion.http_client import DataSourceRequestError, HttpClient, HttpClientConfig
from src.data_ingestion.provider_registry import DataSourceRegistry, load_data_source_registry


LOGGER = logging.getLogger(__name__)
MODEL_REGIONS = ("DACH", "EU ex-DACH", "UK", "US", "Mainland China", "Hong Kong")


@dataclass(frozen=True)
class MultiSourceResult:
    fx_rates: pd.DataFrame
    macro_observations: pd.DataFrame
    source_status: pd.DataFrame


def build_source_status(registry: DataSourceRegistry | None = None) -> pd.DataFrame:
    registry = registry or load_data_source_registry()
    rows = []
    for provider in registry.providers.values():
        rows.append(
            {
                "provider": provider.name,
                "enabled": provider.enabled,
                "credential_required": bool(provider.credential_env),
                "credential_available": provider.credential_available,
                "available": provider.available,
                "asset_classes": ",".join(provider.asset_classes),
                "regions": ",".join(provider.regions),
                "base_url": provider.base_url,
            }
        )
    return pd.DataFrame(rows).sort_values("provider").reset_index(drop=True)


def _http_client(registry: DataSourceRegistry) -> HttpClient:
    policy = registry.policy
    return HttpClient(
        HttpClientConfig(
            timeout_seconds=int(policy.get("request_timeout_seconds", 30)),
            retry_attempts=int(policy.get("retry_attempts", 3)),
            retry_backoff_seconds=float(policy.get("retry_backoff_seconds", 1.0)),
            user_agent=str(policy.get("user_agent", "wolf-quant-model/1.0")),
        )
    )


def pull_configured_macro_and_fx(
    start: str | None = None,
    end: str | None = None,
    registry: DataSourceRegistry | None = None,
) -> MultiSourceResult:
    """Pull all available configured macro and FX feeds without hiding failures."""
    registry = registry or load_data_source_registry()
    client = _http_client(registry)
    macro_frames: list[pd.DataFrame] = []
    fx_frames: list[pd.DataFrame] = []
    statuses: list[dict[str, object]] = []

    def record(provider: str, dataset: str, status: str, rows: int = 0, error: str = "") -> None:
        statuses.append(
            {"provider": provider, "dataset": dataset, "status": status, "rows": rows, "error": error}
        )

    frankfurter = registry.providers["frankfurter"]
    if frankfurter.available:
        try:
            currencies = [str(value) for value in frankfurter.settings.get("currencies", []) if value != "USD"]
            frame = FrankfurterAdapter(frankfurter, client).load_fx_rates("USD", currencies, start, end)
            fx_frames.append(frame)
            record("frankfurter", "fx_rates", "completed", len(frame))
        except DataSourceRequestError as exc:
            record("frankfurter", "fx_rates", "failed", error=str(exc))

    fred = registry.providers["fred"]
    if fred.available:
        adapter = FredAdapter(fred, client)
        for label, series_id in dict(fred.settings.get("series", {})).items():
            try:
                frame = adapter.load_series(str(series_id), start, end, preserve_vintages=True)
                macro_frames.append(frame)
                record("fred", str(label), "completed", len(frame))
            except DataSourceRequestError as exc:
                record("fred", str(label), "failed", error=str(exc))
    else:
        record("fred", "configured_series", "credentials_missing")

    ecb = registry.providers["ecb"]
    if ecb.available:
        adapter = EcbAdapter(ecb, client)
        for label, series in dict(ecb.settings.get("series", {})).items():
            try:
                frame = adapter.load_series(
                    str(series["flow"]),
                    str(series["key"]),
                    start,
                    end,
                    include_history=True,
                )
                macro_frames.append(frame)
                record("ecb", str(label), "completed", len(frame))
            except (DataSourceRequestError, KeyError, ValueError) as exc:
                record("ecb", str(label), "failed", error=str(exc))

    china = registry.providers["china_data"]
    if china.available:
        adapter = ChinaDataAdapter(china, client)
        for dataset_id in china.settings.get("datasets", []):
            try:
                frame = adapter.load_dataset(str(dataset_id))
                macro_frames.append(frame)
                record("china_data", str(dataset_id), "completed", len(frame))
            except (DataSourceRequestError, ValueError) as exc:
                record("china_data", str(dataset_id), "failed", error=str(exc))

    macro = pd.concat(macro_frames, ignore_index=True) if macro_frames else pd.DataFrame()
    fx = pd.concat(fx_frames, ignore_index=True) if fx_frames else pd.DataFrame()
    status = pd.DataFrame(statuses)
    return MultiSourceResult(fx_rates=fx, macro_observations=macro, source_status=status)
