import pandas as pd

from src.sentiment.event_classifier import classify_event_signals, classify_events


def test_specific_events_are_classified():
    assert "profit_warning" in classify_events("profit warning due to weak demand")
    assert "dividend_cut" in classify_events("board announces dividend cut")
    assert "regulatory_probe" in classify_events("company faces regulatory probe")


def test_event_signal_schema():
    documents = pd.DataFrame(
        [
            {
                "document_id": "DOC-1",
                "title": "AAA profit warning",
                "body_text": "AAA issued a profit warning and dividend cut.",
                "publication_timestamp": pd.Timestamp("2026-01-01"),
                "source_type": "news",
            }
        ]
    )
    mentions = pd.DataFrame(
        [
            {
                "document_id": "DOC-1",
                "security_id": "SEC-1",
                "mention_confidence": 0.95,
            }
        ]
    )
    events = classify_event_signals(documents, mentions)
    assert {"event_id", "event_type", "event_direction", "event_severity"}.issubset(events.columns)
    assert "profit_warning" in set(events["event_type"])
