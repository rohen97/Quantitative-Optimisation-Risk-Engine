from __future__ import annotations

EVENT_KEYWORDS = {
    "dividend_cut": ["dividend cut", "cuts dividend"],
    "dividend_increase": ["dividend increase", "raises dividend"],
    "profit_warning": ["profit warning"],
    "buyback": ["buyback", "share repurchase"],
    "capital_raise": ["capital raise", "rights issue"],
    "management_change": ["ceo resigns", "management change"],
    "regulatory_probe": ["regulatory probe", "investigation"],
    "credit_stress": ["default", "credit stress"],
    "legal_case": ["lawsuit", "legal case"],
    "governance_red_flag": ["governance", "fraud"],
}


def classify_events(text: str) -> list[str]:
    lower = text.lower()
    return [event for event, keywords in EVENT_KEYWORDS.items() if any(keyword in lower for keyword in keywords)]
