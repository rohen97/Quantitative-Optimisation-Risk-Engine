from __future__ import annotations

import pandas as pd

EVENT_KEYWORDS = {
    "dividend_cut": ["dividend cut", "cuts dividend"],
    "dividend_increase": ["dividend increase", "raises dividend"],
    "profit_warning": ["profit warning"],
    "buyback": ["buyback", "share repurchase"],
    "capital_raise": ["capital raise", "rights issue"],
    "management_change": ["ceo resigns", "management change"],
    "regulatory_probe": ["regulatory probe", "investigation"],
    "rating_downgrade": ["credit downgrade", "rating downgrade"],
    "rating_upgrade": ["credit upgrade", "rating upgrade"],
    "major_contract_win": ["contract win", "major contract"],
    "debt_refinancing": ["debt refinancing", "refinancing risk"],
    "credit_stress": ["default", "credit stress"],
    "legal_case": ["lawsuit", "legal case", "litigation"],
    "governance_red_flag": ["governance", "fraud"],
    "liquidity_stress": ["liquidity stress", "crowding"],
    "earnings_upgrade": ["guidance raised", "earnings upgrade"],
    "earnings_downgrade": ["earnings downgrade", "guidance cut"],
}
NEGATIVE_EVENTS = {
    "dividend_cut",
    "profit_warning",
    "capital_raise",
    "management_change",
    "regulatory_probe",
    "rating_downgrade",
    "debt_refinancing",
    "legal_case",
    "governance_red_flag",
    "credit_stress",
    "liquidity_stress",
    "earnings_downgrade",
}
POSITIVE_EVENTS = {"dividend_increase", "buyback", "rating_upgrade", "major_contract_win", "earnings_upgrade"}


def classify_events(text: str) -> list[str]:
    lower = text.lower()
    return [event for event, keywords in EVENT_KEYWORDS.items() if any(keyword in lower for keyword in keywords)]


def classify_event_signals(documents: pd.DataFrame, mentions: pd.DataFrame) -> pd.DataFrame:
    """Classify mapped document/security mentions into structured event signals."""
    mapped = mentions.merge(
        documents[["document_id", "body_text", "title", "publication_timestamp", "source_type"]],
        on="document_id",
        how="left",
    )
    rows = []
    for _, row in mapped.iterrows():
        text = f"{row.get('title', '')} {row.get('body_text', '')}"
        for event_type in classify_events(text):
            direction = "positive" if event_type in POSITIVE_EVENTS else "negative" if event_type in NEGATIVE_EVENTS else "neutral"
            severity = 75 if direction == "negative" else 55 if direction == "positive" else 35
            rows.append(
                {
                    "event_id": f"{row['document_id']}-{row['security_id']}-{event_type}",
                    "document_id": row["document_id"],
                    "security_id": row["security_id"],
                    "event_type": event_type,
                    "event_severity": severity,
                    "event_direction": direction,
                    "event_timestamp": row["publication_timestamp"],
                    "confidence_score": row["mention_confidence"],
                    "source_type": row["source_type"],
                }
            )
    return pd.DataFrame(rows)
