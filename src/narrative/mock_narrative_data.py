from __future__ import annotations

from pathlib import Path

import pandas as pd


NARRATIVE_STORIES = [
    ("earnings_release", "quality growth update", "strong cash flow dividend increase share buyback guidance raised margin expansion major contract win pricing power resilient demand"),
    ("annual_report", "ordinary annual update", "annual report released ordinary dividend confirmed board meeting update quarterly trading update"),
    ("analyst_note", "demand and margin caution", "weak demand margin pressure guidance cut cost pressure profit warning"),
    ("credit_update", "balance sheet pressure", "debt refinancing pressure credit downgrade liquidity pressure impairment distress"),
    ("regulatory_notice", "regulatory and governance update", "regulatory probe litigation risk governance concern management resignation"),
    ("dividend_announcement", "capital return update", "strong cash flow ordinary dividend confirmed dividend increase deleveraging"),
]


def generate_mock_narrative_documents(universe: pd.DataFrame, as_of_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Generate deterministic mock financial narrative documents for the active universe."""
    as_of = (as_of_date or pd.Timestamp.today()).normalize()
    rows = []
    for idx, security in universe.reset_index(drop=True).iterrows():
        for story_idx in range(5):
            document_type, title, body = NARRATIVE_STORIES[(idx + story_idx) % len(NARRATIVE_STORIES)]
            publication = as_of - pd.Timedelta(days=int((idx * 5 + story_idx * 21) % 170))
            rows.append(
                {
                    "document_id": f"NARR-{idx + 1:03d}-{story_idx + 1}",
                    "security_id": security["security_id"],
                    "ticker": security["ticker"],
                    "company_name": security["company_name"],
                    "source_type": "analyst_commentary" if document_type == "analyst_note" else "news",
                    "source_name": "Mock Narrative Wire",
                    "publication_timestamp": publication,
                    "ingestion_timestamp": as_of,
                    "language": "en",
                    "country": security["country"],
                    "title": f"{security['ticker']} {title}",
                    "body_text": f"{security['company_name']}: {body}",
                    "document_type": document_type,
                    "url_or_reference": f"mock-narrative://{security['ticker']}/{story_idx + 1}",
                }
            )
    return pd.DataFrame(rows)


def load_narrative_documents(path: str | Path) -> pd.DataFrame:
    """Load local narrative fixture documents."""
    return pd.read_csv(path, parse_dates=["publication_timestamp", "ingestion_timestamp"])
