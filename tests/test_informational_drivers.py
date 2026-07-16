import pandas as pd

from src.regime.informational_drivers import run_informational_driver_model


def test_informational_driver_model_outputs_probabilities_and_importances():
    alt_features = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "macro_news_uncertainty": [70, 50],
            "policy_uncertainty": [60, 40],
            "credit_stress_news": [30, 20],
            "dividend_risk_news": [15, 25],
        }
    )
    narrative_features = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "narrative_instability_score": [75, 45],
            "risk_reframing_score": [80, 30],
            "markov_negative_to_distress_prob": [0.30, 0.10],
        }
    )
    output = run_informational_driver_model(alt_features, narrative_features)
    assert output["regime_deterioration_probability"].between(0, 1).all()
    assert output["driver_importances_json"].str.contains("macro_news_uncertainty").all()
