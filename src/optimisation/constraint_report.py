from __future__ import annotations

import pandas as pd

from src.optimisation.portfolio_math import (
    calculate_country_exposure,
    calculate_currency_exposure,
    calculate_effective_number_of_holdings,
    calculate_hhi,
    calculate_portfolio_cvar_proxy,
    calculate_portfolio_dividend_cut_risk,
    calculate_portfolio_dividend_yield,
    calculate_portfolio_drawdown_probability,
    calculate_portfolio_expected_shortfall_proxy,
    calculate_portfolio_var_proxy,
    calculate_portfolio_volatility,
    calculate_region_exposure,
    calculate_sector_exposure,
    calculate_turnover,
)


def _row(name: str, ctype: str, limit, actual, breach: bool, affected: str = "", commentary: str = "") -> dict:
    return {
        "constraint_name": name,
        "constraint_type": ctype,
        "limit": limit,
        "actual_value": actual,
        "breach_flag": bool(breach),
        "severity": "High" if breach else "OK",
        "affected_stocks": affected,
        "commentary": commentary,
    }


def build_constraint_report(portfolio: pd.DataFrame, constraints: dict | None = None) -> pd.DataFrame:
    """Build hard/soft constraint report for an optimised portfolio."""
    limits = constraints or {}
    weights = portfolio["target_weight"].fillna(0)
    rows = []
    invested = portfolio.loc[weights.gt(1e-12)].copy()
    total_weight = float(weights.sum())
    rows.append(
        _row(
            "fully_invested",
            "hard",
            1.0,
            total_weight,
            not abs(total_weight - 1.0) <= 1e-8,
        )
    )
    recommendation = invested.get("final_recommendation", pd.Series("", index=invested.index)).fillna("").astype(str)
    prohibited = recommendation.str.contains("avoid|exclude", case=False, regex=True)
    rows.append(
        _row(
            "recommendation_eligibility",
            "hard",
            "no Avoid or Exclude",
            int(prohibited.sum()),
            bool(prohibited.any()),
            ", ".join(invested.loc[prohibited, "ticker"].astype(str)),
        )
    )
    if "issuer_id" in invested:
        duplicated_issuer = invested["issuer_id"].fillna("").astype(str).duplicated(keep=False)
        rows.append(
            _row(
                "unique_issuer",
                "hard",
                "one listing per issuer",
                int(duplicated_issuer.sum()),
                bool(duplicated_issuer.any()),
                ", ".join(invested.loc[duplicated_issuer, "ticker"].astype(str)),
            )
        )
    price_excluded = invested.get(
        "price_data_exclusion_flag",
        pd.Series(False, index=invested.index),
    ).fillna(False).astype(bool)
    rows.append(
        _row(
            "price_data_quality",
            "hard",
            "no quarantined price histories",
            int(price_excluded.sum()),
            bool(price_excluded.any()),
            ", ".join(invested.loc[price_excluded, "ticker"].astype(str)),
        )
    )
    max_weight = float(limits.get("max_single_name_weight", 0.05))
    rows.append(_row("single_name_concentration", "hard", max_weight, float(weights.max()), weights.max() > max_weight + 1e-9))
    for name, exposure_fn, key in [
        ("sector_concentration", calculate_sector_exposure, "max_sector_weight"),
        ("country_concentration", calculate_country_exposure, "max_country_weight"),
        ("region_concentration", calculate_region_exposure, "max_region_weight"),
        ("currency_concentration", calculate_currency_exposure, "max_currency_weight"),
    ]:
        limit = float(limits.get(key, 1.0))
        exposure = exposure_fn(portfolio)
        actual = float(exposure["weight"].max()) if not exposure.empty else 0.0
        rows.append(_row(name, "hard", limit, actual, actual > limit + 1e-9, ", ".join(exposure.loc[exposure["weight"] > limit, exposure.columns[0]].astype(str))))
    liquidity_breaches = portfolio.loc[(portfolio["target_weight"] > 0) & (portfolio["liquidity_score"] < limits.get("minimum_liquidity_score", 40)), "ticker"].astype(str)
    rows.append(_row("liquidity", "hard", limits.get("minimum_liquidity_score", 40), int(len(liquidity_breaches)), len(liquidity_breaches) > 0, ", ".join(liquidity_breaches)))
    rows.extend(
        [
            _row("turnover", "soft", limits.get("maximum_turnover", 0.35), calculate_turnover(portfolio), calculate_turnover(portfolio) > limits.get("maximum_turnover", 0.35)),
            _row(
                "portfolio_dividend_yield",
                "soft",
                limits.get("minimum_portfolio_dividend_yield", 0.03),
                calculate_portfolio_dividend_yield(portfolio),
                calculate_portfolio_dividend_yield(portfolio) < limits.get("minimum_portfolio_dividend_yield", 0.03),
            ),
            _row("portfolio_volatility", "soft", limits.get("maximum_portfolio_volatility", 0.20), calculate_portfolio_volatility(portfolio), calculate_portfolio_volatility(portfolio) > limits.get("maximum_portfolio_volatility", 0.20)),
            _row("portfolio_var_5", "soft", limits.get("maximum_portfolio_var_5", -0.15), calculate_portfolio_var_proxy(portfolio), calculate_portfolio_var_proxy(portfolio) < limits.get("maximum_portfolio_var_5", -0.15)),
            _row("portfolio_cvar_5", "soft", limits.get("maximum_portfolio_cvar_5", -0.25), calculate_portfolio_cvar_proxy(portfolio), calculate_portfolio_cvar_proxy(portfolio) < limits.get("maximum_portfolio_cvar_5", -0.25)),
            _row("portfolio_expected_shortfall_5", "soft", limits.get("maximum_portfolio_expected_shortfall_5", -0.25), calculate_portfolio_expected_shortfall_proxy(portfolio), calculate_portfolio_expected_shortfall_proxy(portfolio) < limits.get("maximum_portfolio_expected_shortfall_5", -0.25)),
            _row("dividend_cut_risk", "soft", limits.get("maximum_dividend_cut_probability", 0.35), calculate_portfolio_dividend_cut_risk(portfolio), calculate_portfolio_dividend_cut_risk(portfolio) > limits.get("maximum_dividend_cut_probability", 0.35)),
            _row("drawdown_risk", "soft", limits.get("maximum_large_drawdown_probability", 0.35), calculate_portfolio_drawdown_probability(portfolio), calculate_portfolio_drawdown_probability(portfolio) > limits.get("maximum_large_drawdown_probability", 0.35)),
            _row("HHI", "soft", limits.get("maximum_hhi", 0.15), calculate_hhi(weights), calculate_hhi(weights) > limits.get("maximum_hhi", 0.15)),
            _row("effective_holdings", "soft", limits.get("minimum_effective_number_of_holdings", 15), calculate_effective_number_of_holdings(weights), calculate_effective_number_of_holdings(weights) < limits.get("minimum_effective_number_of_holdings", 15)),
        ]
    )
    for flag, name in [
        ("regime_review_required_flag", "regime_risk"),
        ("reframing_review_required_flag", "narrative_risk"),
        ("alt_data_review_required_flag", "alt_data_risk"),
    ]:
        affected = portfolio.loc[(portfolio["target_weight"] > 0) & portfolio[flag].fillna(False).astype(bool), "ticker"].astype(str)
        rows.append(_row(name, "soft", "no reviewed names preferred", int(len(affected)), len(affected) > 0, ", ".join(affected)))
    return pd.DataFrame(rows)
