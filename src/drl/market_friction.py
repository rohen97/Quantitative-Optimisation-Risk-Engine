from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MarketFrictionResult:
    turnover: float
    traded_notional: float
    commission_cost: float
    half_spread_cost: float
    nonlinear_market_impact: float
    currency_conversion_cost: float
    transaction_tax_cost: float
    total_cost: float
    max_participation_rate: float


def _config(config: dict | None) -> dict:
    cfg = (config or {}).get("market_friction", config or {})
    return {
        "commission_bps": float(cfg.get("commission_bps", cfg.get("transaction_cost_bps", 12.0))),
        "half_spread_bps": float(cfg.get("half_spread_bps", cfg.get("slippage_bps", 5.0))),
        "impact_coefficient": float(cfg.get("impact_coefficient", 10.0)),
        "currency_conversion_bps": float(cfg.get("currency_conversion_bps", 0.0)),
        "missing_adv_usd": float(cfg.get("missing_adv_usd", 5_000_000.0)),
        "minimum_adv_usd": float(cfg.get("minimum_adv_usd", 1_000_000.0)),
        "max_participation_rate": float(cfg.get("max_participation_rate", 0.25)),
        "enable_country_transaction_tax": bool(cfg.get("enable_country_transaction_tax", False)),
        "country_transaction_tax_bps": cfg.get("country_transaction_tax_bps", {}),
    }


def _numeric_series(frame: pd.DataFrame, column: str, default: float) -> pd.Series:
    if column in frame:
        values = frame[column]
    else:
        values = pd.Series(default, index=frame.index)
    return pd.to_numeric(values, errors="coerce").fillna(default)


def calculate_market_friction_costs(
    target_weights: np.ndarray,
    pre_trade_weights: np.ndarray,
    asset_metadata: pd.DataFrame,
    portfolio_nav: float,
    config: dict | None = None,
) -> MarketFrictionResult:
    """Calculate conservative transaction costs and market frictions.

    Costs are returned as portfolio-return units, so a cost of 0.001 is 10 bps
    of NAV. Total cost is positive and should be subtracted from gross return.
    """
    cfg = _config(config)
    target = np.asarray(target_weights, dtype=float)
    previous = np.asarray(pre_trade_weights, dtype=float)
    if target.shape != previous.shape:
        raise ValueError("target_weights and pre_trade_weights must have the same shape.")
    meta = asset_metadata.reset_index(drop=True).copy()
    if len(meta) != len(target):
        raise ValueError("asset_metadata length must match weight vectors.")
    nav = max(float(portfolio_nav), 1.0)
    delta_weight = np.abs(target - previous)
    trade_notional_by_asset = delta_weight * nav
    traded_notional = float(trade_notional_by_asset.sum())
    turnover = float(delta_weight.sum())
    commission_cost = cfg["commission_bps"] / 10_000 * traded_notional / nav
    half_spread_cost = cfg["half_spread_bps"] / 10_000 * traded_notional / nav
    adv = _numeric_series(meta, "average_daily_value_usd", cfg["missing_adv_usd"]).clip(lower=cfg["minimum_adv_usd"])
    participation = trade_notional_by_asset / adv.to_numpy(dtype=float)
    participation = np.clip(participation, 0.0, cfg["max_participation_rate"])
    impact_bps = cfg["impact_coefficient"] * np.sqrt(participation)
    nonlinear_market_impact = float(((impact_bps / 10_000) * trade_notional_by_asset / nav).sum())
    if "currency" in meta:
        non_usd = ~meta["currency"].astype(str).str.upper().eq("USD")
    else:
        non_usd = pd.Series(False, index=meta.index)
    currency_conversion_cost = float(cfg["currency_conversion_bps"] / 10_000 * trade_notional_by_asset[non_usd.to_numpy()].sum() / nav)
    tax_cost = 0.0
    if cfg["enable_country_transaction_tax"] and "country" in meta:
        tax_map = {str(key): float(value) for key, value in cfg["country_transaction_tax_bps"].items()}
        tax_bps = meta["country"].astype(str).map(tax_map).fillna(0.0).to_numpy(dtype=float)
        tax_cost = float(((tax_bps / 10_000) * trade_notional_by_asset / nav).sum())
    total_cost = float(commission_cost + half_spread_cost + nonlinear_market_impact + currency_conversion_cost + tax_cost)
    return MarketFrictionResult(
        turnover=turnover,
        traded_notional=traded_notional,
        commission_cost=float(commission_cost),
        half_spread_cost=float(half_spread_cost),
        nonlinear_market_impact=nonlinear_market_impact,
        currency_conversion_cost=currency_conversion_cost,
        transaction_tax_cost=tax_cost,
        total_cost=total_cost,
        max_participation_rate=float(participation.max()) if len(participation) else 0.0,
    )
