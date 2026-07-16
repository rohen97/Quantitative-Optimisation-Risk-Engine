from __future__ import annotations

import pandas as pd


SOURCE_TYPES = [
    "news",
    "exchange_announcement",
    "analyst_commentary",
    "regulatory_filing",
    "credit_signal",
]

MOCK_STORIES = [
    (
        "dividend_announcement",
        "dividend increase and share buyback",
        "Management announced a dividend increase, resilient cash flow, margin expansion and a share buyback.",
    ),
    (
        "profit_warning",
        "profit warning and margin pressure",
        "The company issued a profit warning due to weak demand, margin pressure and visibility limited by macro headwinds.",
    ),
    (
        "regulatory_notice",
        "regulatory probe update",
        "A regulatory probe and governance concern remain under review after delayed disclosures.",
    ),
    (
        "litigation_notice",
        "litigation and debt pressure",
        "Litigation, debt pressure and refinancing risk increased after a credit downgrade.",
    ),
    (
        "earnings_release",
        "contract win and guidance raised",
        "Strong demand, a major contract win and guidance raised supported cash flow and management confidence.",
    ),
    (
        "annual_report",
        "annual report released",
        "Annual report released with ordinary dividend confirmed and board meeting update.",
    ),
]


def generate_mock_text_documents(universe: pd.DataFrame, as_of_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Generate deterministic mock text documents for active-universe securities."""
    as_of = (as_of_date or pd.Timestamp.today()).normalize()
    rows = []
    for idx, row in universe.reset_index(drop=True).iterrows():
        for story_idx, (document_type, title_suffix, body) in enumerate(MOCK_STORIES[:3]):
            story = MOCK_STORIES[(idx + story_idx) % len(MOCK_STORIES)]
            document_type, title_suffix, body = story
            publication = as_of - pd.Timedelta(days=int((idx * 3 + story_idx * 11) % 95))
            rows.append(
                {
                    "document_id": f"DOC-{idx + 1:03d}-{story_idx + 1}",
                    "source_type": SOURCE_TYPES[(idx + story_idx) % len(SOURCE_TYPES)],
                    "source_name": "Mock Financial Newswire",
                    "publication_timestamp": publication,
                    "ingestion_timestamp": as_of,
                    "language": "en",
                    "country": row["country"],
                    "title": f"{row['ticker']} {title_suffix}",
                    "body_text": f"{row['company_name']} ({row['ticker']}): {body}",
                    "document_type": document_type,
                    "url_or_reference": f"mock://{row['ticker']}/{story_idx + 1}",
                }
            )
    return pd.DataFrame(rows)
