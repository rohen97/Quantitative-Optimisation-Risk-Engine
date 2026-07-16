from __future__ import annotations

import pandas as pd


FRAME_RULES = {
    "dividend_strength_frame": {"dividend increase", "strong cash flow", "share buyback"},
    "capital_return_strength_frame": {"dividend increase", "share buyback", "strong cash flow"},
    "cashflow_strength_frame": {"strong cash flow", "margin expansion", "pricing power"},
    "growth_frame": {"guidance raised", "major contract win", "resilient demand"},
    "margin_pressure_frame": {"weak demand", "margin pressure", "guidance cut"},
    "dividend_risk_frame": {"dividend cut", "weak demand", "cash flow"},
    "credit_stress_frame": {"debt refinancing pressure", "credit downgrade", "liquidity pressure"},
    "regulatory_risk_frame": {"regulatory probe"},
    "governance_risk_frame": {"governance concern", "management resignation"},
    "litigation_risk_frame": {"litigation risk"},
    "distress_frame": {"distress", "impairment", "liquidity pressure"},
    "turnaround_frame": {"turnaround", "deleveraging"},
    "neutral_update_frame": {"annual report released", "board meeting update", "quarterly trading update"},
}


def _label_frame(concepts: set[str]) -> str:
    best_label = "neutral_update_frame"
    best_overlap = 0
    for label, required in FRAME_RULES.items():
        overlap = len(concepts & required)
        if overlap > best_overlap:
            best_label = label
            best_overlap = overlap
    return best_label


def build_narrative_frames(concepts: pd.DataFrame, min_confidence: float = 60) -> pd.DataFrame:
    """Build document-level narrative frames from co-occurring concepts."""
    if concepts.empty:
        return pd.DataFrame()
    rows = []
    for (document_id, security_id), group in concepts.groupby(["document_id", "security_id"]):
        concept_set = set(group["concept_text"])
        label = _label_frame(concept_set)
        negative_share = (group["concept_polarity"] == "negative").mean()
        positive_share = (group["concept_polarity"] == "positive").mean()
        polarity = "negative" if negative_share > positive_share else "positive" if positive_share > negative_share else "neutral"
        severity = float(group["concept_severity"].max())
        confidence = float(group["concept_confidence"].mean())
        if confidence < min_confidence:
            continue
        first = group.iloc[0]
        rows.append(
            {
                "frame_id": f"FRAME-{document_id}-{security_id}",
                "document_id": document_id,
                "security_id": security_id,
                "ticker": first["ticker"],
                "publication_timestamp": first["publication_timestamp"],
                "frame_text": " ".join(sorted(concept_set)),
                "concepts_in_frame": "|".join(sorted(concept_set)),
                "frame_label": label,
                "frame_polarity": polarity,
                "frame_severity": severity,
                "frame_confidence": confidence,
                "source_type": first["source_type"],
            }
        )
    return pd.DataFrame(rows)
