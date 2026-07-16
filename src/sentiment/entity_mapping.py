from __future__ import annotations

import pandas as pd


def _count_mentions(text: str, ticker: str, company_name: str) -> int:
    lower = text.lower()
    return lower.count(ticker.lower()) + lower.count(company_name.lower())


def map_entities(documents: pd.DataFrame, universe: pd.DataFrame, min_confidence: float = 0.70) -> pd.DataFrame:
    """Map documents to securities using ticker/company mentions with a conservative threshold."""
    rows = []
    for _, document in documents.iterrows():
        text = f"{document.get('title', '')} {document.get('body_text', '')}"
        for _, security in universe.iterrows():
            count = _count_mentions(text, security["ticker"], security["company_name"])
            if count <= 0:
                continue
            confidence = min(1.0, 0.65 + 0.15 * count)
            if confidence < min_confidence:
                continue
            rows.append(
                {
                    "document_id": document["document_id"],
                    "security_id": security["security_id"],
                    "ticker": security["ticker"],
                    "company_name_mentioned": security["company_name"],
                    "mention_confidence": confidence,
                    "mention_count": count,
                    "primary_subject_flag": confidence >= 0.80,
                }
            )
    return pd.DataFrame(rows)
