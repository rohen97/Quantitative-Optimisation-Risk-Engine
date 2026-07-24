from __future__ import annotations

from dataclasses import dataclass


FORBIDDEN_CAUSAL_WORDS = ("caused", "proves", "guarantees", "guaranteed", "certain", "will outperform")


@dataclass(frozen=True)
class NarrativePoint:
    title: str
    text: str
    severity: str
    source_section: str


def format_percentage(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.{decimals}%}"


def _clean_language(text: str) -> str:
    replacements = {
        "caused": "was associated with",
        "proves": "indicates",
        "guarantees": "suggests",
        "guaranteed": "suggested",
        "certain": "reported",
        "will outperform": "has a higher model estimate than",
    }
    output = text
    for forbidden, replacement in replacements.items():
        output = output.replace(forbidden, replacement).replace(forbidden.title(), replacement.title())
    return output


def build_concentration_commentary(
    maximum_weight: float | None,
    effective_holdings: float | None,
    warning_threshold: float,
) -> NarrativePoint:
    if maximum_weight is None:
        return NarrativePoint("Concentration", "Concentration metrics are unavailable.", "warning", "portfolio")
    if maximum_weight > warning_threshold:
        text = (
            f"The largest position represents {maximum_weight:.1%} of the portfolio, "
            "which remains above the configured concentration-warning threshold."
        )
        severity = "high"
    else:
        text = f"The largest position represents {maximum_weight:.1%} of the portfolio."
        severity = "normal"
    if effective_holdings is not None:
        text += f" The effective number of holdings is {effective_holdings:.1f}."
    return NarrativePoint("Concentration", _clean_language(text), severity, "portfolio")


def build_narrative_points(summary: dict[str, object]) -> list[NarrativePoint]:
    points = [
        NarrativePoint(
            "Readiness",
            _clean_language(
                f"The report-readiness status is {summary.get('decision_readiness_status', 'unavailable')}. "
                "This is a model/reporting control status, not investment approval."
            ),
            "normal" if summary.get("decision_readiness_status") == "READY" else "warning",
            "executive_summary",
        ),
        NarrativePoint(
            "Regime",
            _clean_language(
                f"Model outputs indicate a dominant regime of {summary.get('dominant_regime', 'unavailable')} "
                f"with a Wolf Chaos Index of {summary.get('wolf_chaos_index', 'unavailable')}. "
                "Regime probabilities are estimates and should not be interpreted as certainty."
            ),
            "warning" if "chaos" in str(summary.get("dominant_regime", "")).lower() else "normal",
            "regime",
        ),
        NarrativePoint(
            "Expected Return",
            _clean_language(
                f"The 12-month expected total return estimate is {format_percentage(_as_float(summary.get('expected_total_return_12m')))}. "
                "Expected return is separate from realised return."
            ),
            "normal",
            "forecasts",
        ),
        build_concentration_commentary(
            _as_float(summary.get("maximum_single_name_weight")),
            _as_float(summary.get("effective_number_of_holdings")),
            warning_threshold=0.05,
        ),
        NarrativePoint(
            "Risk",
            _clean_language(
                f"Authoritative risk output reports VaR 5% at {format_percentage(_as_float(summary.get('portfolio_var_5')))} "
                f"and CVaR 5% at {format_percentage(_as_float(summary.get('portfolio_cvar_5')))}."
            ),
            "warning",
            "risk",
        ),
        NarrativePoint(
            "DRL Governance",
            _clean_language(
                f"The DRL status is {summary.get('drl_status', 'unavailable')}. "
                "DRL attributions are model attributions and not causal explanations."
            ),
            "normal",
            "drl",
        ),
    ]
    return points


def build_narrative(summary: dict[str, object]) -> str:
    return " ".join(point.text for point in build_narrative_points(summary))


def _as_float(value: object) -> float | None:
    try:
        if value in (None, "", "Unavailable"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
