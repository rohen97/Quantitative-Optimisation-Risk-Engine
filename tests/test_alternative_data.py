from pathlib import Path
import subprocess
import sys

import pandas as pd

from src.alternative_data.alt_features import run_alternative_data_pipeline
from src.alternative_data.risk_signals import build_risk_signal_overlay
from src.data_ingestion.universe import build_universe
from src.sentiment.entity_mapping import map_entities
from src.sentiment.text_ingestion import load_or_generate_text_documents


def test_mock_documents_and_entity_mapping():
    universe = build_universe()
    documents = load_or_generate_text_documents(universe)
    mentions = map_entities(documents, universe)
    assert not documents.empty
    assert not mentions.empty
    assert mentions["mention_confidence"].between(0.70, 1.0).all()


def test_alt_pipeline_outputs_and_score_ranges():
    universe = build_universe()
    outputs = run_alternative_data_pipeline(universe)
    features = outputs["alt_features_monthly"]
    assert not outputs["alt_text_documents"].empty
    assert not outputs["alt_entity_mentions"].empty
    assert not outputs["alt_sentiment_scores"].empty
    assert not outputs["alt_event_signals"].empty
    for column in ["sentiment_alt_data_score", "dividend_risk_score", "regulatory_risk_score", "credit_stress_score"]:
        assert features[column].between(0, 100).all()


def test_risk_flags_trigger_on_thresholds():
    frame = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "dividend_risk_score": 90,
                "regulatory_risk_score": 90,
                "governance_red_flag_count": 3,
                "credit_stress_score": 90,
                "litigation_risk_score": 90,
                "negative_news_intensity_30d": 10,
                "management_confidence_score": 20,
            }
        ]
    )
    flags = build_risk_signal_overlay(frame)
    assert flags.loc[0, "dividend_risk_flag"]
    assert flags.loc[0, "alt_data_exclusion_flag"]
    assert flags.loc[0, "alt_data_review_required_flag"]


def test_run_sentiment_engine_script_creates_outputs():
    result = subprocess.run([sys.executable, "scripts/run_sentiment_engine.py"], check=True, capture_output=True, text=True)
    assert result.returncode == 0
    assert Path("reports/outputs/alt_features_monthly.csv").exists()
