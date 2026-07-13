from src.sentiment.event_classifier import classify_events
from src.sentiment.sentiment_model import score_text


def test_sentiment_scoring_and_event_classification():
    assert score_text("resilient cash dividend increase") > 0
    assert score_text("profit warning regulatory probe default") < 0
    assert "profit_warning" in classify_events("Company issues profit warning after regulatory probe")
