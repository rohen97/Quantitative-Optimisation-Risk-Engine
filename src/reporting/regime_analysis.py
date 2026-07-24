from __future__ import annotations

import pandas as pd

from src.reporting.models import ICDataBundle
from src.reporting.portfolio_resolver import ResolvedPortfolio


def build_regime_summary(bundle: ICDataBundle) -> dict[str, object]:
    regime = bundle.frames.get("regime_summary", pd.DataFrame())
    return regime.iloc[0].to_dict() if not regime.empty else {}


def build_ic_regime_summary(bundle: ICDataBundle, resolved: ResolvedPortfolio) -> pd.DataFrame:
    summary = bundle.frames.get("regime_summary", pd.DataFrame()).copy()
    factor = bundle.frames.get("factor_regime_probabilities", pd.DataFrame()).copy()
    chaos = bundle.frames.get("chaos_regime_probabilities", pd.DataFrame()).copy()
    suitability = bundle.frames.get("regime_suitability", pd.DataFrame()).copy()
    drivers = bundle.frames.get("regime_informational_drivers", pd.DataFrame()).copy()
    transitions = bundle.frames.get("regime_transition_matrix", pd.DataFrame()).copy()
    row: dict[str, object] = {}
    if not summary.empty:
        row.update(summary.iloc[-1].to_dict())
    probability_candidates = []
    for source_name, frame in (("factor", factor), ("chaos", chaos)):
        if not frame.empty:
            numeric = frame.select_dtypes(include="number")
            for column in numeric.columns:
                probability_candidates.append((f"{source_name}:{column}", float(numeric[column].iloc[-1])))
                row[f"{source_name}_{column}"] = float(numeric[column].iloc[-1])
    probability_candidates.sort(key=lambda item: item[1], reverse=True)
    row["dominant_regime"] = row.get("dominant_regime", probability_candidates[0][0] if probability_candidates else "Unavailable")
    row["second_most_likely_regime"] = probability_candidates[1][0] if len(probability_candidates) > 1 else "Unavailable"
    row["regime_probability_is_certain"] = False
    row["change_from_previous_decision_date"] = "Unavailable" if len(summary) < 2 else "Changed" if summary.iloc[-1].to_dict() != summary.iloc[-2].to_dict() else "No material change"
    row["regime_sensitive_holdings"] = ", ".join(suitability.sort_values(suitability.select_dtypes(include="number").columns[-1], ascending=True).head(5).get("ticker", pd.Series(dtype=str)).astype(str)) if not suitability.empty and not suitability.select_dtypes(include="number").empty else ""
    row["sectors_helped_by_regime"] = ""
    row["sectors_hurt_by_regime"] = ""
    row["informational_drivers_available"] = not drivers.empty
    row["transition_probabilities_available"] = not transitions.empty
    row["portfolio_regime_suitability"] = float(pd.to_numeric(resolved.portfolio.get("regime_suitability_score", pd.Series(dtype=float)), errors="coerce").mean()) if "regime_suitability_score" in resolved.portfolio else pd.NA
    return pd.DataFrame([row])
