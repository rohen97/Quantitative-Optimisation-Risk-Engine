from src.sentiment.event_classifier import classify_events
from src.sentiment.sentiment_model import score_document_text, score_text


def test_sentiment_scoring_and_event_classification():
    assert score_text("resilient cash dividend increase") > 0
    assert score_text("profit warning regulatory probe default") < 0
    assert "profit_warning" in classify_events("Company issues profit warning after regulatory probe")


def test_rule_based_sentiment_scores_are_normalised():
    positive = score_document_text("strong demand cash flow dividend increase contract win")
    negative = score_document_text("profit warning dividend cut regulatory probe litigation debt pressure")
    assert 0 <= positive["positive_score"] <= 100
    assert 0 <= negative["negative_score"] <= 100
    assert positive["positive_score"] > positive["negative_score"]
    assert negative["negative_score"] > negative["positive_score"]
