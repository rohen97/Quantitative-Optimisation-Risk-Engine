from __future__ import annotations

import pandas as pd

from src.reporting.column_resolver import canonicalise_dataframe
from src.reporting.models import ICDataBundle
from src.reporting.portfolio_resolver import ResolvedPortfolio


def build_forecast_summary(bundle: ICDataBundle) -> pd.DataFrame:
    rows = []
    for horizon in [3, 6, 9, 12]:
        frame = bundle.frames.get(f"recommendations_{horizon}m", pd.DataFrame())
        if frame.empty:
            continue
        numeric = frame.select_dtypes(include="number")
        rows.append(
            {
                "horizon_months": horizon,
                "rows": len(frame),
                "mean_expected_total_return": float(numeric.filter(like="expected_total_return").mean().mean()) if not numeric.empty else pd.NA,
                "mean_p5": float(numeric.filter(like="p5").mean().mean()) if not numeric.empty else pd.NA,
                "mean_p50": float(numeric.filter(like="p50").mean().mean()) if not numeric.empty else pd.NA,
                "mean_p95": float(numeric.filter(like="p95").mean().mean()) if not numeric.empty else pd.NA,
            }
        )
    return pd.DataFrame(rows)


FORECAST_COLUMNS = {
    "expected_total_return": "expected_total_return",
    "expected_price_return": "expected_price_return",
    "expected_dividend_return": "expected_dividend_return",
    "p5_return": "p5",
    "p50_return": "p50",
    "p95_return": "p95",
    "expected_volatility": "volatility",
    "var_5": "var_5",
    "cvar_5": "cvar_5",
    "expected_shortfall_5": "expected_shortfall_5",
    "dividend_cut_probability": "dividend_cut_probability",
    "large_drawdown_probability": "drawdown_probability",
    "distribution_model_confidence": "forecast_confidence",
    "distribution_name": "selected_distribution",
}


def _forecast_frame(
    bundle: ICDataBundle,
    horizon: int,
    security_ids: set[str] | None = None,
    tickers: set[str] | None = None,
) -> pd.DataFrame:
    frame = bundle.frames.get(f"ml_forecasts_{horizon}m", pd.DataFrame())
    if frame.empty:
        frame = bundle.frames.get(f"recommendations_{horizon}m", pd.DataFrame())
    data = canonicalise_dataframe(frame)
    if data.empty:
        return data
    if "security_id" not in data:
        data["security_id"] = data.get("ticker", pd.Series(range(len(data)), index=data.index)).astype(str)
    if security_ids or tickers:
        selected = data["security_id"].astype(str).isin(security_ids or set())
        if "ticker" in data:
            selected |= data["ticker"].astype(str).isin(tickers or set())
        data = data.loc[selected].copy()
    output = pd.DataFrame(
        {
            "horizon": f"{horizon}M",
            "horizon_months": horizon,
            "security_id": data["security_id"].astype(str),
            "ticker": data.get("ticker", data["security_id"]).astype(str),
            "company_name": data.get("company_name", ""),
            "model_version": data.get("model_version", data.get("distribution_family", "mock_distributional_v1")),
        }
    )
    for source, target in FORECAST_COLUMNS.items():
        output[target] = pd.to_numeric(data[source], errors="coerce") if source in data and target not in {"selected_distribution"} else data.get(source, "")
    return output


def build_security_forecast_summary(
    bundle: ICDataBundle,
    resolved: ResolvedPortfolio | None = None,
) -> pd.DataFrame:
    security_ids: set[str] | None = None
    tickers: set[str] | None = None
    if resolved is not None and not resolved.portfolio.empty:
        security_ids = set(resolved.portfolio.get("security_id", pd.Series(dtype=str)).dropna().astype(str))
        tickers = set(resolved.portfolio.get("ticker", pd.Series(dtype=str)).dropna().astype(str))
    frames = [_forecast_frame(bundle, horizon, security_ids, tickers) for horizon in (3, 6, 9, 12)]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_forecast_horizon_summary(bundle: ICDataBundle, resolved: ResolvedPortfolio) -> pd.DataFrame:
    security = build_security_forecast_summary(bundle, resolved)
    if security.empty:
        return security
    weights = resolved.portfolio.copy()
    if "security_id" not in weights:
        weights["security_id"] = weights.get("ticker", pd.Series(range(len(weights)), index=weights.index)).astype(str)
    weights["portfolio_weight"] = pd.to_numeric(weights.get("target_weight", weights.get("final_weight", 0.0)), errors="coerce").fillna(0.0)
    merged = security.merge(weights[["security_id", "portfolio_weight"]], on="security_id", how="left")
    merged["portfolio_weight"] = merged["portfolio_weight"].fillna(0.0)
    rows = []
    metrics = [
        "expected_total_return",
        "expected_price_return",
        "expected_dividend_return",
        "p5",
        "p50",
        "p95",
        "volatility",
        "var_5",
        "cvar_5",
        "expected_shortfall_5",
        "dividend_cut_probability",
        "drawdown_probability",
        "forecast_confidence",
    ]
    for horizon, group in merged.groupby("horizon", sort=False):
        row = {"horizon": horizon, "horizon_months": int(group["horizon_months"].iloc[0]), "security_count": len(group)}
        total_weight = group["portfolio_weight"].sum()
        for metric in metrics:
            values = pd.to_numeric(group.get(metric), errors="coerce")
            row[f"weighted_{metric}"] = float((values.fillna(0.0) * group["portfolio_weight"]).sum() / total_weight) if total_weight > 0 else pd.NA
        rows.append(row)
    return pd.DataFrame(rows).sort_values("horizon_months").reset_index(drop=True)
