from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.alternative_data.alt_features import run_alternative_data_pipeline
from src.data_ingestion.universe import build_universe
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    """Run the mock/local sentiment and alternative-data engine."""
    base_config = load_yaml("configs/base.yaml")
    sentiment_config = load_yaml("configs/sentiment.yaml")
    alternative_data_config = load_yaml("configs/alternative_data.yaml")
    output_dir = ensure_output_dir(base_config)
    universe = build_universe(n=int(base_config.get("mock_data", {}).get("securities", 24)))
    outputs = run_alternative_data_pipeline(universe, sentiment_config, alternative_data_config)
    filenames = {
        "alt_text_documents": "alt_text_documents.csv",
        "alt_entity_mentions": "alt_entity_mentions.csv",
        "alt_sentiment_scores": "alt_sentiment_scores.csv",
        "alt_event_signals": "alt_event_signals.csv",
        "alt_features_monthly": "alt_features_monthly.csv",
    }
    for key, filename in filenames.items():
        write_csv(outputs[key], output_dir, filename)
    logging.info("Sentiment engine completed with %s documents.", len(outputs["alt_text_documents"]))


if __name__ == "__main__":
    main()
