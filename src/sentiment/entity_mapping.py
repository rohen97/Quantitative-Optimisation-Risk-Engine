from __future__ import annotations

import pandas as pd


def _count_mentions(text: str, ticker: str, company_name: str) -> int:
    lower = text.lower()
    return lower.count(ticker.lower()) + lower.count(company_name.lower())


def map_entities(documents: pd.DataFrame, universe: pd.DataFrame, min_confidence: float = 0.70) -> pd.DataFrame:
    """Map documents to securities using ticker/company mentions with a conservative threshold."""
    rows = []
    by_security_id = universe.drop_duplicates("security_id").copy()
    by_security_id.index = by_security_id["security_id"].astype(str)
    by_ticker = universe.drop_duplicates("ticker").copy()
    by_ticker.index = by_ticker["ticker"].astype(str).str.casefold()
    for _, document in documents.iterrows():
        text = f"{document.get('title', '')} {document.get('body_text', '')}"
        candidates = pd.DataFrame()
        security_id = document.get("security_id")
        ticker = document.get("ticker")
        if pd.notna(security_id) and str(security_id) in by_security_id.index:
            candidates = by_security_id.loc[[str(security_id)]]
        elif pd.notna(ticker) and str(ticker).casefold() in by_ticker.index:
            candidates = by_ticker.loc[[str(ticker).casefold()]]
        else:
            candidates = universe
        for _, security in candidates.iterrows():
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
