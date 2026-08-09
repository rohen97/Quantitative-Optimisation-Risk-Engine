from __future__ import annotations

import pandas as pd


SUBSTITUTION_COLUMNS = [
    "risky_security_id",
    "risky_ticker",
    "risky_company_name",
    "risk_reason",
    "suggested_security_id",
    "suggested_ticker",
    "suggested_company_name",
    "substitution_type",
    "expected_risk_reduction",
    "dividend_yield_change",
    "expected_return_change",
    "regime_suitability_change",
    "liquidity_change",
    "substitution_commentary",
]


def build_defensive_substitution_recommendations(portfolio: pd.DataFrame, candidates: pd.DataFrame | None = None) -> pd.DataFrame:
    """Suggest safer equity replacements for high-risk holdings."""
    data = portfolio.copy()
    universe = candidates.copy() if candidates is not None and not candidates.empty else data.copy()
    high_risk = data[
        (data.get("target_weight", pd.Series(0, index=data.index)).fillna(0) > 0)
        & (
            (data.get("cvar_5_12m", pd.Series(0, index=data.index)).fillna(0) < -0.25)
            | (data.get("dividend_cut_probability", pd.Series(0, index=data.index)).fillna(0) > 0.35)
            | (data.get("large_drawdown_probability_12m", pd.Series(0, index=data.index)).fillna(0) > 0.35)
            | (data.get("tail_risk_score", pd.Series(0, index=data.index)).fillna(0) > 70)
        )
    ]
    rows = []
    for _, risky in high_risk.iterrows():
        safer = universe[
            (universe["ticker"] != risky["ticker"])
            & (universe["dividend_safety_score"].fillna(50) >= risky.get("dividend_safety_score", 50))
            & (universe["dividend_cut_probability"].fillna(0.10) <= risky.get("dividend_cut_probability", 0.10))
            & (universe["cvar_5_12m"].fillna(-0.30) >= risky.get("cvar_5_12m", -0.30))
        ].copy()
        if safer.empty:
            rows.append(
                {
                    "risky_security_id": risky.get("security_id", ""),
                    "risky_ticker": risky.get("ticker", ""),
                    "risky_company_name": risky.get("company_name", ""),
                    "risk_reason": "No suitable equity substitute found; consider cash allocation.",
                    "suggested_security_id": "CASH",
                    "suggested_ticker": "CASH",
                    "suggested_company_name": "Cash allocation",
                    "substitution_type": "cash_allocation",
                    "expected_risk_reduction": 1.0,
                    "dividend_yield_change": -risky.get("dividend_yield", 0),
                    "expected_return_change": -risky.get("expected_total_return_12m", 0),
                    "regime_suitability_change": 0,
                    "liquidity_change": 0,
                    "substitution_commentary": "Cash allocation is a risk-control fallback in mock mode.",
                }
            )
            continue
        safer["sub_score"] = (
            safer["dividend_safety_score"].fillna(50)
            + safer["regime_suitability_score"].fillna(50)
            + safer["liquidity_score"].fillna(50)
            - 100 * safer["dividend_cut_probability"].fillna(0.10)
            + 100 * safer["cvar_5_12m"].fillna(-0.30)
        )
        pick = safer.sort_values("sub_score", ascending=False).iloc[0]
        rows.append(
            {
                "risky_security_id": risky.get("security_id", ""),
                "risky_ticker": risky.get("ticker", ""),
                "risky_company_name": risky.get("company_name", ""),
                "risk_reason": "Elevated CVaR, drawdown, dividend or tail risk.",
                "suggested_security_id": pick.get("security_id", ""),
                "suggested_ticker": pick.get("ticker", ""),
                "suggested_company_name": pick.get("company_name", ""),
                "substitution_type": "same_sector_safer_name" if pick.get("sector") == risky.get("sector") else "same_region_defensive_name",
                "expected_risk_reduction": float(abs(risky.get("cvar_5_12m", -0.30)) - abs(pick.get("cvar_5_12m", -0.30))),
                "dividend_yield_change": float(pick.get("dividend_yield", 0) - risky.get("dividend_yield", 0)),
                "expected_return_change": float(pick.get("expected_total_return_12m", 0) - risky.get("expected_total_return_12m", 0)),
                "regime_suitability_change": float(pick.get("regime_suitability_score", 50) - risky.get("regime_suitability_score", 50)),
                "liquidity_change": float(pick.get("liquidity_score", 50) - risky.get("liquidity_score", 50)),
                "substitution_commentary": "Suggested replacement has better downside, dividend or regime characteristics.",
            }
        )
    return pd.DataFrame(rows, columns=SUBSTITUTION_COLUMNS)
