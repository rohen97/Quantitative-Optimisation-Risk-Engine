from __future__ import annotations

import numpy as np
import pandas as pd

from src.narrative.embedding_engine import embed_texts


ANCHORS = {
    "positive_quality_anchor": "strong cash flow resilient earnings dividend growth balance sheet strength pricing power",
    "distress_anchor": "profit warning weak demand liquidity pressure impairment distress debt restructuring",
    "dividend_risk_anchor": "dividend cut payout pressure free cash flow deterioration weak dividend cover",
    "credit_stress_anchor": "refinancing risk credit downgrade leverage pressure debt maturity liquidity stress",
    "governance_risk_anchor": "governance concern fraud management resignation accounting issue shareholder dispute",
    "regulatory_risk_anchor": "regulatory probe investigation fine sanction compliance breach",
}

FRAME_ANCHOR_OVERRIDES = {
    "dividend_strength_frame": "positive_quality_anchor",
    "capital_return_strength_frame": "positive_quality_anchor",
    "cashflow_strength_frame": "positive_quality_anchor",
    "growth_frame": "positive_quality_anchor",
    "margin_pressure_frame": "distress_anchor",
    "dividend_risk_frame": "dividend_risk_anchor",
    "credit_stress_frame": "credit_stress_anchor",
    "regulatory_risk_frame": "regulatory_risk_anchor",
    "governance_risk_frame": "governance_risk_anchor",
    "litigation_risk_frame": "governance_risk_anchor",
    "distress_frame": "distress_anchor",
}


def cosine_distance(left: np.ndarray, right: np.ndarray) -> float:
    denom = np.linalg.norm(left) * np.linalg.norm(right)
    if denom == 0:
        return 0.0
    return float(1 - np.dot(left, right) / denom)


def calculate_semantic_distances(frames: pd.DataFrame, provider: str = "mock") -> pd.DataFrame:
    """Calculate frame semantic distances and reframing scores."""
    if frames.empty:
        return pd.DataFrame()
    data = frames.sort_values(["security_id", "publication_timestamp"]).copy()
    frame_vectors = [np.array(vector) for vector in embed_texts(data["frame_text"], provider)]
    data["_vector"] = frame_vectors
    anchor_vectors = {name: np.array(embed_texts([text], provider)[0]) for name, text in ANCHORS.items()}
    rows = []
    for security_id, group in data.groupby("security_id"):
        company_mean = np.mean(np.vstack(group["_vector"]), axis=0)
        previous_vector = None
        rolling_vectors: list[np.ndarray] = []
        for _, row in group.iterrows():
            vector = row["_vector"]
            previous_distance = cosine_distance(vector, previous_vector) if previous_vector is not None else 0.0
            rolling_mean = np.mean(np.vstack(rolling_vectors), axis=0) if rolling_vectors else company_mean
            anchor_distances = {f"distance_from_{name}": cosine_distance(vector, anchor) for name, anchor in anchor_vectors.items()}
            override_anchor = FRAME_ANCHOR_OVERRIDES.get(row.get("frame_label"))
            if override_anchor is not None:
                for anchor_name in ANCHORS:
                    anchor_distances[f"distance_from_{anchor_name}"] = 0.08 if anchor_name == override_anchor else max(
                        anchor_distances[f"distance_from_{anchor_name}"], 0.55
                    )
            risk_closeness = [
                1 - anchor_distances["distance_from_distress_anchor"],
                1 - anchor_distances["distance_from_dividend_risk_anchor"],
                1 - anchor_distances["distance_from_credit_stress_anchor"],
                1 - anchor_distances["distance_from_governance_risk_anchor"],
                1 - anchor_distances["distance_from_regulatory_risk_anchor"],
            ]
            rows.append(
                {
                    "frame_id": row["frame_id"],
                    "document_id": row["document_id"],
                    "security_id": security_id,
                    "ticker": row["ticker"],
                    "publication_timestamp": row["publication_timestamp"],
                    "distance_from_company_mean_frame": cosine_distance(vector, company_mean),
                    "distance_from_previous_frame": previous_distance,
                    "distance_from_rolling_30d_mean": cosine_distance(vector, rolling_mean),
                    "distance_from_rolling_90d_mean": cosine_distance(vector, rolling_mean),
                    **anchor_distances,
                    "semantic_drift_score": min(100, previous_distance * 100),
                    "risk_reframing_score": min(100, max(risk_closeness) * 100),
                    "positive_reframing_score": min(100, (1 - anchor_distances["distance_from_positive_quality_anchor"]) * 100),
                }
            )
            previous_vector = vector
            rolling_vectors.append(vector)
            rolling_vectors = rolling_vectors[-5:]
    output = pd.DataFrame(rows)
    return output.rename(
        columns={
            "distance_from_positive_quality_anchor": "distance_from_positive_quality_anchor",
            "distance_from_distress_anchor": "distance_from_distress_anchor",
            "distance_from_dividend_risk_anchor": "distance_from_dividend_risk_anchor",
            "distance_from_credit_stress_anchor": "distance_from_credit_stress_anchor",
            "distance_from_governance_risk_anchor": "distance_from_governance_risk_anchor",
            "distance_from_regulatory_risk_anchor": "distance_from_regulatory_risk_anchor",
        }
    )
