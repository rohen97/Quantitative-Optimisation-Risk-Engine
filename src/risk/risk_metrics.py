from __future__ import annotations

import numpy as np
import pandas as pd

from src.risk.drawdown import max_drawdown
from src.risk.expected_shortfall import expected_shortfall_proxy
from src.risk.var_cvar import var_cvar
from src.optimisation.portfolio_math import (
    calculate_effective_number_of_holdings,
    calculate_hhi,
    calculate_portfolio_cvar_proxy,
    calculate_portfolio_dividend_cut_risk,
    calculate_portfolio_dividend_yield,
    calculate_portfolio_drawdown_probability,
    calculate_portfolio_expected_return,
    calculate_portfolio_expected_shortfall_proxy,
    calculate_portfolio_var_proxy,
    calculate_portfolio_volatility,
    calculate_country_exposure,
    calculate_currency_exposure,
    calculate_region_exposure,
    calculate_sector_exposure,
)


def portfolio_return_series(prices: pd.DataFrame, portfolio: pd.DataFrame) -> pd.Series:
    returns = prices.pivot(index="date", columns="ticker", values="return").fillna(0)
    weight_col = "target_weight" if "target_weight" in portfolio else "weight"
    if weight_col not in portfolio and "market_value_usd" in portfolio:
        portfolio = portfolio.copy()
        portfolio["weight"] = portfolio["market_value_usd"] / portfolio["market_value_usd"].sum()
        weight_col = "weight"
    weights = portfolio.set_index("ticker")[weight_col].reindex(returns.columns).fillna(0)
    return returns.mul(weights, axis=1).sum(axis=1)


def _series(portfolio: pd.DataFrame, column: str, default: float) -> pd.Series:
    if column in portfolio:
        return portfolio[column].fillna(default)
    return pd.Series(default, index=portfolio.index)


def build_risk_report(prices: pd.DataFrame, portfolio: pd.DataFrame) -> pd.DataFrame:
    """Build portfolio-level risk metrics from optimised weights or current holdings."""
    if "target_weight" in portfolio and "expected_total_return_12m" in portfolio:
        weights = portfolio["target_weight"].fillna(0)
        sector = calculate_sector_exposure(portfolio)
        country = calculate_country_exposure(portfolio)
        region = calculate_region_exposure(portfolio)
        currency = calculate_currency_exposure(portfolio)
        return pd.DataFrame(
            [
                {
                    "portfolio_expected_total_return": calculate_portfolio_expected_return(portfolio),
                    "portfolio_expected_dividend_yield": calculate_portfolio_dividend_yield(portfolio),
                    "portfolio_expected_volatility": calculate_portfolio_volatility(portfolio),
                    "portfolio_var_5": calculate_portfolio_var_proxy(portfolio),
                    "portfolio_var_1": float((weights * portfolio.get("var_1_12m", portfolio["var_5_12m"] - 0.05).fillna(-0.25)).sum()),
                    "portfolio_cvar_5": calculate_portfolio_cvar_proxy(portfolio),
                    "portfolio_cvar_1": float((weights * portfolio.get("cvar_1_12m", portfolio["cvar_5_12m"] - 0.05).fillna(-0.35)).sum()),
                    "portfolio_expected_shortfall_5": calculate_portfolio_expected_shortfall_proxy(portfolio),
                    "portfolio_expected_shortfall_1": expected_shortfall_proxy(portfolio.get("expected_shortfall_1_12m", portfolio["expected_shortfall_5_12m"] - 0.05), weights),
                    "portfolio_max_drawdown_proxy": float((weights * portfolio.get("expected_max_drawdown_12m", portfolio["cvar_5_12m"]).fillna(-0.25)).sum()),
                    "portfolio_drawdown_probability": calculate_portfolio_drawdown_probability(portfolio),
                    "portfolio_dividend_cut_risk": calculate_portfolio_dividend_cut_risk(portfolio),
                    "portfolio_tail_risk_score": float((weights * _series(portfolio, "tail_risk_score", 50)).sum()),
                    "portfolio_skewness_risk_score": float((weights * _series(portfolio, "skewness_risk_score", 50)).sum()),
                    "portfolio_forecast_uncertainty_score": float((weights * _series(portfolio, "forecast_uncertainty_score", 50)).sum()),
                    "portfolio_liquidity_risk_score": float((weights * (100 - _series(portfolio, "liquidity_score", 50))).sum()),
                    "portfolio_regime_risk_score": float((weights * (100 - _series(portfolio, "regime_suitability_score", 50))).sum()),
                    "portfolio_narrative_risk_score": float((weights * _series(portfolio, "narrative_reframing_score", 50)).sum()),
                    "portfolio_alt_data_risk_score": float((weights * (100 - _series(portfolio, "sentiment_alt_data_score", 50))).sum()),
                    "HHI": calculate_hhi(weights),
                    "effective_number_of_holdings": calculate_effective_number_of_holdings(weights),
                    "max_single_name_weight": float(weights.max()) if len(weights) else 0.0,
                    "max_sector_weight": float(sector["weight"].max()) if not sector.empty else 0.0,
                    "max_country_weight": float(country["weight"].max()) if not country.empty else 0.0,
                    "max_region_weight": float(region["weight"].max()) if not region.empty else 0.0,
                    "max_currency_weight": float(currency["weight"].max()) if not currency.empty else 0.0,
                }
            ]
        )
    returns = portfolio_return_series(prices, portfolio)
    var5, cvar5 = var_cvar(returns, 0.05)
    wealth = (1 + returns).cumprod()
    ann_return = float((1 + returns.mean()) ** 252 - 1)
    ann_vol = float(returns.std() * np.sqrt(252))
    return pd.DataFrame(
        [
            {
                "annualised_return": ann_return,
                "annualised_volatility": ann_vol,
                "sharpe_ratio": ann_return / ann_vol if ann_vol else 0.0,
                "sortino_ratio": ann_return / (returns[returns < 0].std() * np.sqrt(252)) if (returns < 0).any() else 0.0,
                "calmar_ratio": ann_return / abs(max_drawdown(wealth)) if max_drawdown(wealth) else 0.0,
                "max_drawdown": max_drawdown(wealth),
                "var_5": var5,
                "cvar_5": cvar5,
            }
        ]
    )
