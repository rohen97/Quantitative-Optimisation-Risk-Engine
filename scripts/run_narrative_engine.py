from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_ingestion.universe import build_universe
from src.narrative.pipeline import run_narrative_pipeline
from src.reporting.report_writer import write_csv
from src.utils.config import ensure_output_dir, load_yaml


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    """Run the mock financial narrative reframing engine."""
    base_config = load_yaml("configs/base.yaml")
    narrative_config = load_yaml("configs/narrative.yaml")
    output_dir = ensure_output_dir(base_config)
    universe = build_universe(n=int(base_config.get("mock_data", {}).get("securities", 24)))
    outputs = run_narrative_pipeline(universe, narrative_config)
    filenames = {
        "narrative_concepts": "narrative_concepts.csv",
        "narrative_frames": "narrative_frames.csv",
        "narrative_semantic_distances": "narrative_semantic_distances.csv",
        "narrative_markov_transitions": "narrative_markov_transitions.csv",
        "narrative_reframing_features": "narrative_reframing_features.csv",
    }
    for key, filename in filenames.items():
        write_csv(outputs[key], output_dir, filename)
    logging.info("Narrative engine completed with %s frames.", len(outputs["narrative_frames"]))


if __name__ == "__main__":
    main()
