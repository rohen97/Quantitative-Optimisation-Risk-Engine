from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config import load_yaml
from src.utils.env import env_flag, get_env


@dataclass(frozen=True)
class ProviderDefinition:
    name: str
    enabled: bool
    base_url: str
    credential_env: str | None
    secret_env: str | None
    asset_classes: tuple[str, ...]
    regions: tuple[str, ...]
    settings: dict[str, Any]
    availability_env: str | None = None

    @property
    def credential_available(self) -> bool:
        if not self.credential_env:
            return True
        primary = bool(get_env(self.credential_env, ""))
        secondary = not self.secret_env or bool(get_env(self.secret_env, ""))
        return primary and secondary

    @property
    def available(self) -> bool:
        explicitly_available = not self.availability_env or env_flag(self.availability_env, False)
        return self.enabled and self.credential_available and explicitly_available


@dataclass(frozen=True)
class DataSourceRegistry:
    providers: dict[str, ProviderDefinition]
    price_provider_order: tuple[str, ...]
    policy: dict[str, Any]
    research_references: tuple[dict[str, Any], ...]

    def available_for(self, asset_class: str, region: str | None = None) -> tuple[ProviderDefinition, ...]:
        ordered_names = list(self.price_provider_order)
        ordered_names.extend(name for name in self.providers if name not in ordered_names)
        matches = []
        for name in ordered_names:
            provider = self.providers[name]
            if not provider.available or asset_class not in provider.asset_classes:
                continue
            if region is not None and region not in provider.regions:
                continue
            matches.append(provider)
        return tuple(matches)

    def coverage_gaps(self, regions: tuple[str, ...], asset_class: str) -> tuple[str, ...]:
        return tuple(
            region
            for region in regions
            if not any(
                provider.enabled
                and asset_class in provider.asset_classes
                and region in provider.regions
                for provider in self.providers.values()
            )
        )


def load_data_source_registry(path: str | Path = "configs/data_sources.yaml") -> DataSourceRegistry:
    raw = load_yaml(path).get("data_sources", {})
    providers: dict[str, ProviderDefinition] = {}
    for name, config in raw.get("providers", {}).items():
        config = dict(config or {})
        credential_env = config.get("credential_env")
        secret_env = config.get("secret_env")
        env_base_name = str(config.get("base_url_env", f"{str(name).upper()}_BASE_URL"))
        base_url = get_env(env_base_name, str(config.get("base_url", ""))) or ""
        providers[name] = ProviderDefinition(
            name=name,
            enabled=bool(config.get("enabled", True)),
            base_url=base_url.rstrip("/"),
            credential_env=str(credential_env) if credential_env else None,
            secret_env=str(secret_env) if secret_env else None,
            asset_classes=tuple(str(value) for value in config.get("asset_classes", [])),
            regions=tuple(str(value) for value in config.get("regions", [])),
            settings=config,
            availability_env=(
                str(config["availability_env"]) if config.get("availability_env") else None
            ),
        )
    return DataSourceRegistry(
        providers=providers,
        price_provider_order=tuple(raw.get("price_provider_order", [])),
        policy=dict(raw.get("policy", {})),
        research_references=tuple(raw.get("research_references", [])),
    )
