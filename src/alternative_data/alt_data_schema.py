TEXT_DOCUMENT_COLUMNS = [
    "document_id",
    "source_type",
    "source_name",
    "publication_timestamp",
    "ingestion_timestamp",
    "language",
    "country",
    "title",
    "body_text",
    "document_type",
    "url_or_reference",
]

ENTITY_MENTION_COLUMNS = [
    "document_id",
    "security_id",
    "ticker",
    "company_name_mentioned",
    "mention_confidence",
    "mention_count",
    "primary_subject_flag",
]

SENTIMENT_SCORE_COLUMNS = [
    "document_id",
    "security_id",
    "sentiment_score",
    "positive_score",
    "negative_score",
    "neutral_score",
    "uncertainty_score",
    "management_confidence_score",
    "dividend_language_score",
    "cashflow_language_score",
    "regulatory_risk_score",
    "litigation_risk_score",
    "governance_risk_score",
    "credit_stress_score",
    "model_name",
    "model_version",
]
