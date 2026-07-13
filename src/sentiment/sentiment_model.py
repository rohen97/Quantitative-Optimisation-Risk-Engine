from __future__ import annotations

NEGATIVE_WORDS = {"cut", "probe", "fraud", "warning", "default", "lawsuit", "downgrade", "stress"}
POSITIVE_WORDS = {"increase", "buyback", "beat", "upgrade", "resilient", "cash", "dividend"}


def score_text(text: str) -> float:
    tokens = {token.strip(".,:;!?").lower() for token in text.split()}
    score = len(tokens & POSITIVE_WORDS) - len(tokens & NEGATIVE_WORDS)
    return max(-1.0, min(1.0, score / 4))
