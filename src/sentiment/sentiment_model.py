from __future__ import annotations

import pandas as pd

NEGATIVE_WORDS = {
    "profit warning",
    "dividend cut",
    "downgrade",
    "weak demand",
    "margin pressure",
    "regulatory probe",
    "litigation",
    "debt pressure",
    "refinancing risk",
    "governance concern",
    "fraud",
    "delay",
    "impairment",
    "warning",
    "stress",
}
POSITIVE_WORDS = {
    "growth",
    "strong demand",
    "resilient",
    "cash flow",
    "dividend increase",
    "buyback",
    "upgrade",
    "margin expansion",
    "guidance raised",
    "contract win",
}
UNCERTAINTY_WORDS = {"uncertain", "challenging", "volatile", "visibility limited", "macro headwinds", "risk remains", "under review"}
MANAGEMENT_POSITIVE = {"guidance raised", "management confidence", "contract win", "strong demand"}
DIVIDEND_NEGATIVE = {"dividend cut", "dividend suspension", "payout pressure"}
DIVIDEND_POSITIVE = {"dividend increase", "ordinary dividend confirmed"}
CASHFLOW_POSITIVE = {"cash flow", "resilient cash flow", "free cash flow"}
REGULATORY_WORDS = {"regulatory probe", "regulatory notice", "investigation"}
LITIGATION_WORDS = {"litigation", "lawsuit", "legal case"}
GOVERNANCE_WORDS = {"governance concern", "fraud", "delayed disclosures", "management resignation"}
CREDIT_WORDS = {"credit downgrade", "debt pressure", "refinancing risk", "default"}


def _phrase_hits(text: str, phrases: set[str]) -> int:
    lower = text.lower()
    return sum(lower.count(phrase) for phrase in phrases)


def _score_from_hits(hits: int, scale: int = 3) -> float:
    return float(min(100, hits / scale * 100))


def score_text(text: str) -> float:
    positive = _phrase_hits(text, POSITIVE_WORDS)
    negative = _phrase_hits(text, NEGATIVE_WORDS)
    score = positive - negative
    return max(-1.0, min(1.0, score / 4))


def score_document_text(text: str, model_name: str = "rule_based_financial_sentiment", model_version: str = "v0.1") -> dict[str, float | str]:
    """Score a single text document with deterministic financial keyword rules."""
    positive_hits = _phrase_hits(text, POSITIVE_WORDS)
    negative_hits = _phrase_hits(text, NEGATIVE_WORDS)
    uncertainty_hits = _phrase_hits(text, UNCERTAINTY_WORDS)
    positive_score = _score_from_hits(positive_hits)
    negative_score = _score_from_hits(negative_hits)
    uncertainty_score = _score_from_hits(uncertainty_hits)
    sentiment_score = (50 + positive_score * 0.35 - negative_score * 0.45 - uncertainty_score * 0.10).clip(0, 100) if hasattr(50, "clip") else max(0, min(100, 50 + positive_score * 0.35 - negative_score * 0.45 - uncertainty_score * 0.10))
    return {
        "sentiment_score": float(sentiment_score),
        "positive_score": positive_score,
        "negative_score": negative_score,
        "neutral_score": float(max(0, 100 - positive_score * 0.5 - negative_score * 0.5)),
        "uncertainty_score": uncertainty_score,
        "management_confidence_score": float(max(0, min(100, 50 + _score_from_hits(_phrase_hits(text, MANAGEMENT_POSITIVE)) * 0.4 - negative_score * 0.2))),
        "dividend_language_score": float(max(0, min(100, 50 + _score_from_hits(_phrase_hits(text, DIVIDEND_POSITIVE)) * 0.4 - _score_from_hits(_phrase_hits(text, DIVIDEND_NEGATIVE)) * 0.5))),
        "cashflow_language_score": float(max(0, min(100, 50 + _score_from_hits(_phrase_hits(text, CASHFLOW_POSITIVE)) * 0.4 - negative_score * 0.15))),
        "regulatory_risk_score": _score_from_hits(_phrase_hits(text, REGULATORY_WORDS), 2),
        "litigation_risk_score": _score_from_hits(_phrase_hits(text, LITIGATION_WORDS), 2),
        "governance_risk_score": _score_from_hits(_phrase_hits(text, GOVERNANCE_WORDS), 2),
        "credit_stress_score": _score_from_hits(_phrase_hits(text, CREDIT_WORDS), 2),
        "model_name": model_name,
        "model_version": model_version,
    }


def score_documents(documents: pd.DataFrame, mentions: pd.DataFrame, model_name: str, model_version: str) -> pd.DataFrame:
    """Score mapped document/security mentions."""
    mapped = mentions.merge(documents[["document_id", "title", "body_text"]], on="document_id", how="left")
    rows = []
    for _, row in mapped.iterrows():
        scores = score_document_text(f"{row.get('title', '')} {row.get('body_text', '')}", model_name, model_version)
        rows.append({"document_id": row["document_id"], "security_id": row["security_id"], **scores})
    return pd.DataFrame(rows)
