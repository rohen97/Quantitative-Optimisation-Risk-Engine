from __future__ import annotations

from collections.abc import Mapping
import math

import numpy as np
import pandas as pd


MACRO_FEATURE_SERIES = {
    "macro_policy_rate": ("DFF", "FEDFUNDS"),
    "macro_yield_curve_slope": ("T10Y2Y",),
    "macro_credit_spread": ("BAMLH0A0HYM2", "BAA10YM"),
    "macro_market_volatility": ("VIXCLS",),
}


def splice_benchmark_prehistory(
    bars: pd.DataFrame,
    *,
    primary_symbol: str,
    fallback_symbol: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Rebase a fallback index before the primary starts without inventing returns."""
    data = bars.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    primary = data.loc[data["symbol"].astype(str).eq(primary_symbol)].sort_values("date")
    fallback = data.loc[data["symbol"].astype(str).eq(fallback_symbol)].sort_values("date")
    if primary.empty or fallback.empty:
        return data, {
            "applied": False,
            "primary_symbol": primary_symbol,
            "fallback_symbol": fallback_symbol,
        }
    primary_start = pd.Timestamp(primary["date"].min())
    prehistory = fallback.loc[fallback["date"].lt(primary_start)].copy()
    if prehistory.empty:
        return data, {
            "applied": False,
            "primary_symbol": primary_symbol,
            "fallback_symbol": fallback_symbol,
        }
    primary_level = float(pd.to_numeric(primary.iloc[0]["adjusted_close"], errors="coerce"))
    fallback_level = float(pd.to_numeric(prehistory.iloc[-1]["adjusted_close"], errors="coerce"))
    if not np.isfinite(primary_level) or not np.isfinite(fallback_level) or fallback_level <= 0:
        raise ValueError("Benchmark prehistory splice requires positive finite boundary levels.")
    prehistory["adjusted_close"] = (
        pd.to_numeric(prehistory["adjusted_close"], errors="coerce")
        * primary_level
        / fallback_level
    )
    prehistory["source_symbol"] = fallback_symbol
    prehistory["symbol"] = primary_symbol
    primary_rows = data.loc[data["symbol"].astype(str).eq(primary_symbol)].copy()
    primary_rows["source_symbol"] = primary_symbol
    other = data.loc[
        ~data["symbol"].astype(str).isin({primary_symbol, fallback_symbol})
    ].copy()
    if "source_symbol" not in other:
        other["source_symbol"] = other["symbol"]
    combined = pd.concat([other, prehistory, primary_rows], ignore_index=True, sort=False)
    combined = combined.sort_values(["symbol", "date"]).drop_duplicates(
        ["symbol", "date"], keep="last"
    )
    return combined.reset_index(drop=True), {
        "applied": True,
        "primary_symbol": primary_symbol,
        "fallback_symbol": fallback_symbol,
        "fallback_start": prehistory["date"].min(),
        "primary_start": primary_start,
        "boundary_method": "fallback_levels_rebased_to_first_primary_level",
    }


def _tail_mean(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return 0.0
    count = max(1, int(math.ceil(len(clean) * 0.05)))
    return float(clean.nsmallest(count).mean() * np.sqrt(12.0))


def _bounded_inverse_volatility(values: pd.Series, cap: float = 0.40) -> pd.Series:
    volatility = pd.to_numeric(values, errors="coerce").replace(0.0, np.nan)
    inverse = 1.0 / volatility
    if not np.isfinite(inverse).any():
        inverse = pd.Series(1.0, index=values.index)
    inverse = inverse.replace([np.inf, -np.inf], np.nan).fillna(inverse.median()).clip(lower=0.0)
    weights = inverse / max(float(inverse.sum()), 1.0e-12)
    for _ in range(10):
        excess = weights.clip(lower=cap) - cap
        excess_total = float(excess.sum())
        weights = weights.clip(upper=cap)
        eligible = weights.lt(cap - 1.0e-12)
        if excess_total <= 1.0e-12 or not eligible.any():
            break
        weights.loc[eligible] += excess_total * weights.loc[eligible] / max(
            float(weights.loc[eligible].sum()), 1.0e-12
        )
    return weights / max(float(weights.sum()), 1.0e-12)


def _fx_factor(
    fred_wide: pd.DataFrame,
    currency: str,
    definition: Mapping[str, object] | None,
) -> pd.Series:
    if currency.upper() == "USD":
        return pd.Series(1.0, index=fred_wide.index)
    if not definition:
        return pd.Series(np.nan, index=fred_wide.index)
    primary = fred_wide.get(str(definition["primary"]), pd.Series(np.nan, index=fred_wide.index))
    values = pd.to_numeric(primary, errors="coerce")
    pre_euro = definition.get("pre_euro")
    if pre_euro:
        earlier = pd.to_numeric(
            fred_wide.get(str(pre_euro), pd.Series(np.nan, index=fred_wide.index)),
            errors="coerce",
        )
        values = values.combine_first(earlier)
    values = values.ffill(limit=10)
    direction = str(definition.get("direction", "usd_per_unit"))
    if direction == "units_per_usd":
        values = 1.0 / values.replace(0.0, np.nan)
    elif direction != "usd_per_unit":
        raise ValueError(f"Unsupported FX direction for {currency}: {direction}")
    return values * float(definition.get("unit_scale", 1.0))


def convert_regional_benchmarks_to_usd(
    bars: pd.DataFrame,
    fred: pd.DataFrame,
    regional_benchmarks: Mapping[str, Mapping[str, object]],
    fx_definitions: Mapping[str, Mapping[str, object]],
) -> pd.DataFrame:
    required = {"date", "symbol", "adjusted_close"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"Benchmark bars are missing columns: {sorted(missing)}")
    data = bars.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    data["adjusted_close"] = pd.to_numeric(data["adjusted_close"], errors="coerce")
    data["volume"] = pd.to_numeric(data.get("volume", 0.0), errors="coerce").fillna(0.0)
    fred_data = fred.copy()
    if fred_data.empty:
        fred_wide = pd.DataFrame(index=pd.DatetimeIndex(sorted(data["date"].unique())))
    else:
        fred_data["date"] = pd.to_datetime(fred_data["date"]).dt.normalize()
        fred_data["value"] = pd.to_numeric(fred_data["value"], errors="coerce")
        fred_wide = fred_data.pivot_table(
            index="date", columns="series_id", values="value", aggfunc="last"
        )
        fred_wide = fred_wide.reindex(
            pd.date_range(data["date"].min(), data["date"].max(), freq="D")
        ).ffill(limit=10)

    frames: list[pd.DataFrame] = []
    for region, definition in regional_benchmarks.items():
        symbol = str(definition["symbol"])
        currency = str(definition.get("currency", "USD")).upper()
        rows = data.loc[data["symbol"].astype(str).eq(symbol)].copy()
        if rows.empty:
            continue
        factors = _fx_factor(fred_wide, currency, fx_definitions.get(currency))
        rows["fx_to_usd"] = rows["date"].map(factors)
        rows["adjusted_close_usd"] = rows["adjusted_close"] * rows["fx_to_usd"]
        rows["dollar_volume_usd"] = rows["volume"] * rows["adjusted_close_usd"]
        rows["region"] = str(region)
        rows["currency"] = currency
        frames.append(rows)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["region", "date"])


def point_in_time_macro_features(
    vintages: pd.DataFrame,
    decision_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    output = pd.DataFrame({"date": pd.DatetimeIndex(decision_dates).normalize()})
    if vintages.empty:
        for feature in MACRO_FEATURE_SERIES:
            output[feature] = 0.0
        output["macro_evidence_available"] = False
        return output
    data = vintages.copy()
    data["observation_date"] = pd.to_datetime(data["observation_date"]).dt.normalize()
    data["available_from"] = pd.to_datetime(data["available_from"], utc=True).dt.tz_localize(None)
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data = data.dropna(subset=["series_id", "observation_date", "available_from", "value"])

    for feature, candidates in MACRO_FEATURE_SERIES.items():
        series = next((value for value in candidates if data["series_id"].astype(str).eq(value).any()), None)
        values: list[float] = []
        subset = data.loc[data["series_id"].astype(str).eq(series)].copy() if series else pd.DataFrame()
        if subset.empty:
            output[feature] = 0.0
            continue
        for decision_date in output["date"]:
            eligible = subset.loc[
                subset["available_from"].le(decision_date + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1))
                & subset["observation_date"].le(decision_date)
            ]
            if eligible.empty:
                values.append(np.nan)
                continue
            latest_vintages = (
                eligible.sort_values(["observation_date", "available_from"])
                .drop_duplicates("observation_date", keep="last")
                .sort_values("observation_date")
            )
            values.append(float(latest_vintages.iloc[-1]["value"]))
        output[feature] = pd.Series(values, dtype=float).ffill().fillna(0.0)
    output["macro_evidence_available"] = output[list(MACRO_FEATURE_SERIES)].ne(0.0).any(axis=1)
    return output


def build_long_history_regional_panel(
    usd_bars: pd.DataFrame,
    macro_vintages: pd.DataFrame,
    *,
    start_date: str | pd.Timestamp = "1997-01-31",
    end_date: str | pd.Timestamp | None = None,
    region_cap: float = 0.40,
) -> pd.DataFrame:
    if usd_bars.empty:
        return pd.DataFrame()
    start = pd.Timestamp(start_date) + pd.offsets.MonthEnd(0)
    end = (
        pd.Timestamp(end_date) + pd.offsets.MonthEnd(0)
        if end_date is not None
        else pd.Timestamp(usd_bars["date"].max()) + pd.offsets.MonthEnd(0)
    )
    region_frames: list[pd.DataFrame] = []
    for region, frame in usd_bars.groupby("region", sort=False):
        daily = frame.sort_values("date").set_index(pd.to_datetime(frame["date"]))
        monthly = pd.DataFrame(
            {
                "price": pd.to_numeric(daily["adjusted_close_usd"], errors="coerce").resample("ME").last(),
                "dollar_volume": pd.to_numeric(daily["dollar_volume_usd"], errors="coerce").resample("ME").median(),
            }
        )
        monthly["monthly_return"] = monthly["price"].pct_change(fill_method=None)
        monthly["momentum_6m"] = monthly["price"].pct_change(6, fill_method=None)
        monthly["momentum_12m"] = monthly["price"].pct_change(12, fill_method=None)
        monthly["realized_volatility_3m"] = monthly["monthly_return"].rolling(3, min_periods=3).std() * np.sqrt(12.0)
        monthly["expected_volatility_12m"] = monthly["monthly_return"].rolling(12, min_periods=6).std() * np.sqrt(12.0)
        monthly["downside_volatility_12m"] = (
            monthly["monthly_return"].clip(upper=0.0).rolling(12, min_periods=6).std() * np.sqrt(12.0)
        )
        monthly["cvar_5_12m"] = monthly["monthly_return"].rolling(36, min_periods=12).apply(_tail_mean)
        monthly["forward_return"] = monthly["monthly_return"].shift(-1)
        monthly["sleeve"] = str(region)
        monthly["benchmark_symbol"] = str(frame["symbol"].iloc[0])
        monthly.index.name = "date"
        region_frames.append(monthly.reset_index())
    panel = pd.concat(region_frames, ignore_index=True)
    complete_regions = int(panel["sleeve"].nunique())
    counts = panel.groupby("date")["sleeve"].transform("nunique")
    panel = panel.loc[counts.eq(complete_regions) & panel["date"].between(start, end)].copy()
    panel["benchmark_relative_momentum_12m"] = panel["momentum_12m"] - panel.groupby("date")[
        "momentum_12m"
    ].transform("mean")
    risk_adjusted = panel["momentum_12m"] / panel["expected_volatility_12m"].replace(0.0, np.nan)
    panel["final_recommendation_score"] = risk_adjusted.groupby(panel["date"]).rank(pct=True) * 100.0
    momentum_rank = panel["benchmark_relative_momentum_12m"].groupby(panel["date"]).rank(pct=True)
    volatility_rank = panel["expected_volatility_12m"].groupby(panel["date"]).rank(pct=True)
    panel["regime_suitability_score"] = (0.60 * momentum_rank + 0.40 * (1.0 - volatility_rank)) * 100.0
    positive_liquidity = panel["dollar_volume"].where(panel["dollar_volume"].gt(0.0))
    panel["liquidity_score"] = (
        np.log1p(positive_liquidity)
        .groupby(panel["date"])
        .rank(pct=True)
        .mul(100.0)
        .fillna(50.0)
    )
    panel["expected_total_return_12m"] = panel["momentum_12m"]
    panel["dividend_safety_score"] = 50.0
    panel["valid_outcome_weight"] = panel["forward_return"].notna().astype(float)
    panel["holding_count"] = 1
    panel["baseline_weight"] = panel.groupby("date", group_keys=False)[
        "expected_volatility_12m"
    ].apply(lambda values: _bounded_inverse_volatility(values, region_cap))

    macro = point_in_time_macro_features(
        macro_vintages,
        pd.DatetimeIndex(sorted(panel["date"].unique())),
    )
    panel = panel.merge(macro, on="date", how="left")
    panel["panel_source"] = "public_regional_benchmark_proxy"
    panel["evidence_tier"] = "reconstructed_pit_market_macro"
    panel["stock_signal_evidence_available"] = False
    numeric_defaults = {
        "expected_total_return_12m": 0.0,
        "expected_volatility_12m": 0.20,
        "cvar_5_12m": -0.25,
        "final_recommendation_score": 50.0,
        "momentum_6m": 0.0,
        "dividend_safety_score": 50.0,
        "liquidity_score": 50.0,
        "regime_suitability_score": 50.0,
        "benchmark_relative_momentum_12m": 0.0,
        "realized_volatility_3m": 0.20,
        "downside_volatility_12m": 0.15,
        **{feature: 0.0 for feature in MACRO_FEATURE_SERIES},
    }
    for column, default in numeric_defaults.items():
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(default)
    panel = panel.loc[panel["forward_return"].notna()].copy()
    return panel.sort_values(["date", "sleeve"]).reset_index(drop=True)
