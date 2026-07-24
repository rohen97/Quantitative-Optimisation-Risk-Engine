from __future__ import annotations

import pandas as pd

from src.reporting.models import ICDataBundle


def build_hedge_summary(bundle: ICDataBundle) -> dict[str, pd.DataFrame]:
    return {
        "hedges": bundle.frames.get("hedges", pd.DataFrame()),
        "defensive_substitutions": bundle.frames.get("defensive_substitutions", pd.DataFrame()),
    }


def build_hedge_and_substitution_outputs(bundle: ICDataBundle) -> dict[str, pd.DataFrame]:
    hedges = bundle.frames.get("hedges", pd.DataFrame()).copy()
    substitutions = bundle.frames.get("defensive_substitutions", pd.DataFrame()).copy()
    if not hedges.empty:
        for column in (
            "risk_exposure",
            "scenario",
            "hedge_type",
            "suggested_basket_or_instrument",
            "target_weight_or_notional",
            "expected_effectiveness",
            "cost_tradeoff",
            "residual_risk",
            "priority",
            "implementation_complexity",
        ):
            if column not in hedges:
                hedges[column] = hedges.get(column.replace("_or_", "_"), "")
        hedges["execution_label"] = "Optional institutional risk-management concept requiring execution review."
    if not substitutions.empty:
        for column in (
            "risky_holding",
            "suggested_substitute",
            "reason",
            "expected_risk_reduction",
            "dividend_yield_change",
            "expected_return_change",
            "regime_suitability_change",
        ):
            if column not in substitutions:
                substitutions[column] = substitutions.get(column.replace("risky_holding", "ticker"), "")
    return {
        "hedge_concepts": hedges,
        "defensive_substitution_summary": substitutions,
    }
