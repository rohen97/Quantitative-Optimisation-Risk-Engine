from __future__ import annotations

import numpy as np
import pandas as pd

from src.reporting.column_resolver import canonicalise_dataframe, resolve_column
from src.reporting.models import ICDataBundle
from src.reporting.portfolio_resolver import ResolvedPortfolio


def build_exposure_tables(bundle: ICDataBundle) -> dict[str, pd.DataFrame]:
    return {
        name: bundle.frames.get(name, pd.DataFrame())
        for name in ["sector_exposure", "country_exposure", "region_exposure", "currency_exposure"]
        if name in bundle.frames
    }


def current_vs_target_holdings(bundle: ICDataBundle, resolved: ResolvedPortfolio) -> pd.DataFrame:
    current = canonicalise_dataframe(bundle.frames.get("current_portfolio", pd.DataFrame()))
    target = canonicalise_dataframe(resolved.portfolio)
    if current.empty:
        current = pd.DataFrame({"security_id": pd.Series(dtype=str), "current_weight": pd.Series(dtype=float)})
    if "security_id" not in current and "ticker" in current:
        current = current.copy()
        current["security_id"] = current["ticker"].astype(str)
    if "security_id" not in target and "ticker" in target:
        target = target.copy()
        target["security_id"] = target["ticker"].astype(str)
    current_weight = resolve_column(current, "current_weight")
    if current_weight is None and "market_value_usd" in current:
        total = pd.to_numeric(current["market_value_usd"], errors="coerce").sum()
        current = current.copy()
        current["current_weight"] = pd.to_numeric(current["market_value_usd"], errors="coerce").fillna(0.0) / total if total > 0 else 0.0
    merged = target.merge(current, on="security_id", how="outer", suffixes=("_target", "_current"))
    merged["target_weight"] = pd.to_numeric(merged.get("target_weight", merged.get("final_weight", 0.0)), errors="coerce").fillna(0.0)
    merged["current_weight"] = pd.to_numeric(merged.get("current_weight", merged.get("current_weight_current", 0.0)), errors="coerce").fillna(0.0)
    merged["weight_change"] = merged["target_weight"] - merged["current_weight"]
    merged["current_rank"] = merged["current_weight"].rank(ascending=False, method="min").astype(int)
    merged["target_rank"] = merged["target_weight"].rank(ascending=False, method="min").astype(int)
    merged["concentration_contribution"] = merged["target_weight"] ** 2
    for column in ("ticker", "company_name", "sector", "country", "region", "currency", "recommendation"):
        if column not in merged:
            merged[column] = merged.get(f"{column}_target", merged.get(f"{column}_current", ""))
    return merged[
        [
            "security_id",
            "ticker",
            "company_name",
            "sector",
            "country",
            "region",
            "currency",
            "recommendation",
            "current_weight",
            "target_weight",
            "weight_change",
            "current_rank",
            "target_rank",
            "concentration_contribution",
        ]
    ].sort_values("target_weight", ascending=False).reset_index(drop=True)


def _bucket_dividend_yield(value: float) -> str:
    if value <= 0:
        return "0%"
    if value < 0.02:
        return "0-2%"
    if value < 0.04:
        return "2-4%"
    if value < 0.06:
        return "4-6%"
    return "6%+"


def _bucket_risk(value: float) -> str:
    if value < 0.25:
        return "low"
    if value < 0.50:
        return "moderate"
    if value < 0.75:
        return "high"
    return "severe"


def exposure_by_group(holdings: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if holdings.empty or group_column not in holdings:
        return pd.DataFrame(columns=[group_column, "current_weight", "target_weight", "weight_change"])
    grouped = holdings.groupby(group_column, dropna=False)[["current_weight", "target_weight", "weight_change"]].sum()
    return grouped.reset_index().sort_values("target_weight", ascending=False)


def build_ic_exposure_outputs(bundle: ICDataBundle, resolved: ResolvedPortfolio) -> dict[str, pd.DataFrame]:
    holdings = current_vs_target_holdings(bundle, resolved)
    enriched = holdings.copy()
    if "dividend_yield" in resolved.portfolio:
        dy = pd.to_numeric(resolved.portfolio["dividend_yield"], errors="coerce").fillna(0.0)
        enriched["dividend_yield_bucket"] = dy.reindex(enriched.index, fill_value=0.0).map(_bucket_dividend_yield)
    else:
        enriched["dividend_yield_bucket"] = "unavailable"
    risk_source = resolved.portfolio.get("cvar_5", resolved.portfolio.get("var_5", pd.Series(0.0, index=resolved.portfolio.index)))
    risk_values = pd.to_numeric(risk_source, errors="coerce").abs().fillna(0.0).reindex(enriched.index, fill_value=0.0)
    enriched["risk_bucket"] = risk_values.map(_bucket_risk)
    hhi = float(np.square(pd.to_numeric(holdings["target_weight"], errors="coerce").fillna(0.0)).sum()) if not holdings.empty else 0.0
    concentration = pd.DataFrame(
        [
            {
                "maximum_single_name_weight": float(holdings["target_weight"].max()) if not holdings.empty else 0.0,
                "hhi": hhi,
                "effective_number_of_holdings": float(1.0 / hhi) if hhi > 0 else 0.0,
                "top_1_concentration": float(holdings["target_weight"].nlargest(1).sum()) if not holdings.empty else 0.0,
                "top_3_concentration": float(holdings["target_weight"].nlargest(3).sum()) if not holdings.empty else 0.0,
                "top_5_concentration": float(holdings["target_weight"].nlargest(5).sum()) if not holdings.empty else 0.0,
            }
        ]
    )
    return {
        "current_vs_target_holdings": enriched,
        "sector_exposures": exposure_by_group(enriched, "sector"),
        "country_exposures": exposure_by_group(enriched, "country"),
        "region_exposures": exposure_by_group(enriched, "region"),
        "currency_exposures": exposure_by_group(enriched, "currency"),
        "recommendation_exposures": exposure_by_group(enriched, "recommendation"),
        "dividend_yield_bucket_exposures": exposure_by_group(enriched, "dividend_yield_bucket"),
        "risk_bucket_exposures": exposure_by_group(enriched, "risk_bucket"),
        "concentration_summary": concentration,
    }
