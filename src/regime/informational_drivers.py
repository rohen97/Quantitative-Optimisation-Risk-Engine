from __future__ import annotations

import json
import pandas as pd


def run_informational_driver_model(
    alt_features: pd.DataFrame | None = None,
    narrative_features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Estimate regime deterioration from sentiment, alt-data and narrative proxies."""
    alt = alt_features if alt_features is not None and not alt_features.empty else pd.DataFrame()
    narrative = narrative_features if narrative_features is not None and not narrative_features.empty else pd.DataFrame()
    macro_news_uncertainty = float(alt.get("negative_news_intensity_30d", pd.Series([0])).mean() * 10)
    policy_uncertainty = float(alt.get("regulatory_risk_score", pd.Series([0])).mean())
    credit_stress_news = float(alt.get("credit_stress_score", pd.Series([0])).mean())
    dividend_risk_news = float(alt.get("dividend_risk_score", pd.Series([0])).mean())
    narrative_instability = float(narrative.get("narrative_instability_score", pd.Series([0])).mean())
    risk_reframing = float(narrative.get("risk_reframing_score", pd.Series([0])).mean())
    markov_distress = float(narrative.get("markov_negative_to_distress_prob", pd.Series([0])).mean() * 100)
    driver_scores = {
        "macro_news_uncertainty": macro_news_uncertainty,
        "policy_uncertainty": policy_uncertainty,
        "credit_stress_news": credit_stress_news,
        "dividend_risk_news": dividend_risk_news,
        "narrative_instability_score": narrative_instability,
        "risk_reframing_score": risk_reframing,
        "markov_negative_to_distress_prob": markov_distress,
        "china_policy_uncertainty": policy_uncertainty * 0.8,
        "europe_recession_uncertainty": macro_news_uncertainty * 0.7,
        "uk_rate_uncertainty": macro_news_uncertainty * 0.5,
    }
    top = sorted(driver_scores, key=driver_scores.get, reverse=True)[:3]
    deterioration = min(100, 20 + 0.20 * risk_reframing + 0.20 * credit_stress_news + 0.15 * policy_uncertainty + 0.15 * macro_news_uncertainty + 0.10 * markov_distress)
    driver_importance_json = json.dumps(driver_scores, sort_keys=True)
    return pd.DataFrame(
        [
            {
                "as_of_date": pd.Timestamp.today().normalize(),
                "expected_volatility_next_period": min(100, 10 + deterioration * 0.45),
                "expected_chaos_index_next_period": min(100, 20 + deterioration * 0.60),
                "regime_deterioration_probability": deterioration / 100,
                "top_regime_driver_1": top[0],
                "top_regime_driver_2": top[1],
                "top_regime_driver_3": top[2],
                "driver_importance_json": driver_importance_json,
                "driver_importances_json": driver_importance_json,
                "informational_driver_confidence": 0.70,
                **driver_scores,
            }
        ]
    )
