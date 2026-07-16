from __future__ import annotations

import pandas as pd


CONCEPT_DICTIONARY: dict[str, tuple[str, str, int]] = {
    "dividend increase": ("dividend", "positive", 45),
    "ordinary dividend confirmed": ("dividend", "positive", 30),
    "dividend cut": ("dividend", "negative", 90),
    "strong cash flow": ("cash_flow", "positive", 45),
    "cash flow": ("cash_flow", "positive", 35),
    "weak demand": ("demand", "negative", 70),
    "resilient demand": ("demand", "positive", 35),
    "margin expansion": ("margin", "positive", 35),
    "margin pressure": ("margin", "negative", 70),
    "guidance raised": ("guidance", "positive", 40),
    "guidance cut": ("guidance", "negative", 75),
    "profit warning": ("profit_warning", "negative", 85),
    "share buyback": ("buyback", "positive", 35),
    "major contract win": ("order_book", "positive", 40),
    "pricing power": ("pricing_power", "positive", 35),
    "deleveraging": ("debt", "positive", 35),
    "debt refinancing pressure": ("refinancing", "negative", 85),
    "credit downgrade": ("credit_stress", "negative", 85),
    "liquidity pressure": ("liquidity", "negative", 85),
    "regulatory probe": ("regulation", "negative", 85),
    "litigation risk": ("litigation", "negative", 80),
    "governance concern": ("governance", "negative", 85),
    "management resignation": ("management", "negative", 75),
    "impairment": ("impairment", "negative", 75),
    "distress": ("distress", "negative", 90),
    "annual report released": ("growth", "neutral", 20),
    "board meeting update": ("management", "neutral", 20),
    "quarterly trading update": ("growth", "neutral", 20),
    "cost pressure": ("cost_pressure", "negative", 65),
    "turnaround": ("turnaround", "positive", 45),
    "capital raise": ("capital_raise", "negative", 60),
}


def extract_financial_concepts(documents: pd.DataFrame, min_confidence: float = 60) -> pd.DataFrame:
    """Extract financial narrative concepts using deterministic phrase rules."""
    rows = []
    for _, document in documents.iterrows():
        text = f"{document.get('title', '')} {document.get('body_text', '')}".lower()
        for phrase, (category, polarity, severity) in CONCEPT_DICTIONARY.items():
            count = text.count(phrase)
            if count == 0:
                continue
            confidence = min(100, 60 + count * 20)
            if confidence < min_confidence:
                continue
            rows.append(
                {
                    "document_id": document["document_id"],
                    "security_id": document["security_id"],
                    "ticker": document["ticker"],
                    "concept_id": f"{document['document_id']}-{phrase.replace(' ', '_')}",
                    "concept_text": phrase,
                    "concept_category": category,
                    "concept_polarity": polarity,
                    "concept_severity": severity,
                    "concept_confidence": confidence,
                    "publication_timestamp": document["publication_timestamp"],
                    "source_type": document["source_type"],
                }
            )
    return pd.DataFrame(rows)
